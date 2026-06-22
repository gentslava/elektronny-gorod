# Design: Two-way talk по домофону (SIP-аудио)

- **Date:** 2026-06-22
- **Owner:** Vyacheslav Scherbinin
- **Status:** Approved (brainstorming 2026-06-22)
- **Источник требований:** [PRD-two-way-audio.md](../../../research/intercom-call-probe/PRD-two-way-audio.md)
- **Технические доказательства:** [FINDINGS.md](../../../research/intercom-call-probe/FINDINGS.md)

## 1. Проблема и цель

После события вызова (FCM, фича `feat/doorbell-fcm-event`) логичный следующий шаг —
**ответить на вызов из HA и говорить с гостем у двери** (двусторонний звук), как
это делает приложение. Открытие двери (`accessControlOpen`) и видео (go2rtc) уже
есть — не хватает аудио-разговора.

**Success criteria:** пользователь из HA принимает входящий вызов домофона → слышит
гостя и говорит ему; за NAT без проброса порта; не ломает обычную работу (телефон
продолжает звонить, HA «забирает» вызов только по явному действию).

## 2. Фундамент (доказано, не гипотезы)

Из [FINDINGS.md](../../../research/intercom-call-probe/FINDINGS.md) (live 2026-06-22,
эталон [`probe_sip_media.py`](../../../research/intercom-call-probe/probe_sip_media.py)):

- Бэкенд оператора — Kazoo (FreeSWITCH `mod_sofia` + Kamailio SBC).
- SIP-креды: `POST /rest/v1/places/{placeId}/accesscontrols/{acId}/sipdevices`
  `{installationId}` → `{login,password,realm}`, realm = `{acId}.intercom.{operator}.ru`.
- Сигнализация: REGISTER (Digest MD5) → форк INVITE на все зарег. устройства →
  **первый ответивший забирает** (остальным `CALL_END_ANSWERED_MOBILE`).
- 🔴 INVITE — **компактные заголовки** (`f/t/i/v/m`): валидный `200 OK` обязан копировать
  `From/To/Call-ID` дословно + эхо всех `Via`/`Record-Route`, иначе нет `ACK`.
- SDP: **audio-only** `G.711 PCMU/PCMA` + `telephone-event`(DTMF) + `CN`, `ptime:20`.
  Видео в SIP нет (его покрывает go2rtc по `externalCameraId`).
- Двусторонний RTP работает за **symmetric NAT** благодаря RTP-latching FreeSWITCH +
  STUN для публичного адреса в SDP `c=`. **Проброс порта не нужен.**
- Доказано: answer → RTP оба направления (877 пакетов PCMU) → авто-открытие → `BYE`.
- ⚠️ Side-effect: постоянная авто-отвечающая регистрация делает линию «Занято» для
  панели → регистрироваться **транзиентно**, не блокировать линию.

## 3. Ключевые решения (brainstorming 2026-06-22)

### 3.1. SIP-стек: asyncio-модуль на основе `probe` (spike-verified 2026-06-23)

go2rtc **не умеет SIP**: в дереве `internal/` нет пакета `sip`, в списке источников
SIP отсутствует, запрос [issue #1750](https://github.com/AlexxIT/go2rtc/issues/1750)
**open и нереализован** (и предлагает UAC — исходящий, а нам нужен UAS — приём INVITE).

**Решение (спайк [research-spike.md](research-spike.md) D1):** SIP-UAS строим как
**ручной `asyncio`-модуль на основе `probe_sip_media.py`** (чистый `asyncio` +
`audioop` + `socket`, без тяжёлых зависимостей). Изначально гипотеза была взять базой
`voip-utils` (SIP-клиент из HA core), но **спайк показал — он не подходит** под Kazoo:

- 🔴 `SipMessage.parse_sip` хранит заголовки в `dict[str,str]` → **множественные
  `Via`/`Record-Route` схлопываются**, `answer()` эхо-ит один `Via` и не эхо-ит
  `Record-Route` (`voip_utils/sip.py:172-173,890-901`). Kazoo требует эхо **всех**
  дословно — иначе нет `ACK`.
- 🔴 `answer()` и RTP-слой **хардкодят Opus** (`sip.py:861-862`, `voip.py:177-178`);
  домофон — только G.711.
- 🔴 Нет `REGISTER`/`Digest`; `send_audio` — блокирующий `time.sleep` (`voip.py:264,283`).

`probe` уже **точнее под Kazoo** (эхо всех Via/Record-Route, G.711, Digest REGISTER,
STUN, latching, BYE — доказано live). Из `voip-utils` заимствуем лишь изолированный
`SipEndpoint` (regex-парсер SIP URI) — copy/адаптация, **не зависимость** (в manifest
`voip-utils` не добавляем).

Модуль закрывает N3 «настоящий SIP-стек» — корректными транзакциями/заголовками/BYE,
а не «фреймером наугад»; **без тяжёлых зависимостей**, работает в **HA Container**.
Слои G.711-транскод ([sip/audio.py](../../../custom_components/elektronny_gorod/sip/audio.py))
и STUN ([sip/stun.py](../../../custom_components/elektronny_gorod/sip/stun.py)) —
реализованы (Slice 0 Task 2–3).

### 3.2. Целевая трубка — браузер HA через go2rtc (вариант A)

HA headless — у сервера нет «трубки». Звук терминируется в **браузере** (Lovelace
WebRTC-карта на телефоне/ПК с открытым HA) — самый mirror-подобный путь (как
приложение). Микрофон+динамик берём из браузера через WebRTC.

Транспорт «`sip.py` ↔ браузер» — **go2rtc** (`exec`-источник с `#backchannel=1`):
go2rtc пишет звук микрофона браузера в stdin процесса и отдаёт downlink из stdout
(подтверждено докой go2rtc `internal/exec`). Так переиспользуется готовая WebRTC-карта
с кнопкой микрофона (AlexxIT/WebRTC) — свою карту писать не надо. ⚠️ uplink через
`exec`-backchannel — известный риск (§6.5), проверяем PoC до Slice 2.

### 3.3. Инкрементально

Полный two-way строим слайсами: фундамент (SIP-приём + downlink/прослушка) — первый
проверяемый результат; uplink (микрофон) — следующий. Uplink без работающего
downlink-пути не отладить.

### 3.4. go2rtc SIP-source на Go — отдельная инициатива (вне scope)

Вклад в go2rtc (SIP-источник на Go) — достойная, но **отдельная** работа со своим
темпом, наш `sip.py` как живой референс. Мотивация — переиспользовать SIP-фундамент
go2rtc и для 2-way домашней камеры. **В текущий scope не входит** — не блокируем
свою фичу зависимостью от чужого upstream-ревью на другом языке.

### 3.5. Готовые SIP-решения: что переиспользуем (research 2026-06-22)

Три research-прохода (Python-стеки + HA-каркасы + Asterisk/gateways). Вывод: **наш
кейс уникален** — ни один публичный HA-домофон (Doorbird, Hikvision, Dahua, 2N, Aqara)
не гонит two-way по SIP; все подают backchannel в *проприетарный канал самого
устройства* (ONVIF/RTSP/ISAPI/HTTP). У нас устройство недоступно — звук уходит в
**RTP-сессию SIP-вызова на realm оператора**. **Готового end-to-end решения для HA
Container нет** (HACS поставляет Python + Lovelace, не C/Go media-daemon).

🔑 **Наше ключевое преимущество:** `probe_sip_media.py` **уже закрыл весь
server-side SIP-gap** на чистом Python (REGISTER Digest MD5 + приём INVITE как UAS +
RTP G.711 + STUN + symmetric latching + BYE). Мы **не ищем gateway — мы уже написали
минимальный UAS**. Поэтому берём из экосистемы **паттерны**, а не код.

| Проект | Лиц. | Что берём |
|---|---|---|
| **`voip-utils`** (HA core) | Apache-2.0 | **Только `SipEndpoint`** (regex-парсер URI). Как базу спайк отверг — схлопывает multi-Via/Record-Route, хардкодит Opus (§3.1) |
| **`zacs/ha-voipshim`** | MIT | **Паттерн REGISTER+приём INVITE к чужому realm** + conference-bridge транскод G.711↔Opus. Идея, не код (он sidecar/PJSIP — см. §3.1, мы in-process) |
| **`absent42/aqara-doorbell`** | MIT | **Паттерн raw-audio ⟂ видео** + 🔴 **`exec`-source пишется прямо в `go2rtc.yaml`** (bundled go2rtc блокирует `exec` через REST API — security) |
| **`felipecrs/dahua-vto`** | MIT | **Multi-source go2rtc stream**: видео ⟂ аудио в одном потоке, G.711 сквозной |
| **AlexxIT/WebRTC `custom:webrtc-camera`** | MIT | **Готовая frontend-карта two-way** (`media: video,audio,microphone`). Свою карту НЕ пишем |

**Кодек:** держим **G.711 PCMA/PCMU 8000 сквозным** — WebRTC несёт PCMA/PCMU 8000
нативно, Kazoo/FreeSWITCH дают G.711 baseline → транскод может вообще не
понадобиться, go2rtc только репакетизирует.

**Отклонено (с обоснованием):**
- **Kamailio / Kazoo** — это **серверная сторона оператора** (SIP-сервер/SBC + облачная
  АТС), не клиентский UA. Не ставим свою АТС, чтобы ответить на один вызов.
- **Asterisk / PJSIP-sidecar** (паттерн ha-voipshim) — отдельный Docker-контейнер
  (host networking), сложная установка для HACS, не mirror-app. Отклонено в пользу
  in-process (§3.1).
- **Браузерный SIP.js / `TECH7Fox/HA-SIP` / `sip-doorbell`** — требуют SIP-over-WebSocket
  (`wss://`), которого у оператора скорее всего нет → пришлось бы поднимать свой
  WS-gateway (= дублирует SIP-слой). Отклонено.
- **Janus SIP plugin / Asterisk chan_pjsip / baresip / pjsua2 (ha-sip)** —
  полноценные SIP↔WebRTC gateway-сервисы. Все требуют отдельный сервис вне HA (нет
  HACS/Container-пути), часть под GPL/AGPL. `pjsua2` — release-линия заглохла +
  unpatched CVE-2026-25994 (CVSS 9.8 в ICE). Наш `probe` уже закрыл SIP-gap на чистом
  Python → sidecar-gateway избыточен.
- **HA VoIP official** — только listener, **нет outbound REGISTER** к чужому realm,
  Opus-only, звук в Assist (не в браузер). Не подходит (но его движок = `voip-utils`,
  который мы берём ниже уровнем).
- **pjsip/pjsua2, sipsimple, baresipy, aiosip** — нативные C-deps без py3.13-колеса /
  прячут медиа / мертвы. Не ставятся в HA Container (детали — research).

## 4. Целевая архитектура

```
       Домофон оператора (Kazoo/FreeSWITCH)
              │  SIP INVITE + RTP G.711 (audio-only)
              ▼
   ┌──────────────────────────────────────────┐
   │  sip.py  (в интеграции; voip-utils + наш    │  mint creds → REGISTER (transient)
   │  G.711/REGISTER/STUN-слой, §3.1)            │  → 200 OK → RTP ↕ → BYE
   │  SIP-UAS: 200 OK, RTP, STUN, latching, DTMF │
   └──────────────┬───────────────────────────┘
        downlink ▲│▼ uplink   (локальный IPC)
   ┌──────────────┴───────────────────────────┐
   │  go2rtc exec-bridge   (#backchannel=1)     │  переиспользуем go2rtc
   └──────────────┬───────────────────────────┘
              │  WebRTC (Opus ↔ G.711 транскод go2rtc)
              ▼
   Lovelace WebRTC-карта в браузере = трубка (динамик + микрофон)

   Параллельно (уже есть, не трогаем):
   • видео   → go2rtc RTSP (camera.py)
   • сигнал  → FCM event (event.py)
   • дверь   → lock / accessControlOpen
```

### Компоненты и границы

| Компонент | Назначение | Зависит от |
|---|---|---|
| `sip.py` (новый) | SIP-UAS: mint → register → answer → RTP-media → bye; STUN; latching. На базе `voip-utils` + наш слой (§3.1). | `voip-utils`, `api.py` (mint), `_logging.py` (redact), FCM-сигнал |
| `go2rtc.py` (расширение) | upsert аудио-`exec`-stream при активном вызове | go2rtc HTTP API |
| exec-bridge (новый, тонкий) | мост go2rtc stdin/stdout ↔ `sip.py` IPC | `sip.py` IPC |
| сервисы `answer`/`hangup` | явное действие пользователя | `sip.py` |
| `binary_sensor` «вызов активен» (расширение) | индикация активного разговора | `sip.py` state |

`sip.py` проектируем **изолированно** (ясные границы mint/register/answer/media/bye,
без знания про go2rtc) — чтобы он был и хорошим модулем, и референсом для Go-порта.

## 5. Фазирование (vertical slices)

| Slice | Что | Проверяемый результат | Фаза PRD |
|---|---|---|---|
| **0** | SIP-логику `probe` → чистый модуль `sip.py` (mint→register→answer→media→bye). Юнит-тесты: парсинг SDP, Digest MD5, компактные заголовки, BYE-диалог. | Тесты зелёные + ручной приём вызова с логом RTP | — |
| **1** | FCM `CALL_INCOMING` → `sip.py` поднимается, transient-register, отвечает, качает **downlink**. Вывод звука гостя в HA. Сервис `answer`. | **Слышим гостя** в HA | B |
| **2** | **uplink**: go2rtc `exec`-bridge + backchannel, микрофон браузера → домофон. WebRTC-карта. Сервисы `answer`/`hangup`, `binary_sensor` «активен». | **Полный разговор** | C |
| **3** | Polish: открытие двери в разговоре (REST уже есть / DTMF), edge cases, docs, ADR-0012, тесты. | Готово к релизу | — |
| позже | go2rtc SIP-source на Go (upstream-PR) | вклад в сообщество | отдельно |

## 6. Технические развилки / открытые вопросы (добить в плане/экспериментом)

1. ✅ **Регистрация — REGISTER-on-answer (pcap-доказано 2026-06-23).**
   Полная модель — [call-answer-model.md](call-answer-model.md). Приложение **НЕ держит**
   SIP-регистрацию: `INVITE` приходит **только после `REGISTER`**, который шлётся в момент
   нажатия «ответить» → сервер немедленно (≈90мс) шлёт `INVITE` → `200 OK` мгновенно
   (≈80мс) → RTP-latching → разговор. «Раздумья» — **ДО** `REGISTER` (окно `CallInvalidated`
   **30с** — домофон сам сбрасывает на 30-й секунде).
   → **Наша held-регистрация была ошибкой**: forked `INVITE` приходил рано, поздний `200 OK`
   → сервер сносил media (`BYE`, downlink 0). Правильно: по «ответить» → `REGISTER` →
   принять `INVITE` → `200 OK` сразу + RTP uplink (latching). Доказано pcap реального
   приложения (Linphone 5.4.42, голый accept, без STUN, локальный SDP + latching).
2. **IPC `sip.py` ↔ go2rtc exec-bridge.** Связать долгоживущий SIP-стек в HA с
   lazy-запуском exec в go2rtc (UNIX-socket / TCP loopback / pipe). Жизненный цикл:
   вызов активен в `sip.py` ↔ карта открыта в браузере ↔ exec-bridge подключён.
3. **Frontend-карта.** Штатная HA camera-card микрофон **не даёт** — нужна сторонняя
   (AlexxIT/WebRTC). Внешняя зависимость для пользователя → задокументировать в README.
4. **HTTPS.** Браузер даёт доступ к микрофону только на HTTPS-origin.
5. 🔴 **go2rtc `exec`-backchannel — главный риск uplink (Slice 2).** Несколько
   открытых багов: поток анонсируется `send-only` вместо `sendrecv`, кнопка микрофона
   не появляется, нестабильный 2-way на G.711
   ([#2084](https://github.com/AlexxIT/go2rtc/issues/2084),
   [#1932](https://github.com/AlexxIT/go2rtc/issues/1932),
   [#1899](https://github.com/AlexxIT/go2rtc/issues/1899)). Listen-direction (downlink)
   надёжен — uplink проверяем **PoC до Slice 2**. Fallback если exec-backchannel не
   взлетит: подавать uplink в `sip.py` иным путём (свой минимальный WebRTC-приём /
   пересмотр на aiortc-мост вариант B).
6. 🔴 **Bundled go2rtc блокирует `exec`-source через REST API** (security). Если go2rtc
   встроен в HA — `exec`-stream через `go2rtc.py` (REST) не поднять; писать **прямо в
   `go2rtc.yaml`** (паттерн `aqara-doorbell`) или вынести аудио иным транспортом.
   Решаем в Slice 2.

## 7. Non-goals (scope discipline)

- **Push-to-talk / исходящий вызов на панель** — запрещён оператором (486), вне scope.
- **2-way домашней камеры** — мотивация для будущего go2rtc-вклада, не реализуем здесь.
- **go2rtc SIP-source на Go** — отдельная инициатива после фундамента.
- **Конференция / barge-in** — недоступно у оператора (модель first-answer-wins).
- **Авто-ответ** — только по явному действию пользователя (N2).

## 8. Влияние

- **Existing entries:** не трогаем `entry.data` schema / config-entry VERSION в Slice 0–1.
  Возможен новый `CONF_*` для SIP-настроек (решим в плане) → миграция при необходимости.
- **Security:** SIP-`password` / `realm` — секреты. Не логировать
  ([`no-secret-logs.md`](../../../.claude/rules/no-secret-logs.md)), добавить в
  `SENSITIVE_KEYS` / `TO_REDACT`.
- **Distribution:** чистый Python (без aiortc) → работает в HA Container. go2rtc уже
  есть у пользователей с аудио-камерами.
- **HA QS:** новый крупный компонент → ADR-0012 обязателен (big change, см. CLAUDE.md).

## 9. Acceptance criteria (целевые, полный two-way)

- [ ] При FCM `CALL_INCOMING` и явном `answer` — `sip.py` отвечает 200 OK, поднимается RTP.
- [ ] Пользователь **слышит** гостя в HA (Slice 1).
- [ ] Пользователь **говорит** гостю через микрофон браузера (Slice 2).
- [ ] `hangup` шлёт BYE, сессия гаснет; авто-`ended` по `CallInvalidated` согласован с `event.py`.
- [ ] Открытие двери в разговоре работает (REST / DTMF).
- [ ] За NAT без проброса порта (STUN + latching).
- [ ] SIP-пароль не утекает в логи/diagnostics.
- [ ] Регистрация транзиентная — панель не залипает в «Занято».

## Quality gate

`SPEC_READY` ✅
