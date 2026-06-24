# Two-way talk по домофону — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Принять входящий вызов домофона из Home Assistant и говорить с гостем у двери (двусторонний SIP-аудио), переиспользуя go2rtc для доставки звука в браузер.

**Architecture:** SIP-UAS внутри интеграции (ручной `asyncio`-модуль на основе `probe`; спайк отверг `voip-utils` как базу — [research-spike.md](research-spike.md) D1) принимает INVITE, держит RTP G.711 за NAT (STUN + symmetric latching). Downlink/uplink мостится в go2rtc (`exec`-backchannel) → готовая WebRTC-карта в браузере = трубка. См. [design.md](design.md).

**Tech Stack:** Python 3.13 (asyncio + socket), `audioop-lts` (G.711 на py3.13), `SipEndpoint` из `voip-utils` (только URI-парсер), go2rtc (`exec`-backchannel), pytest + pytest-homeassistant-custom-component.

---

## Scope этого плана

Фича research-heavy: три развилки нужно снять **экспериментом до** production-кода
SIP-lifecycle:
1. Даёт ли публичный API `voip-utils` переопределить кодек/SDP на G.711 — или fallback на ручной `asyncio`-модуль из `probe`.
2. Тайминг transient-регистрации (успеть к форк-INVITE, не залипнуть в «Занято»).
3. `audioop` удалён из stdlib в Python 3.13 — стратегия транскода.

Поэтому план покрывает **Slice 0 (фундамент)**:
- **Task 1 — Spike** снимает три развилки (research, не TDD).
- **Task 2–3 — TDD** для чистых модулей, которые нужны **независимо** от исхода
  спайка (G.711-транскод, STUN): `voip-utils` хардкодит Opus и не имеет STUN —
  значит эти два слоя наши при любом раскладе.

**SIP-UAS lifecycle, downlink-вывод (Slice 1), uplink через go2rtc (Slice 2),
polish (Slice 3)** — в [roadmap](#roadmap-следующие-слайсы). Их bite-sized задачи
финализируются **после Task 1**, т.к. форма кода зависит от исхода спайка. Не
выдумываем код для неразрешённых развилок.

---

## File Structure

| Файл | Ответственность | Статус |
|---|---|---|
| `custom_components/elektronny_gorod/sip/__init__.py` | маркер пакета SIP-подсистемы | создаётся (Task 2) |
| `custom_components/elektronny_gorod/sip/audio.py` | G.711 (PCMU/PCMA) ↔ linear PCM транскод | создаётся (Task 2) |
| `custom_components/elektronny_gorod/sip/stun.py` | STUN Binding parse (публичный RTP-адрес за NAT) | создаётся (Task 3) |
| `custom_components/elektronny_gorod/manifest.json` | requirements: `audioop-lts` (для `sip/audio.py`). `voip-utils` как базу спайк отверг (D1) — не добавляем | модифицируется (Task 2) |
| `tests/test_sip_audio.py` | unit-тесты транскода | создаётся (Task 2) |
| `tests/test_sip_stun.py` | unit-тесты STUN-parse | создаётся (Task 3) |
| `docs/features/intercom-two-way-audio/research-spike.md` | результаты спайка + 3 решения | создаётся (Task 1) |

> Примечание: design.md называет модуль `sip.py` условно — реально это пакет `sip/`
> (SIP-стек = крупная подсистема, дробится по ответственности: `audio`/`stun`/далее
> `protocol`/`session`). Плоские модули проекта (camera.py, lock.py) — для одиночных
> платформ; SIP оправданно инкапсулируется в пакет.

---

## Task 1: Spike — снять три развилки

**Тип:** research (НЕ TDD). Цель — evidence-based решения, без production-кода.

**Files:**
- Create: `docs/features/intercom-two-way-audio/research-spike.md`
- Modify: `docs/features/intercom-two-way-audio/design.md` (§6 — закрыть открытые вопросы)
- Использует: `research/intercom-call-probe/` (готовый harness)

- [ ] **Step 1: Установить и изучить `voip-utils` API**

```bash
.venv/bin/pip install voip-utils
.venv/bin/python -c "import voip_utils, inspect; print(voip_utils.__file__)"
```

Прочитать исходники `voip_utils/sip.py` и `voip_utils/const.py`. Ответить письменно:
- Класс приёма INVITE (ожид. `SipDatagramProtocol`) — как переопределить SDP-answer?
- `OPUS_PAYLOAD_TYPE` / детектор кодека в SDP — можно ли подменить на PCMU(0)/PCMA(8) через публичный API, или нужен subclass / форк?
- Делает ли `voip-utils` REGISTER + Digest, или только direct-INVITE-listener?

- [ ] **Step 2: Проверить `audioop` на Python 3.13**

```bash
.venv/bin/python -c "import audioop" 2>&1 | head -1   # ожидаемо: ModuleNotFoundError на 3.13
.venv/bin/pip install audioop-lts
.venv/bin/python -c "import audioop; print(audioop.lin2ulaw(b'\\x00\\x00', 2))"  # ожидаемо: байты без ошибки
```

Зафиксировать: `audioop-lts` возвращает рабочий `import audioop` на py3.13. (Если нет — fallback на vendored `voip_utils.pyaudioop`.)

- [ ] **Step 3: Измерить тайминг вызова + протестировать transient-REGISTER**

Прогнать harness `research/intercom-call-probe/` на реальном вызове (нужен живой
звонок в домофон). Инструментировать probe: залогировать монотонные timestamps
`FCM CALL_INCOMING` (probe_fcm) и первого `INVITE` (probe_sip_media). Замерить дельту.
Затем проверить сценарий: стартовать REGISTER **по** приходу FCM (не держать заранее)
и проверить, приходит ли INVITE на свежую регистрацию.

Зафиксировать в `research-spike.md`: дельта FCM→INVITE (мс); успевает ли
transient-register; вывод — стратегия регистрации (`transient-by-FCM` vs
`held-short-window`).

- [ ] **Step 4: Записать решения и обновить спеку**

Создать `research-spike.md` с тремя решениями:
- **D1 (SIP-база):** `voip-utils` ✅ / fallback `asyncio`-модуль из probe — с обоснованием.
- **D2 (регистрация):** стратегия из Step 3.
- **D3 (audioop):** `audioop-lts` ✅ / vendored.

Обновить `design.md` §6: п.1 (тайминг) — заменить «**Риск: тайминг.**» на измеренный
результат + выбранную стратегию; §3.1 — отметить подтверждённый исход развилки voip-utils.

- [ ] **Step 5: Commit**

```bash
git add docs/features/intercom-two-way-audio/research-spike.md docs/features/intercom-two-way-audio/design.md
git commit -m "docs(two-way-audio): спайк — voip-utils API, тайминг, audioop-lts

Снимает 3 развилки Slice 0: SIP-база (voip-utils vs asyncio), стратегия
transient-регистрации, audioop на Python 3.13. Закрывает design.md §6 п.1.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: G.711 ↔ PCM транскод (`sip/audio.py`)

**Зачем:** `voip-utils` хардкодит Opus; домофон шлёт только G.711 (PCMU pt=0 / PCMA
pt=8). Транскод — наш слой при любом исходе спайка. `audioop` удалён из py3.13 →
зависимость `audioop-lts`.

**Files:**
- Create: `custom_components/elektronny_gorod/sip/__init__.py`
- Create: `custom_components/elektronny_gorod/sip/audio.py`
- Modify: `custom_components/elektronny_gorod/manifest.json:14-16` (requirements)
- Test: `tests/test_sip_audio.py`

- [ ] **Step 1: Добавить `audioop-lts` в manifest и установить**

`audioop` удалён из stdlib в Python 3.13 (PEP 594) → backport нужен для `sip/audio.py`.
`voip-utils` НЕ добавляем сейчас (в Task 2–3 не используется; версию подтвердит
спайк Task 1) — добавим в Slice 0-lifecycle.

Изменить `manifest.json` requirements:

```json
  "requirements": [
    "firebase-messaging>=0.4",
    "audioop-lts>=0.2.1;python_version>='3.13'"
  ],
```

```bash
.venv/bin/pip install "audioop-lts>=0.2.1"
```

- [ ] **Step 2: Создать пустой маркер пакета**

Create `custom_components/elektronny_gorod/sip/__init__.py`:

```python
"""SIP-подсистема: приём вызова домофона и двусторонний аудио (design.md)."""
```

- [ ] **Step 3: Написать падающий тест**

Create `tests/test_sip_audio.py`:

```python
"""Unit-тесты G.711 (PCMU/PCMA) <-> PCM транскода (sip/audio.py)."""
from __future__ import annotations

import pytest

from custom_components.elektronny_gorod.sip.audio import (
    PCMA_PAYLOAD_TYPE,
    PCMU_PAYLOAD_TYPE,
    g711_to_pcm,
    pcm_to_g711,
)


@pytest.mark.parametrize("pt", [PCMU_PAYLOAD_TYPE, PCMA_PAYLOAD_TYPE])
def test_g711_roundtrip_reaches_fixed_point(pt: int) -> None:
    # G.711 lossy: первый decode->encode может канонизировать избыточный код
    # (µ-law: 0x7F и 0xFF оба декодируются в 0 -> канон 0xFF). Но второй проход
    # уже стабилен — транскод не дрейфует при повторной переупаковке.
    g711 = bytes(range(256))  # все кодовые точки
    once = pcm_to_g711(g711_to_pcm(g711, pt), pt)
    twice = pcm_to_g711(g711_to_pcm(once, pt), pt)
    assert twice == once


@pytest.mark.parametrize("pt", [PCMU_PAYLOAD_TYPE, PCMA_PAYLOAD_TYPE])
def test_decode_doubles_byte_width(pt: int) -> None:
    # 8-bit G.711 -> 16-bit linear PCM = вдвое больше байт.
    assert len(g711_to_pcm(bytes(160), pt)) == 320


def test_unsupported_payload_type_raises() -> None:
    with pytest.raises(ValueError):
        g711_to_pcm(b"\x00", 99)
    with pytest.raises(ValueError):
        pcm_to_g711(b"\x00\x00", 99)
```

- [ ] **Step 4: Запустить тест — убедиться, что падает**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_sip_audio.py -v`
Expected: FAIL — `ModuleNotFoundError: ...sip.audio`

- [ ] **Step 5: Реализовать `sip/audio.py`**

Create `custom_components/elektronny_gorod/sip/audio.py`:

```python
"""G.711 (PCMU/PCMA) <-> 16-bit linear PCM транскод для SIP-аудио домофона.

Домофон оператора шлёт только G.711 (PCMU pt=0 / PCMA pt=8); voip-utils хардкодит
Opus — поэтому транскод наш слой (design.md §3.1). `audioop` удалён из stdlib в
Python 3.13 (PEP 594) → зависимость `audioop-lts` (manifest) возвращает модуль.
"""
from __future__ import annotations

import audioop  # audioop-lts на py3.13+

PCMU_PAYLOAD_TYPE = 0
PCMA_PAYLOAD_TYPE = 8
_SAMPLE_WIDTH = 2  # 16-bit signed linear PCM


def g711_to_pcm(data: bytes, payload_type: int) -> bytes:
    """G.711 байты -> 16-bit linear PCM (downlink: звук гостя)."""
    if payload_type == PCMU_PAYLOAD_TYPE:
        return audioop.ulaw2lin(data, _SAMPLE_WIDTH)
    if payload_type == PCMA_PAYLOAD_TYPE:
        return audioop.alaw2lin(data, _SAMPLE_WIDTH)
    raise ValueError(f"unsupported G.711 payload type: {payload_type}")


def pcm_to_g711(pcm: bytes, payload_type: int) -> bytes:
    """16-bit linear PCM -> G.711 байты (uplink: микрофон -> домофон)."""
    if payload_type == PCMU_PAYLOAD_TYPE:
        return audioop.lin2ulaw(pcm, _SAMPLE_WIDTH)
    if payload_type == PCMA_PAYLOAD_TYPE:
        return audioop.lin2alaw(pcm, _SAMPLE_WIDTH)
    raise ValueError(f"unsupported G.711 payload type: {payload_type}")
```

- [ ] **Step 6: Запустить тест — убедиться, что проходит**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_sip_audio.py -v`
Expected: PASS (5 тестов: 2+2 параметризованных + 1)

- [ ] **Step 7: Commit**

```bash
git add custom_components/elektronny_gorod/sip/ custom_components/elektronny_gorod/manifest.json tests/test_sip_audio.py
git commit -m "feat(sip): G.711 PCMU/PCMA <-> PCM транскод + deps

Slice 0 фундамент two-way talk: наш audio-слой (voip-utils хардкодит Opus,
домофон — только G.711). audioop-lts для Python 3.13. См. design.md §3.1.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: STUN Binding parse (`sip/stun.py`)

**Зачем:** за symmetric NAT нужен публичный RTP-адрес для SDP `c=` (downlink доходит
через latching). `voip-utils` STUN не имеет — наш слой. Parse-функция чистая и
юнит-тестируемая; сетевой `discover` (socket I/O) — тонкая обёртка, тестируется
позже в интеграции.

**Files:**
- Create: `custom_components/elektronny_gorod/sip/stun.py`
- Test: `tests/test_sip_stun.py`

- [ ] **Step 1: Написать падающий тест**

Create `tests/test_sip_stun.py`:

```python
"""Unit-тесты STUN Binding Response parse (sip/stun.py)."""
from __future__ import annotations

import socket
import struct

from custom_components.elektronny_gorod.sip.stun import parse_stun_binding_response

_MAGIC = 0x2112A442


def _build_xor_mapped_response(ip: str, port: int) -> bytes:
    # XOR-MAPPED-ADDRESS (0x0020): reserved(1) family(1=IPv4) X-Port(2) X-Addr(4).
    xport = port ^ (_MAGIC >> 16)
    xaddr = struct.unpack("!I", socket.inet_aton(ip))[0] ^ _MAGIC
    value = struct.pack("!BBHI", 0, 0x01, xport, xaddr)
    attr = struct.pack("!HH", 0x0020, len(value)) + value
    header = struct.pack("!HHI", 0x0101, len(attr), _MAGIC) + b"\x00" * 12
    return header + attr


def test_parse_xor_mapped_address() -> None:
    assert parse_stun_binding_response(
        _build_xor_mapped_response("203.0.113.5", 40016)
    ) == ("203.0.113.5", 40016)


def test_parse_returns_none_on_short_packet() -> None:
    assert parse_stun_binding_response(b"\x00" * 10) is None


def test_parse_returns_none_without_address_attribute() -> None:
    header = struct.pack("!HHI", 0x0101, 0, _MAGIC) + b"\x00" * 12
    assert parse_stun_binding_response(header) is None
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_sip_stun.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_stun_binding_response'`

- [ ] **Step 3: Реализовать `sip/stun.py`**

Create `custom_components/elektronny_gorod/sip/stun.py`:

```python
"""STUN Binding Response parse — публичный RTP-адрес за NAT для SDP `c=`.

Источник логики — probe_sip_media.py `_parse_stun`. Поддержка XOR-MAPPED-ADDRESS
(0x0020, RFC 5389) и legacy MAPPED-ADDRESS (0x0001). Magic cookie 0x2112A442.
"""
from __future__ import annotations

import socket
import struct

_MAGIC = 0x2112A442


def parse_stun_binding_response(data: bytes) -> tuple[str, int] | None:
    """Разобрать STUN Binding Response -> (public_ip, public_port) или None."""
    if len(data) < 20:
        return None
    i = 20
    while i + 4 <= len(data):
        atype, alen = struct.unpack("!HH", data[i : i + 4])
        i += 4
        val = data[i : i + alen]
        i += alen + ((4 - alen % 4) % 4)
        if atype in (0x0020, 0x0001) and len(val) >= 8:
            if atype == 0x0020:  # XOR-MAPPED-ADDRESS
                port = struct.unpack("!H", val[2:4])[0] ^ (_MAGIC >> 16)
                addr = struct.unpack("!I", val[4:8])[0] ^ _MAGIC
            else:  # MAPPED-ADDRESS (legacy)
                port = struct.unpack("!H", val[2:4])[0]
                addr = struct.unpack("!I", val[4:8])[0]
            return socket.inet_ntoa(struct.pack("!I", addr)), port
    return None
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_sip_stun.py -v`
Expected: PASS (3 теста)

- [ ] **Step 5: Прогнать весь suite — нет регрессий**

Run: `PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: все прежние тесты + новые зелёные

- [ ] **Step 6: Commit**

```bash
git add custom_components/elektronny_gorod/sip/stun.py tests/test_sip_stun.py
git commit -m "feat(sip): STUN Binding parse для NAT-обхода RTP

Публичный RTP-адрес (XOR-MAPPED-ADDRESS) для SDP c= -> downlink за symmetric
NAT через latching. Из probe_sip_media.py. Slice 0 фундамент. design.md §2.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Roadmap (следующие слайсы)

Bite-sized задачи финализируются **после Task 1** (форма зависит от исхода спайка).

### Slice 0-lifecycle — чистые юнит-тестируемые модули (без сети, без звонка)
> D1 решён (спайк): база — `asyncio`-модуль из `probe`, НЕ `voip-utils`.
> Эти задачи извлекают из `probe` чистую логику в тестируемые функции. Сетевые
> части (REGISTER-transport, RTP-loop, STUN-discover, transient-register по D2) —
> следующий слайс (часть ждёт живого звонка).

- **L1 — `sip/digest.py`:** `md5()`, `digest_response()` (RFC 2617 Digest MD5,
  qop/non-qop), `build_authorization()` (заголовок). Из `probe_sip.py:52-64,162-172`.
  Тест: golden-vector ha1/ha2/response для известных user/realm/pass/nonce.
- **L2 — `sip/sdp.py`:** `parse_sdp()` (conn_ip, media-линии, rtpmap — из
  `probe_sip_media.py:120-132`), `build_g711_answer(media_ip, port, pt, codec)`
  (SDP 200 OK для G.711 — из `probe_sip_media.py:287-298`). Тест: parse реального
  offer-а домофона (G.711+telephone-event), build даёт корректный `m=audio`/rtpmap.
- **L3 — `sip/message.py`:** `parse_sip_headers()` — раскладывает raw SIP на
  request-line + headers, 🔴 **сохраняя множественные `Via`/`Record-Route` списком**
  (урок спайка: dict теряет). Тест: 2× `Via` + 2× `Record-Route` → оба сохранены.
- **L4 — `sip/dialog.py`:** `DialogState` (callid, local/remote с тегами, target,
  route[], addr — из INVITE), `build_200_ok(invite, sdp_body)` (эхо **всех**
  Via/Record-Route + To-tag — из `probe_sip_media.py:255-310`), `build_bye(dialog)`
  (из `probe_sip_media.py:377-399`). Тест: 200 OK эхо-ит оба Via и оба Record-Route
  дословно + добавляет To-tag; BYE адресован remote Contact с Route из Record-Route.

### Slice 0-network — следующий слайс (модель **REGISTER-on-answer**, доказано pcap)
> См. [call-answer-model.md](call-answer-model.md). Held-регистрация — отвергнута.
- `sip/protocol.py` (`asyncio.DatagramProtocol`): **НЕ держим регистрацию**. По сервису
  `answer` (в окне `CallInvalidated` ~30с) → `REGISTER` (Expires=30, проприет. push-params:
  `app-id=com.novotelecom.domophone;pn-type=google;pn-tok=<fcm>`) → приём `INVITE` →
  `200 OK` **мгновенно** (локальный SDP, G.711, `a=rtcp:<sep>`) → **сразу** RTP uplink +
  keepalive (активировать latching) → downlink. `SipManager` фасад (`async_answer`/`async_hangup`).
- **НЕ нужны:** STUN (локальный SDP + FreeSWITCH latching), held-регистрация,
  183/early-media/session-timers (реверс: приложение их не использует).
- Видео при ответе — go2rtc (отдельно), как «подгрузка видео» в приложении.

### Slice 1 — downlink (прослушка), Фаза B
- FCM `CALL_INCOMING` (из `fcm.py`) → `SipManager.async_answer()` по сервису/кнопке.
- Downlink RTP G.711 → PCM (`sip/audio.py`) → вывод в HA (go2rtc rtsp-source от `sip.py` ИЛИ `media_player` — выбрать на старте Slice 1).
- Сервис `elektronny_gorod.answer`. Проверяемо: **слышим гостя**.

### Slice 2 — uplink (полный two-way), Фаза C
- 🔴 PoC go2rtc `exec`-backchannel ДО кода (риск design.md §6.5/§6.6: `send-only` баг + bundled go2rtc блокирует exec через REST → писать в `go2rtc.yaml`).
- exec-bridge: go2rtc stdin (микрофон PCMA) → `sip.py` uplink; stdout ← downlink.
- WebRTC-карта `custom:webrtc-camera` (AlexxIT/WebRTC) — документировать как зависимость пользователя; HTTPS обязателен.
- Сервисы `answer`/`hangup`, `binary_sensor` «вызов активен». Проверяемо: **полный разговор**.

### Slice 3 — polish
- Открытие двери в разговоре (REST `accessControlOpen` уже есть / DTMF telephone-event).
- Согласование авто-`ended` с `event.py` по `CallInvalidated`.
- Security: SIP-`password`/`realm` → `SENSITIVE_KEYS`/`TO_REDACT`; diagnostics.
- ADR-0012 (big change), docs sync (project-map, api-reference, CHANGELOG), тесты.

---

## Self-Review

**1. Spec coverage (design.md → план):**
- §3.1 SIP-стек (voip-utils + G.711/REGISTER/STUN) → Task 1 (D1), Task 2 (G.711), Task 3 (STUN), roadmap Slice 0 (REGISTER/lifecycle). ✅
- §6 открытые вопросы → Task 1 спайк (п.1 тайминг, п.3.1 voip-utils, audioop). ✅
- §3.2 целевая трубка / §6.5–6.6 go2rtc риски → roadmap Slice 2 (PoC до кода). ✅
- §5 фазирование → план Slice 0 + roadmap Slice 1–3. ✅
- §8 security (redact SIP-пароль), ADR-0012 → roadmap Slice 3. ✅
- Gap (намеренный): детальный код Slice 0-lifecycle / Slice 1–3 не bite-sized — зависит от Task 1. Зафиксировано в [Scope](#scope-этого-плана). ✅

**2. Placeholder scan:** Task 1–3 содержат полный код/команды/ожидаемый вывод.
Roadmap-секции явно помечены как «после Task 1» — это не плейсхолдеры, а корректная
инкрементальность research-heavy фичи. ✅

**3. Type consistency:** `PCMU_PAYLOAD_TYPE`/`PCMA_PAYLOAD_TYPE`, `g711_to_pcm`/
`pcm_to_g711`, `parse_stun_binding_response` — имена согласованы между тестами и
реализацией во всех задачах. ✅
