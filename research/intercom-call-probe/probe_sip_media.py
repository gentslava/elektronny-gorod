"""Медиа-разведка SIP: поднять вызов и размотать аудио-путь (SDP + RTP).

За ОДИН звонок:
  1) логирует полный INVITE + SDP-offer домофона (кодеки, media-линии, видео?);
  2) отвечает 200 OK с SDP-answer;
  3) шлёт RTP-тишину на media-эндпоинт домофона (открыть symmetric/NAT путь)
     и логирует входящий RTP (кодек/PT, кол-во пакетов, источник).

Регистрируется с ОТДЕЛЬНЫМ installationId → независимо от probe_sip контейнеров.
Цель — понять, как идёт двусторонний звук (для push-to-talk / ответа на вызов).

Запуск:  python probe_sip_media.py [intercom_index]   (по умолчанию подъезд)
Лог:     logs/sip_media.log
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
import sys
import uuid

import aiohttp

import common
from probe_sip import digest_response, hdr, outbound_ip, SIP_PORT

LOG_PATH = "logs/sip_media.log"
RTP_LOCAL_PORT = 40016
TONE_HZ = 425           # слышимый непрерывный тон (как гудок) для проверки уплинка


def gen_tone_g711(pt: int, freq: int = TONE_HZ, secs: float = 30.0) -> bytes:
    """Сине-тон 8kHz → G.711 (PT8=A-law / PT0=µ-law). Для проверки 'слышно ли у двери'."""
    rate = 8000
    pcm = bytearray()
    for i in range(int(rate * secs)):
        v = int(0.6 * 32767 * math.sin(2 * math.pi * freq * i / rate))
        pcm += struct.pack("<h", v)
    return audioop.lin2ulaw(bytes(pcm), 2) if pt == 0 else audioop.lin2alaw(bytes(pcm), 2)


TRACK_DIR = os.path.join(os.path.dirname(__file__), "audio")


def load_track_frames(pt: int) -> list[bytes] | None:
    """Готовый G.711-трек (audio/track.ulaw для PCMU pt=0 / track.alaw для PCMA pt=8)
    → 160-байт фреймы (20мс). None если файла нет (тогда fallback на тон)."""
    name = "track.ulaw" if pt == 0 else "track.alaw"
    path = os.path.join(TRACK_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = f.read()
    return [data[i:i + 160] for i in range(0, len(data) - 160 + 1, 160)]


STUN_SERVERS = [("stun.cloudflare.com", 3478), ("stun.sipnet.ru", 3478),
                ("stun.nextcloud.com", 443), ("stun.l.google.com", 19302)]


def stun_discover(sock: socket.socket, servers=STUN_SERVERS):
    """STUN Binding Request → (public_ip, public_port) для NAT-обхода RTP.
    Перебираем серверы (Google часто заблокирован). Тот же сокет, что и для RTP."""
    import os
    for server, port in servers:
        data = None
        txid = os.urandom(12)
        req = struct.pack("!HHI", 0x0001, 0x0000, 0x2112A442) + txid
        try:
            srv = (socket.gethostbyname(server), port)
            sock.settimeout(3.0)
            sock.sendto(req, srv)
            data, _ = sock.recvfrom(2048)
        except Exception:
            continue
        finally:
            sock.setblocking(False)
        if data:
            res = _parse_stun(data)
            if res:
                return res
    return None


def _parse_stun(data: bytes):
    i = 20
    while i + 4 <= len(data):
        atype, alen = struct.unpack("!HH", data[i:i + 4])
        i += 4
        val = data[i:i + alen]
        i += alen + ((4 - alen % 4) % 4)
        if atype in (0x0020, 0x0001) and len(val) >= 8:  # XOR-MAPPED / MAPPED-ADDRESS
            if atype == 0x0020:
                xport = struct.unpack("!H", val[2:4])[0] ^ 0x2112
                xaddr = struct.unpack("!I", val[4:8])[0] ^ 0x2112A442
            else:
                xport = struct.unpack("!H", val[2:4])[0]
                xaddr = struct.unpack("!I", val[4:8])[0]
            return socket.inet_ntoa(struct.pack("!I", xaddr)), xport
    return None


def _ts() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def log(line: str) -> None:
    os.makedirs("logs", exist_ok=True)
    msg = f"{_ts()}  {line}"
    print(msg, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


async def mint(intercom: dict, sess: common.Session, install_id: str) -> dict:
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    ) as s:  # macOS: /etc/resolv.conf пуст → aiodns падает, ThreadedResolver работает
        api = common.Api(s, sess.user_agent, access_token=sess.access_token, operator=sess.operator_id)
        r = await api.post(
            f"/rest/v1/places/{intercom['placeId']}/accesscontrols/{intercom['accessControlId']}/sipdevices",
            {"installationId": install_id},
        )
        if not r.ok:
            raise RuntimeError(f"sipdevices mint failed: {r.status}")
        return (await r.json())["data"]


def parse_sdp(body: str) -> dict:
    """Грубый разбор SDP: connection IP, media-линии, rtpmap."""
    info: dict = {"conn_ip": None, "media": [], "rtpmap": {}}
    for ln in body.replace("\r\n", "\n").split("\n"):
        if ln.startswith("c=IN IP4 "):
            info["conn_ip"] = ln.split()[2]
        elif ln.startswith("m="):
            parts = ln[2:].split()
            info["media"].append({"type": parts[0], "port": int(parts[1]), "proto": parts[2], "fmts": parts[3:]})
        elif ln.startswith("a=rtpmap:"):
            pt, _, codec = ln[len("a=rtpmap:"):].partition(" ")
            info["rtpmap"][pt] = codec.strip()
    return info


class MediaProto(asyncio.DatagramProtocol):
    def __init__(self, creds, local_ip, ua, rtp_sock, media_ip, media_port,
                 sess=None, intercom=None, auto_open_sec=0):
        self.login, self.password, self.realm = creds["login"], creds["password"], creds["realm"]
        self.local_ip, self.ua = local_ip, ua
        self.rtp_sock = rtp_sock          # пред-созданный + STUN'нутый RTP-сокет
        self.media_ip = media_ip          # публичный IP для SDP (STUN) или local_ip
        self.media_port = media_port       # публичный порт (STUN) или RTP_LOCAL_PORT
        self.sess = sess                   # для авто-открытия двери (accessControlOpen)
        self.intercom = intercom
        self.auto_open_sec = auto_open_sec # >0 → открыть дверь через N c после ответа
        self._open_done = False
        self.transport = None
        self.call_active = False           # идёт ли активный вызов (для остановки тона)
        # состояние диалога (для отправки BYE):
        self.d_callid = self.d_remote = self.d_local = self.d_target = None
        self.d_route: list[str] = []
        self.d_addr = None
        self.call_id = f"{uuid.uuid4()}@{local_ip}"
        self.cseq = 0
        self.from_tag = uuid.uuid4().hex[:8]
        self._lport = 0
        self.answered = False

    def connection_made(self, transport):
        self.transport = transport
        self._lport = transport.get_extra_info("sockname")[1]
        self.send_register()

    def send_register(self, auth=None):
        self.cseq += 1
        branch = f"z9hG4bK{random.randint(0, 1<<31)}"
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
            "Expires: 120", f"User-Agent: {self.ua}",
        ]
        if auth:
            lines.append(f"Authorization: {auth}")
        lines += ["Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(lines).encode())

    def _dump(self, direction: str, text: str):
        """Полный сырой SIP (заголовки целиком, тело укорочено) — для диагностики."""
        head, _, body = text.partition("\r\n\r\n")
        log(f"────── SIP {direction} ──────")
        for ln in head.split("\r\n"):
            log(f"  {direction}| {ln}")
        if body.strip():
            log(f"  {direction}| <body {len(body)}b: {body[:80]!r}…>")

    def datagram_received(self, data, addr):
        text = data.decode(errors="replace")
        first = text.split("\r\n", 1)[0]
        if text.startswith("SIP/2.0"):
            cseq = hdr(text, "CSeq") or ""
            if "401" in first or "407" in first:
                wa = hdr(text, "WWW-Authenticate") or hdr(text, "Proxy-Authenticate") or ""
                import re
                nonce = re.search(r'nonce="([^"]+)"', wa)
                if nonce:
                    uri = f"sip:{self.realm}"
                    resp = digest_response(self.login, self.password, self.realm, nonce.group(1), "REGISTER", uri)
                    auth = (f'Digest username="{self.login}", realm="{self.realm}", nonce="{nonce.group(1)}", '
                            f'uri="{uri}", response="{resp}", algorithm=MD5')
                    self.send_register(auth)
            elif first.split(" ")[1] == "200" and "REGISTER" in cseq:
                log(f"✅ media-probe REGISTERED {self.login}@{self.realm}. ЗВОНИ В ДОМОФОН.")
            elif "INVITE" not in cseq and "REGISTER" not in cseq:
                self._dump("IN", text)            # прочие ответы по диалогу
        else:
            method = first.split(" ", 1)[0]
            if method == "INVITE":
                self._dump("IN", text)
                self.on_invite(text, addr)
            elif method == "ACK":
                log("🤝 ACK получен — SIP-диалог УСТАНОВЛЕН (медиа должна забриджеваться)")
                if self.auto_open_sec and not self._open_done:
                    self._open_done = True
                    asyncio.ensure_future(self._auto_open())
            elif method in ("BYE", "CANCEL"):
                log(f"call {method}")
                self.call_active = False        # стоп тон
                self._respond(text, addr, "200 OK")
            else:
                self._dump("IN", text)

    def on_invite(self, text, addr):
        if self.answered:
            return
        self.answered = True
        head, _, body = text.partition("\r\n\r\n")
        log("🔔 INVITE получен. Сырой SDP-offer ниже:")
        for ln in head.split("\r\n"):
            if ln.split(":", 1)[0].lower() in ("from", "to", "call-id", "contact", "content-type"):
                log(f"    {ln}")
        for ln in body.replace("\r\n", "\n").split("\n"):
            if ln.strip():
                log(f"    SDP| {ln}")
        sdp = parse_sdp(body)
        log(f"  → SDP parsed: conn={sdp['conn_ip']} media={sdp['media']} codecs={sdp['rtpmap']}")
        # выбираем первую audio media-линию + кодек
        audio = next((m for m in sdp["media"] if m["type"] == "audio"), None)
        if not audio:
            log("  ⚠️ нет audio media-линии в SDP — отвечаю 200 без RTP")
            self._answer(text, addr, sdp, None, None)
            return
        pt = audio["fmts"][0]
        log(f"  → выбран audio PT={pt} codec={sdp['rtpmap'].get(pt,'?')} door-rtp={sdp['conn_ip']}:{audio['port']}")
        self._answer(text, addr, sdp, audio, pt)
        # стартуем RTP к домофону + приём
        asyncio.ensure_future(self._rtp(sdp["conn_ip"], audio["port"], int(pt)))

    def _answer(self, req, addr, sdp, audio, pt):
        head = req.partition("\r\n\r\n")[0]
        # SIP компактные формы: f=From t=To i=Call-ID v=Via m=Contact l=Content-Length c=Content-Type
        compact = {"v": "via", "f": "from", "t": "to", "i": "call-id", "m": "contact"}
        # Копируем From/To/Call-ID/CSeq/Via/Record-Route ДОСЛОВНО (как пришли — компактные/полные),
        # иначе при компактных заголовках 200 OK получается с пустыми полями и сервер его игнорит.
        # Заодно сохраняем состояние диалога для последующего BYE.
        dlg_lines = []
        my_tag = uuid.uuid4().hex[:8]
        self.d_route = []
        for ln in head.split("\r\n")[1:]:                  # пропускаем request-line
            name = ln.split(":", 1)[0].strip().lower()
            h = compact.get(name, name)
            val = ln.split(":", 1)[1].strip() if ":" in ln else ""
            if h == "to" and ";tag=" not in ln:
                ln = f"{ln};tag={my_tag}"
                val = f"{val};tag={my_tag}"
            if h in ("via", "record-route", "from", "to", "call-id", "cseq"):
                dlg_lines.append(ln)
            if h == "from":
                self.d_remote = val            # удалённая сторона (To в нашем BYE)
            elif h == "to":
                self.d_local = val             # мы (From в нашем BYE)
            elif h == "call-id":
                self.d_callid = val
            elif h == "record-route":
                self.d_route.append(val)
            elif h == "contact":
                m = re.search(r"<([^>]+)>", ln)
                self.d_target = m.group(1) if m else None
        self.d_addr = addr
        self.call_active = True
        sdp_body = ""
        if audio:
            sdp_body = (
                "v=0\r\n"
                f"o=- {random.randint(1,1<<31)} 1 IN IP4 {self.media_ip}\r\n"
                "s=probe\r\n"
                f"c=IN IP4 {self.media_ip}\r\n"          # публичный (STUN) → даунлинк дойдёт
                "t=0 0\r\n"
                f"m=audio {self.media_port} RTP/AVP {pt}\r\n"
                f"a=rtpmap:{pt} {sdp['rtpmap'].get(pt, 'PCMA/8000')}\r\n"
                "a=sendrecv\r\n"
            )
        ct = ["Content-Type: application/sdp"] if sdp_body else []
        lines = [
            "SIP/2.0 200 OK", *dlg_lines,
            f"Contact: <sip:{self.login}@{self.local_ip}:{self._lport};transport=udp>",
            f"User-Agent: {self.ua}",
            "Allow: INVITE, ACK, BYE, CANCEL, OPTIONS",
            *ct, f"Content-Length: {len(sdp_body.encode())}", "", sdp_body,
        ]
        msg = "\r\n".join(lines)
        self.transport.sendto(msg.encode(), addr)
        self._dump("OUT", msg)
        log("  → отправил 200 OK" + (" + SDP-answer" if sdp_body else ""))

    async def _rtp(self, door_ip, door_port, pt):
        """Шлём RTP-тишину домофону (открыть путь) + логируем входящий RTP."""
        if not door_ip:
            return
        sock = self.rtp_sock              # пред-созданный + STUN'нутый сокет
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        frames = load_track_frames(pt)
        if frames:
            tname = "track.ulaw" if pt == 0 else "track.alaw"
            log(f"  → уплинк: АУДИО-ТРЕК audio/{tname} ({len(frames)} фреймов ≈{len(frames)*0.02:.1f}с), зацикленно. СЛУШАЙ У ДВЕРИ.")
        else:
            tone = gen_tone_g711(pt)             # fallback: тон, если трека нет
            frames = [tone[i:i + 160] for i in range(0, len(tone) - 160, 160)]
            log(f"  → уплинк: тон {TONE_HZ}Гц ({'µ-law' if pt==0 else 'A-law'}), {len(frames)} фреймов. СЛУШАЙ У ДВЕРИ.")
        ssrc = random.randint(0, 1 << 31)
        seq, tsv = 0, 0
        recv = {"count": 0, "pts": set(), "src": None}

        async def receiver():
            while True:
                try:
                    data, src = await loop.sock_recvfrom(sock, 2048)
                    recv["count"] += 1
                    recv["pts"].add(data[1] & 0x7F if len(data) > 1 else -1)
                    recv["src"] = src
                except Exception:
                    await asyncio.sleep(0.05)

        rtask = asyncio.ensure_future(receiver())
        log(f"  → шлю RTP({pt}) на {door_ip}:{door_port}, слушаю входящий на :{RTP_LOCAL_PORT}")
        i = 0
        while self.call_active:  # зацикливаем трек/тон, пока вызов активен (BYE → стоп)
            frame = frames[i % len(frames)]
            hdr_b = struct.pack("!BBHII", 0x80, pt | (0x80 if i == 0 else 0), seq & 0xFFFF, tsv & 0xFFFFFFFF, ssrc)
            try:
                sock.sendto(hdr_b + frame, (door_ip, door_port))
            except Exception:
                pass
            seq += 1
            tsv += 160
            i += 1
            if i % 50 == 49:  # раз в ~секунду
                log(f"  RTP[+{(i+1)//50}s]: входящих пакетов={recv['count']} PT={recv['pts']} src={recv['src']}")
            await asyncio.sleep(0.02)
        log("  уплинк остановлен (вызов завершён)")
        rtask.cancel()
        self.answered = False             # готов к следующему звонку (сокет не закрываем)
        log(f"  ИТОГ RTP: получено {recv['count']} пакетов, PT={recv['pts']}, от {recv['src']}")
        log("  Вывод: двусторонний звук " + ("РАБОТАЕТ" if recv["count"] > 0 else "downlink НЕ пришёл (NAT/символ. RTP — нужна правка)"))

    async def _auto_open(self):
        """Через N c после установки вызова — открыть дверь (accessControlOpen)."""
        log(f"  ⏳ авто-открытие двери через {self.auto_open_sec} c…")
        await asyncio.sleep(self.auto_open_sec)
        try:
            async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    ) as s:  # macOS: /etc/resolv.conf пуст → aiodns падает, ThreadedResolver работает
                api = common.Api(s, self.sess.user_agent, access_token=self.sess.access_token,
                                 operator=self.sess.operator_id)
                r = await api.post(
                    f"/rest/v1/places/{self.intercom['placeId']}/accesscontrols/"
                    f"{self.intercom['accessControlId']}/actions",
                    {"name": "accessControlOpen"},
                )
                body = await r.text()
                log(f"  🚪 accessControlOpen → HTTP {r.status} {body[:120]}")
        except Exception as e:
            log(f"  ⚠️ auto-open ошибка: {e}")
        await asyncio.sleep(1)      # дать двери открыться
        self.send_bye()             # завершить вызов, чтобы тон/сессия не висели

    def send_bye(self):
        """Инициировать завершение вызова (in-dialog BYE) — глушит тон/сессию."""
        if not (self.d_callid and self.d_target):
            log("  ⚠️ нет состояния диалога — BYE не отправлен")
            return
        self.cseq += 1
        branch = f"z9hG4bK{random.randint(0, 1 << 31)}"
        route = [f"Route: {rr}" for rr in self.d_route]
        lines = [
            f"BYE {self.d_target} SIP/2.0",
            f"Via: SIP/2.0/UDP {self.local_ip}:{self._lport};branch={branch};rport",
            *route,
            "Max-Forwards: 70",
            f"From: {self.d_local}",        # мы (UAS)
            f"To: {self.d_remote}",         # удалённая сторона
            f"Call-ID: {self.d_callid}",
            f"CSeq: {self.cseq} BYE",
            f"User-Agent: {self.ua}",
            "Content-Length: 0", "", "",
        ]
        self.transport.sendto("\r\n".join(lines).encode(), self.d_addr)
        self.call_active = False
        log("  📴 отправил BYE — завершаю вызов (тон выключен)")

    def _respond(self, req, addr, status):
        via = hdr(req, "Via") or ""
        lines = ["SIP/2.0 " + status, f"Via: {via}", f"From: {hdr(req,'From')}",
                 f"To: {hdr(req,'To')}", f"Call-ID: {hdr(req,'Call-ID')}",
                 f"CSeq: {hdr(req,'CSeq')}", "Content-Length: 0", "", ""]
        self.transport.sendto("\r\n".join(lines).encode(), addr)


async def main():
    sess = common.Session.load("session.json")
    intercoms = sess.intercoms or []
    # выбор домофона: argv[1] (индекс) → env INTERCOM_AC (по accessControlId) → 0
    ac_env = os.environ.get("INTERCOM_AC")
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else (
        next((i for i, ic in enumerate(intercoms) if ic["accessControlId"] == ac_env), 0)
        if ac_env else 0)
    intercom = intercoms[idx]
    # ВАЖНО: тот же installationId, что у базового sip-probe для этого домофона —
    # чтобы получить тот же SIP-login, который реально звонит. Конфликтующий
    # базовый контейнер (sipN) для этого домофона нужно остановить.
    install_id = sess.install_id
    log(f"=== SIP MEDIA probe: {intercom['name']} (ac={intercom['accessControlId']}) install={install_id} ===")

    creds = await mint(intercom, sess, install_id)
    ip = socket.gethostbyname(creds["realm"])
    local_ip = outbound_ip(ip)
    log(f"minted, realm={creds['realm']} → {ip}:{SIP_PORT}, local_ip={local_ip}")

    # RTP-сокет + STUN: узнаём публичный mapping, чтобы даунлинк дошёл за NAT
    rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtp_sock.bind(("0.0.0.0", RTP_LOCAL_PORT))
    stun = stun_discover(rtp_sock)
    if stun:
        media_ip, media_port = stun
        log(f"STUN: публичный RTP-адрес {media_ip}:{media_port} → анонсирую его в SDP")
    else:
        media_ip, media_port = local_ip, RTP_LOCAL_PORT
        log(f"STUN не ответил — fallback на local {media_ip}:{media_port} (даунлинк может не дойти)")

    loop = asyncio.get_running_loop()
    # Фиксированный локальный SIP-порт → стабильный Contact, рестарты не плодят
    # «кладбище» устаревших регистраций в Kazoo.
    auto_open_sec = int(os.environ.get("AUTO_OPEN_SEC", "0"))
    if auto_open_sec:
        log(f"режим авто-открытия: дверь откроется через {auto_open_sec} c после ответа")
    transport, proto = await loop.create_datagram_endpoint(
        lambda: MediaProto(creds, local_ip, sess.user_agent, rtp_sock, media_ip, media_port,
                           sess, intercom, auto_open_sec),
        local_addr=("0.0.0.0", 5066), remote_addr=(ip, SIP_PORT))
    try:
        while True:
            await asyncio.sleep(100)
            proto.send_register()   # NAT keep-alive + продление регистрации
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
