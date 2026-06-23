"""Проба канала SIP — REGISTER на домофон-registrar, детект входящего INVITE.

Это проверенный экосистемой domru путь (domru-webhook/domru-ha/z81/homey):
  POST /rest/v1/places/{placeId}/accesscontrols/{acId}/sipdevices {installationId}
    → {data:{login,password,realm}}, realm = {acId}.intercom.2090000.ru
  → SIP REGISTER (Digest MD5) на realm:5060/UDP
  → входящий INVITE = ЗВОНОК В ДОМОФОН.

Проба только ДЕТЕКТИРУЕТ вызов (отвечает 180 Ringing, трубку не поднимает),
телефон продолжает звонить (SIP forking, отдельный installationId).

⚠️ За NAT входящий INVITE приходит на mapped-порт — держим его открытым
частым re-REGISTER. На home.server надёжнее, чем за домашним NAT (см. README).

Запуск:  python probe_sip.py [intercom_index]
Лог:     logs/sip.log
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import os
import random
import re
import socket
import sys
import uuid

import aiohttp

import common

LOG_PATH = "logs/sip.log"
SIP_PORT = 5060
REGISTER_EXPIRES = 120  # часто, чтобы держать NAT-mapping


def _ts() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def log(line: str) -> None:
    os.makedirs("logs", exist_ok=True)
    msg = f"{_ts()}  {line}"
    print(msg, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def digest_response(
    user: str, password: str, realm: str, nonce: str, method: str, uri: str,
    qop: str | None = None, cnonce: str | None = None, nc: str | None = None,
) -> str:
    ha1 = md5(f"{user}:{realm}:{password}")
    ha2 = md5(f"{method}:{uri}")
    if qop:
        return md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
    return md5(f"{ha1}:{nonce}:{ha2}")


def hdr(text: str, name: str) -> str | None:
    m = re.search(rf"^{name}\s*:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else None


def outbound_ip(host: str) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, SIP_PORT))
        return s.getsockname()[0]
    finally:
        s.close()


async def mint_sip(intercom: dict, sess: common.Session) -> dict:
    """POST sipdevices → SIP creds {login,password,realm}."""
    async with aiohttp.ClientSession() as s:
        api = common.Api(s, sess.user_agent, access_token=sess.access_token, operator=sess.operator_id)
        r = await api.post(
            f"/rest/v1/places/{intercom['placeId']}/accesscontrols/{intercom['accessControlId']}/sipdevices",
            {"installationId": sess.install_id},
        )
        if not r.ok:
            raise RuntimeError(f"sipdevices mint failed: {r.status}")
        return (await r.json())["data"]


class SipProto(asyncio.DatagramProtocol):
    def __init__(self, creds: dict, local_ip: str, ua: str):
        self.login = creds["login"]
        self.password = creds["password"]
        self.realm = creds["realm"]          # = SIP domain + registrar host
        self.local_ip = local_ip
        self.ua = ua
        self.transport: asyncio.DatagramTransport | None = None
        self.call_id = f"{uuid.uuid4()}@{local_ip}"
        self.cseq = 0
        self.from_tag = uuid.uuid4().hex[:8]
        self.registered = asyncio.Event()
        self._lport = 0

    # --- lifecycle ---
    def connection_made(self, transport):
        self.transport = transport
        self._lport = transport.get_extra_info("sockname")[1]
        self.send_register()

    def datagram_received(self, data: bytes, addr):
        text = data.decode(errors="replace")
        first = text.split("\r\n", 1)[0]
        if text.startswith("SIP/2.0"):
            self._on_response(text, first)
        else:                                  # request from server (INVITE/OPTIONS/...)
            self._on_request(text, first, addr)

    # --- REGISTER ---
    def send_register(self, auth: str | None = None):
        self.cseq += 1
        branch = f"z9hG4bK{random.randint(0, 1 << 31)}"
        uri = f"sip:{self.realm}"
        lines = [
            f"REGISTER {uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {self.local_ip}:{self._lport};branch={branch};rport",
            "Max-Forwards: 70",
            f"From: <sip:{self.login}@{self.realm}>;tag={self.from_tag}",
            f"To: <sip:{self.login}@{self.realm}>",
            f"Call-ID: {self.call_id}",
            f"CSeq: {self.cseq} REGISTER",
            f"Contact: <sip:{self.login}@{self.local_ip}:{self._lport};transport=udp>",
            f"Expires: {REGISTER_EXPIRES}",
            f"User-Agent: {self.ua}",
        ]
        if auth:
            lines.append(f"Authorization: {auth}")
        lines += ["Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(lines).encode())

    def _on_response(self, text: str, first: str):
        code = first.split(" ")[1]
        cseq = hdr(text, "CSeq") or ""
        if "REGISTER" not in cseq:
            return
        if code == "401" or code == "407":
            wa = hdr(text, "WWW-Authenticate") or hdr(text, "Proxy-Authenticate") or ""
            nonce = re.search(r'nonce="([^"]+)"', wa)
            realm_m = re.search(r'realm="([^"]+)"', wa)
            qop_m = re.search(r"qop=\"?([^\",]+)", wa)
            if not nonce:
                log(f"REGISTER auth challenge без nonce: {wa[:120]}")
                return
            realm = realm_m.group(1) if realm_m else self.realm
            uri = f"sip:{self.realm}"
            cnonce = uuid.uuid4().hex[:16]
            nc = "00000001"
            qop = qop_m.group(1) if qop_m else None
            resp = digest_response(
                self.login, self.password, realm, nonce.group(1),
                "REGISTER", uri, qop, cnonce, nc,
            )
            auth = (
                f'Digest username="{self.login}", realm="{realm}", '
                f'nonce="{nonce.group(1)}", uri="{uri}", response="{resp}", algorithm=MD5'
            )
            if qop:
                auth += f', qop={qop}, nc={nc}, cnonce="{cnonce}"'
            self.send_register(auth)
        elif code == "200":
            if not self.registered.is_set():
                log(f"✅ SIP REGISTERED as {self.login}@{self.realm} (port {self._lport}). ЗВОНИ В ДОМОФОН.")
            self.registered.set()
        else:
            log(f"REGISTER → SIP {first.split(' ',1)[1]}")

    # --- incoming requests ---
    def _on_request(self, text: str, first: str, addr):
        method = first.split(" ", 1)[0]
        if method == "INVITE":
            frm = hdr(text, "From") or "?"
            cid = hdr(text, "Call-ID") or "?"
            log("🔔🔔🔔 INCOMING INVITE — ЗВОНОК С ДОМОФОНА!")
            log(f"        From: {frm}")
            log(f"        Call-ID: {cid}")
            self._respond(text, addr, "180 Ringing")
        elif method in ("OPTIONS", "NOTIFY", "INFO"):
            self._respond(text, addr, "200 OK")     # keep-alive
        elif method in ("BYE", "CANCEL"):
            log(f"call {method}")
            self._respond(text, addr, "200 OK")

    def _respond(self, req: str, addr, status: str):
        via = hdr(req, "Via") or ""
        frm = hdr(req, "From") or ""
        to = hdr(req, "To") or ""
        cid = hdr(req, "Call-ID") or ""
        cseq = hdr(req, "CSeq") or ""
        to_resp = to if ";tag=" in to else f"{to};tag={uuid.uuid4().hex[:8]}"
        lines = [
            f"SIP/2.0 {status}",
            f"Via: {via}",
            f"From: {frm}",
            f"To: {to_resp}",
            f"Call-ID: {cid}",
            f"CSeq: {cseq}",
            "Content-Length: 0", "", "",
        ]
        self.transport.sendto("\r\n".join(lines).encode(), addr)


async def main() -> None:
    sess = common.Session.load("session.json")
    intercoms = sess.intercoms or []
    if not intercoms:
        raise SystemExit("в session.json нет домофонов — перелогинься")
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    intercom = intercoms[idx]
    # отдельный лог на каждый домофон, чтобы 3 инстанса не клобберили файл
    global LOG_PATH
    LOG_PATH = f"logs/sip_{intercom['accessControlId']}.log"
    log(f"=== SIP probe: {intercom['name']} (place={intercom['placeId']} ac={intercom['accessControlId']}) ===")

    creds = await mint_sip(intercom, sess)
    realm = creds["realm"]
    reg_host = realm  # registrar host = realm
    ip = socket.gethostbyname(reg_host)
    local_ip = outbound_ip(ip)
    log(f"minted SIP creds, realm={realm} → {ip}:{SIP_PORT}, local_ip={local_ip}")

    loop = asyncio.get_running_loop()
    transport, proto = await loop.create_datagram_endpoint(
        lambda: SipProto(creds, local_ip, sess.user_agent),
        remote_addr=(ip, SIP_PORT),
    )
    try:
        # держим регистрацию: re-REGISTER каждые EXPIRES-10с (NAT keep-alive)
        while True:
            await asyncio.sleep(REGISTER_EXPIRES - 10)
            proto.send_register()
            log("re-REGISTER (keep-alive)")
    except asyncio.CancelledError:
        pass
    finally:
        transport.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
