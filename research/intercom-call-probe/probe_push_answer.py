"""Проба push-to-register: проверяем модель приложения «SIP поднимается по пушу».

НЕ держим SIP-регистрацию. Держим только FCM-listener. На `CALL_INCOMING`
немедленно регистрируемся (transient) и слушаем INVITE — проверяем, доставляет ли
Kazoo вызов на ПОЗДНЮЮ регистрацию (поднятую уже после начала вызова).

SIP-креды минтятся ЗАРАНЕЕ (при старте) → по пушу только REGISTER (минимум задержки).
НЕ забираем вызов (на INVITE отвечаем 180 Ringing, не 200 OK) — только детект+замер.

Env:
  INTERCOM_AC=<ac>     — какой домофон слушать (по умолчанию первый)
  PUSH_PARAMS=1        — добавить RFC 8599 push-параметры в Contact REGISTER
  REG_LISTEN_SEC=20    — сколько ждать INVITE после transient-register

Запуск: python probe_push_answer.py
Лог:    logs/push_answer.log
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import random
import socket
import time
import uuid

import aiohttp

import common
from probe_sip import SIP_PORT, digest_response, hdr, outbound_ip

LOG_PATH = "logs/push_answer.log"
CRED_FILE = "fcm_credentials.json"
FB_CFG_FILE = "firebase_config.json"
SIP_LOCAL_PORT = 5068
REG_LISTEN_SEC = int(os.environ.get("REG_LISTEN_SEC", "20"))
USE_PUSH_PARAMS = os.environ.get("PUSH_PARAMS") == "1"

LOOP: asyncio.AbstractEventLoop | None = None
STATE: dict = {}  # sess, intercom, creds, local_ip, ip, fcm_token, sender
_handled: set[str] = set()


def _ts() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def log(line: str) -> None:
    os.makedirs("logs", exist_ok=True)
    msg = f"{_ts()}  {line}"
    print(msg, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def _session(**kw) -> aiohttp.ClientSession:
    # macOS/контейнер: ThreadedResolver надёжнее aiodns (пустой resolv.conf).
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver()), **kw
    )


# ---------------- FCM creds (из probe_fcm) ----------------
def _load_creds() -> dict | None:
    try:
        with open(CRED_FILE, encoding="utf-8") as f:
            return json.load(f) or None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_creds(creds: dict, *_) -> None:
    with open(CRED_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f)
    log("FCM credentials persisted")


def _device_id(install_id: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_DNS, "push-answer-" + install_id).hex[:16]


async def bind_token(sess: common.Session, fcm_token: str) -> None:
    body = {
        "appVersionCode": int(common.APP_VERSION["code"]),
        "installationId": sess.install_id,
        "appId": 2,
        "appVersion": common.APP_VERSION["name"],
        "platform": "google",
        "pushToken": fcm_token,
        "isDevelop": False,
        "deviceManufacturer": "Google",
        "deviceModelName": "Pixel 8",
        "osVersion": common.ANDROID_OS_VER,
        "deviceId": _device_id(sess.install_id),
        "deviceType": "MOBILE_APPLICATION",
    }
    async with _session() as s:
        api = common.Api(s, sess.user_agent, access_token=sess.access_token, operator=sess.operator_id)
        r1 = await api.post(
            "/api/mh-customer-device/mobile/public/v1/customers/device-installations", body
        )
        r2 = await api.post("/rest/v1/subscriberNotifications", body)
        log(f"bind: device-installations={r1.status} subscriberNotifications={r2.status}")


async def mint_sip(sess: common.Session, intercom: dict) -> dict:
    async with _session() as s:
        api = common.Api(s, sess.user_agent, access_token=sess.access_token, operator=sess.operator_id)
        r = await api.post(
            f"/rest/v1/places/{intercom['placeId']}/accesscontrols/{intercom['accessControlId']}/sipdevices",
            {"installationId": sess.install_id},
        )
        if not r.ok:
            raise RuntimeError(f"sipdevices mint failed: {r.status}")
        return (await r.json())["data"]


# ---------------- transient SIP register + INVITE detect ----------------
class TransientSip(asyncio.DatagramProtocol):
    def __init__(self, creds: dict, local_ip: str, ua: str, t0: float):
        self.login, self.password, self.realm = creds["login"], creds["password"], creds["realm"]
        self.local_ip, self.ua, self.t0 = local_ip, ua, t0
        self.transport = None
        self.call_id = f"{uuid.uuid4()}@{local_ip}"
        self.cseq = 0
        self.from_tag = uuid.uuid4().hex[:8]
        self._lport = 0
        self.registered_mono: float | None = None
        self.invite_mono: float | None = None

    def connection_made(self, transport):
        self.transport = transport
        self._lport = transport.get_extra_info("sockname")[1]
        log("  → transient REGISTER отправляю…")
        self.send_register()

    def _contact(self) -> str:
        c = f"<sip:{self.login}@{self.local_ip}:{self._lport};transport=udp>"
        if USE_PUSH_PARAMS and STATE.get("fcm_token"):
            # RFC 8599 push-параметры — сервер может адресовать вызов по push-токену.
            c = (f"<sip:{self.login}@{self.local_ip}:{self._lport};transport=udp>"
                 f";pn-provider=fcm;pn-param={STATE.get('sender','')};pn-prid={STATE['fcm_token']}")
        return c

    def send_register(self, auth=None):
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
            f"Contact: {self._contact()}",
            "Expires: 120",
            f"User-Agent: {self.ua}",
        ]
        if auth:
            lines.append(f"Authorization: {auth}")
        lines += ["Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(lines).encode())

    def datagram_received(self, data, addr):
        import re
        text = data.decode(errors="replace")
        first = text.split("\r\n", 1)[0]
        if text.startswith("SIP/2.0"):
            code = first.split(" ")[1] if len(first.split(" ")) > 1 else ""
            cseq = hdr(text, "CSeq") or ""
            if "REGISTER" not in cseq:
                return
            if code in ("401", "407"):
                wa = hdr(text, "WWW-Authenticate") or hdr(text, "Proxy-Authenticate") or ""
                nonce = re.search(r'nonce="([^"]+)"', wa)
                if not nonce:
                    return
                realm_m = re.search(r'realm="([^"]+)"', wa)
                qop_m = re.search(r"qop=\"?([^\",]+)", wa)
                realm = realm_m.group(1) if realm_m else self.realm
                uri = f"sip:{self.realm}"
                cnonce, nc = uuid.uuid4().hex[:16], "00000001"
                qop = qop_m.group(1) if qop_m else None
                resp = digest_response(self.login, self.password, realm, nonce.group(1), "REGISTER", uri, qop, cnonce, nc)
                auth = (f'Digest username="{self.login}", realm="{realm}", nonce="{nonce.group(1)}", '
                        f'uri="{uri}", response="{resp}", algorithm=MD5')
                if qop:
                    auth += f', qop={qop}, nc={nc}, cnonce="{cnonce}"'
                self.send_register(auth)
            elif code == "200" and self.registered_mono is None:
                self.registered_mono = time.monotonic()
                log(f"  ✅ transient REGISTERED (t0→register = {self.registered_mono - self.t0:.3f}с). Жду INVITE…")
        else:
            method = first.split(" ", 1)[0]
            if method == "INVITE" and self.invite_mono is None:
                self.invite_mono = time.monotonic()
                d_reg = (self.invite_mono - self.registered_mono) if self.registered_mono else float("nan")
                log("  🔔 INVITE ПРИШЁЛ на transient-register!")
                log(f"     t0(CALL_INCOMING)→INVITE = {self.invite_mono - self.t0:.3f}с; register→INVITE = {d_reg:.3f}с")
                # отвечаем 180 Ringing (не забираем вызов — только детект)
                via = hdr(text, "Via") or ""
                to = hdr(text, "To") or ""
                to_r = to if ";tag=" in to else f"{to};tag={uuid.uuid4().hex[:8]}"
                resp = ["SIP/2.0 180 Ringing", f"Via: {via}", f"From: {hdr(text,'From')}",
                        f"To: {to_r}", f"Call-ID: {hdr(text,'Call-ID')}", f"CSeq: {hdr(text,'CSeq')}",
                        "Content-Length: 0", "", ""]
                self.transport.sendto("\r\n".join(resp).encode(), addr)
            elif method in ("OPTIONS", "NOTIFY", "INFO"):
                via = hdr(text, "Via") or ""
                resp = ["SIP/2.0 200 OK", f"Via: {via}", f"From: {hdr(text,'From')}",
                        f"To: {hdr(text,'To')}", f"Call-ID: {hdr(text,'Call-ID')}",
                        f"CSeq: {hdr(text,'CSeq')}", "Content-Length: 0", "", ""]
                self.transport.sendto("\r\n".join(resp).encode(), addr)


async def do_transient_answer(t0: float) -> None:
    sess, intercom, creds = STATE["sess"], STATE["intercom"], STATE["creds"]
    mode = "С push-параметрами (RFC 8599)" if USE_PUSH_PARAMS else "БЕЗ push-параметров"
    log(f"⚡ CALL_INCOMING → transient register [{mode}]")
    transport, proto = await LOOP.create_datagram_endpoint(
        lambda: TransientSip(creds, STATE["local_ip"], sess.user_agent, t0),
        local_addr=("0.0.0.0", SIP_LOCAL_PORT), remote_addr=(STATE["ip"], SIP_PORT),
    )
    try:
        await asyncio.sleep(REG_LISTEN_SEC)
        if proto.invite_mono is None:
            log(f"  ❌ INVITE НЕ пришёл за {REG_LISTEN_SEC}с после transient-register [{mode}].")
            log("     → Kazoo НЕ доставляет вызов на позднюю регистрацию в этом режиме.")
    finally:
        transport.close()
        log("  transient-сокет закрыт (регистрация снята).")


def on_push(notification, persistent_id, *_):
    t0 = time.monotonic()
    data = (notification or {}).get("data") or {}
    if (data.get("PushType") or data.get("google.c.a.m_l")) != "CALL_INCOMING":
        return
    cid = data.get("Call-ID") or ""
    if cid in _handled:
        return
    _handled.add(cid)
    ac = str(data.get("AccessControlId") or "")
    if ac and ac != str(STATE["intercom"]["accessControlId"]):
        log(f"🔕 CALL_INCOMING для другого домофона (ac={ac}) — пропуск")
        return
    log("🔔🔔🔔 CALL_INCOMING получен по FCM → поднимаю SIP по пушу")
    asyncio.run_coroutine_threadsafe(do_transient_answer(t0), LOOP)


async def main() -> None:
    global LOOP
    LOOP = asyncio.get_running_loop()
    from firebase_messaging import FcmPushClient, FcmRegisterConfig

    sess = common.Session.load("session.json")
    intercoms = sess.intercoms or []
    ac_env = os.environ.get("INTERCOM_AC")
    intercom = next((ic for ic in intercoms if str(ic["accessControlId"]) == ac_env), intercoms[0])

    with open(FB_CFG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    log(f"=== PUSH-ANSWER probe: {intercom['name']} (ac={intercom['accessControlId']}) "
        f"push_params={'ON' if USE_PUSH_PARAMS else 'OFF'} listen={REG_LISTEN_SEC}s ===")

    # SIP-креды минтим ЗАРАНЕЕ → по пушу только REGISTER.
    creds = await mint_sip(sess, intercom)
    ip = socket.gethostbyname(creds["realm"])
    local_ip = outbound_ip(ip)
    STATE.update(sess=sess, intercom=intercom, creds=creds, ip=ip, local_ip=local_ip, sender=cfg["messaging_sender_id"])
    log(f"SIP-креды заминчены заранее (realm={creds['realm']}, local_ip={local_ip}). SIP НЕ зарегистрирован.")

    fcm_config = FcmRegisterConfig(
        project_id=cfg["project_id"], app_id=cfg["app_id"], api_key=cfg["api_key"],
        messaging_sender_id=cfg["messaging_sender_id"], bundle_id=cfg.get("bundle_id"),
    )
    client = FcmPushClient(on_push, fcm_config, _load_creds(), _save_creds)
    fcm_token = await client.checkin_or_register()
    STATE["fcm_token"] = fcm_token
    log(f"FCM token получен (…{fcm_token[-8:]})")
    await bind_token(sess, fcm_token)
    await client.start()
    log("→ FCM listener запущен. SIP поднимется ТОЛЬКО по пушу. ЗВОНИ В ДОМОФОН (с телефона НЕ отвечай).")
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await client.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
