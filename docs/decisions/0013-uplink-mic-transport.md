# ADR-0013: Транспорт uplink-микрофона — HA WebSocket binary-audio (#1)

- **Status:** accepted
- **Date:** 2026-06-24
- **Owner:** SIP / two-way audio
- **Связь:** [uplink-mic-design.md](../features/intercom-two-way-audio/uplink-mic-design.md)
  (каталог механизмов), [audio-bridge-design.md](../features/intercom-two-way-audio/audio-bridge-design.md),
  PoC D-audio-2 ([FINDINGS.md](../../research/intercom-call-probe/FINDINGS.md)).

## Context

Slice 2 (микрофон → домофон): не хватает одного хопа — доставить **живой микрофон
браузера** в Python-процесс интеграции (там → resample → G.711 → RTP-uplink, готово).
Дизайн ([uplink-mic-design.md](../features/intercom-two-way-audio/uplink-mic-design.md))
свёл выбор к каталогу механизмов; финал — по PoC D-audio-2:

- **#1 HA WS-binary** — своя Lovelace-карта `getUserMedia` → Int16 PCM по
  авторизованному HA-WebSocket → bin-handler в интеграции. Без go2rtc/TURN.
- **#2 go2rtc WHIP-pull** — браузер публикует микрофон в go2rtc, тянем RTSP. Нужен
  стрим-таргет/yaml + TURN на 4G.
- **#3 go2rtc exec-backchannel** — `exec:#backchannel=1`. Заблокирован через REST на
  Frigate-go2rtc + upstream-баги (§6.5) + TURN.
- **#4 aiortc** — конфликт `av<17` vs HA `av==17.0.1`, нет колёс armv7l → дисквалифицирован.

## Decision

Выбран **механизм #1 — HA WebSocket binary-audio** (паттерн голосового ассистента
HA: `connection.async_register_binary_handler`).

**Обоснование (evidence D-audio-2):**
- **Серверный аудио-тракт доказан** (loopback-самотест, синтетический тон через
  `UplinkSink`-логику → RTP → декод): дрейф пейсинга **3мс / 9с**, **0 провалов**,
  тон цел. Дрейф-компенсированный пейсинг устранил заикания.
- **Live:** микрофон дошёл до домофона (1-я сессия — пользователь слышал себя у двери).
- Сбои живого вызова (`downlink=0`, флака INVITE) локализованы как **SIP/operator-
  latching + NAT + register-модель + конкуренция с прод-интеграцией** — это среда/
  harness пробы, **не транспорт #1**. Прод-интеграция (register-on-ring, локальный SDP,
  latching) принимает вызовы надёжно.
- #1 — единственный, кто одновременно: **не трогает go2rtc/go2rtc.yaml**, **без TURN**
  (тот же авторизованный HA-WS, что весь UI, 4G-friendly), **без новых зависимостей**
  (`audioop-lts` уже есть), **pure-Python** (HA Container).

## Consequences

**Phase C (продакшн, отдельный план):**
- WS-команда `elektronny_gorod/intercom_uplink` (`async_register_binary_handler`)
  → `controller.feed_uplink` → `UplinkSink` → `SipManager.uplink_provider`. Stop —
  закрытие вкладки/unsubscribe (HA снимает binary-handler автоматически); явная
  `stop`-команда — polish следующего слайса (handler-слоты idle-копятся при многократном
  toggle в одной сессии, не утечка данных).
- Lovelace-карта: `getUserMedia` + AudioWorklet → Int16 PCM по `hass.connection.socket`
  (копия `audio-recorder.ts`); регистрация JS-ресурса.
- Wiring `UplinkSink` в `DoorbellCallController` (создать на answer, `uplink_provider` ←
  `sink.next_frame`, `clear()` на teardown).
- 🔴 **Дрейф-фикс `sip/rtp.py:run_uplink`** — наивный `asyncio.sleep(0.02)` копит дрейф
  (~12% медленнее realtime → буфер саттурируется → drop-кадры → заикания, доказано
  D-audio-2). Заменить на дрейф-компенсированный пейсинг (целиться в абсолютное время
  кадра). Раньше uplink был тишиной-keepalive, дрейф не мешал; с реальным микрофоном —
  критично.
- API-guard тест на контракт `async_register_binary_handler` (stable-internal API).

**Slice 2b (polish):** hands-free (непрерывный поток, джиттер-буфер, UX mic-toggle).

**Известные ограничения (исходы review, A-85):**
- **S-UP-01 (accept-risk).** Uplink-команда доверяет всем authenticated HA-юзерам
  (любой авторизованный HA-юзер может говорить в активный вызов). Паттерн зеркалит
  штатный HA voice-assistant; окно вызова эфемерно (~120с). Guard **не** добавляется
  by-design — задокументировано как accepted-risk (см.
  [`security.md#S-19`](../audit/security.md), [audit A-85](../audit/project-audit.md)).
- **P2-2 (multi-call selection).** При нескольких активных контроллерах WS-команда
  выбирает контроллер недетерминированно. Single concurrent call — by-design
  ограничение слайса (A-81 deferred §2); снятие — будущий слайс с пулом портов.
- **S-UP-02 (slot-leak handler).** Без явной `stop`-команды handler-слоты
  idle-копятся при многократном toggle микрофона в одной сессии (не утечка данных).
  Митигирован card-side кэшем подписки; явная `stop`-команда — polish Slice 2b.

**Отвергнуто:** #2/#3 (go2rtc-зависимость, TURN, yaml/exec-блоки), #4 (конфликт `av`).
Проба (`research/intercom-call-probe/probe_mic_uplink.py`) и альтернативы #2/#3 — для
будущего сравнения, не в проде.
