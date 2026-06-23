# Дизайн: uplink-аудио (микрофон браузера → домофон) — Slice 2

- **Date:** 2026-06-23
- **Owner:** Vyacheslav Scherbinin
- **Status:** Approved (brainstorming 2026-06-23) → к writing-plans
- **Предшествует:** [audio-bridge-design.md](audio-bridge-design.md) (§3/§6 Slice 2 заглушка),
  [call-screen-display-design.md](call-screen-display-design.md) (§«микрофон» forward-compat),
  [design.md](design.md) §6.5 (exec-backchannel риск) / §6.6 (bundled go2rtc блокирует exec через REST),
  [call-answer-model.md](call-answer-model.md).
- **Уточняет/заменяет:** Slice-2-заглушку из `audio-bridge-design.md` §6 (там uplink-механизм
  был выбран заранее как `exec`-backchannel; здесь механизм **выбирается PoC**, а не закладывается).

## 1. Цель и scope

Довести **живой микрофон браузера** до домофона: пользователь в HA-фронтенде (удалённо,
4G) говорит — звук слышен на панели домофона. Цель — **hands-free** (полный дуплекс, как в
оригинальном приложении); **push-to-talk** — приемлемый fallback, если hands-free упрётся.

**Что УЖЕ готово (Slice 0/1, live 2026-06-23):**
- Транспорт `интеграция → G.711 RTP → домофон` (на «Ответить» шлём RTP-uplink,
  FreeSWITCH latching, домофон проигрывает то, что мы шлём).
- Кодек PCM→G.711 (`sip/audio.py:pcm_to_g711`, сейчас staged — см. §10).
- Каркас вытягивания кадров: `RtpSession.run_uplink` дёргает `frame_provider()` каждые
  20мс; `None` → тишина-keepalive (`rtp.py`). `SipManager.uplink_provider` — точка вставки.
- Downlink (звук гостя в браузер) через go2rtc + WebRTC-карту (Slice 1).

**Единственный незакрытый хоп:** взять живой микрофон браузера в реальном времени и довести
аудио до Python-процесса интеграции (там → resample → G.711 → отдать в `uplink_provider`).

**Non-goals:** эхоподавление сверх браузерного `echoCancellation`; конференция / несколько
одновременных вызовов (модель first-answer-wins, фикс-порты); замена go2rtc; изменения
downlink-тракта; своя полная WebRTC-реализация как обязательная (только если PoC выберет).

## 2. Архитектура — механизм-независимый каркас (главное решение)

Конкретный транспорт микрофона выбирается **PoC-пробой** (§3). Чтобы выбор не диктовал
архитектуру, вводим **uplink-границу** — за ней любой транспорт встаёт без переделок:

```
[ТРАНСПОРТ микрофона — выбирает PoC]
   #1 WS-binary  |  #2 go2rtc WHIP-pull  |  #3 go2rtc exec-backchannel
        │  сырой PCM (int16 @ src-rate, обычно 48к) ИЛИ уже G.711
        ▼
   UplinkSink (новый, pure-логика):
        resample src→8к (audioop.ratecv, persistent state)
        → G.711 (pcm_to_g711) → джиттер-буфер (drop-oldest)
        next_frame() → 160 B / 20 мс
        ▼
   SipManager.uplink_provider ✅ (уже дёргается 20мс; None → тишина-keepalive)
        ▼
   RtpSession.run_uplink ✅ → RTP G.711 → домофон ✅
```

`UplinkSink` — чистая логика без знания транспорта/SIP: тестируется юнитами (ресемпл, кодек,
пейсинг, переполнение). Транспорт — за узким интерфейсом `feed(chunk)`. Жизненный цикл sink =
активный вызов.

**Почему отдельная граница, а не «прибить» к выбранному транспорту:** uplink исторически
валит гипотезы (§6.5 + REST-блок + 4G/NAT). Граница позволяет пробовать механизмы
«до победного» и заменить проигравший без переписывания SIP/RTP-слоя.

## 3. PoC-проба (первая задача слайса, де-рискинг как D-audio-1)

Проба в `research/intercom-call-probe/` (переиспользует harness `probe_push_answer.py`:
поднимает живой звонок, шлёт uplink-RTP — меняем только источник кадров на кандидата).

**Критерий приёмки (human-verified):** домофон **слышит микрофон** на живом звонке,
hands-free, разговорная латентность, без дропов. Результат → `FINDINGS.md` (D-audio-2).

**Порядок проб** (механизм-независимый каркас принимает победителя):
1. **Проба 1 — #1 WS-binary** (дешевле всего, без инфры/TURN).
2. **Проба 2 — #2 WHIP-producer → RTSP-pull** (если #1 разочарует по латентности/дуплексу
   или нужна родная карта; проверяем 4G+TURN+стрим-таргет).
3. **Проба 3 — #3 exec-backchannel** (если готовы на go2rtc.yaml и #1/#2 не взлетели;
   кодек `#audio=alaw/8000`, ловим баги #2084/#1888).
4. **#4 aiortc** — крайний резерв (конфликт зависимостей `av<17` vs HA `av==17.0.1`,
   нет колёс armv7l).

Выбор механизма по итогу пробы фиксируется в **ADR-0013** (решение архитектурное и
трудно откатываемое — затрагивает frontend-карту, зависимости, go2rtc-конфиг).

## 4. Каталог механизмов (исследовано 2026-06-23, с подтверждением из исходников)

| # | Механизм | Что писать | go2rtc.yaml? | 4G | Карта | Новые deps | Зрелость / риск |
|---|----------|-----------|:---:|---|---|---|---|
| **1** | **HA WS binary-audio** (как Assist): своя карта `getUserMedia`→Int16 PCM по авторизованному HA-WebSocket → bin-handler в интеграции (`connection.async_register_binary_handler`) | карта (~115 стр, копия `audio-recorder.ts`) + ~30 стр бэк | **Нет** | **Без TURN** (тот же WSS) | своя | **нет** (`audioop-lts` уже есть) | API stable-internal (закрыть тестом). Референс: `n-IA-hane/esphome-intercom/intercom_native` |
| **2** | **go2rtc WHIP/WS-producer** (`api/webrtc?dst=` / `api/ws?dst=`): браузер публикует микрофон как producer → тянем `ffmpeg rtsp://go2rtc/<stream>` (go2rtc сам Opus→G.711) | своя WHIP-карта + ffmpeg-pull | **Почти**: нужен существующий стрим-таргет (стрим камеры домофона во Frigate **или** 1 строка yaml) | **Нужен TURN/8555** на publish | своя (WHIP) | нет | Обходит insecure-гейт (WHIP не валидируется) и exec-баги; не «протоптан» под intercom |
| **3** | **go2rtc exec-backchannel** (`exec:#backchannel=1`) — исходный план design.md | exec-скрипт + мост (готовая карта микрофона) | **Да** (через REST заблокирован: `insecure producer`) | TURN/8555 | **готовая** (AlexxIT/advanced-camera-card) | нет | §6.5: #2084 send-only, #1888 multi-consumer; #1932 лечится `#audio=alaw/8000`. Карту писать не надо |
| **4** | **aiortc** WebRTC-peer в интеграции (или `webrtc:ws://`-source go2rtc→aiortc) | aiortc-узел + signaling + карта | Нет (#4a) | TURN всё равно | своя | **aiortc+PyAV ~100МБ** | ⚠️ конфликт `av<17` vs HA `av==17.0.1`; нет колёс armv7l → фактически дисквалифицирован |
| — | rtsp-publish→ffmpeg-listener / «play on camera» (`POST api/streams?dst=&src=`) / `multitrans:` | — | да / n-a | — | — | — | yaml-only / `src`=URL не live-mic / TP-Link-only — не стартеры |

**Два семейства, оба живые:**
- **go2rtc-нативные (#2, #3):** микрофон в той же WebRTC-сессии что видео, кнопка в карте;
  минус — TURN на 4G + стрим-таргет/yaml + upstream-баги (особенно #3).
- **Self-contained (#1, #4):** не трогаем go2rtc/yaml; #1 без TURN (через HA-WS);
  минус — своя карта (#1) или тяжёлая зависимость (#4).

Подтверждённые факты исследования (для справки исполнителю PoC):
- go2rtc `insecure producer`-гейт хардкод, рубит **только** `exec`/`echo`/`expr` и source
  с пробелами; **WHIP/WS-producer (`?dst=`) гейт обходят** (Validate не вызывается).
- `?dst=` НЕ авто-создаёт стрим (`streams.Get` → 404), `?src=` авто-создаёт но требует
  непустой source; пустой стрим без записи в `go2rtc.yaml` через REST создать нельзя →
  для #2 публиковать в **существующий** стрим (камеры домофона во Frigate).
- HA нативный плеер `ha-web-rtc-player.ts` хардкодит `recvonly` → микрофон не шлёт; кнопка
  микрофона только у сторонних карт (AlexxIT/advanced-camera-card) через go2rtc-backchannel.
- HA core camera не получает mic-трек в Python by-design (SDP проксируется в go2rtc).
- HA WS bin-handler (`async_register_binary_handler`) — `@callback`, `(handler_id, unsub)`,
  формат-агностичный (первый байт = handler_id), несущая для Assist STT, сигнатура стабильна
  2023→2026; формат бинарного кадра публично документирован (developers.home-assistant.io).

## 5. Компоненты и границы

| Компонент | Ответственность | Зависит от | Новый? |
|---|---|---|---|
| **`UplinkSink`** (`sip/uplink.py` или расширение `bridge.py`) | `feed(chunk)`: resample src→8к + G.711 + джиттер-буфер; `next_frame()→bytes\|None` для `uplink_provider` | `audio.py`, `audioop` | да |
| **Транспорт-адаптер** (по итогу PoC) | принять микрофон браузера → `sink.feed()`; teardown | UplinkSink, (#1: websocket_api; #2: go2rtc.py) | да |
| **WS-команда** (если #1/#2) | `elektronny_gorod/intercom_uplink/start\|stop` + bin-handler / WHIP-signaling | HA `websocket_api` | да |
| **Lovelace-карта** (если #1/#2) | `getUserMedia` + AudioWorklet → стрим в HA (#1: bin по `hass.connection.socket`; #2: WHIP PeerConnection) | HTTPS (есть) | да |
| `sip/audio.py` (`pcm_to_g711`) | транскод PCM→G.711 — **расстейджить** (§10) | `audioop-lts` | есть |
| `SipManager` wiring | `uplink_provider` ← `sink.next_frame`; создание/teardown sink на answer/hangup | UplinkSink | правка |
| `go2rtc.py` (если #2) | upsert/pull mic-стрима через REST (реюз `_go2rtc_upsert_stream`) | go2rtc REST | правка |

`UplinkSink` проектируется **изолированно** (чистые границы `feed`/`next_frame`, без знания
SIP/транспорта) — тестируемо и переносимо, симметрично downlink-`AudioBridge`.

## 6. Поток данных

Uplink — **отдельный канал** от downlink (НЕ обязан ехать в одной WebRTC-сессии):

```
🎤 микрофон браузера → [транспорт #1/#2/#3] → UplinkSink (resample+G.711+буфер)
   → SipManager.uplink_provider → RtpSession.run_uplink → RTP G.711 → домофон
```

Downlink не меняется: домофон → `on_downlink` → `AudioBridge` → go2rtc → WebRTC-карта → 🔊.

## 7. Обработка ошибок и жизненный цикл

- **Graceful degrade:** нет микрофона / сломан транспорт / пустой буфер → `next_frame()=None`
  → тишина-keepalive (как сейчас). **SIP-разговор на уровне транспорта живёт** (latching не
  рвётся) — не валим приём вызова из-за uplink-сбоя.
- **Переполнение буфера** (медленный consumer / всплеск) → **drop-oldest** (low-latency
  важнее полноты для разговора).
- **Teardown** на `hangup`/`BYE`/`CANCEL`: остановить транспорт, снять WS-хендлер/карту,
  очистить буфер, освободить ресурсы (best-effort, как `AudioBridge.stop`).
- **Один вызов** (фикс-порты SIP/RTP, first-answer-wins) — sink создаётся на answer, единичный.
- `feed`/bin-handler **не должны бросать** на транзиентных ошибках декода (HA снимает
  bin-handler при исключении) — глотать локально + degrade.

## 8. Безопасность / приватность

- Микрофон идёт по **уже-доверенному** каналу: #1 — авторизованный HA-WebSocket (та же
  сессия, что весь UI); #2/#3 — go2rtc (доверенный для видео). Новых секретов нет.
- HTTPS уже есть (hard-gate браузерного микрофона).
- Если #1/#2 — добавляем кастомный JS-ресурс (Lovelace card): отметить в README + security
  (происхождение карты, что она шлёт только аудио по авторизованному каналу).
- go2rtc-креды уже в `SENSITIVE_KEYS`; SIP-креды в uplink-тракт не попадают (гоняем сырой
  PCM/G.711).

## 9. Тестирование

- **Unit (TDD):** `UplinkSink` — ресемпл (golden src→8к), G.711-кодек (golden-кадры),
  пейсинг 20мс/160B, переполнение → drop-oldest; WS-команда register/unregister bin-handler;
  wiring `uplink_provider` ← `sink.next_frame`. Чистая логика — без сети.
- **API-guard (если #1):** регресс-тест, фиксирующий контракт HA `async_register_binary_handler`
  (`(handler_id, unsub)` + байт-префикс) — API stable-internal, ловим breakage обновления HA.
- **Live/PoC:** звонок → говорим → **домофон слышит** (hands-free; для первого зелёного
  push-to-talk достаточно). Сетевой транспорт — live, как `SipManager` (не юнит).
- **Bug fix → тест** (правило проекта `test-coverage.md`).

## 10. Слайсинг

- **Slice 2a — минимальный end-to-end:** PoC выбирает транспорт → `UplinkSink` + адаптер +
  (карта/WS если нужно) → **микрофон слышен в домофоне** (push-to-talk достаточно для первого
  зелёного). Расстейдж `audio.py` + `audioop-lts` (подключить `pcm_to_g711` в рантайм).
- **Slice 2b — hands-free polish:** непрерывный поток, джиттер-буфер, UX mic-toggle/индикация,
  настройка латентности, эхо (опереться на браузерный `echoCancellation`).

## 11. Влияние

- Новый `UplinkSink` (+ транспорт-адаптер); **расстейдж** `sip/audio.py` + manifest
  `audioop-lts` (из P1-2-staged в рантайм).
- Возможно: frontend Lovelace-карта + WS-команда (#1/#2), или `go2rtc.py` upsert mic-стрима
  (#2), или инструкция по go2rtc.yaml в README (#3) — по итогу PoC.
- `SipManager` wiring (`uplink_provider`); `ADR-0013` (выбор механизма); CHANGELOG; README
  (как пользоваться + зависимость карты).
- Существующие entity / config-entry VERSION / downlink-тракт — **не трогаем**.

## Quality gate

`SPEC_READY` — после вычитки пользователем → writing-plans (первая задача плана = PoC D-audio-2).

## Связь

- [audio-bridge-design.md](audio-bridge-design.md) — downlink + общий мост (Slice 1, live).
- [call-screen-display-design.md](call-screen-display-design.md) — показ экрана (Slice 1, live).
- [call-answer-model.md](call-answer-model.md) — модель приёма (register-on-ring, ADR-0012).
- [design.md](design.md) §6.5/§6.6 — исходные риски uplink (exec-backchannel, bundled go2rtc).
- `research/intercom-call-probe/` — harness проб; FINDINGS.md (D-audio-1 готов, D-audio-2 PoC).
