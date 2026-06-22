"""Push-to-talk: ИСХОДЯЩИЙ вызов на домофон (говорить без входящего звонка).

Мы выступаем как UAC (инициатор): REGISTER → INVITE на sip:000@{realm}
(SIP-идентичность домофонной панели, которую видели в From входящего INVITE)
→ Digest-auth → на 200 OK шлём ACK + тон на уличный динамик → через N c BYE.

Отдельный installationId/SIP-login (-ptt) и порт 5067 — не конфликтует с
медиа-пробой. Это разведка: примет ли панель входящий вызов и пойдёт ли звук
на динамик БЕЗ инициации звонка с улицы.

Запуск:  PTT_TARGET=000 PTT_SEC=15 python probe_ptt.py
Лог:     logs/ptt.log
"""

from __future__ import annotations

import asyncio
import audioop
import datetime as dt
import math
import os
import random
import re
import socket
import struct
import uuid

import aiohttp

import common
from probe_sip import digest_response, hdr, outbound_ip, SIP_PORT
from probe_sip_media import stun_discover

LOG_PATH = "logs/ptt.log"
RTP_PORT = 40018
SIP_LPORT = 5067
TONE_HZ = 425


def _ts():
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def log(line):
    os.makedirs("logs", exist_ok=True)
    msg = f"{_ts()}  {line}"
    print(msg, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def tone(pt):
    rate = 8000
    pcm = bytearray()
    for i in range(rate * 30):
        pcm += struct.pack("<h", int(0.6 * 32767 * math.sin(2 * math.pi * TONE_HZ * i / rate)))
    return audioop.lin2ulaw(bytes(pcm), 2) if pt == 0 else audioop.lin2alaw(bytes(pcm), 2)


def parse_sdp(body):
    info = {"conn_ip": None, "audio_port": None, "pt": None}
    for ln in body.replace("\r\n", "\n").split("\n"):
        if ln.startswith("c=IN IP4 "):
            info["conn_ip"] = ln.split()[2]
        elif ln.startswith("m=audio"):
            p = ln.split()
            info["audio_port"] = int(p[1])
            info["pt"] = int(p[3])
    return info


class PttUAC(asyncio.DatagramProtocol):
    def __init__(self, creds, local_ip, ua, media_ip, media_port, rtp_sock, target, ptt_sec):
        self.login, self.password, self.realm = creds["login"], creds["password"], creds["realm"]
        self.local_ip, self.ua = local_ip, ua
        self.media_ip, self.media_port, self.rtp_sock = media_ip, media_port, rtp_sock
        self.target = target          # кого зовём (000)
        self.ptt_sec = ptt_sec
        self.transport = None
        self._lport = 0
        self.from_tag = uuid.uuid4().hex[:8]
        self.call_id = f"{uuid.uuid4()}@{local_ip}"
        self.cseq = 0
        self.registered = False
        self.invited = False
        self.call_active = False

    def connection_made(self, transport):
        self.transport = transport
        self._lport = transport.get_extra_info("sockname")[1]
        self.send_register()

    # ---------- REGISTER ----------
    def send_register(self, auth=None):
        self.cseq += 1
        b = f"z9hG4bK{random.randint(0,1<<31)}"
        uri = f"sip:{self.realm}"
        L = [f"REGISTER {uri} SIP/2.0",
             f"Via: SIP/2.0/UDP {self.local_ip}:{self._lport};branch={b};rport",
             "Max-Forwards: 70",
             f"From: <sip:{self.login}@{self.realm}>;tag={self.from_tag}",
             f"To: <sip:{self.login}@{self.realm}>",
             f"Call-ID: reg-{self.call_id}", f"CSeq: {self.cseq} REGISTER",
             f"Contact: <sip:{self.login}@{self.local_ip}:{self._lport};transport=udp>",
             "Expires: 120", f"User-Agent: {self.ua}"]
        if auth:
            L.append(f"Authorization: {auth}")
        L += ["Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(L).encode())

    # ---------- INVITE ----------
    def send_invite(self, auth=None):
        self.cseq += 1
        self.invite_cseq = self.cseq
        self.invite_branch = f"z9hG4bK{random.randint(0,1<<31)}"
        ruri = f"sip:{self.target}@{self.realm}"
        sdp = ("v=0\r\n"
               f"o=- {random.randint(1,1<<31)} 1 IN IP4 {self.media_ip}\r\n"
               "s=ptt\r\n"
               f"c=IN IP4 {self.media_ip}\r\n"
               "t=0 0\r\n"
               f"m=audio {self.media_port} RTP/AVP 8 0 101\r\n"
               "a=rtpmap:8 PCMA/8000\r\na=rtpmap:0 PCMU/8000\r\n"
               "a=rtpmap:101 telephone-event/8000\r\na=sendrecv\r\n")
        L = [f"INVITE {ruri} SIP/2.0",
             f"Via: SIP/2.0/UDP {self.local_ip}:{self._lport};branch={self.invite_branch};rport",
             "Max-Forwards: 70",
             f"From: <sip:{self.login}@{self.realm}>;tag={self.from_tag}",
             f"To: <{ruri}>", f"Call-ID: {self.call_id}",
             f"CSeq: {self.invite_cseq} INVITE",
             f"Contact: <sip:{self.login}@{self.local_ip}:{self._lport};transport=udp>",
             f"User-Agent: {self.ua}", "Content-Type: application/sdp",
             f"Content-Length: {len(sdp.encode())}"]
        if auth:
            L.append(f"Authorization: {auth}")
        L += ["", sdp]
        msg = "\r\n".join(L)
        self.transport.sendto(msg.encode())
        log(f"  → INVITE {ruri} (CSeq {self.invite_cseq})")

    def _digest(self, text, method, uri):
        wa = hdr(text, "WWW-Authenticate") or hdr(text, "Proxy-Authenticate") or ""
        nonce = re.search(r'nonce="([^"]+)"', wa)
        realm_m = re.search(r'realm="([^"]+)"', wa)
        if not nonce:
            return None
        realm = realm_m.group(1) if realm_m else self.realm
        resp = digest_response(self.login, self.password, realm, nonce.group(1), method, uri)
        return (f'Digest username="{self.login}", realm="{realm}", nonce="{nonce.group(1)}", '
                f'uri="{uri}", response="{resp}", algorithm=MD5')

    def datagram_received(self, data, addr):
        text = data.decode(errors="replace")
        first = text.split("\r\n", 1)[0]
        cseq = hdr(text, "CSeq") or ""
        if not text.startswith("SIP/2.0"):
            method = first.split(" ", 1)[0]
            if method in ("BYE", "CANCEL"):
                log(f"  входящий {method} — панель завершила")
                self.call_active = False
                self._respond(text, addr, "200 OK")
            return
        code = first.split(" ")[1]
        if "REGISTER" in cseq:
            if code in ("401", "407"):
                a = self._digest(text, "REGISTER", f"sip:{self.realm}")
                if a:
                    self.send_register(a)
            elif code == "200" and not self.registered:
                self.registered = True
                log(f"✅ зарегистрирован {self.login}@{self.realm} → шлю INVITE на {self.target}")
                self.send_invite()
        elif "INVITE" in cseq:
            ruri = f"sip:{self.target}@{self.realm}"
            if code in ("401", "407"):
                a = self._digest(text, "INVITE", ruri)
                if a:
                    self.send_invite(a)
            elif code.startswith("1"):
                log(f"  INVITE → {first.split(' ',1)[1]} (провизорный)")
            elif code == "200":
                if self.call_active:
                    return
                self.call_active = True
                log(f"  🤝 200 OK на INVITE — панель ПРИНЯЛА вызов!")
                head, _, body = text.partition("\r\n\r\n")
                self._on_200(text, body, addr)
            else:
                log(f"  ❌ INVITE отклонён: {first.split(' ',1)[1]}")
                self.call_active = False

    def _on_200(self, text, body, addr):
        # сохранить диалог для ACK/BYE
        self.to_line = hdr(text, "To") or f"<sip:{self.target}@{self.realm}>"
        m = re.search(r"<([^>]+)>", hdr(text, "Contact") or "")
        self.remote_target = m.group(1) if m else f"sip:{self.target}@{self.realm}"
        self.route = []
        for ln in (text.partition("\r\n\r\n")[0]).split("\r\n"):
            if ln.split(":", 1)[0].strip().lower() == "record-route":
                self.route.append(ln.split(":", 1)[1].strip())
        self.d_addr = addr
        self.send_ack()
        sdp = parse_sdp(body)
        log(f"  SDP панели: {sdp}")
        if sdp["conn_ip"] and sdp["audio_port"]:
            asyncio.ensure_future(self._rtp(sdp["conn_ip"], sdp["audio_port"], sdp["pt"] or 0))
        asyncio.ensure_future(self._hangup_after())

    def send_ack(self):
        b = f"z9hG4bK{random.randint(0,1<<31)}"
        route = [f"Route: {r}" for r in self.route]
        L = [f"ACK {self.remote_target} SIP/2.0",
             f"Via: SIP/2.0/UDP {self.local_ip}:{self._lport};branch={b};rport",
             *route, "Max-Forwards: 70",
             f"From: <sip:{self.login}@{self.realm}>;tag={self.from_tag}",
             f"To: {self.to_line}", f"Call-ID: {self.call_id}",
             f"CSeq: {self.invite_cseq} ACK", "Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(L).encode(), self.d_addr)
        log("  → ACK (вызов установлен)")

    async def _rtp(self, ip, port, pt):
        sock = self.rtp_sock
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        frames = [t for t in (lambda d: [d[i:i+160] for i in range(0, len(d)-160, 160)])(tone(pt))]
        log(f"  → шлю тон {TONE_HZ}Гц на динамик {ip}:{port}. СЛУШАЙ У ДВЕРИ.")
        recv = {"n": 0, "src": None}

        async def rx():
            while True:
                try:
                    d, s = await loop.sock_recvfrom(sock, 2048)
                    recv["n"] += 1
                    recv["src"] = s
                except Exception:
                    await asyncio.sleep(0.05)
        rt = asyncio.ensure_future(rx())
        ssrc, seq, tsv = random.randint(0, 1 << 31), 0, 0
        for i in range(len(frames)):
            if not self.call_active:
                break
            h = struct.pack("!BBHII", 0x80, pt | (0x80 if i == 0 else 0), seq & 0xFFFF, tsv & 0xFFFFFFFF, ssrc)
            try:
                sock.sendto(h + frames[i], (ip, port))
            except Exception:
                pass
            seq += 1
            tsv += 160
            if i % 50 == 49:
                log(f"  RTP[+{(i+1)//50}s]: входящих={recv['n']} src={recv['src']}")
            await asyncio.sleep(0.02)
        rt.cancel()
        log(f"  ИТОГ RTP: downlink={recv['n']} пакетов от {recv['src']}")

    async def _hangup_after(self):
        await asyncio.sleep(self.ptt_sec)
        self.send_bye()

    def send_bye(self):
        if not self.call_active:
            return
        self.call_active = False
        self.cseq += 1
        b = f"z9hG4bK{random.randint(0,1<<31)}"
        route = [f"Route: {r}" for r in self.route]
        L = [f"BYE {self.remote_target} SIP/2.0",
             f"Via: SIP/2.0/UDP {self.local_ip}:{self._lport};branch={b};rport",
             *route, "Max-Forwards: 70",
             f"From: <sip:{self.login}@{self.realm}>;tag={self.from_tag}",
             f"To: {self.to_line}", f"Call-ID: {self.call_id}",
             f"CSeq: {self.cseq} BYE", "Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(L).encode(), self.d_addr)
        log("  📴 BYE — push-to-talk завершён")

    def _respond(self, req, addr, status):
        L = ["SIP/2.0 " + status, f"Via: {hdr(req,'Via')}", f"From: {hdr(req,'From')}",
             f"To: {hdr(req,'To')}", f"Call-ID: {hdr(req,'Call-ID')}",
             f"CSeq: {hdr(req,'CSeq')}", "Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(L).encode(), addr)


async def main():
    sess = common.Session.load("session.json")
    intercoms = sess.intercoms or []
    ac_env = os.environ.get("INTERCOM_AC")
    idx = next((i for i, ic in enumerate(intercoms) if ic["accessControlId"] == ac_env), 0) if ac_env else 0
    intercom = intercoms[idx]
    target = os.environ.get("PTT_TARGET", "000")
    ptt_sec = int(os.environ.get("PTT_SEC", "15"))
    install_id = sess.install_id + "-ptt"
    log(f"=== PUSH-TO-TALK: {intercom['name']} (ac={intercom['accessControlId']}) target={target} ===")

    async with aiohttp.ClientSession() as s:
        api = common.Api(s, sess.user_agent, access_token=sess.access_token, operator=sess.operator_id)
        r = await api.post(
            f"/rest/v1/places/{intercom['placeId']}/accesscontrols/{intercom['accessControlId']}/sipdevices",
            {"installationId": install_id})
        creds = (await r.json())["data"]
    ip = socket.gethostbyname(creds["realm"])
    local_ip = outbound_ip(ip)
    rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtp.bind(("0.0.0.0", RTP_PORT))
    stun = stun_discover(rtp)
    media_ip, media_port = stun if stun else (local_ip, RTP_PORT)
    log(f"realm={creds['realm']} login={creds['login']} media={media_ip}:{media_port}")

    loop = asyncio.get_running_loop()
    transport, proto = await loop.create_datagram_endpoint(
        lambda: PttUAC(creds, local_ip, sess.user_agent, media_ip, media_port, rtp, target, ptt_sec),
        local_addr=("0.0.0.0", SIP_LPORT), remote_addr=(ip, SIP_PORT))
    try:
        await asyncio.sleep(ptt_sec + 15)   # дожить до конца push-to-talk
    finally:
        transport.close()
    log("=== PTT probe end ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
