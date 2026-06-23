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

Downlink-вывод звука гостя: на `accept` поднимаем `AudioBridge` + go2rtc-стрим,
`on_downlink` кормит мост → карта. go2rtc нет/не поднялся — degrade на счётчик кадров.
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

from ..const import DOORBELL_CALL_WINDOW_FALLBACK_SEC, GO2RTC_RTSP_PORT, LOGGER
from ..go2rtc import remove_audio_stream, upsert_audio_stream
from .bridge import AudioBridge, detect_lan_ip
from .manager import SipManager

# mint SIP-кредов — на критическом пути hold/ответа. Жёсткий таймаут, чтобы зависший
# POST не «съел» окно вызова (http.py без ClientTimeout, A-21).
_MINT_TIMEOUT_SEC = 8.0

# Аудио-мост downlink: фикс HTTP-порт ffmpeg-сервера + имя go2rtc-стрима вызова.
AUDIO_HTTP_PORT = 40020
# Стрим вызова: видео камеры (RTSP) + аудио моста, склеенные go2rtc (B, ADR-0012).
# Если камера не разрешилась — только аудио (fallback). Карточка экрана читает его.
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
        self._call_timeout: asyncio.TimerHandle | None = None
        self._hold_timeout: asyncio.TimerHandle | None = None
        # Сериализует hold/answer: без него параллельные register создали бы 2 SipManager
        # на фикс-портах. Hold и accept проходят под одним локом.
        self._answer_lock = asyncio.Lock()
        self.downlink_packets = 0

    # ---- трекинг активного вызова (из SIGNAL_DOORBELL) ----
    @callback
    def handle_signal(self, payload: dict[str, Any]) -> None:
        """SIGNAL_DOORBELL: `ring` → запомнить + держать SIP; `ended` → снять."""
        event_type = payload.get("event_type")
        attrs = payload.get("attributes") or {}
        if event_type == "ring":
            if self._manager is not None:
                # Уже держим/в разговоре (фикс-порты) — игнор параллельного ring.
                LOGGER.info("SIP: уже держим/в разговоре — игнор параллельного ring")
                return
            self._active = ActiveCall(
                call_id=attrs.get("call_id"),
                place_id=str(payload.get("place_id") or ""),
                access_control_id=str(payload.get("access_control_id") or ""),
                deadline=self._compute_deadline(attrs.get("call_invalidated")),
            )
            # register-on-ring: держим SIP сразу (зеркало приложения, ADR-0012).
            self._hass.async_create_task(self._async_hold_current())
        elif event_type == "ended" and self._active is not None:
            cid = attrs.get("call_id")
            if cid is None or cid == self._active.call_id:
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
                on_ended=self._schedule_audio_cleanup,
                on_cancelled=self._on_ring_cancelled,
            )
            try:
                held = await manager.register_and_hold(lambda: self._mint(call))
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

            bridge, on_downlink = await self._setup_audio_bridge(call)
            self.downlink_packets = 0
            self._cancel_hold_timeout()

            if self._manager is not None and self._manager.holding:
                ok = await self._manager.accept(on_downlink=on_downlink)  # быстрый путь
            else:
                # Fallback: held не поднялся → register-on-answer (приём не регрессирует).
                manager = SipManager(
                    fcm_token,
                    on_ended=self._schedule_audio_cleanup,
                    on_cancelled=self._on_ring_cancelled,
                )
                ok = await manager.async_answer(lambda: self._mint(call), on_downlink=on_downlink)
                if ok:
                    self._manager = manager

            if ok:
                self._bridge = bridge
                self._fire_call_state(True)
                self._schedule_call_timeout()
            else:
                await self._teardown_audio_bridge(bridge)
            return ok

    async def async_hangup(self) -> None:
        """Завершить разговор (BYE) / снять держимый (release) + снять аудио-мост."""
        self._cancel_call_timeout()
        self._cancel_hold_timeout()
        manager, self._manager = self._manager, None
        bridge, self._bridge = self._bridge, None
        if manager is not None:
            await manager.async_hangup()
            self._fire_call_state(False)
        await self._teardown_audio_bridge(bridge)

    async def _async_release_held(self) -> None:
        """FCM `ended` при держимом (CANCEL не пришёл) — снять held + dismiss."""
        async with self._answer_lock:
            if self._manager is None or not self._manager.holding:
                return
            self._cancel_hold_timeout()
            manager, self._manager = self._manager, None
            await manager.async_hangup()
            self._fire_call_state(False)

    async def _mint(self, call: ActiveCall) -> dict[str, Any]:
        """mint SIP-device для вызова с жёстким таймаутом (http.py без ClientTimeout)."""
        async with asyncio.timeout(_MINT_TIMEOUT_SEC):
            return await self._api.mint_sip_device(call.place_id, call.access_control_id)

    @callback
    def _fire_call_state(self, active: bool) -> None:
        """Сигнал шины о старте/конце SIP (UI: active=false → off + чистка хелпера)."""
        self._hass.bus.async_fire(EVENT_SIP_CALL, {"active": active})

    @callback
    def _on_ring_cancelled(self) -> None:
        """Держимый вызов отменён (CANCEL: сброс панели / ответ на др. устройстве) →
        мгновенный dismiss экрана. Моста ещё нет (не отвечали) — только сигнал."""
        self._cancel_hold_timeout()
        self._manager = None
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

    # ---- стрим вызова (видео камеры + аудио моста) ----
    def _call_stream_srcs(self, call: ActiveCall, bridge: AudioBridge) -> list[str]:
        """Источники go2rtc-стрима вызова: видео камеры (RTSP, если разрешилась) +
        аудио моста. Видео тянем из уже существующего go2rtc-стрима камеры по RTSP —
        НЕ из оператора (токен не трогаем) и НЕ трогая сам стрим камеры (camera.py)."""
        srcs: list[str] = []
        cam_id = (
            self._camera_resolver(call.access_control_id)
            if self._camera_resolver else None
        )
        if cam_id and self._go2rtc is not None:
            srcs.append(
                f"rtsp://{self._go2rtc.rtsp_host}:{GO2RTC_RTSP_PORT}/eg_{cam_id}#video=copy"
            )
        srcs.append(bridge.go2rtc_src)  # аудио всегда (fallback — только звук)
        return srcs

    async def _setup_audio_bridge(
        self, call: ActiveCall,
    ) -> tuple[AudioBridge | None, Callable[[bytes], None]]:
        """Поднять мост + go2rtc-стрим вызова. Возвращает (bridge|None, on_downlink)."""
        if self._go2rtc is None:
            return None, self._on_downlink  # go2rtc не настроен → счётчик (degrade)
        loop = asyncio.get_running_loop()
        host_ip = await loop.run_in_executor(None, detect_lan_ip)
        bridge = AudioBridge(host_ip, AUDIO_HTTP_PORT, _DOWNLINK_PT)
        try:
            await bridge.start()
            await upsert_audio_stream(
                self._go2rtc.base_url, CALL_STREAM_NAME, self._call_stream_srcs(call, bridge),
                async_get_clientsession(self._hass), self._go2rtc.headers,
            )
        except Exception:  # noqa: BLE001 — degrade, не валим приём вызова
            LOGGER.warning(
                "Мост/go2rtc-стрим вызова не поднялись — медиа в браузере недоступно (degrade)"
            )
            await bridge.stop()
            return None, self._on_downlink
        LOGGER.info("Стрим вызова поднят: go2rtc '%s'", CALL_STREAM_NAME)
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
        self._fire_call_state(False)
        if bridge is not None:
            self._hass.async_create_task(self._teardown_audio_bridge(bridge))

    @callback
    def _count_downlink(self, payload: bytes) -> None:
        """Fallback downlink-sink (go2rtc нет): счётчик кадров — доказательство RTP."""
        self.downlink_packets += 1
        if self.downlink_packets == 1:
            LOGGER.info(
                "SIP downlink: пошёл RTP от домофона (первый кадр %d байт)", len(payload)
            )
