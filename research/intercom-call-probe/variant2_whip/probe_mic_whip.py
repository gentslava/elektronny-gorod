"""
ЭКСПЕРИМЕНТ, НЕ ПРОВЕРЕНО LIVE — scaffolding для будущего сравнения с #1 (WS-binary).
Нельзя тестировать без доступа к go2rtc и живого вызова в домофон.
Если тестируете на продакшн-go2rtc — делайте в нерабочее время, go2rtc общий.

PoC D-audio-variant2: транспорт uplink-микрофона — кандидат #2 (WHIP-pull).

Принцип:
  1. Браузер (`mic_whip.html`) публикует микрофон как WHIP-producer в go2rtc:
       POST go2rtc/api/webrtc?dst=<stream>  (или /api/ws?dst=<stream>)
     go2rtc принимает WebRTC (Opus) как producer, mix-реле с существующим стримом.
  2. Этот процесс тянет аудио из go2rtc через RTSP:
       ffmpeg -i rtsp://<go2rtc>:8554/<stream> -f s16le -ar 8000 -ac 1 pipe:1
     go2rtc сам перекодирует Opus → PCM/G.711 (зависит от параметров pull).
  3. Кадры → hook `probe_push_answer.UPLINK_PROVIDER` → RTP uplink → домофон.

Отличие от #1 (WS-binary):
  - Источник микрофона: браузер → go2rtc WHIP → RTSP-pull (не HA-WebSocket).
  - Требует: существующий стрим go2rtc (камеры домофона или 1 строка yaml),
    TURN-сервер на 4G (WHIP ICE traversal).
  - Не требует: модификации HA, авторизованного HA-WebSocket.

Env (все — обязательны при live-тесте):
  GO2RTC_HOST  — hostname/IP go2rtc (напр. home.server или localhost)
  GO2RTC_PORT  — RTSP-порт go2rtc (по умолчанию 8554)
  GO2RTC_STREAM — имя существующего стрима в go2rtc (напр. doorbell_front)
  GO2RTC_TOKEN — Bearer-токен go2rtc (если auth включён), иначе пусто
  WHIP_PORT    — HTTP-порт для mic_whip.html + WHIP-proxy (по умолчанию 8766)

Требует (для RTP-uplink):
  - probe_push_answer.py запущен параллельно (ANSWER=1 MIRROR_APP=1).
  Или встроен через harness (см. комментарий в main()).

Зависимости: aiohttp, ffmpeg (системный), probe_push_answer (harness).
Лог: logs/push_answer.log (общий с harness).

Процедура live-теста — см. variant2_whip/README.md.
"""
from __future__ import annotations

# ЭКСПЕРИМЕНТ, НЕ ПРОВЕРЕНО LIVE

import asyncio
import os
import struct
import subprocess
from collections import deque

from aiohttp import web

import probe_push_answer as harness

# ---------------------------------------------------------------------------
# Конфигурация (через env — не хардкодим реальные адреса/токены)
# ---------------------------------------------------------------------------
GO2RTC_HOST = os.environ.get("GO2RTC_HOST", "localhost")
GO2RTC_PORT = int(os.environ.get("GO2RTC_PORT", "8554"))
GO2RTC_STREAM = os.environ.get("GO2RTC_STREAM", "")  # ОБЯЗАТЕЛЕН — имя стрима в go2rtc
GO2RTC_TOKEN = os.environ.get("GO2RTC_TOKEN", "")    # Bearer-токен go2rtc (если auth)
WHIP_PORT = int(os.environ.get("WHIP_PORT", "8766"))

# Параметры джиттер-буфера (те же умолчания что в #1 probe_mic_uplink.py)
_FRAME_BYTES = 160   # G.711 8кГц, 20мс
_MAX_FRAMES = int(os.environ.get("MIC_MAX_FRAMES", "50"))
_PREROLL = int(os.environ.get("MIC_PREROLL", "4"))

# ---------------------------------------------------------------------------
# Джиттер-буфер (та же логика что _Sink в probe_mic_uplink.py)
# ---------------------------------------------------------------------------


class _Sink:
    """PCM s16le @ 8кГц (от ffmpeg) → G.711 → джиттер-буфер 160B/20мс.

    ffmpeg с параметрами -ar 8000 -ac 1 -f s16le уже отдаёт 8кГц mono,
    поэтому audioop.ratecv не нужен — только lin2ulaw/lin2alaw.
    PT выясняется из кодека вызова (probe_push_answer.UPLINK_PROVIDER вызывается с pt).
    """

    def __init__(self, pt: int) -> None:
        self.pt = pt
        self._accum = bytearray()
        self._frames: deque[bytes] = deque()
        self._primed = False
        self.fed = 0
        self.underruns = 0
        self.overflows = 0

    def feed(self, pcm_s16le_8k: bytes) -> None:
        """Принять PCM int16 @ 8кГц, нарезать на G.711-кадры."""
        if not pcm_s16le_8k:
            return
        try:
            import audioop
            g711 = (audioop.lin2ulaw(pcm_s16le_8k, 2)
                    if self.pt == 0 else audioop.lin2alaw(pcm_s16le_8k, 2))
        except Exception as exc:
            harness.log(f"  ⚠️ whip-sink: audioop error: {exc}")
            return
        self._accum += g711
        while len(self._accum) >= _FRAME_BYTES:
            if len(self._frames) >= _MAX_FRAMES:
                self._frames.popleft()
                self.overflows += 1
            self._frames.append(bytes(self._accum[:_FRAME_BYTES]))
            self.fed += 1
            del self._accum[:_FRAME_BYTES]

    def next_frame(self) -> bytes | None:
        if not self._primed:
            if len(self._frames) < _PREROLL:
                return None
            self._primed = True
        if not self._frames:
            self._primed = False
            self.underruns += 1
            return None
        return self._frames.popleft()


# ---------------------------------------------------------------------------
# Глобальное состояние (один вызов одновременно — аналог #1)
# ---------------------------------------------------------------------------
_BOX: dict = {
    "pt": int(os.environ.get("MIC_PT", "0")),
    "sink": None,
}
_BOX["sink"] = _Sink(_BOX["pt"])
_ffmpeg_proc: asyncio.subprocess.Process | None = None


# ---------------------------------------------------------------------------
# Uplink provider (hook для probe_push_answer.UPLINK_PROVIDER)
# ---------------------------------------------------------------------------


def _uplink_provider(pt: int) -> bytes | None:
    """harness зовёт каждые 20мс при активном вызове → G.711-кадр микрофона."""
    sink: _Sink = _BOX["sink"]
    if pt != _BOX["pt"]:
        _BOX["pt"] = pt
        _BOX["sink"] = _Sink(pt)
        harness.log(f"  🎚 whip-pull: кодек вызова PT={pt} — sink пересоздан")
    return _BOX["sink"].next_frame()


# ---------------------------------------------------------------------------
# ffmpeg RTSP-pull: go2rtc → PCM s16le 8кГц → _Sink
# ---------------------------------------------------------------------------


def _rtsp_url() -> str:
    """RTSP URL для pull из go2rtc. Bearer-токен в URL если задан."""
    # ВАЖНО: GO2RTC_STREAM должен быть существующим стримом (камеры домофона).
    # go2rtc НЕ авто-создаёт пустой стрим через ?dst= — только существующие.
    host = GO2RTC_HOST
    if GO2RTC_TOKEN:
        # go2rtc поддерживает Basic auth в URL: rtsp://user:token@host:port/stream
        host = f":{GO2RTC_TOKEN}@{GO2RTC_HOST}"
    return f"rtsp://{host}:{GO2RTC_PORT}/{GO2RTC_STREAM}"


async def _ffmpeg_pull_loop(sink: _Sink) -> None:
    """Запускает ffmpeg RTSP-pull, читает stdout в sink.

    ЭКСПЕРИМЕНТ: кодек RTSP из go2rtc при WHIP-producer зависит от того,
    как go2rtc микширует Opus-producer с RTSP-consumer. Ожидаем PCM (ffmpeg
    всегда декодирует на выходе s16le). Проверить PT нет смысла — ffmpeg сам.

    Известный вопрос: go2rtc ?dst=<stream> ДОБАВЛЯЕТ браузер как producer к
    существующему стриму камеры — это означает, что pull вернёт MIX видео+аудио.
    ffmpeg -vn отрезает видео. Аудио = Opus от браузера (если go2rtc корректно
    микширует). На практике нужно проверить что в RTSP-потоке есть audio-трек
    от браузера, а не только аудио домофона (downlink). Это основной неизвестный.
    """
    global _ffmpeg_proc
    if not GO2RTC_STREAM:
        harness.log("  ❌ WHIP variant2: GO2RTC_STREAM не задан — ffmpeg не запускается")
        return

    rtsp_url = _rtsp_url()
    cmd = [
        "ffmpeg",
        "-loglevel", "warning",
        "-rtsp_transport", "tcp",     # TCP надёжнее UDP для RTSP через LAN
        "-i", rtsp_url,
        "-vn",                         # только аудио
        "-ar", "8000",                 # ресемпл → 8кГц (go2rtc обычно Opus 48кГц)
        "-ac", "1",                    # моно
        "-f", "s16le",                 # raw PCM int16 LE
        "pipe:1",
    ]
    harness.log(f"  🎬 ffmpeg RTSP-pull: {rtsp_url!r} (GO2RTC_STREAM={GO2RTC_STREAM!r})")
    harness.log("  ⚠️  ЭКСПЕРИМЕНТ: go2rtc WHIP-producer mix с RTSP не проверен live")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _ffmpeg_proc = proc
        harness.log(f"  → ffmpeg PID={proc.pid}")
        # Читаем stderr в фоне (диагностика без блокировки stdout)
        asyncio.ensure_future(_drain_stderr(proc))
        # Читаем stdout → sink.feed
        buf = bytearray()
        chunk_size = _FRAME_BYTES * 4  # ~80мс за раз
        while True:
            chunk = await proc.stdout.read(chunk_size)
            if not chunk:
                break
            buf += chunk
            # Нарезаем кратно _FRAME_BYTES чтобы не дробить кадры
            while len(buf) >= _FRAME_BYTES:
                sink.feed(bytes(buf[:_FRAME_BYTES]))
                del buf[:_FRAME_BYTES]
        code = await proc.wait()
        harness.log(f"  ⚠️  ffmpeg завершился с кодом {code}")
    except FileNotFoundError:
        harness.log("  ❌ ffmpeg не найден — установи ffmpeg в PATH")
    except Exception as exc:
        harness.log(f"  ❌ ffmpeg-pull: {exc}")
    finally:
        _ffmpeg_proc = None


async def _drain_stderr(proc: asyncio.subprocess.Process) -> None:
    """Читаем ffmpeg stderr и пишем в лог (для диагностики RTSP-ошибок)."""
    try:
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            harness.log(f"  ffmpeg|{line.decode(errors='replace').rstrip()}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# HTTP: mic_whip.html (статика) и /api/webrtc WHIP-proxy (опционально)
# ---------------------------------------------------------------------------


async def _html_handler(request: web.Request):
    """Отдаём mic_whip.html."""
    html_path = os.path.join(os.path.dirname(__file__), "mic_whip.html")
    if not os.path.exists(html_path):
        return web.Response(status=404, text="mic_whip.html not found")
    return web.FileResponse(html_path)


async def _stats_loop() -> None:
    """Диагностика джиттер-буфера в лог (аналог #1)."""
    prev = (0, 0)
    while True:
        await asyncio.sleep(2)
        sink: _Sink = _BOX["sink"]
        if sink.fed == 0:
            continue
        du, do = sink.underruns - prev[0], sink.overflows - prev[1]
        prev = (sink.underruns, sink.overflows)
        harness.log(
            f"  📊 whip-buf: depth={len(sink._frames)} primed={sink._primed} "
            f"fed={sink.fed} underruns={sink.underruns}(+{du}) overflows={sink.overflows}(+{do})"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    # Проверка конфигурации
    if not GO2RTC_STREAM:
        harness.log(
            "  ❌ WHIP variant2: GO2RTC_STREAM не задан.\n"
            "  Задай GO2RTC_STREAM=<имя_стрима> (существующий стрим в go2rtc).\n"
            "  Пример: GO2RTC_STREAM=doorbell_front GO2RTC_HOST=home.server python probe_mic_whip.py"
        )
        return

    harness.log(
        f"=== ЭКСПЕРИМЕНТ variant2 WHIP-pull: GO2RTC_HOST={GO2RTC_HOST!r} "
        f"PORT={GO2RTC_PORT} STREAM={GO2RTC_STREAM!r} WHIP_PORT={WHIP_PORT} ==="
    )
    harness.log("  ℹ️  НЕ ПРОВЕРЕНО LIVE — scaffolding для сравнения с #1")

    # HTTP-сервер для mic_whip.html
    app = web.Application()
    app.router.add_get("/", _html_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", WHIP_PORT).start()
    harness.log(
        f"  → HTTP на :{WHIP_PORT} — открой http://localhost:{WHIP_PORT}/ (mic_whip.html)"
    )

    # Регистрируем uplink provider в harness
    harness.UPLINK_PROVIDER = _uplink_provider

    # Запуск: (1) ffmpeg-pull в фоне, (2) stats, (3) harness (FCM + SIP + RTP)
    sink: _Sink = _BOX["sink"]
    asyncio.ensure_future(_ffmpeg_pull_loop(sink))
    asyncio.ensure_future(_stats_loop())

    harness.log(
        "  ℹ️  Порядок действий:\n"
        "  1. Открой mic_whip.html на устройстве с микрофоном.\n"
        "  2. Нажми 'Publish mic to go2rtc' — браузер публикует микрофон в go2rtc WHIP.\n"
        "  3. Позвони в домофон — проба ответит через FCM/SIP.\n"
        "  4. Говори — ffmpeg тянет аудио из go2rtc → uplink → домофон."
    )
    await harness.main()  # FCM listen + SIP answer + RTP uplink


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
