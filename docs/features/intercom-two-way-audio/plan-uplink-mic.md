# Slice 2 Uplink (микрофон) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Довести живой микрофон браузера до домофона — построить механизм-независимый каркас `UplinkSink` (resample→G.711→джиттер-буфер) и PoC-пробой (D-audio-2) выбрать транспорт микрофона.

**Architecture:** `UplinkSink` — чистая логика за узкой границей `feed(pcm, rate)` / `next_frame()`: ресемпл src→8кГц (`audioop.ratecv`), кодек G.711 (`sip/audio.py:pcm_to_g711`), джиттер-буфер кадрами 160 B/20 мс с drop-oldest. `SipManager.uplink_provider` (уже дёргается `RtpSession.run_uplink` каждые 20 мс; `None`→тишина) подключается к `sink.next_frame`. Транспорт микрофона (HA WS-binary / go2rtc WHIP-pull / exec-backchannel) выбирается PoC и встаёт за границей `feed()` без переписывания SIP/RTP.

**Tech Stack:** Python 3.13, asyncio, Home Assistant custom integration, `audioop-lts` (resample+G.711), pytest (`PYTHONPATH=. .venv/bin/pytest`). Ветка `feat/intercom-uplink-mic`.

**Scope этого плана = Phase A (каркас) + Phase B (PoC).** Транспорт-специфичный код (Lovelace-карта, WS-команда / go2rtc-upsert, wiring sink в контроллер, hands-free polish — Slice 2b) **не может быть написан до выбора механизма** и оформляется **отдельным планом после PoC** (см. «Phase C — после PoC» в конце).

---

## File Structure

| Файл | Ответственность | Действие |
|---|---|---|
| `custom_components/elektronny_gorod/sip/uplink.py` | `UplinkSink` — чистая логика приёма аудио микрофона → G.711-кадры для RTP-uplink | Create |
| `tests/test_sip_uplink.py` | Юнит-тесты `UplinkSink` (framing, resample, overflow, FIFO, clear) | Create |
| `custom_components/elektronny_gorod/sip/audio.py` | `pcm_to_g711` — расстейдж (теперь используется в рантайме `uplink.py`) | Modify (docstring) |
| `research/intercom-call-probe/probe_mic_uplink.py` | PoC-проба: uplink-источник harness'а ← `UplinkSink` ← кандидат-транспорт | Create |
| `research/intercom-call-probe/mic_ws_probe.html` | Минимальная страница `getUserMedia` → WS (кандидат #1) для пробы | Create |
| `research/intercom-call-probe/FINDINGS.md` | Раздел D-audio-2: результат пробы, выбор механизма | Modify |
| `docs/decisions/0013-uplink-mic-transport.md` | ADR: выбранный транспорт + обоснование (заполняется по итогу PoC) | Create |

---

## Task 1: `UplinkSink` — каркас приёма микрофона → G.711-кадры

Чистая логика, без сети/SIP. Зеркало downlink-`AudioBridge`, но обратная ветка: транспорт зовёт `feed(pcm, rate)`, `uplink_provider` зовёт `next_frame()`.

**Files:**
- Create: `custom_components/elektronny_gorod/sip/uplink.py`
- Test: `tests/test_sip_uplink.py`

Опорные факты (проверено в коде):
- `sip/audio.py`: `pcm_to_g711(pcm: bytes, payload_type: int) -> bytes`; `PCMU_PAYLOAD_TYPE=0` (µ-law, тишина=`0xFF`), `PCMA_PAYLOAD_TYPE=8` (A-law, тишина=`0xD5`); `_SAMPLE_WIDTH=2`. `audioop.lin2ulaw(b"\x00\x00", 2) == b"\xff"`, `lin2alaw(b"\x00\x00", 2) == b"\xd5"`.
- `sip/rtp.py`: `FRAME_BYTES=160` (G.711 8кГц 20мс), `frame_provider() -> bytes|None`, `None`→тишина-keepalive.
- `audioop.ratecv(fragment, width, nchannels, inrate, outrate, state)` → `(fragment, newstate)`; `state` (изначально `None`) надо сохранять между вызовами.

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_sip_uplink.py
"""Юнит-тесты UplinkSink (sip/uplink.py) — чистая логика обратной ветки uplink.

Транспорт микрофона зовёт feed(pcm, rate); SipManager.uplink_provider зовёт
next_frame() каждые 20мс. Сеть/транспорт — за этой границей (живой звонок/PoC).
"""
from __future__ import annotations

import audioop

from custom_components.elektronny_gorod.sip.uplink import UplinkSink

_PCMU = 0
_PCMA = 8


def test_feed_8k_silence_yields_one_pcmu_frame():
    # 160 сэмплов 16-бит тишины @ 8кГц = 320 байт → 1 кадр G.711 (µ-law тишина = 0xFF).
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x00\x00" * 160, 8000)
    frame = sink.next_frame()
    assert frame == b"\xff" * 160
    assert sink.next_frame() is None  # буфер опустел


def test_feed_8k_silence_yields_one_pcma_frame():
    sink = UplinkSink(_PCMA)
    sink.feed(b"\x00\x00" * 160, 8000)
    assert sink.next_frame() == b"\xd5" * 160  # A-law тишина


def test_next_frame_none_when_empty():
    assert UplinkSink(_PCMU).next_frame() is None


def test_partial_frame_accumulates_across_feeds():
    # 80 сэмплов (160 байт PCM @ 8к) → пол-кадра G.711 (80 байт) → ещё нет кадра.
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x00\x00" * 80, 8000)
    assert sink.next_frame() is None  # < 160 байт G.711 накоплено
    sink.feed(b"\x00\x00" * 80, 8000)  # ещё 80 → суммарно 160 → 1 кадр
    assert sink.next_frame() == b"\xff" * 160
    assert sink.next_frame() is None


def test_fifo_order_multiple_frames():
    # Два разных кадра: тишина (0x00→0xFF), затем max-амплитуда → разный G.711.
    sink = UplinkSink(_PCMU)
    loud = audioop.lin2ulaw(b"\x00\x7f" * 160, 2)  # ненулевой PCM → не 0xFF
    sink.feed(b"\x00\x00" * 160, 8000)            # кадр A (тишина)
    sink.feed(b"\x00\x7f" * 160, 8000)            # кадр B (громкий)
    assert sink.next_frame() == b"\xff" * 160      # A первым (FIFO)
    assert sink.next_frame() == loud               # B вторым
    assert sink.next_frame() is None


def test_resample_48k_to_8k_produces_frames():
    # 48кГц → 8к: 9600 сэмплов (0.2с) → ~1600 сэмплов 8к → ~10 кадров по 160.
    # Допуск ±1 кадр (прайминг фильтра ratecv); без ресемпла было бы ~60 кадров.
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x00\x00" * 9600, 48000)
    frames = []
    while (f := sink.next_frame()) is not None:
        frames.append(f)
    assert 9 <= len(frames) <= 11  # ресемпл произошёл (не 60)
    assert all(len(f) == 160 for f in frames)


def test_resample_state_persists_across_feeds():
    # Тот же вход одним куском vs двумя — ресемпл со state даёт тот же суммарный поток.
    one = UplinkSink(_PCMU)
    one.feed(b"\x11\x11" * 9600, 48000)
    out_one = b""
    while (f := one.next_frame()) is not None:
        out_one += f

    two = UplinkSink(_PCMU)
    two.feed(b"\x11\x11" * 4800, 48000)
    two.feed(b"\x11\x11" * 4800, 48000)
    out_two = b""
    while (f := two.next_frame()) is not None:
        out_two += f

    assert out_one == out_two  # persistent ratecv state → бесшовная склейка


def test_overflow_drops_oldest():
    # Буфер ограничен _MAX_FRAMES; переполнение выкидывает старейшие (low-latency).
    from custom_components.elektronny_gorod.sip.uplink import MAX_FRAMES
    sink = UplinkSink(_PCMU)
    # Кадр-маркеры: первый блок тишина (0xFF), последний — громкий (не 0xFF).
    sink.feed(b"\x00\x00" * 160 * (MAX_FRAMES + 5), 8000)   # тишина: переполнит буфер
    sink.feed(b"\x00\x7f" * 160, 8000)                      # 1 громкий кадр в конец
    drained = []
    while (f := sink.next_frame()) is not None:
        drained.append(f)
    assert len(drained) == MAX_FRAMES          # не больше предела
    assert drained[-1] == audioop.lin2ulaw(b"\x00\x7f" * 160, 2)  # новейший уцелел
    assert drained[0] == b"\xff" * 160          # старейшие (тишина) частично сброшены, но FIFO


def test_clear_resets_buffer_and_state():
    sink = UplinkSink(_PCMU)
    sink.feed(b"\x00\x00" * 160, 8000)
    sink.clear()
    assert sink.next_frame() is None
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_sip_uplink.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named '...sip.uplink'`.

- [ ] **Step 3: Реализовать `UplinkSink`**

```python
# custom_components/elektronny_gorod/sip/uplink.py
"""UplinkSink — приём аудио микрофона (любой транспорт) → G.711-кадры для RTP-uplink.

Механизм-независимая граница (uplink-mic-design.md §2): транспорт микрофона зовёт
feed(pcm, rate); SipManager.uplink_provider зовёт next_frame() каждые 20мс. Чистая
логика (ресемпл/кодек/джиттер-буфер) — тестируема юнитами; сеть/транспорт — за этой
границей (живой звонок/PoC). Зеркало downlink-AudioBridge, обратная ветка.
"""
from __future__ import annotations

import audioop
from collections import deque

from .audio import pcm_to_g711

_TARGET_RATE = 8000
_SAMPLE_WIDTH = 2  # 16-bit signed linear PCM
_CHANNELS = 1
_FRAME_BYTES = 160  # G.711 8кГц, 20мс (== rtp.FRAME_BYTES)
MAX_FRAMES = 50  # джиттер-буфер ~1с; переполнение → drop-oldest (low-latency)


class UplinkSink:
    """Аудио микрофона → resample 8к → G.711 → джиттер-буфер кадрами 160B/20мс."""

    def __init__(self, payload_type: int) -> None:
        self._pt = payload_type
        self._ratecv_state = None  # persistent state audioop.ratecv (бесшовная склейка)
        self._accum = bytearray()  # G.711-байты, ещё не нарезанные в полный кадр
        self._frames: deque[bytes] = deque()

    def feed(self, pcm: bytes, sample_rate: int) -> None:
        """int16 mono PCM @ sample_rate → resample 8к → G.711 → кадры в буфер."""
        if not pcm:
            return
        if sample_rate != _TARGET_RATE:
            pcm, self._ratecv_state = audioop.ratecv(
                pcm, _SAMPLE_WIDTH, _CHANNELS, sample_rate, _TARGET_RATE, self._ratecv_state
            )
        self._accum += pcm_to_g711(pcm, self._pt)
        while len(self._accum) >= _FRAME_BYTES:
            self._frames.append(bytes(self._accum[:_FRAME_BYTES]))
            del self._accum[:_FRAME_BYTES]
            if len(self._frames) > MAX_FRAMES:
                self._frames.popleft()  # drop-oldest

    def next_frame(self) -> bytes | None:
        """Один G.711-кадр 160B для uplink, или None (буфер пуст → тишина-keepalive)."""
        return self._frames.popleft() if self._frames else None

    def clear(self) -> None:
        """Сброс буфера/ресемпл-состояния на teardown вызова."""
        self._ratecv_state = None
        self._accum.clear()
        self._frames.clear()
```

- [ ] **Step 4: Запустить — убедиться, что проходят**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_sip_uplink.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Полный набор не сломан**

Run: `PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: PASS (предыдущие 273 + новые).

- [ ] **Step 6: Commit**

```bash
git add custom_components/elektronny_gorod/sip/uplink.py tests/test_sip_uplink.py
git commit -m "$(cat <<'EOF'
feat(sip): UplinkSink — каркас приёма микрофона → G.711-кадры (Slice 2a)

Механизм-независимая граница uplink (uplink-mic-design.md §2): feed(pcm,rate)
→ resample src→8к (audioop.ratecv, persistent state) → G.711 → джиттер-буфер
160B/20мс с drop-oldest; next_frame() для SipManager.uplink_provider. Чистая
логика, без сети — транспорт микрофона (PoC) встаёт за feed(). Зеркало
downlink-AudioBridge.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Расстейдж `sip/audio.py` (теперь используется в рантайме)

`UplinkSink` импортирует `pcm_to_g711` → `audio.py` и зависимость `audioop-lts` больше **не** staged: они работают в рантайме. Снять staged-маркер из docstring (manifest `audioop-lts` уже на месте — не трогаем).

**Files:**
- Modify: `custom_components/elektronny_gorod/sip/audio.py` (docstring)

- [ ] **Step 1: Обновить docstring модуля**

Заменить блок `STAGED FOR UPLINK SLICE …` на актуальное состояние:

```python
"""G.711 (PCMU/PCMA) <-> 16-bit linear PCM транскод для SIP-аудио домофона.

Домофон оператора шлёт только G.711 (PCMU pt=0 / PCMA pt=8); voip-utils хардкодит
Opus — поэтому транскод наш слой (design.md §3.1). `audioop` удалён из stdlib в
Python 3.13 (PEP 594) → зависимость `audioop-lts` (manifest) возвращает модуль.

`pcm_to_g711` используется в рантайме `sip/uplink.py` (uplink-микрофон → G.711 →
RTP). `g711_to_pcm` (downlink G.711→PCM) — резерв; downlink-транскод сейчас делает
ffmpeg в `bridge.py`, прямой вызов появится при оптимизации одинарного транскода.
"""
```

- [ ] **Step 2: Тесты `audio.py` зелёные (без изменений поведения)**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_sip_audio.py tests/test_sip_uplink.py -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add custom_components/elektronny_gorod/sip/audio.py
git commit -m "$(cat <<'EOF'
docs(sip): расстейдж audio.py — pcm_to_g711 используется в рантайме (UplinkSink)

P1-2 staged-маркер снят: после Task 1 pcm_to_g711 вызывается UplinkSink в
рантайме (uplink-микрофон → G.711), audioop-lts больше не «про запас».

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: PoC-проба D-audio-2 — выбрать транспорт микрофона (живой звонок)

**Процедурная research-задача (не TDD-юнит)** — де-рискинг выбора механизма на живом проде, как D-audio-1 (uplink-mic-design.md §3). Реюзает harness `probe_push_answer.py`: меняет uplink-источник кадров с `load_track_frames` на `UplinkSink.next_frame`, кормимый кандидат-транспортом. Критерий — **домофон слышит микрофон**, hands-free, разговорная латентность.

**Files:**
- Create: `research/intercom-call-probe/probe_mic_uplink.py`
- Create: `research/intercom-call-probe/mic_ws_probe.html`
- Modify: `research/intercom-call-probe/FINDINGS.md` (раздел D-audio-2)
- Create: `docs/decisions/0013-uplink-mic-transport.md`

Порядок проб (uplink-mic-design.md §3): **#1 WS-binary → #2 go2rtc WHIP-pull → #3 exec-backchannel**. Начать с #1 (дешевле, без инфры/TURN).

- [ ] **Step 1: Кандидат #1 — минимальная страница `getUserMedia` → WS**

`research/intercom-call-probe/mic_ws_probe.html`: открыть на телефоне (HTTPS/LAN), захватить микрофон, слать Int16 PCM по WebSocket на пробу. Минимум (AudioWorklet или ScriptProcessor):

```html
<!doctype html><meta charset=utf-8><title>mic probe</title>
<button id=go>start mic</button><pre id=log></pre>
<script>
const log = m => document.getElementById('log').textContent += m + '\n';
document.getElementById('go').onclick = async () => {
  const ws = new WebSocket(`ws://${location.hostname}:8765`);
  ws.binaryType = 'arraybuffer';
  await new Promise(r => ws.onopen = r);
  const stream = await navigator.mediaDevices.getUserMedia(
    { audio: { echoCancellation: true, noiseSuppression: true } });
  const ac = new AudioContext();
  log('sampleRate=' + ac.sampleRate);     // обычно 48000
  ws.send(JSON.stringify({ type: 'start', sample_rate: ac.sampleRate }));
  const src = ac.createMediaStreamSource(stream);
  const node = ac.createScriptProcessor(2048, 1, 0);  // mono in
  node.onaudioprocess = e => {
    const f32 = e.inputBuffer.getChannelData(0);
    const i16 = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++)
      i16[i] = Math.max(-1, Math.min(1, f32[i])) * 0x7fff;
    if (ws.readyState === 1) ws.send(i16.buffer);
  };
  src.connect(node); node.connect(ac.destination);
  log('mic streaming…');
};
</script>
```

- [ ] **Step 2: Проба — uplink-источник harness'а ← UplinkSink ← WS**

`research/intercom-call-probe/probe_mic_uplink.py`: лёгкий websockets-сервер (`:8765`) принимает `{type:start, sample_rate}` + бинарные PCM-кадры → `UplinkSink.feed(pcm, rate)`; параллельно harness `probe_push_answer.py` (режим `ANSWER MIRROR_APP RTP_EARLY`) поднимает живой звонок и в `_rtp` берёт uplink-кадр из `sink.next_frame()` вместо `frames[...]`. Опорные точки для интеграции (из `probe_push_answer.py`): uplink-кадр формируется в цикле `_rtp` (строка ~420 `frame = frames[talk_i % len(frames)] if (answered and frames) else silence`) — заменить на `frame = sink.next_frame() or silence`. Импорт `UplinkSink` из `custom_components` (добавить корень репозитория в `sys.path` пробы) — `pcm_to_g711`/`audioop` уже доступны.

Запуск (на проде, как D-audio-1):
```
cd research/intercom-call-probe
# терминал 1: статика для html (телефон в той же LAN)
python -m http.server 8000
# терминал 2: проба (WS-сервер + FCM-listener + SIP-ответ)
ANSWER=1 MIRROR_APP=1 RTP_EARLY=1 python probe_mic_uplink.py
# на телефоне открыть http(s)://<host>:8000/mic_ws_probe.html → start mic
# позвонить в домофон, проба ответит → ГОВОРИТЬ в телефон, СЛУШАТЬ у домофона
```

- [ ] **Step 3: Критерий приёмки (human-verified)**

Зафиксировать: домофон **слышит микрофон** (да/нет), разборчивость, **латентность** (разговорная?), дропы/джиттер, hands-free против эха. Если #1 проходит → механизм выбран. Если нет (латентность/качество) → перейти к #2 (WHIP-pull), затем #3 (exec-backchannel) по тем же критериям.

- [ ] **Step 4: Записать результат в `FINDINGS.md` (D-audio-2)**

Добавить раздел `## D-audio-2 — uplink transport (PoC 2026-…)`: какой кандидат пробовали, метрики (латентность, качество), вердикт, выбранный механизм. Формат — как D-audio-1. **Без реальных PII** (placeholder'ы для ac/place/адресов; `2090000` — публичный код, не скрабить).

- [ ] **Step 5: Зафиксировать решение — ADR-0013**

`docs/decisions/0013-uplink-mic-transport.md` (шаблон проекта, status `accepted`): контекст (PoC-выбор), решение (выбранный транспорт #1/#2/#3), обоснование (evidence D-audio-2), последствия (что писать в Phase C, зависимости, нужна ли карта/go2rtc.yaml).

- [ ] **Step 6: Commit (research + ADR)**

```bash
git add research/intercom-call-probe/probe_mic_uplink.py \
        research/intercom-call-probe/mic_ws_probe.html \
        research/intercom-call-probe/FINDINGS.md \
        docs/decisions/0013-uplink-mic-transport.md
git commit -m "$(cat <<'EOF'
chore(research): PoC D-audio-2 — выбор транспорта uplink-микрофона

Проба на живом звонке (reuse probe_push_answer harness): uplink-кадры ←
UplinkSink ← кандидат-транспорт. Критерий — домофон слышит микрофон,
hands-free, разговорная латентность. Результат → FINDINGS.md D-audio-2;
выбранный механизм зафиксирован в ADR-0013.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

> ⚠️ Если PoC покажет, что НИ один кандидат не даёт приемлемого hands-free — зафиксировать в ADR-0013 fallback на **push-to-talk** (uplink-mic-design.md §1: PTT — приемлемый запасной), а hands-free отложить в backlog. Каркас `UplinkSink` от этого не меняется.

---

## Phase C — после PoC (отдельный план, НЕ в этом документе)

Транспорт-специфичный продакшн-код пишется **после** выбора механизма (ADR-0013), отдельным `writing-plans`-проходом, т.к. код зависит от победителя:

- **Если #1 (WS-binary):** WS-команда `elektronny_gorod/intercom_uplink/start|stop` (`connection.async_register_binary_handler`) + Lovelace-карта (`getUserMedia`→`hass.connection.socket`) + регистрация JS-ресурса.
- **Если #2 (WHIP-pull):** `go2rtc.py` upsert mic-стрима + ffmpeg-pull в `UplinkSink` + WHIP-карта.
- **Если #3 (exec):** инструкция go2rtc.yaml в README + exec-мост в `UplinkSink` + готовая карта.
- **Общее (все варианты):** wiring `UplinkSink` в `DoorbellCallController` (создать на answer, `uplink_provider`←`sink.next_frame`, `sink.clear()` на teardown hangup/BYE/CANCEL); Slice 2b — hands-free polish (UX mic-toggle, латентность); README + CHANGELOG; CHANGELOG `[Unreleased]`.

---

## Self-Review (выполнено при написании плана)

- **Spec coverage:** §2 каркас → Task 1; §10 расстейдж audio.py → Task 2; §3 PoC + §4 каталог + ADR-0013 → Task 3; §5 wiring + транспорт + §10 карта → Phase C (после PoC, обоснованно отложено). §9 тестирование → Task 1 (unit) + Task 3 (live). Покрыто.
- **Placeholder scan:** код в Task 1/2 полный; Task 3 процедурный (research, не TDD — помечено явно); Phase C отложен с обоснованием (механизм неизвестен до PoC) — это не placeholder, а scope-граница из дизайна.
- **Type consistency:** `UplinkSink(payload_type)`, `feed(pcm, sample_rate)`, `next_frame()->bytes|None`, `clear()`, `MAX_FRAMES` — едины между тестами Task 1 и реализацией; `pcm_to_g711(pcm, payload_type)` совпадает с `audio.py`; `FRAME_BYTES=160` совпадает с `rtp.py`.
