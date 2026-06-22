"""SIP-транспорт REGISTER-on-answer (asyncio.DatagramProtocol).

Склеивает register/message/dialog/sdp в флоу: REGISTER → 401-auth → 200 →
приём INVITE → 200 OK (мгновенно) → BYE. RTP — отдельно (rtp.py). По модели
call-answer-model.md (доказано pcap+probe). Сетевой слой — проверяется
research-пробой/живым звонком, не юнит-тестами.
"""
from __future__ import annotations

import asyncio
import random
import re
import uuid
from collections.abc import Callable

from ..const import LOGGER
from .dialog import DialogState, build_200_ok, build_bye, extract_dialog
from .message import parse_sip
from .register import build_contact, build_register, build_register_authorization
from .sdp import build_g711_answer


class SipProtocol(asyncio.DatagramProtocol):
    """Один SIP-диалог приёма вызова: REGISTER → INVITE → 200 OK → BYE."""

    def __init__(
        self,
        creds: dict,
        local_ip: str,
        fcm_token: str,
        user_agent: str,
        on_bye: Callable[[], None] | None = None,
    ) -> None:
        self.login = creds["login"]
        self.password = creds["password"]
        self.realm = creds["realm"]
        self.local_ip = local_ip
        self.fcm_token = fcm_token
        self.ua = user_agent
        self.on_bye = on_bye
        self.transport: asyncio.DatagramTransport | None = None
        self._lport = 0
        self.call_id = f"{uuid.uuid4()}@{local_ip}"
        self.from_tag = uuid.uuid4().hex[:8]
        self.local_tag = uuid.uuid4().hex[:8]
        self.cseq = 0
        self.registered: asyncio.Future[bool] | None = None
        self.invite: asyncio.Future[tuple] | None = None
        self.dialog: DialogState | None = None

    # ---- lifecycle ----
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]
        self._lport = transport.get_extra_info("sockname")[1]
        loop = asyncio.get_event_loop()
        self.registered = loop.create_future()
        self.invite = loop.create_future()
        self.send_register()

    def send_register(self, auth: str | None = None) -> None:
        if self.transport is None:
            return
        self.cseq += 1
        branch = f"z9hG4bK{random.randint(0, 1 << 31)}"
        contact = build_contact(self.login, self.local_ip, self._lport, self.fcm_token)
        reg = build_register(
            self.login, self.realm, self.local_ip, self._lport, self.call_id,
            self.from_tag, self.cseq, contact, branch, self.ua, auth=auth,
        )
        self.transport.sendto(reg.encode())

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            msg = parse_sip(data.decode("utf-8", errors="replace"))
            if msg.start_line.startswith("SIP/2.0"):
                self._on_response(msg)
                return
            method = msg.start_line.split(" ", 1)[0]
            if method == "INVITE":
                self._on_invite(msg, addr)
            elif method in ("BYE", "CANCEL"):
                self._respond_200(msg, addr)
                if self.on_bye is not None:
                    self.on_bye()
            elif method in ("OPTIONS", "NOTIFY", "INFO"):
                self._respond_200(msg, addr)
        except Exception:  # noqa: BLE001 — не валим сокет на битом пакете
            LOGGER.exception("SIP: ошибка обработки datagram")

    # ---- handlers ----
    def _on_response(self, msg) -> None:
        if "REGISTER" not in (msg.first("cseq") or ""):
            return
        code = msg.start_line.split(" ")[1] if len(msg.start_line.split(" ")) > 1 else ""
        if code in ("401", "407"):
            wa = msg.first("www-authenticate") or msg.first("proxy-authenticate") or ""
            nonce = re.search(r'nonce="([^"]+)"', wa)
            if not nonce:
                return
            realm_m = re.search(r'realm="([^"]+)"', wa)
            realm = realm_m.group(1) if realm_m else self.realm
            auth = build_register_authorization(
                self.login, self.password, realm, nonce.group(1), f"sip:{self.realm}"
            )
            self.send_register(auth)
        elif code == "200" and self.registered is not None and not self.registered.done():
            self.registered.set_result(True)

    def _on_invite(self, msg, addr: tuple) -> None:
        if self.invite is not None and not self.invite.done():
            self.invite.set_result((msg, addr))

    def answer(self, invite_msg, addr: tuple, media_ip: str, media_port: int,
               payload_type: int, codec: str) -> None:
        """200 OK с G.711 SDP-answer (мгновенно) + сохранение dialog-state для BYE."""
        if self.transport is None:
            return
        sdp_body = build_g711_answer(media_ip, media_port, payload_type, codec)
        contact = f"<sip:{self.login}@{self.local_ip}:{self._lport};transport=udp>"
        ok = build_200_ok(invite_msg, sdp_body, self.local_tag, contact, self.ua)
        self.transport.sendto(ok.encode(), addr)
        self.dialog = extract_dialog(invite_msg, self.local_tag)

    def send_bye(self) -> None:
        if self.transport is None or self.dialog is None:
            return
        self.cseq += 1
        branch = f"z9hG4bK{random.randint(0, 1 << 31)}"
        bye = build_bye(self.dialog, self.local_ip, self._lport, self.ua, self.cseq, branch)
        self.transport.sendto(bye.encode())

    def _respond_200(self, msg, addr: tuple) -> None:
        if self.transport is None:
            return
        lines = ["SIP/2.0 200 OK"]
        for name in ("via", "from", "to", "call-id", "cseq"):
            lines.extend(msg.raw_lines(name))
        lines += ["Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(lines).encode(), addr)

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
            self.transport = None
