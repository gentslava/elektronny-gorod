# Аудио-мост Slice 1 (downlink — слышать гостя) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Вывести звук гостя (G.711-кадры из `SipManager.on_downlink`) в браузер HA через go2rtc + Advanced Camera Card — «слышим гостя».

**Architecture:** Тонкий `sip/bridge.py` берёт downlink-кадры из `SipManager.on_downlink` и отдаёт их go2rtc (механизм A=exec-источник или B=нативный RTP/UDP — решает PoC Task 1). go2rtc транскодит/раздаёт в WebRTC, Advanced Camera Card играет. Мост и go2rtc-стрим живут на время вызова (контроллер). Uplink — отдельный Slice 2.

**Tech Stack:** Python 3.13 asyncio + socket; go2rtc REST (`/api/streams`); существующий `sip/rtp.py` (`build_rtp_packet`); pytest + pytest-homeassistant-custom-component; деплой — копирование в `/opt/homeassistant/custom_components/elektronny_gorod/` + `docker restart`.

---

## Scope этого плана

Только **downlink** (слышать гостя). Slice 1 research-heavy: механизм моста (A exec vs
B RTP) снимается **PoC до production-кода** (Task 1) — форма сетевой обвязки (Task 4)
финализируется после него. Чистые модули, нужные при любом исходе (go2rtc audio-upsert,
RTP-packetizer моста), — TDD сразу (Task 2–3). Uplink (микрофон), ADR-0012, полный
two-way — вне scope (Slice 2).

## File Structure

| Файл | Ответственность | Статус |
|---|---|---|
| `research/intercom-call-probe/probe_audio_bridge.py` | PoC A(exec) vs B(RTP): подать тестовый G.711 в go2rtc, открыть в браузере | создаётся (Task 1) |
| `custom_components/elektronny_gorod/go2rtc.py` | **консолидация go2rtc-клиента** (принять upsert/src/auth/url из camera.py) + `upsert_audio_stream`/`remove_audio_stream` + ClientTimeout/redact (A-72/S-17/S-18) | модифицируется (Task 2) |
| `custom_components/elektronny_gorod/camera.py` | убрать вынесенный go2rtc-клиент → импорт из go2rtc.py (P1 рефактор, поведение неизменно) | модифицируется (Task 2) |
| `custom_components/elektronny_gorod/sip/bridge.py` | мост downlink: `feed_downlink(frame)` → go2rtc transport (RTP-packetize / exec-pipe) | создаётся (Task 3, transport финал post-PoC) |
| `custom_components/elektronny_gorod/sip/manager.py` | прокинуть `on_downlink` в мост на answer; teardown на hangup | модифицируется (Task 4) |
| `custom_components/elektronny_gorod/sip/call_controller.py` | lifecycle моста + go2rtc-стрима (create на answer, remove на hangup) | модифицируется (Task 4) |
| `tests/test_go2rtc_audio.py` | контракт `upsert_audio_stream`/`remove_audio_stream` | создаётся (Task 2) |
| `tests/test_sip_bridge.py` | чистая логика моста (RTP seq/ts, формат src) | создаётся (Task 3) |
| `docs/features/intercom-two-way-audio/README.md` | конфиг Advanced Camera Card (трубка) | модифицируется (Task 5) |

---

## Task 1: PoC — механизм моста A(exec) vs B(RTP)

**Тип:** research (НЕ TDD). Цель — evidence-based выбор механизма, без production-кода.
Прогон на **проде** (там go2rtc-контейнер + домофон).

**Files:**
- Create: `research/intercom-call-probe/probe_audio_bridge.py`
- Uses: standalone go2rtc (`home-assistant-go2rtc-yxrm01-go2rtc-1`), Advanced Camera Card.

- [ ] **Step 1: Сгенерировать тестовый G.711-источник**

Тон 440Гц, PCMU, 20мс-кадры (160 байт), бесконечно — имитирует downlink без звонка:

```python
# probe_audio_bridge.py (фрагмент)
import math, struct
def pcmu_tone(freq=440, rate=8000):
    # linear16 -> mu-law (audioop)
    import audioop
    buf, t = bytearray(), 0
    for i in range(rate // 50):  # 20мс
        s = int(0.3 * 32767 * math.sin(2 * math.pi * freq * (i / rate)))
        buf += struct.pack("<h", s)
    return audioop.lin2ulaw(bytes(buf), 2)  # 160 байт PCMU
```

- [ ] **Step 2: Вариант B — нативный RTP/UDP в go2rtc**

Слать тон как RTP PCMU на UDP-порт; создать go2rtc-стрим, читающий этот RTP по SDP.
Проверить, играет ли карта.

```bash
# B-1: на ХОСТЕ go2rtc — слушаем RTP и пробуем go2rtc-источник.
# Вариант источника go2rtc для RTP (через SDP-файл или ffmpeg):
#   src = "ffmpeg:rtp://0.0.0.0:5004?...#audio=opus"  ИЛИ  SDP-источник.
# Создать стрим:
curl -X PUT "http://<go2rtc>:1984/api/streams?name=eg_probe&src=<RTP-SRC>"
# Слать RTP тон на 5004 (probe_audio_bridge.py B-mode), открыть webrtc:
#   http://<go2rtc>:1984/stream.html?src=eg_probe
```

Зафиксировать: завёлся ли RTP-источник go2rtc, слышно ли тон, задержка, нужен ли SDP.

- [ ] **Step 3: Вариант A — go2rtc exec-источник**

go2rtc запускает ffmpeg-exec, читающий тон из эндпоинта моста (TCP) → stdout.

```bash
# A-1: мост отдаёт сырой PCMU на TCP; go2rtc exec тянет ffmpeg-ом.
curl -X PUT "http://<go2rtc>:1984/api/streams?name=eg_probe_exec&src=\
exec:ffmpeg -hide_banner -f mulaw -ar 8000 -ac 1 -i tcp://<ha-host>:9101 -c:a opus -f rtp...#audio=opus"
# probe_audio_bridge.py A-mode слушает TCP:9101, шлёт тон. Открыть webrtc.
```

Зафиксировать: завёлся ли exec на standalone go2rtc, дотянулся ли до моста
(cross-container сеть!), слышно ли тон.

- [ ] **Step 4: Решение D-audio-1**

В `audio-bridge-design.md` (новая секция «PoC-результаты») записать:
- **D-audio-1 (механизм downlink):** A(exec) ✅ / B(RTP) ✅ — с обоснованием
  (что чище завелось, задержка, cross-container нюансы, нужен ли транскод или
  passthrough PCMU).
- Точный go2rtc `src`-шаблон выбранного варианта (для Task 3/4).

- [ ] **Step 5: Commit**

```bash
git add research/intercom-call-probe/probe_audio_bridge.py docs/features/intercom-two-way-audio/audio-bridge-design.md
git commit -m "research(two-way-audio): PoC аудио-моста downlink — A(exec) vs B(RTP), D-audio-1"
```

---

## Task 2: Консолидация go2rtc-клиента → аудио-стрим методы (рефактор + feat)

**Зачем:** go2rtc REST-логика размазана — `_go2rtc_upsert_stream` + `_build_go2rtc_src`
+ auth-header в `camera.py`, а `validate_go2rtc`/`cleanup_go2rtc_stream` в `go2rtc.py`
(**3 копии** auth-header + URL-builder). Аудио-upsert стал бы 4-й копией + ручным
дублем security-guard S-A71-01 (token-leak — опасно). Поэтому **сначала консолидируем
go2rtc-клиент в `go2rtc.py`** (P1 рефактор-оценки 2026-06-23), потом строим аудио-методы
поверх. Заодно — A-72 (`ClientTimeout`) + S-17/S-18 (redact body) в `go2rtc.py`.

⚠️ **Plan Mode + ask-first** (трогает `camera.py` hot path `stream_source`). Рефактор →
не diagnose-before-fix, но **зелёный `pytest` до и после обязателен** (поведение неизменно).

**Files:**
- Modify: `custom_components/elektronny_gorod/go2rtc.py` (принять upsert/src/auth/url + аудио-методы)
- Modify: `custom_components/elektronny_gorod/camera.py:75-134,332-339` (убрать вынесенное → импорт из go2rtc)
- Modify: `tests/test_go2rtc_upsert.py:26` (import camera → go2rtc)
- Test: `tests/test_go2rtc_audio.py` (новые аудио-методы)

### Рефактор-преамбула (P1, ДО аудио-методов) — отдельный commit

- [ ] **R1: Зелёный baseline** — `PYTHONPATH=. .venv/bin/pytest tests/ -q` (рефактор поведение не меняет; точка отсчёта, особенно `test_go2rtc_upsert` 8 кейсов).
- [ ] **R2: Вынести в `go2rtc.py` дословно** — `_build_go2rtc_src` (camera.py:75-77), `_go2rtc_upsert_stream` (camera.py:80-134; **token-leak guard `from None` сохранить дословно** — S-A71-01). Выделить общие `_go2rtc_auth_header(username, password)` (источник camera.py:332-339 + go2rtc.py:86-90) и `_streams_url(base_url, **params)`. `validate_go2rtc`/`cleanup` перевести на них.
- [ ] **R3: `camera.py`** — удалить вынесенное, `from .go2rtc import _build_go2rtc_src, _go2rtc_upsert_stream`; `_go2rtc_auth_headers` → общий `_go2rtc_auth_header`. Обновить `tests/test_go2rtc_upsert.py:26` import (camera → go2rtc).
- [ ] **R4: A-72/S-17/S-18** — `_GO2RTC_TIMEOUT = ClientTimeout(total=10)` на все go2rtc-запросы (validate GET/PUT, cleanup DELETE); в логах только `resp.status`, без сырого `body`.
- [ ] **R5: Зелёный после рефактора** — `pytest tests/ -q` (вкл. `test_go2rtc_upsert` с новым import) — поведение неизменно.
- [ ] **R6: Commit рефактора** — `refactor(go2rtc): консолидация go2rtc-клиента в go2rtc.py (+ ClientTimeout, redact); закрывает A-72/S-17/S-18`.
- [ ] **R7: go2rtc config bloat (A-84)** — найдено пользователем 2026-06-23: на каждое `stream_source()` стрим дописывается в `go2rtc_homekit.yml` новым `streams:`-блоком (не merge) → сотни дублей + протухшие operator-токены на диске + `cleanup failed: path not exist`. **Сначала DIAG** (controlled: повторить upsert с разным src на throwaway-стриме → какой write, PATCH/PUT, дописывает блок) → фикс: пропускать re-upsert если src не изменился / периодическая компакция конфига / go2rtc-side опция. Закрывает A-84. Объём M-L; через DIAG (не спекулятивно). Пользователь чистит текущий раздутый конфиг сам.

### Аудио-методы (feat, поверх консолидированного клиента)

`upsert_audio_stream` ниже **реюзает `_streams_url`/`_GO2RTC_TIMEOUT`** из R2/R4 (не свой URL/timeout — DRY).

- [ ] **Step 1: Падающий тест**

Create `tests/test_go2rtc_audio.py`:

```python
"""Unit-тесты upsert/remove аудио-стрима вызова (go2rtc.py)."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.elektronny_gorod.go2rtc import upsert_audio_stream


class _Ctx:
    def __init__(self, resp): self._r = resp
    async def __aenter__(self): return self._r
    async def __aexit__(self, *a): return False


def _resp(status: int, text: str = ""):
    r = AsyncMock(); r.status = status; r.text = AsyncMock(return_value=text)
    return r


def _session(patch_status: int):
    s = MagicMock()
    s.patch = MagicMock(return_value=_Ctx(_resp(patch_status)))
    s.put = MagicMock(return_value=_Ctx(_resp(200)))
    return s


async def test_upsert_audio_stream_patch_first():
    s = _session(200)
    await upsert_audio_stream("http://go2rtc:1984", "eg_intercom_talk", "exec:ffmpeg...", s, {})
    s.patch.assert_called_once()           # PATCH-first (idempotent)
    s.put.assert_not_called()
    url = s.patch.call_args.args[0]
    assert "name=eg_intercom_talk" in url and "/api/streams" in url


async def test_upsert_audio_stream_put_fallback_on_patch_4xx():
    s = _session(404)
    await upsert_audio_stream("http://go2rtc:1984", "eg_intercom_talk", "exec:x", s, {})
    s.put.assert_called_once()             # PATCH 404 → PUT fallback
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_go2rtc_audio.py -q`
Expected: FAIL — `ImportError: cannot import name 'upsert_audio_stream'`

- [ ] **Step 3: Реализовать в `go2rtc.py`**

Добавить (рядом с `cleanup_go2rtc_stream`):

```python
from aiohttp import ClientError, ClientTimeout
from urllib.parse import urlencode

_AUDIO_STREAM_TIMEOUT = ClientTimeout(total=10)


async def upsert_audio_stream(
    base_url: str, name: str, src: str, session, headers: dict | None = None
) -> None:
    """Создать/обновить go2rtc аудио-стрим вызова. PATCH-first, PUT-fallback.

    PATCH идемпотентен (не убивает producer); PUT — fallback на 4xx/5xx/ClientError.
    Источник `src` — шаблон выбранного механизма (D-audio-1). Креды НЕ логируются.
    """
    base_url = normalize_base_url(base_url)
    qs = urlencode({"name": name, "src": src})
    url = f"{base_url}/api/streams?{qs}"
    h = headers or {}
    try:
        async with session.patch(url, headers=h, timeout=_AUDIO_STREAM_TIMEOUT) as resp:
            if resp.status in (200, 201, 204):
                return
    except ClientError:
        pass
    try:
        async with session.put(url, headers=h, timeout=_AUDIO_STREAM_TIMEOUT) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"go2rtc audio PUT failed: HTTP {resp.status}") from None
    except ClientError as exc:
        raise RuntimeError(f"go2rtc audio PUT failed: {type(exc).__name__}") from None


async def remove_audio_stream(base_url: str, name: str, session, headers: dict | None = None) -> None:
    """Снять аудио-стрим вызова (best-effort) — обёртка над cleanup_go2rtc_stream."""
    await cleanup_go2rtc_stream(base_url, name, session, headers)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_go2rtc_audio.py -q`
Expected: PASS (2 теста)

- [ ] **Step 5: Commit**

```bash
git add custom_components/elektronny_gorod/go2rtc.py tests/test_go2rtc_audio.py
git commit -m "feat(go2rtc): upsert/remove аудио-стрима вызова (two-way downlink)"
```

---

## Task 3: мост downlink — RTP-packetizer (`sip/bridge.py`)

**Зачем:** мост превращает downlink G.711-кадры в RTP-поток к go2rtc (вариант B) или
кормит exec-эндпоинт (вариант A). **Чистая часть** (RTP seq/ts инкремент, формат src)
TDD-ится сразу; сетевой `start/stop` transport — Task 4 (форма из D-audio-1).

**Files:**
- Create: `custom_components/elektronny_gorod/sip/bridge.py`
- Test: `tests/test_sip_bridge.py`

- [ ] **Step 1: Падающий тест (чистая логика packetizer)**

Create `tests/test_sip_bridge.py`:

```python
"""Unit-тесты чистой логики аудио-моста (sip/bridge.py)."""
from __future__ import annotations

from custom_components.elektronny_gorod.sip.bridge import DownlinkPacketizer


def test_packetizer_increments_seq_and_ts():
    p = DownlinkPacketizer(payload_type=0, ssrc=0x1234)
    pkt1 = p.packetize(b"\xff" * 160)
    pkt2 = p.packetize(b"\xff" * 160)
    # 12-байт RTP header + payload
    assert len(pkt1) == 172 and len(pkt2) == 172
    seq1 = int.from_bytes(pkt1[2:4], "big")
    seq2 = int.from_bytes(pkt2[2:4], "big")
    assert seq2 == seq1 + 1                       # seq инкремент
    ts1 = int.from_bytes(pkt1[4:8], "big")
    ts2 = int.from_bytes(pkt2[4:8], "big")
    assert ts2 - ts1 == 160                       # G.711 8kHz, 20мс = 160


def test_packetizer_payload_type_in_header():
    p = DownlinkPacketizer(payload_type=8, ssrc=1)  # PCMA
    pkt = p.packetize(b"\x00" * 160)
    assert pkt[1] & 0x7F == 8
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_sip_bridge.py -q`
Expected: FAIL — `ModuleNotFoundError: ...sip.bridge`

- [ ] **Step 3: Реализовать чистую логику в `sip/bridge.py`**

Create `custom_components/elektronny_gorod/sip/bridge.py`:

```python
"""Аудио-мост two-way: downlink G.711 из SipManager → go2rtc (audio-bridge-design.md).

Slice 1 (downlink): packetize кадры гостя в RTP → отдать go2rtc (механизм D-audio-1).
Чистая логика (RTP seq/ts) — здесь; сетевой transport (start/stop) — Task 4.
"""
from __future__ import annotations

from .rtp import FRAME_BYTES, build_rtp_packet


class DownlinkPacketizer:
    """Превращает downlink G.711-кадры в RTP-пакеты (seq/ts инкремент)."""

    def __init__(self, payload_type: int, ssrc: int) -> None:
        self._pt = payload_type
        self._ssrc = ssrc
        self._seq = 0
        self._ts = 0

    def packetize(self, frame: bytes) -> bytes:
        pkt = build_rtp_packet(self._pt, self._seq, self._ts, self._ssrc, frame)
        self._seq = (self._seq + 1) & 0xFFFF
        self._ts = (self._ts + FRAME_BYTES) & 0xFFFFFFFF
        return pkt
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_sip_bridge.py -q`
Expected: PASS (2 теста)

- [ ] **Step 5: Прогнать весь suite — нет регрессий**

Run: `PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: все прежние + новые зелёные

- [ ] **Step 6: Commit**

```bash
git add custom_components/elektronny_gorod/sip/bridge.py tests/test_sip_bridge.py
git commit -m "feat(sip): аудио-мост downlink — RTP-packetizer (чистая логика)"
```

---

## Roadmap (после Task 1 PoC — финализируется по D-audio-1)

Сетевые задачи — форма зависит от выбранного механизма (A exec / B RTP). Bite-sized
шаги дописываются после Task 1, по аналогии с Slice 0-network ([plan.md](plan.md)).

### Task 4 — transport + lifecycle (network, live-verify)
- `sip/bridge.py`: добавить сетевой слой выбранного механизма:
  - **B (RTP):** `AudioBridge` (asyncio `DatagramProtocol`) — на каждый
    `feed_downlink` шлёт `DownlinkPacketizer.packetize(frame)` UDP-ом на go2rtc-порт.
  - **A (exec):** мост поднимает TCP-сервер, отдающий сырой PCMU; go2rtc exec тянет.
- `sip/manager.py`: на answer — `on_downlink = bridge.feed_downlink` (вместо счётчика);
  на teardown — `bridge.stop()`.
- `sip/call_controller.py`: на answer — `upsert_audio_stream(...)` (src из D-audio-1,
  имя `eg_intercom_talk`), создать мост, прокинуть в `SipManager`; на hangup —
  `remove_audio_stream(...)` + `bridge.stop()`. go2rtc-конфиг берётся из entry
  (`_get_go2rtc_cfg` уже есть). Сбой upsert → log + degrade (вызов живёт).
- **Live-verify:** деплой на прод (копирование + `docker restart`), звонок →
  открыть Advanced Camera Card стрима `eg_intercom_talk` → **слышим гостя**.

### Task 5 — docs + Advanced Camera Card (трубка)
- `README.md` фичи: пример карты (`type: custom:advanced-camera-card`, go2rtc live,
  стрим `eg_intercom_talk`) — динамик (микрофон — Slice 2). HTTPS-напоминание.
- `CHANGELOG.md` `[Unreleased]`: downlink (слышим гостя).
- `project-map.md`: новый `sip/bridge.py`, `test_sip_bridge.py`, `test_go2rtc_audio.py`.

---

## Self-Review

**1. Spec coverage (audio-bridge-design.md → план):**
- §4 `sip/bridge.py` (мост) → Task 3 (чистая) + Task 4 (transport). ✅
- §4 `go2rtc.py` audio upsert → Task 2. ✅
- §4 Advanced Camera Card → Task 5. ✅
- §5 downlink flow → Task 3+4. ✅
- §6 Slice 1 + PoC A/B → Task 1 (PoC), Task 4 (выбранный механизм). ✅
- §7 lifecycle (answer/hangup, degrade) → Task 4. ✅
- §9 testing (unit packetizer + go2rtc mock, live) → Task 2/3 (unit), Task 4 (live). ✅
- §10 PoC-вопросы → Task 1. ✅
- Gap (намеренный): Task 4–5 не bite-sized — зависят от D-audio-1 (как Slice 0-network
  в plan.md). Зафиксировано в Scope. ✅
- Out of scope (Slice 2): uplink/микрофон, ADR-0012 — не здесь. ✅

**2. Placeholder scan:** Task 1–3 — полный код/команды/ожидаемый вывод. Roadmap-секции
явно «после Task 1» (корректная инкрементальность research-heavy, не плейсхолдеры). ✅

**3. Type consistency:** `upsert_audio_stream(base_url, name, src, session, headers)` /
`remove_audio_stream` / `DownlinkPacketizer(payload_type, ssrc).packetize(frame)` /
`build_rtp_packet`, `FRAME_BYTES` (из rtp.py) — согласованы между тестами, реализацией,
roadmap. ✅
