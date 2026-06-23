"""Самотест аудио-тракта uplink БЕЗ домофона/оператора/микрофона.

Эмулирует «микрофон»: синтетический тон 440Гц @48кГц Int16 (как браузерный
getUserMedia) → тот же тракт, что в продакшне: UplinkSink-логика (ресемпл 48→8к +
G.711 + джиттер-буфер + дрейф-компенсированный пейсинг) → RTP → локальный приёмник
(«домофон») → декод G.711 → анализ. Доказывает, что тракт несёт звук чисто и
непрерывно (без провалов/дрейфа). Не трогает SIP/оператора — те матчат интеграцию.

Запуск: python probe_loopback.py   (нужен python3.12+audioop или audioop-lts)
"""
from __future__ import annotations

import asyncio
import audioop
import math
import socket
import struct
import time
import wave
from collections import deque

SRC_RATE = 48000
TARGET_RATE = 8000
FRAME_BYTES = 160  # G.711 8кГц 20мс
CHUNK = 1024       # как ScriptProcessor @48к (~21мс)
FREQ = 440.0
DUR = 8.0          # сек теста
PT = 0             # PCMU
MAX_FRAMES = 50
PREROLL = 4
EAR_PORT = 40099


# ── UplinkSink (зеркало sip/uplink.py: ресемпл→G.711→джиттер-буфер) ──
class Sink:
    def __init__(self) -> None:
        self._st = None
        self._accum = bytearray()
        self._frames: deque[bytes] = deque()
        self._primed = False
        self.fed = self.under = self.over = 0

    def feed(self, pcm: bytes, rate: int) -> None:
        if rate != TARGET_RATE:
            pcm, self._st = audioop.ratecv(pcm, 2, 1, rate, TARGET_RATE, self._st)
        self._accum += audioop.lin2ulaw(pcm, 2)
        while len(self._accum) >= FRAME_BYTES:
            if len(self._frames) >= MAX_FRAMES:
                self._frames.popleft(); self.over += 1
            self._frames.append(bytes(self._accum[:FRAME_BYTES])); self.fed += 1
            del self._accum[:FRAME_BYTES]

    def next_frame(self):
        if not self._primed:
            if len(self._frames) < PREROLL:
                return None
            self._primed = True
        if not self._frames:
            self._primed = False; self.under += 1
            return None
        return self._frames.popleft()


def tone_chunk(n0: int) -> bytes:
    b = bytearray()
    for i in range(CHUNK):
        s = int(0.5 * 32767 * math.sin(2 * math.pi * FREQ * (n0 + i) / SRC_RATE))
        b += struct.pack("<h", s)
    return bytes(b)


async def mic_emulator(sink: Sink) -> None:
    """Синтетический микрофон: подаём тон чанками в реальном темпе (как браузер)."""
    total = int(SRC_RATE * DUR)
    n = 0
    next_t = asyncio.get_running_loop().time()
    while n < total:
        sink.feed(tone_chunk(n), SRC_RATE)
        n += CHUNK
        next_t += CHUNK / SRC_RATE
        await asyncio.sleep(max(0, next_t - asyncio.get_running_loop().time()))


async def rtp_sender(sink: Sink, sock: socket.socket, stats: dict) -> None:
    """Тот же пейсинг, что в пробе/интеграции: 20мс, дрейф-компенсация."""
    loop = asyncio.get_running_loop()
    silence = bytes([0xFF] * FRAME_BYTES)
    seq = ts = 0
    ssrc = 0x1234ABCD
    next_send = loop.time()
    t0 = loop.time()
    while loop.time() - t0 < DUR + 1.0:
        frame = sink.next_frame()
        payload = frame if frame is not None else silence
        if frame is None:
            stats["sent_silence"] += 1
        else:
            stats["sent_real"] += 1
        hb = struct.pack("!BBHII", 0x80, PT | (0x80 if seq == 0 else 0),
                         seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc)
        sock.sendto(hb + payload, ("127.0.0.1", EAR_PORT))
        seq += 1; ts += FRAME_BYTES
        next_send += 0.02
        await asyncio.sleep(max(0, next_send - loop.time()))
    stats["send_wall"] = loop.time() - t0


async def ear(sock: socket.socket, pcm_out: bytearray, stats: dict) -> None:
    """«Домофон»: принимает RTP, декодирует G.711→PCM, копит для анализа."""
    loop = asyncio.get_running_loop()
    last = None
    while True:
        try:
            data = await asyncio.wait_for(loop.sock_recv(sock, 2048), timeout=2.0)
        except asyncio.TimeoutError:
            break
        now = loop.time()
        if last is not None:
            gap = now - last
            if gap > 0.045:  # >2 кадра без пакета = провал
                stats["gaps"].append(round(gap * 1000))
        last = now
        stats["recv"] += 1
        pcm_out += audioop.ulaw2lin(data[12:], 2)


def analyse(pcm: bytes) -> dict:
    """RMS по 200мс-окнам + общая длительность — тон должен быть ровным, без тишины."""
    win = TARGET_RATE * 2 * 200 // 1000  # байт в 200мс
    rms = []
    for i in range(0, len(pcm) - win, win):
        rms.append(audioop.rms(pcm[i:i + win], 2))
    return {
        "samples": len(pcm) // 2,
        "duration_s": round(len(pcm) / 2 / TARGET_RATE, 2),
        "rms_min": min(rms) if rms else 0,
        "rms_max": max(rms) if rms else 0,
        "rms_windows": len(rms),
        "silent_windows": sum(1 for r in rms if r < 500),
    }


async def main() -> None:
    sink = Sink()
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", EAR_PORT)); rx.setblocking(False)
    stats = {"sent_real": 0, "sent_silence": 0, "recv": 0, "gaps": [], "send_wall": 0}
    pcm_out = bytearray()

    print(f"=== loopback самотест: тон {FREQ:.0f}Гц, {DUR:.0f}с, 48к→8к→G.711→RTP→декод ===")
    await asyncio.gather(
        mic_emulator(sink),
        rtp_sender(sink, tx, stats),
        ear(rx, pcm_out, stats),
    )

    a = analyse(bytes(pcm_out))
    exp_frames = int(DUR * 50)  # 50 кадров/с
    print("\n── РЕЗУЛЬТАТ ──")
    print(f"sink: подано кадров={sink.fed} underruns={sink.under} overflows={sink.over}")
    print(f"RTP: отправлено реальных={stats['sent_real']} тишины={stats['sent_silence']} "
          f"получено={stats['recv']} (ожидалось ~{exp_frames})")
    print(f"пейсинг: стена отправки={stats['send_wall']:.2f}с (идеал {DUR + 1:.0f}с) "
          f"→ дрейф={abs(stats['send_wall'] - (DUR + 1)) * 1000:.0f}мс")
    print(f"провалы>45мс: {len(stats['gaps'])} {stats['gaps'][:10]}")
    print(f"декод: {a['duration_s']}с звука, окон={a['rms_windows']} "
          f"тихих(<500)={a['silent_windows']} RMS[{a['rms_min']}..{a['rms_max']}]")

    with wave.open("loopback_out.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(TARGET_RATE)
        w.writeframes(bytes(pcm_out))
    print("WAV сохранён: loopback_out.wav (что услышал бы домофон)")

    ok = (stats["recv"] >= exp_frames * 0.95 and len(stats["gaps"]) == 0
          and a["silent_windows"] == 0 and a["rms_min"] > 1000)
    print(f"\n{'✅ ТРАКТ РАБОТАЕТ' if ok else '❌ ЕСТЬ ПРОБЛЕМЫ'}: тон "
          f"{'прошёл ровно, без провалов' if ok else 'искажён/прерывист — см. выше'}")


if __name__ == "__main__":
    asyncio.run(main())
