"""SipManager — оркестрация REGISTER-on-answer приёма вызова домофона.

`async_answer(creds_minter)`: REGISTER → ждать INVITE → `200 OK` мгновенно →
RtpSession (uplink latching + downlink). `async_hangup`: BYE + cleanup. Привязка
к одному активному вызову (PRD F1 first-answer-wins). По call-answer-model.md.

Слой downlink-вывода (Slice 1) и uplink-микрофона (Slice 2) подключаются через
`on_downlink` / `uplink_provider` — здесь они опциональны (тишина-keepalive держит
latching). Сетевой — проверяется research-пробой/живым звонком, не юнит-тестами.
"""
from __future__ import annotations

import asyncio
import socket
from collections.abc import Awaitable, Callable

from ..const import LOGGER
from .protocol import SipProtocol
from .rtp import RtpSession
from .sdp import parse_sdp

SIP_PORT = 5060
SIP_LOCAL_PORT = 5066  # фиксированный (стабильный Contact, без «кладбища» регистраций)
RTP_LOCAL_PORT = 40016
SIP_USER_AGENT = "Myhome/Myhome-android"  # зеркало приложения (call-answer-model.md)
REGISTER_TIMEOUT = 5.0
INVITE_TIMEOUT = 8.0  # INVITE приходит за ~90мс после REGISTER; запас на сеть


def _outbound_ip(host: str) -> str:
    """Локальный IP, с которого уходит трафик к host (для SDP/Contact)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, SIP_PORT))
        return s.getsockname()[0]
    finally:
        s.close()


class ActiveCall:
    """Хэндл активного вызова (SIP + RTP + uplink-задача)."""

    def __init__(
        self,
        sip: SipProtocol,
        sip_transport: asyncio.BaseTransport,
        rtp_transport: asyncio.BaseTransport,
        uplink_task: asyncio.Task,
        stop: asyncio.Event,
    ) -> None:
        self.sip = sip
        self._sip_transport = sip_transport
        self._rtp_transport = rtp_transport
        self._uplink_task = uplink_task
        self._stop = stop

    async def teardown(self, send_bye: bool = True) -> None:
        self._stop.set()
        if send_bye:
            self.sip.send_bye()
        self._uplink_task.cancel()
        self._rtp_transport.close()
        self.sip.close()
        self._sip_transport.close()


class SipManager:
    """Приём вызова домофона по модели REGISTER-on-answer (один активный вызов)."""

    def __init__(
        self,
        fcm_token: str,
        on_downlink: Callable[[bytes], None] | None = None,
        uplink_provider: Callable[[], bytes | None] | None = None,
    ) -> None:
        self._fcm_token = fcm_token
        self._on_downlink = on_downlink
        self._uplink_provider = uplink_provider
        self._active: ActiveCall | None = None

    @property
    def in_call(self) -> bool:
        return self._active is not None

    async def async_answer(self, mint_creds: Callable[[], Awaitable[dict]]) -> bool:
        """Ответить на текущий вызов: REGISTER → INVITE → 200 OK → RTP. True при успехе."""
        if self._active is not None:
            LOGGER.warning("SIP: уже есть активный вызов — игнор повторного answer")
            return False
        loop = asyncio.get_running_loop()
        creds = await mint_creds()
        registrar_ip = await loop.run_in_executor(None, socket.gethostbyname, creds["realm"])
        local_ip = await loop.run_in_executor(None, _outbound_ip, registrar_ip)

        sip_transport, sip = await loop.create_datagram_endpoint(
            lambda: SipProtocol(creds, local_ip, self._fcm_token, SIP_USER_AGENT,
                                on_bye=self._on_remote_bye),
            local_addr=("0.0.0.0", SIP_LOCAL_PORT), remote_addr=(registrar_ip, SIP_PORT),
        )
        try:
            await asyncio.wait_for(sip.registered, timeout=REGISTER_TIMEOUT)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001
            LOGGER.warning(
                "SIP: REGISTER не подтверждён за %.0fs (нет 200 OK) — отмена ответа",
                REGISTER_TIMEOUT,
            )
            sip.close()
            sip_transport.close()
            return False
        try:
            invite_msg, addr = await asyncio.wait_for(sip.invite, timeout=INVITE_TIMEOUT)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001
            LOGGER.warning(
                "SIP: INVITE не пришёл за %.0fs после успешного REGISTER — отмена ответа",
                INVITE_TIMEOUT,
            )
            sip.close()
            sip_transport.close()
            return False

        sdp = parse_sdp(invite_msg.body)
        audio = next((m for m in sdp["media"] if m["type"] == "audio"), None)
        if not audio:
            LOGGER.warning("SIP: нет audio в SDP-offer")
            sip.close()
            sip_transport.close()
            return False
        pt = int(audio["fmts"][0])
        codec = sdp["rtpmap"].get(str(pt), "PCMU/8000" if pt == 0 else "PCMA/8000")
        door_ip, door_port = sdp["conn_ip"], audio["port"]

        rtp_transport, rtp = await loop.create_datagram_endpoint(
            lambda: RtpSession(pt, on_downlink=self._on_downlink),
            local_addr=("0.0.0.0", RTP_LOCAL_PORT),
        )
        # 200 OK мгновенно (локальный SDP → latching), затем сразу RTP uplink.
        sip.answer(invite_msg, addr, local_ip, RTP_LOCAL_PORT, pt, codec)
        stop = asyncio.Event()
        uplink_task = loop.create_task(
            rtp.run_uplink(door_ip, door_port, self._frame_provider, stop)
        )
        self._active = ActiveCall(sip, sip_transport, rtp_transport, uplink_task, stop)
        LOGGER.info("SIP: вызов принят (PT=%s %s), latching uplink запущен", pt, codec)
        return True

    async def async_hangup(self) -> None:
        """Завершить активный вызов (BYE + cleanup)."""
        active, self._active = self._active, None
        if active is not None:
            await active.teardown(send_bye=True)
            LOGGER.info("SIP: вызов завершён (hangup)")

    def _frame_provider(self) -> bytes | None:
        return self._uplink_provider() if self._uplink_provider is not None else None

    def _on_remote_bye(self) -> None:
        """Домофон/оператор завершил вызов — снять активный без повторного BYE."""
        active, self._active = self._active, None
        if active is not None:
            asyncio.get_running_loop().create_task(active.teardown(send_bye=False))
            LOGGER.info("SIP: вызов завершён удалённой стороной (BYE)")
