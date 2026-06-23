"""Оффлайн door-эмулятор: мини-оператор (registrar) + домофон (caller) со СТРОГИМ
RTP-latching. Воспроизводит поведение FreeSWITCH/Kazoo из app_call.pcap БЕЗ
физического домофона и БЕЗ оператора — чтобы тестировать/чинить probe_push_answer.py.

Рецепт — test_harness/PCAP_RECIPE.md. Эмулятор:
  1. Registrar: REGISTER без auth → 401(Digest nonce); REGISTER с auth → 200 OK,
     запоминает Contact/source пробы. Пароль не проверяем строго (фейк-креды),
     но требуем валидный Digest-формат (algorithm=MD5, response=…).
  2. Caller (домофон): после регистрации шлёт INVITE пробе с SDP-offer ИЗ РЕЦЕПТА
     (PCMU PT=0, c=/m=audio <DOOR_RTP_PORT>). From sip:000@<realm>.
  3. На 200 OK пробы: парсит SDP-answer (её RTP addr:port), шлёт ACK (эхо
     Via/Record-Route/To-tag).
  4. СТРОГИЙ latching: на door-RTP-сокете ждёт ПЕРВЫЙ uplink от пробы. Проверяет
     symmetric (uplink_src_port == порт SDP-answer m=audio). Защёлкивает src и
     ТОЛЬКО ТОГДА шлёт downlink (PCMU-тон) на защёлкнутый src N секунд.
  5. BYE → 200 OK. В конце — ОТЧЁТ (stdout + exit-code): 200 OK? SDP валиден?
     uplink (кол-во, src-порт, SYMMETRIC ok/fail)? downlink доставлен?

Запуск:  python3 door_emulator.py
Env:
  DOOR_SIP_IP=127.0.0.1   адрес SIP-сокета эмулятора (куда проба шлёт REGISTER/SIP)
  DOOR_SIP_PORT=5060      порт SIP-сокета (== probe_sip.SIP_PORT; проба шлёт сюда)
  DOOR_RTP_PORT=39000     порт door-RTP-сокета (анонсируется в SDP-offer)
  REALM=test.local        SIP realm (== TEST_REALM пробы)
  TALK_SEC=8              сколько секунд слать downlink после latching
  STRICT_SYMMETRIC=1      1 → latch ТОЛЬКО при symmetric (строгий FS); 0 → latch на любой src
  WAIT_SEC=40             общий бюджет ожидания всего флоу
Exit-code: 0 = полный двусторонний вызов (200 OK + ACK + symmetric uplink + downlink).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import random
import re
import socket
import struct
import sys
import threading
import time
import uuid

DOOR_SIP_IP = os.environ.get("DOOR_SIP_IP", "127.0.0.1")
DOOR_SIP_PORT = int(os.environ.get("DOOR_SIP_PORT", "5060"))
DOOR_RTP_PORT = int(os.environ.get("DOOR_RTP_PORT", "39000"))
REALM = os.environ.get("REALM", "test.local")
TALK_SEC = float(os.environ.get("TALK_SEC", "8"))
STRICT_SYMMETRIC = os.environ.get("STRICT_SYMMETRIC", "1") == "1"
WAIT_SEC = float(os.environ.get("WAIT_SEC", "40"))
NONCE = uuid.uuid4().hex
DOOR_MEDIA_IP = DOOR_SIP_IP  # в локали media и sip на одном loopback


def _ts() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def log(line: str) -> None:
    print(f"{_ts()}  [door] {line}", flush=True)


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def hdr(text: str, name: str) -> str | None:
    m = re.search(rf"^{name}\s*:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else None


def pcmu_tone(freq: int = 425, secs: float = 0.2) -> bytes:
    """G.711 µ-law (PT=0) тон → 160-байт фреймы готовить через срез. Без audioop:
    кодируем µ-law вручную (8kHz, 1 период повторяем). secs мал — фреймы зацикливаем."""
    import math

    rate = 8000
    out = bytearray()
    for i in range(int(rate * secs)):
        sample = int(0.5 * 32767 * math.sin(2 * math.pi * freq * i / rate))
        out.append(_lin2ulaw_sample(sample))
    return bytes(out)


_ULAW_BIAS = 0x84
_ULAW_CLIP = 32635


def _lin2ulaw_sample(sample: int) -> int:
    """16-bit PCM → 8-bit µ-law (G.711), без audioop (для py3.13+ совместимости)."""
    sign = 0x80 if sample < 0 else 0x00
    if sample < 0:
        sample = -sample
    if sample > _ULAW_CLIP:
        sample = _ULAW_CLIP
    sample += _ULAW_BIAS
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


class Report:
    """Накопитель результатов для финального вердикта + exit-code."""

    def __init__(self) -> None:
        self.registered = False
        self.invite_sent = False
        self.ok_200 = False
        self.sdp_valid = False
        self.ack = False
        self.answer_rtp_port: int | None = None  # порт из SDP-answer пробы
        self.answer_rtp_ip: str | None = None
        self.uplink_count = 0
        self.uplink_src_port: int | None = None
        self.symmetric: bool | None = None
        self.latched = False
        self.downlink_sent = 0
        self.bye = False

    def verdict(self) -> int:
        log("=" * 64)
        log("ИТОГОВЫЙ ОТЧЁТ door-эмулятора")
        log("=" * 64)
        log(f"  REGISTER 200 OK ............ {'ДА' if self.registered else 'НЕТ'}")
        log(f"  INVITE отправлен .......... {'ДА' if self.invite_sent else 'НЕТ'}")
        log(f"  проба ответила 200 OK ..... {'ДА' if self.ok_200 else 'НЕТ'}")
        log(f"  SDP-answer валиден ........ {'ДА' if self.sdp_valid else 'НЕТ'}"
            + (f" (RTP {self.answer_rtp_ip}:{self.answer_rtp_port})" if self.sdp_valid else ""))
        log(f"  ACK отправлен ............. {'ДА' if self.ack else 'НЕТ'}")
        log(f"  uplink принят ............. {self.uplink_count} пакетов"
            + (f", src-порт={self.uplink_src_port}" if self.uplink_src_port else ""))
        sym = {True: "OK", False: "FAIL", None: "n/a"}[self.symmetric]
        log(f"  SYMMETRIC RTP ............. {sym}"
            + (f" (uplink_src={self.uplink_src_port} vs sdp={self.answer_rtp_port})"
               if self.uplink_src_port and self.answer_rtp_port else ""))
        log(f"  latched (защёлкнут) ....... {'ДА' if self.latched else 'НЕТ'}")
        log(f"  downlink отправлено ....... {self.downlink_sent} пакетов на защёлкнутый src")
        log(f"  BYE ....................... {'ДА' if self.bye else 'НЕТ'}")
        log("=" * 64)
        ok = (self.registered and self.invite_sent and self.ok_200 and self.sdp_valid
              and self.ack and self.uplink_count > 0 and self.latched
              and self.downlink_sent > 0)
        if STRICT_SYMMETRIC:
            ok = ok and (self.symmetric is True)
        if ok:
            log("ВЕРДИКТ: ✅ ПОЛНЫЙ ДВУСТОРОННИЙ ВЫЗОВ (two-way media работает, "
                f"symmetric={sym}).")
            return 0
        # детализируем причину
        if not self.ok_200:
            log("ВЕРДИКТ: ❌ проба не ответила 200 OK (нет ответа на INVITE).")
        elif not self.ack:
            log("ВЕРДИКТ: ❌ ACK не сформирован (SDP-answer не распарсился?).")
        elif self.uplink_count == 0:
            log("ВЕРДИКТ: ❌ downlink=0 РЕПРОДУЦИРОВАН: проба НЕ прислала uplink RTP "
                "→ FreeSWITCH не латчится. Причина: проба не шлёт RTP или шлёт на "
                "неверный door addr:port (см. парсинг SDP-offer в пробе).")
        elif self.symmetric is False and STRICT_SYMMETRIC:
            log("ВЕРДИКТ: ❌ downlink=0 РЕПРОДУЦИРОВАН: НЕсимметричный RTP "
                f"(uplink src-порт {self.uplink_src_port} ≠ SDP-answer порт "
                f"{self.answer_rtp_port}) → строгий FreeSWITCH не латчится.")
        elif not self.latched:
            log("ВЕРДИКТ: ❌ latching не произошёл.")
        else:
            log("ВЕРДИКТ: ❌ неполный вызов (см. отчёт выше).")
        return 1


class DoorEmulator:
    def __init__(self) -> None:
        self.report = Report()
        self.sip = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sip.bind((DOOR_SIP_IP, DOOR_SIP_PORT))
        self.sip.settimeout(0.5)
        self.rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtp.bind((DOOR_MEDIA_IP, DOOR_RTP_PORT))
        self.rtp.settimeout(0.2)
        self.probe_addr: tuple[str, int] | None = None  # source-addr пробы (SIP)
        self.probe_contact: str | None = None
        self.call_id = f"door-{uuid.uuid4()}@{DOOR_MEDIA_IP}"
        self.from_tag = uuid.uuid4().hex[:8]
        self.to_tag: str | None = None  # tag пробы из 200 OK
        self.invite_branch = ""
        self.invite_cseq = 1
        self.invite_sent_mono: float | None = None
        self.remote_target: str | None = None  # Contact пробы (RURI для ACK/BYE)
        self.record_route: list[str] = []
        self.done = threading.Event()
        self.latch_addr: tuple[str, int] | None = None
        self.latch_decided = False  # symmetric-проверка по первому uplink сделана (1 раз)
        self._stop = False

    # ---------- registrar ----------
    def _challenge(self, req: str, addr) -> None:
        via = hdr(req, "Via") or ""
        to = hdr(req, "To") or ""
        resp = [
            "SIP/2.0 401 Unauthorized", f"Via: {via}", f"From: {hdr(req, 'From')}",
            f"To: {to};tag={self.from_tag}", f"Call-ID: {hdr(req, 'Call-ID')}",
            f"CSeq: {hdr(req, 'CSeq')}",
            f'WWW-Authenticate: Digest realm="{REALM}", nonce="{NONCE}", algorithm=MD5',
            "Content-Length: 0", "", "",
        ]
        self.sip.sendto("\r\n".join(resp).encode(), addr)
        log(f"REGISTER без auth → 401 (Digest challenge, nonce={NONCE[:8]}…)")

    def _accept_register(self, req: str, addr) -> None:
        # фейк-креды: не проверяем пароль строго, но требуем валидный Digest-формат.
        auth = hdr(req, "Authorization") or ""
        if "response=" not in auth or "Digest" not in auth:
            log("REGISTER auth без валидного Digest-формата → игнор")
            return
        via = hdr(req, "Via") or ""
        to = hdr(req, "To") or ""
        contact = hdr(req, "Contact") or ""
        self.probe_addr = addr
        m = re.search(r"<([^>]+)>", contact)
        self.probe_contact = m.group(1) if m else contact
        resp = [
            "SIP/2.0 200 OK", f"Via: {via}", f"From: {hdr(req, 'From')}",
            f"To: {to};tag={self.from_tag}", f"Call-ID: {hdr(req, 'Call-ID')}",
            f"CSeq: {hdr(req, 'CSeq')}", f"Contact: {contact}", "Expires: 120",
            "Content-Length: 0", "", "",
        ]
        self.sip.sendto("\r\n".join(resp).encode(), addr)
        if not self.report.registered:
            self.report.registered = True
            log(f"REGISTER с auth → 200 OK. Проба зарегистрирована "
                f"(src={addr}, contact={self.probe_contact}).")

    # ---------- caller (домофон) ----------
    def send_invite(self) -> None:
        if self.probe_addr is None:
            return
        self.invite_branch = f"z9hG4bK{random.randint(0, 1 << 31)}"
        ruri = self.probe_contact or f"sip:{REALM}"
        sdp = (
            "v=0\r\n"
            f"o=FreeSWITCH {int(time.time())} {int(time.time())} IN IP4 {DOOR_MEDIA_IP}\r\n"
            "s=FreeSWITCH\r\n"
            f"c=IN IP4 {DOOR_MEDIA_IP}\r\n"
            "t=0 0\r\n"
            f"m=audio {DOOR_RTP_PORT} RTP/AVP 0 8 101 13\r\n"
            "a=rtpmap:0 PCMU/8000\r\n"
            "a=rtpmap:8 PCMA/8000\r\n"
            "a=rtpmap:101 telephone-event/8000\r\n"
            "a=fmtp:101 0-15\r\n"
            "a=rtpmap:13 CN/8000\r\n"
            "a=ptime:20\r\n"
        )
        # Record-Route как у проксирующего FreeSWITCH (проба должна эхнуть в ACK/BYE).
        rr = f"<sip:{DOOR_MEDIA_IP}:{DOOR_SIP_PORT};lr=on;ftag={self.from_tag}>"
        self.record_route = [rr]
        lines = [
            f"INVITE {ruri} SIP/2.0",
            f"Via: SIP/2.0/UDP {DOOR_MEDIA_IP}:{DOOR_SIP_PORT};branch={self.invite_branch};rport",
            f"Record-Route: {rr}",
            "Max-Forwards: 70",
            f"From: <sip:000@{REALM}>;tag={self.from_tag}",
            f"To: <{ruri}>",
            f"Call-ID: {self.call_id}",
            f"CSeq: {self.invite_cseq} INVITE",
            f"Contact: <sip:mod_sofia@{DOOR_MEDIA_IP}:{DOOR_SIP_PORT}>",
            "User-Agent: FreeSWITCH-door-emulator",
            "Content-Type: application/sdp",
            f"Content-Length: {len(sdp.encode())}",
            "", sdp,
        ]
        self.sip.sendto("\r\n".join(lines).encode(), self.probe_addr)
        self.invite_sent_mono = time.monotonic()
        self.report.invite_sent = True
        log(f"INVITE → проба {self.probe_addr} (SDP-offer PCMU PT=0, "
            f"door-RTP {DOOR_MEDIA_IP}:{DOOR_RTP_PORT})")

    def _parse_answer_sdp(self, text: str) -> None:
        body = text.partition("\r\n\r\n")[2]
        conn_ip = None
        audio_port = None
        for ln in body.replace("\r\n", "\n").split("\n"):
            if ln.startswith("c=IN IP4 "):
                conn_ip = ln.split()[2]
            elif ln.startswith("m=audio"):
                parts = ln.split()
                if len(parts) >= 2:
                    audio_port = int(parts[1])
        if conn_ip and audio_port:
            self.report.sdp_valid = True
            self.report.answer_rtp_ip = conn_ip
            self.report.answer_rtp_port = audio_port
            log(f"SDP-answer пробы: RTP {conn_ip}:{audio_port} (это ожидаемый "
                f"symmetric src uplink'а).")
        else:
            log(f"⚠️ SDP-answer без c=/m=audio (conn={conn_ip} port={audio_port})")

    def send_ack(self, ok_text: str) -> None:
        # Contact пробы → RURI для ACK; To-tag пробы; эхо Record-Route как Route.
        m = re.search(r"<([^>]+)>", hdr(ok_text, "Contact") or "")
        self.remote_target = m.group(1) if m else (self.probe_contact or f"sip:{REALM}")
        to = hdr(ok_text, "To") or ""
        tagm = re.search(r"tag=([^;\s]+)", to)
        self.to_tag = tagm.group(1) if tagm else None
        branch = f"z9hG4bK{random.randint(0, 1 << 31)}"
        route = [f"Route: {rr}" for rr in self.record_route]
        lines = [
            f"ACK {self.remote_target} SIP/2.0",
            f"Via: SIP/2.0/UDP {DOOR_MEDIA_IP}:{DOOR_SIP_PORT};branch={branch};rport",
            *route, "Max-Forwards: 70",
            f"From: <sip:000@{REALM}>;tag={self.from_tag}",
            f"To: {to}",
            f"Call-ID: {self.call_id}",
            f"CSeq: {self.invite_cseq} ACK",
            "Content-Length: 0", "", "",
        ]
        self.sip.sendto("\r\n".join(lines).encode(), self.probe_addr)
        self.report.ack = True
        log(f"ACK → проба (RURI={self.remote_target}, To-tag={self.to_tag}). "
            "Жду первый uplink RTP для latching…")

    def send_bye(self) -> None:
        if not self.remote_target:
            return
        branch = f"z9hG4bK{random.randint(0, 1 << 31)}"
        route = [f"Route: {rr}" for rr in self.record_route]
        lines = [
            f"BYE {self.remote_target} SIP/2.0",
            f"Via: SIP/2.0/UDP {DOOR_MEDIA_IP}:{DOOR_SIP_PORT};branch={branch};rport",
            *route, "Max-Forwards: 70",
            f"From: <sip:000@{REALM}>;tag={self.from_tag}",
            f"To: <{self._probe_aor()}>;tag={self.to_tag}" if self.to_tag else f"To: <{self._probe_aor()}>",
            f"Call-ID: {self.call_id}",
            f"CSeq: {self.invite_cseq + 1} BYE",
            "Content-Length: 0", "", "",
        ]
        self.sip.sendto("\r\n".join(lines).encode(), self.probe_addr)
        self.report.bye = True
        log("BYE → проба (завершаю вызов).")

    def _probe_aor(self) -> str:
        # AOR пробы для To в BYE: из Contact-URI без параметров
        if self.remote_target:
            return self.remote_target.split(";")[0]
        return f"sip:{REALM}"

    # ---------- media latching ----------
    def _media_loop(self) -> None:
        """Поток door-RTP: ждёт первый uplink, проверяет symmetric, защёлкивает,
        затем шлёт downlink на защёлкнутый src TALK_SEC секунд."""
        tone = pcmu_tone()
        frames = [tone[i:i + 160] for i in range(0, max(1, len(tone) - 160 + 1), 160)] or [b"\xff" * 160]
        ssrc = random.randint(0, 1 << 31)
        seq = tsv = 0
        send_until: float | None = None
        next_send = time.monotonic()
        fi = 0
        while not self._stop:
            # приём uplink
            try:
                data, src = self.rtp.recvfrom(2048)
                self.report.uplink_count += 1
                if not self.latch_decided:
                    self.latch_decided = True  # решение по symmetric — один раз (без спама)
                    self.report.uplink_src_port = src[1]
                    sdp_port = self.report.answer_rtp_port
                    symmetric = (sdp_port is not None and src[1] == sdp_port)
                    self.report.symmetric = symmetric
                    if symmetric:
                        log(f"первый uplink от {src}: SYMMETRIC OK "
                            f"(src-порт {src[1]} == SDP-answer {sdp_port}).")
                    else:
                        log(f"первый uplink от {src}: SYMMETRIC FAIL "
                            f"(src-порт {src[1]} ≠ SDP-answer {sdp_port}).")
                    if symmetric or not STRICT_SYMMETRIC:
                        self.latch_addr = src
                        self.report.latched = True
                        send_until = time.monotonic() + TALK_SEC
                        log(f"🔒 LATCHED на {src}. Шлю downlink {TALK_SEC:.0f}с "
                            f"(PCMU тон, PT=0, 20мс).")
                    else:
                        log("строгий режим: НЕ латчусь на несимметричный src → "
                            "downlink НЕ пойдёт (репродукция downlink=0).")
            except socket.timeout:
                pass
            except OSError:
                break

            # отправка downlink на защёлкнутый src
            now = time.monotonic()
            if self.latch_addr is not None and send_until is not None:
                if now >= send_until:
                    log(f"downlink завершён ({self.report.downlink_sent} пакетов "
                        "отправлено). Завершаю вызов.")
                    self.done.set()
                    break
                if now >= next_send:
                    frame = frames[fi % len(frames)]
                    pkt = struct.pack("!BBHII", 0x80, 0, seq & 0xFFFF,
                                      tsv & 0xFFFFFFFF, ssrc) + frame
                    try:
                        self.rtp.sendto(pkt, self.latch_addr)
                        self.report.downlink_sent += 1
                    except OSError:
                        pass
                    seq += 1
                    tsv += 160
                    fi += 1
                    next_send += 0.02
                    if self.report.downlink_sent % 50 == 0:
                        log(f"downlink[+{self.report.downlink_sent // 50}s]: "
                            f"{self.report.downlink_sent} пакетов; uplink={self.report.uplink_count}")
            time.sleep(0.002)

    # ---------- main SIP loop ----------
    def run(self) -> int:
        log(f"door-эмулятор слушает SIP {DOOR_SIP_IP}:{DOOR_SIP_PORT}, "
            f"RTP {DOOR_MEDIA_IP}:{DOOR_RTP_PORT}, realm={REALM}, "
            f"strict_symmetric={STRICT_SYMMETRIC}.")
        media_thread = threading.Thread(target=self._media_loop, daemon=True)
        media_thread.start()
        deadline = time.monotonic() + WAIT_SEC
        invite_done = False
        while time.monotonic() < deadline and not self.done.is_set():
            try:
                data, addr = self.sip.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            text = data.decode(errors="replace")
            first = text.split("\r\n", 1)[0]
            if text.startswith("SIP/2.0"):
                self._on_response(text, first, addr)
            else:
                method = first.split(" ", 1)[0]
                if method == "REGISTER":
                    if "Authorization" in text or "authorization" in text:
                        self._accept_register(text, addr)
                        # после регистрации — звоним (один раз)
                        if not invite_done:
                            invite_done = True
                            time.sleep(0.2)
                            self.send_invite()
                    else:
                        self._challenge(text, addr)
                elif method in ("OPTIONS", "NOTIFY", "INFO"):
                    self._ok(text, addr)
                elif method in ("BYE", "CANCEL"):
                    self._ok(text, addr)
                    log(f"{method} от пробы — вызов завершён пробой.")
                    self.done.set()
        # дать downlink дослаться (если latched, но WAIT истёк)
        if self.report.latched and not self.done.is_set():
            self.done.wait(timeout=TALK_SEC + 2)
        # завершаем
        if self.report.ack and not self.report.bye:
            self.send_bye()
            time.sleep(0.3)
        self._stop = True
        media_thread.join(timeout=2)
        return self.report.verdict()

    def _on_response(self, text: str, first: str, addr) -> None:
        parts = first.split(" ")
        code = parts[1] if len(parts) > 1 else ""
        cseq = hdr(text, "CSeq") or ""
        if "INVITE" not in cseq:
            return
        if code.startswith("1"):  # 100/180/183
            ts = (time.monotonic() - self.invite_sent_mono) if self.invite_sent_mono else 0.0
            log(f"проба → {first.split(' ', 1)[1]} (+{ts:.2f}с) [provisional]")
        elif code == "200":
            if self.report.ok_200:
                return  # ретрансмит 200 OK — ACK уже отправлен
            self.report.ok_200 = True
            ts = (time.monotonic() - self.invite_sent_mono) if self.invite_sent_mono else 0.0
            log(f"проба → 200 OK на INVITE (+{ts:.2f}с)! Парсю SDP-answer + шлю ACK.")
            self._parse_answer_sdp(text)
            self.send_ack(text)
        elif code and code[0] in ("4", "5", "6"):
            log(f"проба → {first.split(' ', 1)[1]} (INVITE отклонён).")

    def _ok(self, req: str, addr) -> None:
        via = hdr(req, "Via") or ""
        resp = ["SIP/2.0 200 OK", f"Via: {via}", f"From: {hdr(req, 'From')}",
                f"To: {hdr(req, 'To')}", f"Call-ID: {hdr(req, 'Call-ID')}",
                f"CSeq: {hdr(req, 'CSeq')}", "Content-Length: 0", "", ""]
        self.sip.sendto("\r\n".join(resp).encode(), addr)

    def close(self) -> None:
        try:
            self.sip.close()
        except OSError:
            pass
        try:
            self.rtp.close()
        except OSError:
            pass


def main() -> int:
    emu = DoorEmulator()
    try:
        return emu.run()
    finally:
        emu.close()


if __name__ == "__main__":
    sys.exit(main())
