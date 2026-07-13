"""DoorbellCallController — HA-glue приёма вызова домофона (register-on-ring, ADR-0012).

Связывает части:
- FCM `SIGNAL_DOORBELL` (ring/ended) → трекинг активного вызова + окно `CallInvalidated`;
  на `ring` сразу **держим** SIP (`SipManager.register_and_hold`: REGISTER → forked
  INVITE → `100 Trying`) — зеркало приложения, чтобы получать `CANCEL` и быстро отвечать;
- сервис `answer` → `SipManager.accept` (200 OK на держимый INVITE) → RTP-latching;
  если held не поднялся — fallback на `async_answer` (register-on-answer);
- приём `CANCEL` (сброс с панели / ответ на др. устройстве) → `on_cancelled` →
  мгновенный dismiss экрана (через EVENT_SIP_CALL active=false, чистит хелпер);
- сервис `hangup` → `SipManager.async_hangup` (BYE / release held).

🔴 Call-ID binding (call-answer-model.md §6.5): держим/отвечаем только на активный
вызов в окне `CallInvalidated`. Один held/активный вызов за раз (фикс-порты).

Downlink-вывод звука гостя: на `accept` поднимаем `AudioBridge`,
`on_downlink` кормит мост → карта. go2rtc нет/не поднялся — degrade на счётчик кадров.
go2rtc-стрим вызова собирает camera-сущность (рефреш-на-открытии, ADR-0012 C).
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from ..const import (
    CALL_STATE_ACTIVE,
    CALL_STATE_CONNECTING,
    CALL_STATE_ENDED,
    CALL_STATE_ERROR,
    CALL_STATE_IDLE,
    CALL_STATE_RINGING,
    DOORBELL_CALL_WINDOW_FALLBACK_SEC,
    EVENT_CALL_STATE,
    LOGGER,
)
from ..go2rtc import remove_audio_stream
from .bridge import AudioBridge, detect_lan_ip
from .manager import SipManager
from .uplink import UplinkSink

# mint SIP-кредов — на критическом пути hold/ответа. Жёсткий таймаут, чтобы зависший
# POST не «съел» окно вызова (http.py без ClientTimeout, A-21).
_MINT_TIMEOUT_SEC = 8.0

# Аудио-мост downlink: фикс HTTP-порт ffmpeg-сервера + имя go2rtc-стрима вызова.
AUDIO_HTTP_PORT = 40020
# Имя go2rtc-стрима активного вызова; контроллер снимает его на конце вызова,
# camera-сущность создаёт/обновляет на открытии экрана (ADR-0012 C).
CALL_STREAM_NAME = "eg_intercom_call"
# Домофон оператора шлёт PCMU(0) (live-доказано: «PT=0 PCMU»). Мост — под него.
_DOWNLINK_PT = 0

# Событие шины: состояние SIP-разговора (start/end). UI ведёт экран по нему. На end
# (BYE/CANCEL/hangup) — active=false → input_boolean off + чистка хелпера (dismiss).
EVENT_SIP_CALL = "elektronny_gorod_sip_call"

# Страховка: макс. длительность отвеченного разговора (нет BYE/сброса) → авто-hangup.
_MAX_CALL_SEC = 120
# Страховка: макс. время держания неотвеченного вызова (нет CANCEL/ответа) → release,
# чтобы освободить фикс-порт SIP для следующего вызова. Чуть больше окна вызова (~30с).
_HOLD_MAX_SEC = 40
# Грейс после дедлайна окна ответа: страховочный ring-таймаут завершает `ringing`,
# если FCM `ended` не пришёл (degrade held / неотвеченный звонок / протухший реплей
# FCM-очереди после рестарта HA). Небольшой запас — дать шанс живому `ended` (A-72).
_RING_GRACE_SEC = 3.0
# Задержка возврата терминальной фазы (`ended`/`error`) в `idle`: даёт карточке
# показать финальный экран (её hold ~2.5с), затем сенсор чистится, не залипая (A-72).
_IDLE_RESET_SEC = 6.0


@dataclass
class Go2RtcConfig:
    """go2rtc для стрима вызова: base_url + auth-заголовки + RTSP-хост (из entry)."""

    base_url: str
    headers: dict
    rtsp_host: str


@dataclass
class ActiveCall:
    """Активный FCM-вызов, на который допустим hold/answer (в окне CallInvalidated)."""

    call_id: str | None
    place_id: str
    access_control_id: str
    deadline: datetime


class DoorbellCallController:
    """Трекинг вызова + register-on-ring hold/accept через SipManager (один на entry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: Any,
        fcm_token_getter: Callable[[], str | None],
        on_downlink: Callable[[bytes], None] | None = None,
        go2rtc: Go2RtcConfig | None = None,
        camera_resolver: Callable[[str], str | None] | None = None,
    ) -> None:
        self._hass = hass
        self._api = api
        self._fcm_token_getter = fcm_token_getter
        self._on_downlink = on_downlink or self._count_downlink
        self._go2rtc = go2rtc
        # access_control_id → camera_id (для видео-источника стрима вызова, B).
        self._camera_resolver = camera_resolver
        self._active: ActiveCall | None = None
        self._manager: SipManager | None = None
        self._bridge: AudioBridge | None = None
        # Uplink-микрофон (Phase C, ADR-0013): WS-транспорт кормит sink через
        # feed_uplink; SipManager.uplink_provider (=_pull_uplink) тянет next_frame
        # каждые 20мс. None вне активного вызова → uplink = тишина-keepalive.
        self._uplink_sink: UplinkSink | None = None
        self._call_timeout: asyncio.TimerHandle | None = None
        self._hold_timeout: asyncio.TimerHandle | None = None
        # Страховка залипшего `ringing` (нет FCM `ended`) и возврата терминала в idle.
        self._ring_timeout: asyncio.TimerHandle | None = None
        self._idle_timeout: asyncio.TimerHandle | None = None
        # Сериализует hold/answer: без него параллельные register создали бы 2 SipManager
        # на фикс-портах. Hold и accept проходят под одним локом.
        self._answer_lock = asyncio.Lock()
        self.downlink_packets = 0
        # Состояние вызова для sensor.*_call_state (EVENT_CALL_STATE). _last_* кешируют
        # ids активного вызова — на `ended` self._active уже может быть None. _last_state
        # дедуплицирует одинаковые подряд (несколько terminal-путей → один `ended`).
        self._call_state: str | None = None
        self._last_ac: str | None = None
        self._last_place_id: str | None = None
        self._last_call_id: str | None = None
        self._call_started_at: str | None = None

    # ---- трекинг активного вызова (из SIGNAL_DOORBELL) ----
    @callback
    def handle_signal(self, payload: dict[str, Any]) -> None:
        """SIGNAL_DOORBELL: `ring` → запомнить + держать SIP; `ended` → снять."""
        event_type = payload.get("event_type")
        attrs = payload.get("attributes") or {}
        # Диагностика гонки двух звонков (какой `ended` какой вызов трогает).
        if event_type in ("ring", "ended"):
            LOGGER.debug(
                "SIP signal %s: call_id=%s place=%s ac=%s (active call_id=%s ac=%s)",
                event_type, attrs.get("call_id"), payload.get("place_id"),
                payload.get("access_control_id"),
                self._active.call_id if self._active else None,
                self._active.access_control_id if self._active else None,
            )
        if event_type == "ring":
            active = ActiveCall(
                call_id=attrs.get("call_id"),
                place_id=str(payload.get("place_id") or ""),
                access_control_id=str(payload.get("access_control_id") or ""),
                deadline=self._compute_deadline(attrs.get("call_invalidated")),
            )
            # Протухший ring: дедлайн окна ответа уже в прошлом (реплей FCM-очереди
            # после рестарта HA / устаревшее событие). Не поднимаем `ringing` — иначе
            # фаза залипнет без последующего `ended` (A-72).
            if dt_util.utcnow() >= active.deadline:
                LOGGER.info("SIP: протухший ring (дедлайн в прошлом) — игнор")
                return
            if self._manager is not None:
                # A-89: уже держим/в разговоре. Различаем разговор vs держимый.
                if self._manager.in_call:
                    # Идёт разговор — одновременный второй вне scope, не рвём текущий.
                    LOGGER.info("SIP: идёт разговор — игнор ring другого домофона")
                    return
                same_call = self._active is not None and (
                    active.call_id == self._active.call_id
                    and active.access_control_id == self._active.access_control_id
                )
                if same_call:
                    # Повторный ring того же держимого вызова — дедуп, не пере-hold.
                    LOGGER.info("SIP: повторный ring держимого вызова — игнор")
                    return
                # holding + другой домофон → смена активного звонящего (A-89):
                # снять старый held и захватить новый (карта переключится на новый).
                # `self._manager` обнуляем сразу — иначе `_async_hold_current` увидит
                # ещё-живого старого и не поднимет новый. ENDED не эмитим: карта не
                # должна мигать «Завершён» — сразу RINGING нового (ниже).
                LOGGER.info("SIP: смена звонящего — снимаю держимый, захватываю новый")
                old_manager, self._manager = self._manager, None
                # Синхронно снять колбэки старого: поздний CANCEL/BYE №1 в окне до
                # `async_hangup` иначе дёрнул бы `_on_ring_cancelled` → обнулил бы уже
                # поднятый новый manager / стёр вызов №2 (cross-call порча).
                old_manager.detach()
                task = self._async_switch_caller(old_manager)
            else:
                # register-on-ring: держим SIP сразу (зеркало приложения, ADR-0012).
                task = self._async_hold_current()
            self._active = active
            self._emit_call_state(CALL_STATE_RINGING)
            self._schedule_ring_timeout()  # страховка залипшего ringing (нет `ended`)
            self._hass.async_create_task(task)
        elif event_type == "ended" and self._active is not None:
            cid = attrs.get("call_id")
            ac = str(payload.get("access_control_id") or "")
            # Cross-call guard: `ended` от ДРУГОГО домофона/вызова не должен завершать
            # текущий активный вызов. Один контроллер обслуживает все домофоны, а
            # запоздавший `ended` первого (сброшенного) звонка мог прийти уже во время
            # второго → «Завершён» на живом разговоре (прод 2026-07-08). Завершаем
            # только если НЕТ доказательств, что событие про иной вызов: не совпал
            # call_id, либо не совпал access_control_id (когда они присутствуют).
            if (cid is not None and cid != self._active.call_id) or (
                ac and ac != self._active.access_control_id
            ):
                LOGGER.info(
                    "SIP: `ended` относится к другому вызову (cid=%s ac=%s) — "
                    "активный вызов не трогаем",
                    cid, ac,
                )
                return
            # A-90: оператор снимает ring-уведомление со ВСЕХ устройств, когда вызов
            # приняли → шлёт FCM `ended` (reason=answered_elsewhere) сразу после «Принять»,
            # хотя SIP-диалог ещё жив (BYE приходит на несколько секунд позже). Для уже
            # ПРИНЯТОГО вызова источник истины о завершении — SIP (BYE/CANCEL/hangup/
            # страховка `_MAX_CALL_SEC`), не FCM. Иначе HA гасит «Вызов завершён» на живом
            # разговоре (прод 2026-07-08 20:57). Для неотвеченного (`holding`/`ringing`)
            # `in_call`=False → FCM `ended` по-прежнему корректно завершает.
            if self._manager is not None and self._manager.in_call:
                LOGGER.info(
                    "SIP: FCM `ended` во время активного разговора — игнор "
                    "(завершение придёт по SIP BYE/hangup)"
                )
                return
            self._emit_call_state(CALL_STATE_ENDED)  # до сброса _active (читает ids)
            self._active = None
            # CANCEL мог не прийти (ответ на др. устройстве) — снять держимый сами.
            if self._manager is not None and self._manager.holding:
                self._hass.async_create_task(self._async_release_held())

    def _compute_deadline(self, invalidated: str | None) -> datetime:
        """Дедлайн ответа: операторское `call_invalidated` или fallback-окно."""
        if invalidated:
            parsed = dt_util.parse_datetime(invalidated)
            if parsed is not None:
                return parsed
        return dt_util.utcnow() + timedelta(seconds=DOORBELL_CALL_WINDOW_FALLBACK_SEC)

    def current_call(self, now: datetime | None = None) -> ActiveCall | None:
        """Активный вызов, если он есть и окно ещё не истекло; иначе None."""
        if self._active is None:
            return None
        if (now or dt_util.utcnow()) >= self._active.deadline:
            return None
        return self._active

    # ---- register-on-ring: hold ----
    async def _async_hold_current(self) -> None:
        """На ring: mint → register_and_hold (держим INVITE). Degrade при ошибке."""
        async with self._answer_lock:
            if self._manager is not None:
                return  # уже держим/в разговоре
            call = self.current_call()
            if call is None:
                return
            fcm_token = self._fcm_token_getter()
            if not fcm_token:
                LOGGER.warning("SIP hold: FCM-токен не готов — REGISTER невозможен (degrade)")
                return
            manager = SipManager(
                fcm_token,
                uplink_provider=self._pull_uplink,
                on_ended=self._schedule_audio_cleanup,
                on_cancelled=self._on_ring_cancelled,
            )
            try:
                held = await manager.register_and_hold(
                    lambda: self._mint(call), fcm_call_id=call.call_id
                )
            except Exception:  # noqa: BLE001 — degrade: экран живёт от FCM, dismiss по таймеру
                LOGGER.warning("SIP hold: REGISTER/hold не удался — degrade", exc_info=True)
                held = False
            if held:
                self._manager = manager
                self._schedule_hold_timeout()

    # ---- сервисы answer / hangup ----
    async def async_answer(self) -> bool:
        """Ответить: accept держимого INVITE, либо fallback register-on-answer."""
        async with self._answer_lock:
            call = self.current_call()
            if call is None:
                LOGGER.warning("SIP answer: нет активного вызова в окне — игнор")
                return False
            if self._manager is not None and self._manager.in_call:
                LOGGER.warning("SIP answer: уже идёт разговор — игнор")
                return False
            fcm_token = self._fcm_token_getter()
            if not fcm_token:
                LOGGER.warning("SIP answer: FCM-токен не готов — REGISTER невозможен")
                return False

            self._emit_call_state(CALL_STATE_CONNECTING)
            bridge, on_downlink = await self._setup_audio_bridge(call)
            self.downlink_packets = 0
            self._cancel_hold_timeout()

            # accept/async_answer парсят SDP-offer из сети (untrusted). Если accept
            # регрессирует и кинет — мост (ffmpeg + HTTP-сервер) обязан быть снят,
            # иначе течёт (P1-1). Зеркалим teardown ниже на любом исходе.
            try:
                if self._manager is not None and self._manager.holding:
                    ok = await self._manager.accept(on_downlink=on_downlink)  # быстрый путь
                else:
                    # Fallback: held не поднялся → register-on-answer (приём не регрессирует).
                    manager = SipManager(
                        fcm_token,
                        uplink_provider=self._pull_uplink,
                        on_ended=self._schedule_audio_cleanup,
                        on_cancelled=self._on_ring_cancelled,
                    )
                    ok = await manager.async_answer(
                        lambda: self._mint(call),
                        on_downlink=on_downlink,
                        fcm_call_id=call.call_id,
                    )
                    if ok:
                        self._manager = manager
            except Exception:  # noqa: BLE001 — degrade: мост снять, экран живёт от FCM
                LOGGER.warning("SIP answer: accept/register упал — снимаю мост (degrade)",
                               exc_info=True)
                # Контракт `error` (review P2): терминальное состояние неудачного
                # ответа. Естественно сбрасывается следующим `ended`/CANCEL/новым
                # `ring`; карточка вызова (Slice 3b) сама гасит error по таймеру —
                # авто-переход в `ended` намеренно отложен до появления потребителя.
                self._emit_call_state(CALL_STATE_ERROR)
                self._clear_uplink_sink()
                await self._teardown_audio_bridge(bridge)
                return False

            if ok:
                self._bridge = bridge
                self._emit_call_state(CALL_STATE_ACTIVE)
                self._fire_call_state(True)
                self._schedule_call_timeout()
            else:
                self._emit_call_state(CALL_STATE_ERROR)
                self._clear_uplink_sink()
                await self._teardown_audio_bridge(bridge)
            return ok

    async def async_hangup(self) -> None:
        """Завершить разговор (BYE) / снять держимый (release) + снять аудио-мост.

        Под `_answer_lock` — иначе гонка с `async_answer`: пока answer внутри
        лока await-ит `_setup_audio_bridge` (`self._bridge` ещё None, ставится
        ПОСЛЕ await'ов), параллельный hangup забрал бы teardown, не увидев
        ещё-None мост → answer присвоил бы `self._bridge` → orphaned ffmpeg +
        HTTP-listener :40020. Вызывается только из сервис-хендлеров/unload-таймера
        (не из методов под локом) — self-deadlock'а нет."""
        async with self._answer_lock:
            self._cancel_call_timeout()
            self._cancel_hold_timeout()
            manager, self._manager = self._manager, None
            bridge, self._bridge = self._bridge, None
            self._clear_uplink_sink()
            if manager is not None:
                await manager.async_hangup()
                self._emit_call_state(CALL_STATE_ENDED)
                self._fire_call_state(False)
            self._active = None  # вызов окончен — не оставляем висеть до idle-reset
            await self._teardown_audio_bridge(bridge)

    async def _async_release_held(self) -> None:
        """FCM `ended` при держимом (CANCEL не пришёл) — снять held + dismiss."""
        async with self._answer_lock:
            if self._manager is None or not self._manager.holding:
                return
            self._cancel_hold_timeout()
            manager, self._manager = self._manager, None
            self._clear_uplink_sink()
            await manager.async_hangup()
            self._emit_call_state(CALL_STATE_ENDED)
            self._active = None  # держимый снят — вызов окончен
            self._fire_call_state(False)

    async def _async_switch_caller(self, old_manager: SipManager) -> None:
        """A-89: смена активного звонящего. Снимаем СТАРЫЙ держимый (release SIP/RTP-
        порты) и поднимаем held нового вызова. `self._active`/`self._manager` уже
        выставлены под новый вызов в `handle_signal` (active=новый, manager=None),
        поэтому здесь трогаем только `old_manager` по ссылке, а затем `_async_hold_
        current` mint'ит новый held под новые ids. Оба шага берут `_answer_lock`
        последовательно (не вложенно) — self-deadlock'а нет. В окне release→hold
        `self._manager is None`, поэтому параллельный ring уходит в else-ветку
        `_async_hold_current`, а не в switch; дубль-hold отсекается гвардом в начале
        `_async_hold_current` (`if self._manager is not None: return`)."""
        async with self._answer_lock:
            self._cancel_hold_timeout()  # старый hold-таймаут снят — новый переставит
            try:
                await old_manager.async_hangup()
            except Exception:  # noqa: BLE001 — release старого не должен блокировать новый
                LOGGER.warning("SIP switch: release старого held упал", exc_info=True)
        await self._async_hold_current()

    async def _mint(self, call: ActiveCall) -> dict[str, Any]:
        """mint SIP-device для вызова с жёстким таймаутом (http.py без ClientTimeout)."""
        async with asyncio.timeout(_MINT_TIMEOUT_SEC):
            return await self._api.mint_sip_device(call.place_id, call.access_control_id)

    @callback
    def _fire_call_state(self, active: bool) -> None:
        """Сигнал шины о старте/конце SIP (UI: active=false → off + чистка хелпера)."""
        self._hass.bus.async_fire(EVENT_SIP_CALL, {"active": active})

    @callback
    def _emit_call_state(self, state: str) -> None:
        """Опубликовать фазу вызова на EVENT_CALL_STATE → sensor.*_call_state.

        Параллельно EVENT_SIP_CALL (тот гоняет input_boolean dismiss). Bus-event,
        а не dispatcher — консистентно с `_fire_call_state` и работает с MagicMock-hass
        в юнит-тестах. Дедуп одинаковых подряд: несколько terminal-путей дают один `ended`.
        Дедуп **identity-aware** (A-89): та же фаза, но ДРУГОЙ вызов (смена звонящего
        holding→ring другого домофона: RINGING→RINGING) обязан эмититься — иначе
        sensor нового домофона (фильтр по своим ac/place) не получит событие.
        """
        if state == self._call_state and (
            self._active is None or self._active.call_id == self._last_call_id
        ):
            return
        call = self._active
        if call is not None:
            self._last_ac = call.access_control_id
            self._last_place_id = call.place_id
            self._last_call_id = call.call_id
        if state == CALL_STATE_ACTIVE:
            self._call_started_at = dt_util.utcnow().isoformat()
        elif state in (CALL_STATE_ENDED, CALL_STATE_ERROR):
            self._call_started_at = None
        self._call_state = state
        self._hass.bus.async_fire(
            EVENT_CALL_STATE,
            {
                "place_id": self._last_place_id,
                "access_control_id": self._last_ac,
                "state": state,
                "call_id": self._last_call_id,
                "started_at": self._call_started_at,
            },
        )
        # Watchdog'и фаз (A-72): вне `ringing` снять ring-таймаут; терминал
        # (`ended`/`error`) — запланировать возврат в `idle`, иначе фаза залипает.
        if state != CALL_STATE_RINGING:
            self._cancel_ring_timeout()
        if state in (CALL_STATE_ENDED, CALL_STATE_ERROR):
            self._schedule_idle_reset()
        elif state != CALL_STATE_IDLE:
            self._cancel_idle_timeout()

    @callback
    def _on_ring_cancelled(self) -> None:
        """Держимый вызов отменён (CANCEL: сброс панели / ответ на др. устройстве) →
        мгновенный dismiss экрана. Моста ещё нет (не отвечали) — только сигнал."""
        self._cancel_hold_timeout()
        self._manager = None
        self._clear_uplink_sink()
        self._emit_call_state(CALL_STATE_ENDED)
        self._active = None  # CANCEL — вызов окончен, не путаем следующий
        self._fire_call_state(False)

    @callback
    def _schedule_call_timeout(self) -> None:
        """Страховочный авто-hangup отвеченного разговора (нет BYE/сброса)."""
        self._cancel_call_timeout()
        self._call_timeout = self._hass.loop.call_later(
            _MAX_CALL_SEC,
            lambda: self._hass.async_create_task(self.async_hangup()),
        )

    @callback
    def _cancel_call_timeout(self) -> None:
        if self._call_timeout is not None:
            self._call_timeout.cancel()
            self._call_timeout = None

    @callback
    def _schedule_hold_timeout(self) -> None:
        """Страховочный release держимого вызова (нет CANCEL/ответа) — освободить порт."""
        self._cancel_hold_timeout()
        self._hold_timeout = self._hass.loop.call_later(
            _HOLD_MAX_SEC,
            lambda: self._hass.async_create_task(self._async_release_held()),
        )

    @callback
    def _cancel_hold_timeout(self) -> None:
        if self._hold_timeout is not None:
            self._hold_timeout.cancel()
            self._hold_timeout = None

    # ---- ring-таймаут окна ответа + возврат терминала в idle (A-72) ----
    @callback
    def _schedule_ring_timeout(self) -> None:
        """Таймер до дедлайна окна ответа (+грейс): если к нему всё ещё `ringing` —
        завершить. Закрывает залипание, когда FCM `ended` не приходит: degrade held
        (не поднялся `_schedule_hold_timeout`), неотвеченный звонок, протухший реплей
        FCM-очереди после рестарта HA."""
        self._cancel_ring_timeout()
        if self._active is None:
            return
        delay = max(0.0, (self._active.deadline - dt_util.utcnow()).total_seconds())
        self._ring_timeout = self._hass.loop.call_later(
            delay + _RING_GRACE_SEC, self._on_ring_expired
        )

    @callback
    def _cancel_ring_timeout(self) -> None:
        if self._ring_timeout is not None:
            self._ring_timeout.cancel()
            self._ring_timeout = None

    @callback
    def _on_ring_expired(self) -> None:
        """Окно ответа истекло, никто не ответил и `ended` не пришёл → завершить
        зависший `ringing`. Держимый INVITE (если поднят) снять корректно (release)."""
        self._ring_timeout = None
        if self._call_state != CALL_STATE_RINGING:
            return  # уже ответили/завершили — не мешаем
        if self._manager is not None and self._manager.holding:
            self._hass.async_create_task(self._async_release_held())
        else:
            self._emit_call_state(CALL_STATE_ENDED)
            self._fire_call_state(False)
        self._active = None

    @callback
    def _schedule_idle_reset(self) -> None:
        """Отложенный возврат терминала (`ended`/`error`) в `idle`: сенсор не должен
        залипать в конечной фазе. Карточка к этому времени уже показала финальный
        экран (её hold ~2.5с). Отменяется новым `ring`/фазой (см. _emit_call_state)."""
        self._cancel_idle_timeout()
        self._idle_timeout = self._hass.loop.call_later(_IDLE_RESET_SEC, self._on_idle_reset)

    @callback
    def _cancel_idle_timeout(self) -> None:
        if self._idle_timeout is not None:
            self._idle_timeout.cancel()
            self._idle_timeout = None

    @callback
    def _on_idle_reset(self) -> None:
        self._idle_timeout = None
        if self._call_state in (CALL_STATE_ENDED, CALL_STATE_ERROR):
            self._active = None
            self._emit_call_state(CALL_STATE_IDLE)

    # ---- активный вызов: интерфейс для camera-сущности ----
    @callback
    def active_call_media(self) -> tuple[str, AudioBridge] | None:
        """Активный отвеченный вызов → (camera_id, bridge) для camera.intercom_call.

        None, если нет активного разговора / нет моста / камера не разрешилась."""
        if self._bridge is None or self._manager is None or not self._manager.in_call:
            return None
        call = self.current_call()
        if call is None:
            return None
        cam_id = (
            self._camera_resolver(call.access_control_id)
            if self._camera_resolver else None
        )
        if not cam_id:
            return None
        return cam_id, self._bridge

    # ---- аудио-мост downlink ----
    async def _setup_audio_bridge(
        self, call: ActiveCall,
    ) -> tuple[AudioBridge | None, Callable[[bytes], None]]:
        """Поднять аудио-мост. Возвращает (bridge|None, on_downlink).

        go2rtc-стрим вызова НЕ создаётся здесь — это делает camera-сущность
        при открытии экрана (рефреш-на-открытии, ADR-0012 C)."""
        # Uplink-микрофон: sink на тот же PT, что downlink-мост (домофон — PCMU).
        # WS-транспорт начнёт кормить его через feed_uplink, как только карта
        # включит микрофон; до этого uplink — тишина-keepalive (next_frame → None).
        self._uplink_sink = UplinkSink(_DOWNLINK_PT)
        if self._go2rtc is None:
            return None, self._on_downlink  # go2rtc не настроен → счётчик (degrade)
        loop = asyncio.get_running_loop()
        host_ip = await loop.run_in_executor(None, detect_lan_ip)
        bridge = AudioBridge(host_ip, AUDIO_HTTP_PORT, _DOWNLINK_PT)
        try:
            await bridge.start()
        except Exception:  # noqa: BLE001 — degrade
            LOGGER.warning("Аудио-мост не поднялся — медиа недоступно (degrade)")
            await bridge.stop()
            return None, self._on_downlink
        LOGGER.info("Аудио-мост поднят (стрим вызова соберёт camera.intercom_call)")
        return bridge, bridge.feed_downlink

    async def _teardown_audio_bridge(self, bridge: AudioBridge | None) -> None:
        """Остановить мост + снять go2rtc-стрим вызова (best-effort)."""
        if bridge is None:
            return
        await bridge.stop()
        if self._go2rtc is not None:
            await remove_audio_stream(
                self._go2rtc.base_url, CALL_STREAM_NAME,
                async_get_clientsession(self._hass), self._go2rtc.headers,
            )

    @callback
    def _schedule_audio_cleanup(self) -> None:
        """on_ended от SipManager (remote BYE): снять мост + сигнал конца SIP."""
        self._cancel_call_timeout()
        self._cancel_hold_timeout()
        self._manager = None
        bridge, self._bridge = self._bridge, None
        self._clear_uplink_sink()
        self._emit_call_state(CALL_STATE_ENDED)
        self._active = None  # remote BYE — разговор окончен
        self._fire_call_state(False)
        if bridge is not None:
            self._hass.async_create_task(self._teardown_audio_bridge(bridge))

    # ---- uplink-микрофон (Phase C, ADR-0013) ----
    @callback
    def _pull_uplink(self) -> bytes | None:
        """uplink_provider для SipManager: один G.711-кадр из sink, или None (тишина)."""
        if self._uplink_sink is None:
            return None
        return self._uplink_sink.next_frame()

    @callback
    def _clear_uplink_sink(self) -> None:
        """Снять uplink-sink на teardown вызова (clear буфера + None)."""
        if self._uplink_sink is not None:
            self._uplink_sink.clear()
            self._uplink_sink = None

    @callback
    def feed_uplink(self, pcm: bytes, sample_rate: int) -> None:
        """Кадр микрофона (int16 mono PCM @ sample_rate) → sink. Нет вызова → дроп.

        Зовётся WS-транспортом (uplink_ws.ws_intercom_uplink). Если активного
        вызова нет (sink None) — кадр дропается без ошибки (звонок мог уже
        завершиться, пока браузер дослал буфер)."""
        if self._uplink_sink is not None:
            self._uplink_sink.feed(pcm, sample_rate)

    @callback
    def _count_downlink(self, payload: bytes) -> None:
        """Fallback downlink-sink (go2rtc нет): счётчик кадров — доказательство RTP."""
        self.downlink_packets += 1
        if self.downlink_packets == 1:
            LOGGER.info(
                "SIP downlink: пошёл RTP от домофона (первый кадр %d байт)", len(payload)
            )
