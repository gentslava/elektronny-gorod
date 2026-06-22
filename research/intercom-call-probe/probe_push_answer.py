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
import struct
import time
import uuid

import aiohttp

import common
from probe_sip import SIP_PORT, digest_response, hdr, outbound_ip
from probe_sip_media import RTP_LOCAL_PORT, load_track_frames, parse_sdp, stun_discover

LOG_PATH = "logs/push_answer.log"
CRED_FILE = "fcm_credentials.json"
FB_CFG_FILE = "firebase_config.json"
SIP_LOCAL_PORT = 5068
REG_LISTEN_SEC = int(os.environ.get("REG_LISTEN_SEC", "20"))
USE_PUSH_PARAMS = os.environ.get("PUSH_PARAMS") == "1"
PREBIND = os.environ.get("PREBIND") == "1"  # предв. RFC 8599 push-binding до вызова
ANSWER = os.environ.get("ANSWER") == "1"  # на INVITE → 200 OK + аудио (имитация ответа)
ANSWER_DELAY = float(os.environ.get("ANSWER_DELAY", "3"))  # сек «раздумий» до ответа
TALK_SEC = float(os.environ.get("TALK_SEC", "0"))  # сек разговора, затем сами BYE (0=ждём сервер)
RE_REG = os.environ.get("RE_REG") == "1"  # re-register прямо перед 200 OK (гипотеза)
RING_KEEPALIVE = os.environ.get("RING_KEEPALIVE", "1") == "1"  # periodic 180 во время раздумий
EARLY_MEDIA = os.environ.get("EARLY_MEDIA") == "1"  # 183 Session Progress + SDP + ранний RTP
MIRROR_APP = os.environ.get("MIRROR_APP") == "1"  # зеркало приложения: Expires=30, без STUN, проприет. push
RTP_EARLY = os.environ.get("RTP_EARLY") == "1"  # ранний RTP (тишина) с INVITE — активирует latching до ответа

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
    def __init__(self, creds: dict, local_ip: str, ua: str, t0: float,
                 on_registered=None, expires: int = 120):
        self.login, self.password, self.realm = creds["login"], creds["password"], creds["realm"]
        self.local_ip, self.ua, self.t0 = local_ip, ua, t0
        self.on_registered = on_registered  # future/cb — уведомить об успешном REGISTER
        self.expires = expires
        self.transport = None
        self.call_id = f"{uuid.uuid4()}@{local_ip}"
        self.cseq = 0
        self.from_tag = uuid.uuid4().hex[:8]
        self._lport = 0
        self.registered_mono: float | None = None
        self.invite_mono: float | None = None
        # media (режим ANSWER): состояние диалога для 200 OK + RTP + BYE
        self.call_active = False
        self._rtp_stop = False  # ранний RTP умер (вызов завершён до ответа)
        self.cseq_dlg = 0
        self.d_callid = self.d_remote = self.d_local = self.d_target = None
        self.d_route: list[str] = []
        self.d_addr = None

    def connection_made(self, transport):
        self.transport = transport
        self._lport = transport.get_extra_info("sockname")[1]
        log("  → transient REGISTER отправляю…")
        self.send_register()

    def _contact(self) -> str:
        base = f"sip:{self.login}@{self.local_ip}:{self._lport};transport=udp"
        if MIRROR_APP and STATE.get("fcm_token"):
            # проприетарный формат приложения (реверс Linphone): app-id;pn-type;pn-tok
            return f"<{base};app-id=2;pn-type=google;pn-tok={STATE['fcm_token']}>"
        if USE_PUSH_PARAMS and STATE.get("fcm_token"):
            # RFC 8599 push-параметры
            return f"<{base}>;pn-provider=fcm;pn-param={STATE.get('sender', '')};pn-prid={STATE['fcm_token']}"
        return f"<{base}>"

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
            f"Expires: {self.expires}",
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
        if ANSWER and not text.startswith("SIP/2.0"):
            mth = first.split(" ", 1)[0]
            if mth not in ("OPTIONS", "NOTIFY"):  # не шумим keep-alive
                ts = (time.monotonic() - self.invite_mono) if self.invite_mono else 0.0
                log(f"  «IN[+{ts:.1f}с]: {first[:70]}")
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
                tag = " [push-binding]" if USE_PUSH_PARAMS else ""
                log(f"  ✅ REGISTERED (t0→register = {self.registered_mono - self.t0:.3f}с){tag}. Жду INVITE…")
                if self.on_registered is not None and not self.on_registered.done():
                    self.on_registered.set_result(True)
        else:
            method = first.split(" ", 1)[0]
            if method == "INVITE":
                # 180 Ringing на каждый INVITE/ретрансмит (наш tag стабилен = from_tag).
                via = hdr(text, "Via") or ""
                to = hdr(text, "To") or ""
                to_r = to if ";tag=" in to else f"{to};tag={self.from_tag}"
                resp = ["SIP/2.0 180 Ringing", f"Via: {via}", f"From: {hdr(text,'From')}",
                        f"To: {to_r}", f"Call-ID: {hdr(text,'Call-ID')}", f"CSeq: {hdr(text,'CSeq')}",
                        "Content-Length: 0", "", ""]
                self.transport.sendto("\r\n".join(resp).encode(), addr)
                if self.invite_mono is None:
                    self.invite_mono = time.monotonic()
                    d_reg = (self.invite_mono - self.registered_mono) if self.registered_mono else float("nan")
                    log("  🔔 INVITE ПРИШЁЛ на transient-register!")
                    log(f"     t0(CALL_INCOMING)→INVITE = {self.invite_mono - self.t0:.3f}с; register→INVITE = {d_reg:.3f}с")
                    if ANSWER:
                        if EARLY_MEDIA:
                            self._early_media(text, addr)  # 183 + SDP + RTP сразу — резерв media
                        elif RTP_EARLY:
                            sdp, audio, pt = self._parse_audio(text)
                            if audio:
                                log("  🔇 ранний RTP (тишина) с INVITE — активирую latching до ответа")
                                asyncio.ensure_future(
                                    self._rtp(sdp["conn_ip"], audio["port"], pt, early=True))
                        log(f"  📲 имитация: «думаем» {ANSWER_DELAY:.0f}с, затем 200 OK…")
                        asyncio.ensure_future(self._delayed_answer(text, addr))
            elif method in ("OPTIONS", "NOTIFY", "INFO"):
                via = hdr(text, "Via") or ""
                resp = ["SIP/2.0 200 OK", f"Via: {via}", f"From: {hdr(text,'From')}",
                        f"To: {hdr(text,'To')}", f"Call-ID: {hdr(text,'Call-ID')}",
                        f"CSeq: {hdr(text,'CSeq')}", "Content-Length: 0", "", ""]
                self.transport.sendto("\r\n".join(resp).encode(), addr)
            elif method in ("BYE", "CANCEL"):
                self.call_active = False  # стоп аудио
                self._rtp_stop = True  # остановить ранний RTP, если шёл до ответа
                reason = hdr(text, "Reason") or hdr(text, "X-KAZOO-DISPOSITION") or ""
                dt_since_inv = (time.monotonic() - self.invite_mono) if self.invite_mono else float("nan")
                via = hdr(text, "Via") or ""
                resp = ["SIP/2.0 200 OK", f"Via: {via}", f"From: {hdr(text,'From')}",
                        f"To: {hdr(text,'To')}", f"Call-ID: {hdr(text,'Call-ID')}",
                        f"CSeq: {hdr(text,'CSeq')}", "Content-Length: 0", "", ""]
                self.transport.sendto("\r\n".join(resp).encode(), addr)
                rtxt = f" (Reason: {reason})" if reason else ""
                log(f"  📴 {method} от сервера{rtxt} — вызов завершён (через {dt_since_inv:.1f}с после INVITE)")
                for hl in text.split("\r\n"):  # дамп диагностических заголовков
                    key = hl.split(":", 1)[0].lower() if ":" in hl else ""
                    if key in ("reason", "x-kazoo-disposition", "warning", "user-agent", "subject"):
                        log(f"     {method}| {hl[:100]}")

    def _send_ringing(self, req, addr):
        """180 Ringing (с Contact) — provisional-ответ, держит early-dialog."""
        via = hdr(req, "Via") or ""
        to = hdr(req, "To") or ""
        to_r = to if ";tag=" in to else f"{to};tag={self.from_tag}"
        resp = ["SIP/2.0 180 Ringing", f"Via: {via}", f"From: {hdr(req, 'From')}",
                f"To: {to_r}", f"Call-ID: {hdr(req, 'Call-ID')}", f"CSeq: {hdr(req, 'CSeq')}",
                f"Contact: <sip:{self.login}@{self.local_ip}:{self._lport};transport=udp>",
                "Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(resp).encode(), addr)

    def _parse_audio(self, req):
        sdp = parse_sdp(req.partition("\r\n\r\n")[2])
        audio = next((m for m in sdp["media"] if m["type"] == "audio"), None)
        return (sdp, audio, int(audio["fmts"][0])) if audio else (None, None, None)

    def _early_media(self, req, addr):
        """183 Session Progress + SDP + ранний RTP — резервируем media-путь на FreeSWITCH."""
        sdp, audio, pt = self._parse_audio(req)
        if not audio:
            return
        log("  🎵 EARLY MEDIA: 183 Session Progress + SDP + старт RTP (резервируем media)")
        self._answer(req, addr, sdp, audio, pt, status="183 Session Progress")
        asyncio.ensure_future(self._rtp(sdp["conn_ip"], audio["port"], pt))

    async def _delayed_answer(self, req: str, addr) -> None:
        """Имитация раздумий: держим вызов, затем 200 OK (поднимаем трубку)."""
        slept = 0.0
        while slept < ANSWER_DELAY:
            step = min(1.0, ANSWER_DELAY - slept)
            await asyncio.sleep(step)
            slept += step
            if RING_KEEPALIVE and not EARLY_MEDIA and not self.call_active:
                self._send_ringing(req, addr)  # держим early-dialog «alive»
        if RE_REG:
            log("  🔄 re-register перед ответом (гипотеза: обновить binding)")
            self.send_register()
            await asyncio.sleep(0.4)
        sdp, audio, pt = self._parse_audio(req)
        if not audio:
            log("  ⚠️ нет audio в SDP — ответ невозможен")
            return
        log(f"  ✅ ИМИТАЦИЯ ОТВЕТА (через {ANSWER_DELAY:.0f}с, early={EARLY_MEDIA}, "
            f"ring_ka={RING_KEEPALIVE}, re_reg={RE_REG}) → 200 OK")
        self._answer(req, addr, sdp, audio, pt, status="200 OK")
        if not EARLY_MEDIA and not RTP_EARLY:
            await self._rtp(sdp["conn_ip"], audio["port"], pt)
        # в EARLY_MEDIA/RTP_EARLY RTP уже идёт — 200 OK только «поднимает трубку»
        # (call_active=True переключает ранний RTP с тишины на трек)

    def _answer(self, req, addr, sdp, audio, pt, status="200 OK"):
        """status (200 OK / 183 Session Progress) с G.711 SDP; эхо Via/Record-Route + dialog-state."""
        import re
        head = req.partition("\r\n\r\n")[0]
        compact = {"v": "via", "f": "from", "t": "to", "i": "call-id", "m": "contact"}
        dlg_lines = []
        my_tag = self.from_tag
        self.d_route = []
        for ln in head.split("\r\n")[1:]:
            name = ln.split(":", 1)[0].strip().lower()
            h = compact.get(name, name)
            val = ln.split(":", 1)[1].strip() if ":" in ln else ""
            if h == "to" and ";tag=" not in ln:
                ln = f"{ln};tag={my_tag}"
                val = f"{val};tag={my_tag}"
            if h in ("via", "record-route", "from", "to", "call-id", "cseq"):
                dlg_lines.append(ln)
            if h == "from":
                self.d_remote = val
            elif h == "to":
                self.d_local = val
            elif h == "call-id":
                self.d_callid = val
            elif h == "record-route":
                self.d_route.append(val)
            elif h == "contact":
                m = re.search(r"<([^>]+)>", ln)
                self.d_target = m.group(1) if m else None
        self.d_addr = addr
        self.call_active = True
        media_ip, media_port = STATE["media_ip"], STATE["media_port"]
        codec = sdp["rtpmap"].get(str(pt), "PCMU/8000" if pt == 0 else "PCMA/8000")
        sdp_body = (
            "v=0\r\n"
            f"o=- {random.randint(1, 1 << 31)} 1 IN IP4 {media_ip}\r\n"
            "s=app\r\n"
            f"c=IN IP4 {media_ip}\r\n"
            "t=0 0\r\n"
            f"m=audio {media_port} RTP/AVP {pt}\r\n"
            f"a=rtpmap:{pt} {codec}\r\n"
            "a=sendrecv\r\n"
        )
        lines = [
            f"SIP/2.0 {status}", *dlg_lines,
            f"Contact: <sip:{self.login}@{self.local_ip}:{self._lport};transport=udp>",
            f"User-Agent: {self.ua}", "Allow: INVITE, ACK, BYE, CANCEL, OPTIONS",
            "Content-Type: application/sdp", f"Content-Length: {len(sdp_body.encode())}",
            "", sdp_body,
        ]
        self.transport.sendto("\r\n".join(lines).encode(), addr)
        log(f"  → {status} + SDP (G.711) отправлен")

    async def _rtp(self, door_ip, door_port, pt, early=False):
        """RTP-сессия. early=True → тишина с момента INVITE (активирует latching),
        после ответа (call_active) → аудио-трек. Считает downlink."""
        if not door_ip:
            return
        sock = STATE["rtp_sock"]
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        frames = load_track_frames(pt) or []
        silence = bytes([0xFF if pt == 0 else 0xD5] * 160)  # G.711 тишина (µ-law/A-law)
        log(f"  → RTP старт на {door_ip}:{door_port} ({'early-тишина→трек' if early else 'трек'})")
        ssrc = random.randint(0, 1 << 31)
        seq = tsv = 0
        recv = {"count": 0}

        async def receiver():
            while True:
                try:
                    await loop.sock_recvfrom(sock, 2048)
                    recv["count"] += 1
                except Exception:
                    await asyncio.sleep(0.05)

        rtask = asyncio.ensure_future(receiver())
        talk_frames = int(TALK_SEC / 0.02) if TALK_SEC else 0
        i = 0
        talk_i = 0
        logged = False
        while True:
            answered = self.call_active
            if not answered and (self._rtp_stop or not early):
                break  # вызов умер до ответа, или это не early-режим
            if early and not answered and not logged:
                pass
            if answered and not logged:
                log("  🎵 ОТВЕТ — переключаю RTP на аудио-трек. СЛУШАЙ У ДВЕРИ.")
                logged = True
            frame = frames[talk_i % len(frames)] if (answered and frames) else silence
            hb = struct.pack("!BBHII", 0x80, pt | (0x80 if i == 0 else 0),
                             seq & 0xFFFF, tsv & 0xFFFFFFFF, ssrc)
            try:
                sock.sendto(hb + frame, (door_ip, door_port))
            except Exception:
                pass
            seq += 1
            tsv += 160
            i += 1
            if answered:
                talk_i += 1
                if talk_frames and talk_i >= talk_frames:
                    log(f"  ⏱ {TALK_SEC:.0f}с разговора — «кладём трубку»")
                    break
            if i % 50 == 49:
                tag = "" if answered else " (early-тишина)"
                log(f"  RTP[+{(i + 1) // 50}s]: downlink={recv['count']}{tag}")
            await asyncio.sleep(0.02)
        rtask.cancel()
        log(f"  ИТОГ: downlink {recv['count']} пакетов получено. Завершаю BYE.")
        self.send_bye()

    def send_bye(self):
        """In-dialog BYE — глушит сессию."""
        if not (self.d_callid and self.d_target):
            return
        self.cseq_dlg += 1
        branch = f"z9hG4bK{random.randint(0, 1 << 31)}"
        route = [f"Route: {rr}" for rr in self.d_route]
        lines = [
            f"BYE {self.d_target} SIP/2.0",
            f"Via: SIP/2.0/UDP {self.local_ip}:{self._lport};branch={branch};rport",
            *route, "Max-Forwards: 70", f"From: {self.d_local}", f"To: {self.d_remote}",
            f"Call-ID: {self.d_callid}", f"CSeq: {self.cseq_dlg} BYE",
            f"User-Agent: {self.ua}", "Content-Length: 0", "", "",
        ]
        self.transport.sendto("\r\n".join(lines).encode(), self.d_addr)
        self.call_active = False
        log("  📴 BYE отправлен — разговор завершён")


async def do_transient_answer(t0: float) -> None:
    sess, intercom, creds = STATE["sess"], STATE["intercom"], STATE["creds"]
    mode = "С push-параметрами (RFC 8599)" if USE_PUSH_PARAMS else "БЕЗ push-параметров"
    log(f"⚡ CALL_INCOMING → transient register [{mode}]")
    transport, proto = await LOOP.create_datagram_endpoint(
        lambda: TransientSip(creds, STATE["local_ip"], sess.user_agent, t0,
                             expires=(30 if MIRROR_APP else 120)),
        local_addr=("0.0.0.0", SIP_LOCAL_PORT), remote_addr=(STATE["ip"], SIP_PORT),
    )
    listen = (ANSWER_DELAY + 90) if ANSWER else REG_LISTEN_SEC  # в ANSWER ждём весь разговор
    try:
        await asyncio.sleep(listen)
        if proto.invite_mono is None:
            log(f"  ❌ INVITE НЕ пришёл за {listen:.0f}с после transient-register [{mode}].")
            log("     → Kazoo НЕ доставляет вызов на позднюю регистрацию в этом режиме.")
    finally:
        if proto.call_active:
            proto.send_bye()
        transport.close()
        log("  transient-сокет закрыт (регистрация снята).")


async def initial_prebind() -> None:
    """Предв. SIP push-binding (RFC 8599, модель приложения): REGISTER с pn-параметрами
    (длинный Expires), затем закрываем сокет — симулируем спящее push-устройство. Если
    Kazoo хранит push-binding, при вызове он разбудит нас пушем и догонит INVITE."""
    fut = LOOP.create_future()
    transport, _ = await LOOP.create_datagram_endpoint(
        lambda: TransientSip(STATE["creds"], STATE["local_ip"], STATE["sess"].user_agent,
                             time.monotonic(), on_registered=fut, expires=(30 if MIRROR_APP else 3600)),
        local_addr=("0.0.0.0", SIP_LOCAL_PORT), remote_addr=(STATE["ip"], SIP_PORT),
    )
    try:
        await asyncio.wait_for(fut, timeout=10)
        log("  🔗 предв. push-binding установлен (REGISTER с pn-параметрами, Expires=3600).")
    except asyncio.TimeoutError:
        log("  ⚠️ предв. binding: 200 OK не получен за 10с")
    finally:
        await asyncio.sleep(0.3)
        transport.close()
        log("  💤 сокет закрыт — «спим», ждём пуш (binding на Kazoo должен жить).")


def on_push(notification, persistent_id, *_):
    t0 = time.monotonic()
    data = (notification or {}).get("data") or {}
    if (data.get("PushType") or data.get("google.c.a.m_l")) != "CALL_INCOMING":
        return
    # FCM до-доставляет старые пуши при подключении — игнорируем (иначе ANSWER-сессия
    # повиснет на несуществующем вызове). Свежий звонок имеет CallStarted ~now.
    started = data.get("CallStarted")
    if started:
        try:
            age = (dt.datetime.now(dt.timezone.utc)
                   - dt.datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()
            if age > 30:
                log(f"🕰 старый CALL_INCOMING (age={age:.0f}с) — пропуск (re-delivery)")
                return
        except Exception:  # noqa: BLE001
            pass
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

    if ANSWER:
        # RTP-сокет + STUN заранее (для 200 OK SDP-answer и uplink-аудио).
        rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rtp_sock.bind(("0.0.0.0", RTP_LOCAL_PORT))
        if MIRROR_APP:
            # приложение без STUN — локальный адрес в SDP, полагаемся на FreeSWITCH latching
            media_ip, media_port = local_ip, RTP_LOCAL_PORT
            log(f"ANSWER mode [MIRROR_APP]: БЕЗ STUN, локальный RTP {media_ip}:{media_port} (latching)")
        else:
            stun = stun_discover(rtp_sock)
            if stun:
                media_ip, media_port = stun
                log(f"ANSWER mode: RTP публичный адрес (STUN) {media_ip}:{media_port}")
            else:
                media_ip, media_port = local_ip, RTP_LOCAL_PORT
                log(f"ANSWER mode: STUN не ответил — fallback {media_ip}:{media_port}")
        STATE.update(rtp_sock=rtp_sock, media_ip=media_ip, media_port=media_port)
        log(f"ANSWER mode: ответ через {ANSWER_DELAY:.0f}с после INVITE → 200 OK + аудио-трек.")

    fcm_config = FcmRegisterConfig(
        project_id=cfg["project_id"], app_id=cfg["app_id"], api_key=cfg["api_key"],
        messaging_sender_id=cfg["messaging_sender_id"], bundle_id=cfg.get("bundle_id"),
    )
    client = FcmPushClient(on_push, fcm_config, _load_creds(), _save_creds)
    fcm_token = await client.checkin_or_register()
    STATE["fcm_token"] = fcm_token
    log(f"FCM token получен (…{fcm_token[-8:]})")
    await bind_token(sess, fcm_token)
    if PREBIND:
        log("режим PREBIND (схема приложения): ставлю RFC 8599 push-binding ДО вызова, затем «засыпаю»")
        await initial_prebind()
    await client.start()
    log("→ FCM listener запущен. SIP поднимется по пушу"
        + (" (с предв. push-binding)" if PREBIND else "")
        + ". ЗВОНИ В ДОМОФОН (с телефона НЕ отвечай).")
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
