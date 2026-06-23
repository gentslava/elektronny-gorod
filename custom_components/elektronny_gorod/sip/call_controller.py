"""DoorbellCallController — HA-glue приёма вызова домофона (REGISTER-on-answer).

Связывает три части:
- FCM `SIGNAL_DOORBELL` (ring/ended) → трекинг **активного** вызова и окна
  `CallInvalidated` (зеркало event.py);
- сервис `answer` → mint SIP-кред (api.mint_sip_device) → `SipManager.async_answer`
  (доказанный REGISTER → INVITE → 200 OK → RTP-latching);
- сервис `hangup` → `SipManager.async_hangup` (BYE).

🔴 Call-ID binding (call-answer-model.md §6.5): отвечаем **только** на активный
незавершённый вызов в окне `CallInvalidated`. Иначе запоздалый REGISTER поймал бы
INVITE *следующего* вызова → ложный «ответ сразу». Один активный ответ-флоу.

Downlink-вывод звука гостя (Slice 1, D-audio-1): если go2rtc настроен — поднимаем
`AudioBridge` (ffmpeg G.711→mpegts/aac HTTP) + per-call go2rtc-стрим
`ffmpeg:http://<bridge>`, `on_downlink` кормит мост → Advanced Camera Card. Если
go2rtc нет/не поднялся — degrade на счётчик кадров (вызов на уровне SIP живёт).
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

from ..const import DOORBELL_CALL_WINDOW_FALLBACK_SEC, LOGGER
from ..go2rtc import remove_audio_stream, upsert_audio_stream
from .bridge import AudioBridge, detect_lan_ip
from .manager import SipManager

# mint SIP-кредов — на критическом пути ответа (окно CallInvalidated ~30с).
# Жёсткий таймаут, чтобы зависший POST не «съел» окно (http.py без ClientTimeout,
# A-21) → иначе INVITE прилетит для следующего вызова (ложный «ответ сразу»).
_MINT_TIMEOUT_SEC = 8.0

# Аудио-мост downlink (D-audio-1): фикс HTTP-порт ffmpeg-сервера + имя go2rtc-стрима.
AUDIO_HTTP_PORT = 40020
AUDIO_STREAM_NAME = "eg_intercom_talk"
# Домофон оператора шлёт PCMU(0) (live-доказано: «PT=0 PCMU»). Мост — под него.
_DOWNLINK_PT = 0

# Событие шины: состояние SIP-разговора (start/end). UI ведёт экран по нему, а не
# по FCM-событию `ended` (то срабатывает по окну вызова ~30с, разговор живёт дольше).
EVENT_SIP_CALL = "elektronny_gorod_sip_call"


@dataclass
class Go2RtcConfig:
    """go2rtc для аудио-моста: base_url + auth-заголовки (из entry)."""

    base_url: str
    headers: dict


@dataclass
class ActiveCall:
    """Активный FCM-вызов, на который допустим `answer` (в окне CallInvalidated)."""

    call_id: str | None
    place_id: str
    access_control_id: str
    deadline: datetime


class DoorbellCallController:
    """Трекинг активного вызова + answer/hangup через SipManager (один на entry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: Any,
        fcm_token_getter: Callable[[], str | None],
        on_downlink: Callable[[bytes], None] | None = None,
        go2rtc: Go2RtcConfig | None = None,
    ) -> None:
        self._hass = hass
        self._api = api
        self._fcm_token_getter = fcm_token_getter
        self._on_downlink = on_downlink or self._count_downlink
        self._go2rtc = go2rtc
        self._active: ActiveCall | None = None
        self._manager: SipManager | None = None
        self._bridge: AudioBridge | None = None
        # Сериализует answer: защита от двойного нажатия/параллельного сервиса —
        # без него два concurrent answer создали бы 2 SipManager на фикс-портах.
        self._answer_lock = asyncio.Lock()
        self.downlink_packets = 0

    # ---- трекинг активного вызова (из SIGNAL_DOORBELL) ----
    @callback
    def handle_signal(self, payload: dict[str, Any]) -> None:
        """SIGNAL_DOORBELL callback: `ring` → запомнить вызов, `ended` → снять."""
        event_type = payload.get("event_type")
        attrs = payload.get("attributes") or {}
        if event_type == "ring":
            self._active = ActiveCall(
                call_id=attrs.get("call_id"),
                place_id=str(payload.get("place_id") or ""),
                access_control_id=str(payload.get("access_control_id") or ""),
                deadline=self._compute_deadline(attrs.get("call_invalidated")),
            )
        elif event_type == "ended" and self._active is not None:
            # Снять активный только если это тот же вызов (или end без call_id).
            cid = attrs.get("call_id")
            if cid is None or cid == self._active.call_id:
                self._active = None

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

    # ---- сервисы answer / hangup ----
    async def async_answer(self) -> bool:
        """Ответить на текущий вызов: mint → SipManager (REGISTER-on-answer).

        Один concurrent-разговор (фикс-порты SIP/RTP, модель first-answer-wins):
        `_answer_lock` сериализует, in_call-guard отклоняет повторный.
        """
        async with self._answer_lock:
            call = self.current_call()
            if call is None:
                LOGGER.warning(
                    "SIP answer: нет активного вызова в окне CallInvalidated — игнор"
                )
                return False
            if self._manager is not None and self._manager.in_call:
                LOGGER.warning("SIP answer: уже идёт разговор — игнор")
                return False
            fcm_token = self._fcm_token_getter()
            if not fcm_token:
                LOGGER.warning("SIP answer: FCM-токен не готов — REGISTER невозможен")
                return False

            # Аудио-мост (downlink → go2rtc). Если go2rtc нет/не поднялся —
            # degrade на счётчик: вызов на уровне SIP всё равно отвечается.
            bridge, on_downlink = await self._setup_audio_bridge()

            manager = SipManager(
                fcm_token, on_downlink=on_downlink, on_ended=self._schedule_audio_cleanup
            )
            self.downlink_packets = 0

            async def _mint() -> dict[str, Any]:
                # Жёсткий таймаут на mint — http.py без ClientTimeout (A-21).
                async with asyncio.timeout(_MINT_TIMEOUT_SEC):
                    return await self._api.mint_sip_device(
                        call.place_id, call.access_control_id
                    )

            ok = await manager.async_answer(_mint)
            if ok:
                self._manager = manager
                self._bridge = bridge
                self._fire_call_state(True)
            else:
                await self._teardown_audio_bridge(bridge)
            return ok

    async def async_hangup(self) -> None:
        """Завершить активный разговор (BYE) + снять аудио-мост/go2rtc-стрим."""
        manager, self._manager = self._manager, None
        bridge, self._bridge = self._bridge, None
        if manager is not None:
            await manager.async_hangup()
            self._fire_call_state(False)
        await self._teardown_audio_bridge(bridge)

    @callback
    def _fire_call_state(self, active: bool) -> None:
        """Сигнал шины о старте/конце SIP-разговора (для UI-состояния экрана)."""
        self._hass.bus.async_fire(EVENT_SIP_CALL, {"active": active})

    # ---- аудио-мост (downlink) ----
    async def _setup_audio_bridge(
        self,
    ) -> tuple[AudioBridge | None, Callable[[bytes], None]]:
        """Поднять мост + go2rtc-стрим. Возвращает (bridge|None, on_downlink-sink)."""
        if self._go2rtc is None:
            return None, self._on_downlink  # go2rtc не настроен → счётчик (degrade)
        loop = asyncio.get_running_loop()
        host_ip = await loop.run_in_executor(None, detect_lan_ip)
        bridge = AudioBridge(host_ip, AUDIO_HTTP_PORT, _DOWNLINK_PT)
        try:
            await bridge.start()
            await upsert_audio_stream(
                self._go2rtc.base_url, AUDIO_STREAM_NAME, bridge.go2rtc_src,
                async_get_clientsession(self._hass), self._go2rtc.headers,
            )
        except Exception:  # noqa: BLE001 — degrade, не валим приём вызова
            LOGGER.warning(
                "Аудио-мост/go2rtc не поднялись — звук в браузере недоступен (degrade)"
            )
            await bridge.stop()
            return None, self._on_downlink
        LOGGER.info("Аудио-мост поднят: go2rtc-стрим '%s'", AUDIO_STREAM_NAME)
        return bridge, bridge.feed_downlink

    async def _teardown_audio_bridge(self, bridge: AudioBridge | None) -> None:
        """Остановить мост + снять go2rtc-стрим (best-effort)."""
        if bridge is None:
            return
        await bridge.stop()
        if self._go2rtc is not None:
            await remove_audio_stream(
                self._go2rtc.base_url, AUDIO_STREAM_NAME,
                async_get_clientsession(self._hass), self._go2rtc.headers,
            )

    @callback
    def _schedule_audio_cleanup(self) -> None:
        """on_ended от SipManager (remote BYE): снять мост + сигнал конца SIP."""
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
