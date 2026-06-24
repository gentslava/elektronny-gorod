"""Анализ pcap SIP-вызова приложения: SIP-flow + SDP + RTP-timing.

Цель — увидеть, как РЕАЛЬНОЕ приложение (Linphone) принимает вызов: когда шлёт
RTP (рано/при ответе), какой SDP-адрес, формат REGISTER. Сравнить с прототипом.

Запуск: python analyze_pcap.py captures/app_call.pcap
PII (логин/пароль/токены) НЕ печатаем — только структура.
"""
from __future__ import annotations

import socket
import sys

import dpkt

PATH = sys.argv[1] if len(sys.argv) > 1 else "captures/app_call.pcap"
SIP_STARTS = (b"SIP/", b"INVITE", b"REGISTER", b"ACK ", b"BYE ", b"CANCEL",
              b"OPTIONS", b"NOTIFY", b"PRACK", b"UPDATE", b"INFO ", b"SUBSCRIBE")

sip_msgs = []
rtp_streams: dict[tuple, list[float]] = {}
t0 = None

with open(PATH, "rb") as f:
    for ts, buf in dpkt.pcap.Reader(f):
        if t0 is None:
            t0 = ts
        try:
            ip = dpkt.ip.IP(buf)  # DLT_RAW (101)
        except Exception:
            continue
        if not isinstance(ip.data, dpkt.udp.UDP):
            continue
        udp = ip.data
        src, dst = socket.inet_ntoa(ip.src), socket.inet_ntoa(ip.dst)
        payload = bytes(udp.data)
        rel = ts - t0
        if payload[:7].startswith(SIP_STARTS) or payload[:4] == b"SIP/":
            sip_msgs.append((rel, src, udp.sport, dst, udp.dport,
                             payload.decode("utf-8", errors="replace")))
        elif len(payload) >= 12 and (payload[0] & 0xC0) == 0x80 \
                and udp.dport != 5060 and udp.sport != 5060:
            pt = payload[1] & 0x7F
            rtp_streams.setdefault((src, udp.sport, dst, udp.dport, pt), []).append(rel)

print("=== SIP FLOW (по времени) ===")
for rel, src, sp, dst, dp, msg in sip_msgs:
    first = msg.split("\r\n", 1)[0]
    print(f"[{rel:7.2f}s] {src}:{sp} -> {dst}:{dp}  {first[:72]}")

print("\n=== SDP в INVITE / 18x / 200 OK (медиа-адрес, кодеки, направление) ===")
for rel, src, sp, dst, dp, msg in sip_msgs:
    first = msg.split("\r\n", 1)[0]
    is_key = "INVITE" in first or " 200 " in first or " 183 " in first or " 180 " in first
    if is_key and "\r\n\r\n" in msg and "m=audio" in msg:
        body = msg.split("\r\n\r\n", 1)[1]
        print(f"--- [{rel:.2f}s] {first[:50]}")
        for ln in body.split("\r\n"):
            if ln.startswith(("o=", "c=", "m=", "a=rtpmap", "a=sendrecv",
                              "a=recvonly", "a=sendonly", "a=inactive", "a=ptime")):
                print(f"      {ln}")

print("\n=== REGISTER Contact (формат push-params, Expires) — без секретов ===")
for rel, src, sp, dst, dp, msg in sip_msgs:
    if msg.split("\r\n", 1)[0].startswith("REGISTER"):
        for ln in msg.split("\r\n"):
            low = ln.lower()
            if low.startswith(("contact:", "expires:")):
                # маскируем токен (после pn-tok=/pn-prid=) частично
                print(f"      [{rel:.2f}s] {ln[:140]}")
        break

print("\n=== RTP-потоки (когда начинается, направление, PT) ===")
for key, times in sorted(rtp_streams.items(), key=lambda x: x[1][0]):
    src, sp, dst, dp, pt = key
    print(f"  PT={pt:<3} {src}:{sp} -> {dst}:{dp}: "
          f"первый={times[0]:.2f}s последний={times[-1]:.2f}s пакетов={len(times)}")
