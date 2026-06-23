"""PoC D-audio-2: транспорт uplink-микрофона — кандидат #1 (WS-binary).

Браузер (`getUserMedia`) → WebSocket Int16 PCM → этот процесс → ресемпл src→8к →
G.711 → джиттер-буфер → uplink-кадры в ЖИВОЙ звонок (reuse `probe_push_answer`
harness). Критерий PoC: домофон СЛЫШИТ микрофон, латентность разговорная.

Зачем кандидат #1: `браузер → авторизованный HA-WebSocket → интеграция` — путь
голосового ассистента HA (uplink-mic-design.md §4, механизм #1): без go2rtc/exec/
TURN, через тот же канал что весь UI. Эта проба валидирует АУДИО-ПУТЬ и латентность
до двери на упрощённом WS (без HA-auth); 4G/телефон-плечо — Phase C на реальном HA.

Конвертацию делаем ИНЛАЙН (зеркало production `UplinkSink` — sip/uplink.py, покрыт
юнит-тестами): Docker build-context пробы = только research-каталог, custom_components
сюда не копируется, а его import тянет homeassistant. Алгоритм идентичен.

Запуск (Docker, host-net), локально с хоста:
  ANSWER=1 MIRROR_APP=1 RTP_EARLY=1 INTERCOM_AC=<ac> docker compose up --build mic
  → открыть http://localhost:8765/ на ХОСТЕ (localhost = secure origin → микрофон без HTTPS).

Публично (телефон/4G) через cloudflared-туннель (без правок прод-traefik):
  MIC_TOKEN=<секрет> INTERCOM_AC=<ac> docker compose up --build -d mic
  docker run --rm --network host cloudflare/cloudflared:latest tunnel --url http://localhost:8765
  → открыть https://<выданный-url>/?k=<секрет> на телефоне.
Защита: MIC_TOKEN (если задан) проверяется на странице И на WS (?k=…); без него — 403.
Затем: «start mic» → ПОЗВОНИТЬ в домофон → проба ответит → ГОВОРИТЬ, СЛУШАТЬ у двери.
Env: MIC_PT (0=PCMU / 8=PCMA; авто-подстройка под кодек вызова). Лог: logs/push_answer.log.
"""
from __future__ import annotations

import asyncio
import audioop
import json
import os
from collections import deque

from aiohttp import WSMsgType, web

import probe_push_answer as harness

WS_PORT = 8765
_TARGET_RATE = 8000
_FRAME_BYTES = 160  # G.711 8кГц, 20мс
_MAX_FRAMES = 50    # джиттер-буфер ~1с; переполнение → drop-oldest
_HTML = os.path.join(os.path.dirname(__file__), "mic_ws_probe.html")


class _Sink:
    """Инлайн-зеркало UplinkSink: PCM@rate → 8к → G.711 → джиттер-буфер 160B/20мс."""

    def __init__(self, pt: int) -> None:
        self.pt = pt
        self._state = None  # persistent audioop.ratecv state
        self._accum = bytearray()
        self._frames: deque[bytes] = deque()

    def feed(self, pcm: bytes, rate: int) -> None:
        if not pcm:
            return
        if rate != _TARGET_RATE:
            pcm, self._state = audioop.ratecv(pcm, 2, 1, rate, _TARGET_RATE, self._state)
        self._accum += audioop.lin2ulaw(pcm, 2) if self.pt == 0 else audioop.lin2alaw(pcm, 2)
        while len(self._accum) >= _FRAME_BYTES:
            if len(self._frames) >= _MAX_FRAMES:
                self._frames.popleft()  # drop-oldest
            self._frames.append(bytes(self._accum[:_FRAME_BYTES]))
            del self._accum[:_FRAME_BYTES]

    def next_frame(self) -> bytes | None:
        return self._frames.popleft() if self._frames else None


_BOX = {"pt": int(os.environ.get("MIC_PT", "0"))}
_BOX["sink"] = _Sink(_BOX["pt"])
_RATE = {"v": 48000}
_TOKEN = os.environ.get("MIC_TOKEN", "")  # если задан — обязателен в ?k= (защита публичного линка)


def _authorized(request: web.Request) -> bool:
    return not _TOKEN or request.query.get("k") == _TOKEN


def _uplink_provider(pt: int) -> bytes | None:
    """harness зовёт это каждые 20мс при активном вызове → G.711-кадр микрофона."""
    if pt != _BOX["pt"]:
        _BOX["pt"] = pt
        _BOX["sink"] = _Sink(pt)
        harness.log(f"  🎚 mic: кодек вызова PT={pt} — sink пересоздан")
    return _BOX["sink"].next_frame()


async def _ws_handler(request: web.Request):
    if not _authorized(request):
        return web.Response(status=403, text="forbidden")
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    harness.log("  🎤 mic WS: браузер подключён")
    async for msg in ws:
        if msg.type == WSMsgType.BINARY:
            _BOX["sink"].feed(msg.data, _RATE["v"])
        elif msg.type == WSMsgType.TEXT:
            data = json.loads(msg.data)
            if data.get("type") == "start":
                _RATE["v"] = int(data.get("sample_rate", 48000))
                harness.log(f"  🎤 mic WS: start, sample_rate={_RATE['v']}")
    harness.log("  🎤 mic WS: браузер отключился")
    return ws


async def _html_handler(request: web.Request):
    if not _authorized(request):
        return web.Response(status=403, text="forbidden")
    return web.FileResponse(_HTML)


async def main() -> None:
    app = web.Application()
    app.router.add_get("/", _html_handler)
    app.router.add_get("/ws", _ws_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", WS_PORT).start()
    harness.log(f"=== mic-uplink probe: HTTP+WS на :{WS_PORT}. Открой http://localhost:{WS_PORT}/ ===")
    harness.UPLINK_PROVIDER = _uplink_provider  # uplink-кадры ← микрофон (вместо трека/тишины)
    await harness.main()  # FCM listen + SIP answer + RTP


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
