"""SipManager — оркестрация приёма вызова домофона (register-on-ring, ADR-0012).

Фазы (зеркало приложения, pcap):
- `register_and_hold(mint)`: на FCM-ring → REGISTER → forked INVITE → `100 Trying`,
  держим (НЕ `200 OK`). Возвращает True, если вызов на руках.
- `accept(on_downlink)`: на «Ответить» → `200 OK` на держимый INVITE → RTP latching.
- приём `CANCEL` (сброс с панели / ответ на др. устройстве) → `487` + `on_cancelled`.
- `async_answer(mint, on_downlink)`: fallback-композиция hold+accept (если held-фазы
  не было — register-on-answer как раньше, чтобы приём не регрессировал).

`async_hangup`: BYE/release + cleanup. Один активный/держимый вызов (фикс-порты,
PRD F1 first-answer-wins). Слой downlink/uplink — через `on_downlink`/`uplink_provider`.
Сетевой слой — проверяется research-пробой/живым звонком, не юнит-тестами.
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


class HeldCall:
    """Держимый (не отвеченный) вызов: SIP-сессия + сохранённый INVITE для accept/487."""

    def __init__(
        self,
        sip: SipProtocol,
        sip_transport: asyncio.BaseTransport,
        invite_msg,
        addr: tuple,
        local_ip: str,
    ) -> None:
        self.sip = sip
        self.sip_transport = sip_transport
        self.invite_msg = invite_msg
        self.addr = addr
        self.local_ip = local_ip

    def release(self) -> None:
        """Снять держимую сессию (закрыть сокеты). 487 шлёт протокол на CANCEL."""
        self.sip.close()
        self.sip_transport.close()


class ActiveCall:
    """Хэндл активного (отвеченного) вызова (SIP + RTP + uplink-задача)."""

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
    """Приём вызова домофона по модели register-on-ring (один активный/держимый)."""

    def __init__(
        self,
        fcm_token: str,
        uplink_provider: Callable[[], bytes | None] | None = None,
        on_ended: Callable[[], None] | None = None,
        on_cancelled: Callable[[], None] | None = None,
    ) -> None:
        self._fcm_token = fcm_token
        self._uplink_provider = uplink_provider
        # on_ended — вызов завершён удалённой стороной (BYE, in-call).
        # on_cancelled — неотвеченный вызов отменён (CANCEL: сброс панели / др. устройство).
        self._on_ended = on_ended
        self._on_cancelled = on_cancelled
        self._active: ActiveCall | None = None
        self._held: HeldCall | None = None

    @property
    def in_call(self) -> bool:
        return self._active is not None

    @property
    def holding(self) -> bool:
        return self._held is not None

    def detach(self) -> None:
        """Отвязать колбэки контроллера (A-89 switch): поздний BYE/CANCEL этого
        (уже смещённого) держимого вызова не должен дёргать контроллер и трогать
        новый активный вызов. Sync — закрывает окно до `async_hangup`."""
        self._on_ended = None
        self._on_cancelled = None

    async def register_and_hold(
        self,
        mint_creds: Callable[[], Awaitable[dict]],
        *,
        fcm_call_id: str | None = None,
    ) -> bool:
        """На ring: REGISTER → forked INVITE → 100 Trying, держим. True при успехе."""
        if self._active is not None or self._held is not None:
            LOGGER.warning("SIP: уже есть активный/держимый вызов — игнор hold")
            return False
        loop = asyncio.get_running_loop()
        creds = await mint_creds()
        registrar_ip = await loop.run_in_executor(None, socket.gethostbyname, creds["realm"])
        local_ip = await loop.run_in_executor(None, _outbound_ip, registrar_ip)

        sip_transport, sip = await loop.create_datagram_endpoint(
            lambda: SipProtocol(
                creds,
                local_ip,
                self._fcm_token,
                SIP_USER_AGENT,
                on_bye=self._on_remote_bye,
                on_cancel=self._on_remote_cancel,
                fcm_call_id=fcm_call_id,
                accept_sdp=True,
                include_contact_transport=False,
            ),
            local_addr=("0.0.0.0", SIP_LOCAL_PORT), remote_addr=(registrar_ip, SIP_PORT),
        )
        # Узкий except: единственный реальный исход wait_for здесь — timeout (протокол
        # резолвит future только set_result, не set_exception); OSError — на случай
        # сбоя datagram-транспорта. Программные ошибки (KeyError на creds и т.п.) НЕ
        # глотаем — пусть всплывают в контроллер (P2-1).
        try:
            await asyncio.wait_for(sip.registered, timeout=REGISTER_TIMEOUT)
        except (asyncio.TimeoutError, OSError):
            LOGGER.warning("SIP: REGISTER не подтверждён за %.0fs — отмена hold", REGISTER_TIMEOUT)
            sip.close()
            sip_transport.close()
            return False
        try:
            invite_msg, addr = await asyncio.wait_for(sip.invite, timeout=INVITE_TIMEOUT)
        except (asyncio.TimeoutError, OSError):
            LOGGER.warning("SIP: INVITE не пришёл за %.0fs после REGISTER — отмена hold", INVITE_TIMEOUT)
            sip.close()
            sip_transport.close()
            return False

        sip.send_trying()  # 100 Trying — держим вызов «звонящим», без авто-ответа
        self._held = HeldCall(sip, sip_transport, invite_msg, addr, local_ip)
        LOGGER.info("SIP: вызов держится (100 Trying) — ждём «Ответить» или CANCEL")
        return True

    async def accept(self, on_downlink: Callable[[bytes], None] | None = None) -> bool:
        """На «Ответить»: 200 OK на держимый INVITE → RTP latching. True при успехе."""
        held, self._held = self._held, None
        if held is None:
            LOGGER.warning("SIP: accept без держимого вызова — игнор")
            return False
        loop = asyncio.get_running_loop()
        # SDP-offer — untrusted network input (INVITE body). parse_sdp толерантен к
        # битым строкам, но пустой fmts / отсутствие audio — валидный SDP без payload:
        # degrade (release + False), а не краш → утечка моста в контроллере (P1-1).
        sdp = parse_sdp(held.invite_msg.body)
        audio = next((m for m in sdp["media"] if m["type"] == "audio"), None)
        if not audio or not audio["fmts"]:
            LOGGER.warning("SIP: нет audio/payload в SDP-offer — degrade")
            held.release()
            return False
        try:
            pt = int(audio["fmts"][0])
        except ValueError:
            LOGGER.warning("SIP: нечисловой payload-type в SDP-offer — degrade")
            held.release()
            return False
        codec = sdp["rtpmap"].get(str(pt), "PCMU/8000" if pt == 0 else "PCMA/8000")
        door_ip, door_port = sdp["conn_ip"], audio["port"]

        rtp_transport, rtp = await loop.create_datagram_endpoint(
            lambda: RtpSession(pt, on_downlink=on_downlink),
            local_addr=("0.0.0.0", RTP_LOCAL_PORT),
        )
        # 200 OK мгновенно (локальный SDP → latching), затем сразу RTP uplink.
        held.sip.answer(held.invite_msg, held.addr, held.local_ip, RTP_LOCAL_PORT, pt, codec)
        stop = asyncio.Event()
        uplink_task = loop.create_task(
            rtp.run_uplink(door_ip, door_port, self._frame_provider, stop)
        )
        self._active = ActiveCall(held.sip, held.sip_transport, rtp_transport, uplink_task, stop)
        LOGGER.info("SIP: вызов принят (PT=%s %s), latching uplink запущен", pt, codec)
        return True

    async def async_answer(
        self,
        mint_creds: Callable[[], Awaitable[dict]],
        on_downlink: Callable[[bytes], None] | None = None,
        *,
        fcm_call_id: str | None = None,
    ) -> bool:
        """Fallback register-on-answer: hold+accept одним вызовом (если held-фазы не было)."""
        if not await self.register_and_hold(mint_creds, fcm_call_id=fcm_call_id):
            return False
        return await self.accept(on_downlink)

    async def async_hangup(self) -> None:
        """Завершить активный (BYE) или снять держимый вызов + cleanup."""
        active, self._active = self._active, None
        held, self._held = self._held, None
        if active is not None:
            await active.teardown(send_bye=True)
            LOGGER.info("SIP: вызов завершён (hangup)")
        elif held is not None:
            held.release()
            LOGGER.info("SIP: держимый вызов снят (hangup до ответа)")

    def _frame_provider(self) -> bytes | None:
        return self._uplink_provider() if self._uplink_provider is not None else None

    def _on_remote_bye(self) -> None:
        """Домофон/оператор завершил отвеченный вызов (BYE) — снять активный без BYE."""
        active, self._active = self._active, None
        if active is not None:
            asyncio.get_running_loop().create_task(active.teardown(send_bye=False))
            LOGGER.info("SIP: вызов завершён удалённой стороной (BYE)")
            if self._on_ended is not None:
                self._on_ended()

    def _on_remote_cancel(self) -> None:
        """Неотвеченный вызов отменён (CANCEL: сброс панели / ответ на др. устройстве).

        Протокол уже отправил 487 на держимый INVITE — здесь снимаем сессию и
        уведомляем контроллер (→ мгновенный dismiss экрана)."""
        held, self._held = self._held, None
        if held is not None:
            held.release()
            LOGGER.info("SIP: вызов отменён удалённой стороной (CANCEL)")
            if self._on_cancelled is not None:
                self._on_cancelled()
