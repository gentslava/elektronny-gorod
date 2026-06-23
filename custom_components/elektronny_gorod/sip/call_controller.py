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

Downlink-вывод звука гостя (media_player vs go2rtc) — отдельный слайс; здесь
`on_downlink` по умолчанию считает кадры (доказательство, что RTP пошёл).
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from ..const import DOORBELL_CALL_WINDOW_FALLBACK_SEC, LOGGER
from .manager import SipManager

# mint SIP-кредов — на критическом пути ответа (окно CallInvalidated ~30с).
# Жёсткий таймаут, чтобы зависший POST не «съел» окно (http.py без ClientTimeout,
# A-21) → иначе INVITE прилетит для следующего вызова (ложный «ответ сразу»).
_MINT_TIMEOUT_SEC = 8.0


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
    ) -> None:
        self._hass = hass
        self._api = api
        self._fcm_token_getter = fcm_token_getter
        self._on_downlink = on_downlink or self._count_downlink
        self._active: ActiveCall | None = None
        self._manager: SipManager | None = None
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

            manager = SipManager(fcm_token, on_downlink=self._on_downlink)
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
            return ok

    async def async_hangup(self) -> None:
        """Завершить активный разговор (BYE через SipManager)."""
        manager, self._manager = self._manager, None
        if manager is not None:
            await manager.async_hangup()

    @callback
    def _count_downlink(self, payload: bytes) -> None:
        """Дефолтный downlink-sink: счётчик кадров (вывод звука — отдельный слайс)."""
        self.downlink_packets += 1
        if self.downlink_packets == 1:
            LOGGER.info(
                "SIP downlink: пошёл RTP от домофона (первый кадр %d байт)", len(payload)
            )
