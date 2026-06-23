"""
ЭКСПЕРИМЕНТ, НЕ ПРОВЕРЕНО LIVE — scaffolding для сравнения с #1 (WS-binary).
Нельзя тестировать без правки go2rtc.yaml и живого вызова в домофон.
НЕ запускать как standalone-скрипт (запускается go2rtc через exec:).

PoC variant3 exec-bridge: exec-процесс для go2rtc backchannel (#3).

Принцип:
  go2rtc.yaml содержит source: exec:<команда>#backchannel=1
  Когда браузер (advanced-camera-card с кнопкой микрофона) публикует аудио →
  go2rtc запускает эту команду и пишет audio-кадры в её stdin (backchannel).
  Этот скрипт читает stdin (backchannel-аудио) и форвардит в
  probe_push_answer.UPLINK_PROVIDER → RTP uplink → домофон.

Формат stdin (backchannel):
  - По умолчанию go2rtc шлёт G.711 A-law/μ-law в зависимости от согласованного кодека.
  - С параметром #audio=alaw/8000 в exec-строке — A-law 8кГц (workaround bug #1932).
  - Каждый «кадр» — сырые байты без заголовков (не RTP-пакеты).
  - Размер кадра: 160 байт @ 8кГц/20мс (A-law/μ-law G.711).

Связь с probe_push_answer:
  Этот процесс форвардит кадры в harness через Unix-сокет или локальный TCP-порт
  (probe_push_answer слушает на BRIDGE_PORT).
  Альтернатива: встроить в один процесс через multiprocessing.Queue.

Env:
  BRIDGE_PORT  — локальный порт для форвардинга кадров (по умолчанию 9988)
  BRIDGE_PT    — G.711 payload type: 0=PCMU(μ-law), 8=PCMA(A-law) (по умолчанию 8)
  FRAME_BYTES  — байт на кадр (по умолчанию 160)

Запуск: только через go2rtc exec: (не напрямую).
  go2rtc.yaml:
    streams:
      doorbell_backchannel:
        - exec:python /path/to/exec_bridge.py#backchannel=1#audio=alaw/8000

Процедура — см. variant3_exec/README.md.
"""
from __future__ import annotations

# ЭКСПЕРИМЕНТ, НЕ ПРОВЕРЕНО LIVE

import asyncio
import os
import sys

BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "9988"))
BRIDGE_PT = int(os.environ.get("BRIDGE_PT", "8"))    # 8=PCMA (A-law), 0=PCMU (μ-law)
FRAME_BYTES = int(os.environ.get("FRAME_BYTES", "160"))  # G.711 20мс @ 8кГц


def _log(msg: str) -> None:
    """Пишем в stderr (stdout занят двунаправленным потоком go2rtc)."""
    print(f"[exec_bridge] {msg}", file=sys.stderr, flush=True)


async def _forward_to_probe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Читаем backchannel-аудио из stdin и форвардим в probe_push_answer через TCP."""
    _log(f"connected to probe on port {BRIDGE_PORT}, forwarding backchannel frames...")
    try:
        loop = asyncio.get_running_loop()
        buf = bytearray()
        frames_sent = 0
        while True:
            # Читаем из stdin (backchannel от go2rtc) — сырые G.711-байты
            # asyncio не поддерживает stdin напрямую в create_subprocess_exec,
            # поэтому используем loop.run_in_executor для блокирующего чтения.
            chunk = await loop.run_in_executor(None, sys.stdin.buffer.read, FRAME_BYTES * 4)
            if not chunk:
                _log("stdin closed (go2rtc terminated)")
                break
            buf += chunk
            while len(buf) >= FRAME_BYTES:
                frame = bytes(buf[:FRAME_BYTES])
                del buf[:FRAME_BYTES]
                # Форвард: простой wire-формат: [1B pt][2B len][N bytes frame]
                writer.write(bytes([BRIDGE_PT, len(frame) >> 8, len(frame) & 0xFF]) + frame)
                frames_sent += 1
                if frames_sent % 50 == 0:
                    _log(f"forwarded {frames_sent} frames (+{50})")
        await writer.drain()
    except Exception as exc:
        _log(f"forward error: {exc}")
    finally:
        writer.close()
        _log("connection closed")


async def main() -> None:
    _log(
        f"exec_bridge starting: BRIDGE_PORT={BRIDGE_PORT} PT={BRIDGE_PT} "
        f"FRAME_BYTES={FRAME_BYTES}"
    )
    _log("ЭКСПЕРИМЕНТ — НЕ ПРОВЕРЕНО LIVE")
    _log(
        "Ожидается: go2rtc запустил этот процесс через exec:#backchannel=1\n"
        "  stdin = backchannel-аудио от go2rtc (G.711 A-law/μ-law)\n"
        "  Форвардим в probe_push_answer на BRIDGE_PORT"
    )

    # Соединяемся с probe_push_answer (он слушает на BRIDGE_PORT)
    retry = 0
    while retry < 5:
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", BRIDGE_PORT)
            break
        except ConnectionRefusedError:
            retry += 1
            _log(f"probe not ready (attempt {retry}/5) — retrying in 1s...")
            await asyncio.sleep(1)
    else:
        _log(f"probe not available on port {BRIDGE_PORT} — exit")
        return

    await _forward_to_probe(reader, writer)


if __name__ == "__main__":
    # go2rtc exec: запускает нас как subprocess
    # stdin = backchannel-аудио, stdout = (не используем), stderr = наш лог
    asyncio.run(main())
