# Findings: канал события «вызов с домофона»

Эксперимент 2026-06-22, harness в этой папке. Реальные звонки на прод-аккаунт,
3 канала параллельно, home.server. PII (адрес/квартира/account/Call-ID)
заменены плейсхолдерами; секреты не приводятся.

## Вердикт

**Событие вызова приходит по FCM data-push.** Это основной и достаточный
канал сигнализации. SIP — рабочий, но избыточный для *сигнала* (его ценность —
в *медиа*, см. ниже). STOMP — не несёт вызов.

| Канал | Сигнал вызова | Уровень | Латентность | Метаданные | Вывод |
|---|---|---|---|---|---|
| **FCM** | ✅ да | аккаунт (все домофоны разом) | ~0.5–1 c | полные + lifecycle | **основной** |
| **SIP** | ✅ да (`INVITE`) | per-домофон (N регистраций) | ~0.5 c | бедные (`From`,`Call-ID`) | медиа-канал, не для сигнала |
| **STOMP** `/events` | ❌ нет | аккаунт | — | только `availableFeatures` | не несёт вызов |

STOMP держал коннект 10 мин при живом `CONNECTED`, на 3 звонка — ноль событий.

## FCM: как устроено

### Регистрация (рядом с auth)
FCM-токен (формата `<sender>:<opaque>`) регистрируется у оператора в:
- `POST /api/mh-customer-device/mobile/public/v1/customers/device-installations`
- `POST /rest/v1/subscriberNotifications`

Тело (оба): `{appId:2, appVersion, appVersionCode, platform:"google",
pushToken:<FCM>, installationId:<uuid>, deviceId:<hex>, deviceType:
"MOBILE_APPLICATION", deviceManufacturer, deviceModelName, osVersion}`.
Отписка — `DELETE /rest/v1/subscriberNotifications`.

Серверный приём FCM без Android подтверждён: `firebase-messaging`,
project `ntk-myhome`, sender `369367231553`, package `ru.inetra.intercom`
(публичные идентификаторы из APK/HAR). checkin→register→MTalk работает,
3 звонка приняты без сбоев.

### Payload `CALL_INCOMING`
```jsonc
{
  "from": "<senderId>",
  "fcmOptions": { "analyticsLabel": "CALL_INCOMING" },
  "data": {
    "PushType": "CALL_INCOMING",
    "PushTitle": "Входящий вызов",
    "PlaceId": "<placeId>",
    "AccessControlId": "<acId>",       // какой домофон
    "GateName": "<имя двери>",
    "Apartment": "<кв>",
    "Sender": "<кв>@<acId>.intercom.2090000.ru",
    "Call-ID": "<callId>",             // связывает start↔end
    "CallStarted": "<ISO8601>",
    "CallInvalidated": "<ISO8601>",    // окно ~30 c; по нему авто-сброс
    "AllowOpen": "true",               // можно открыть дверь из события
    "IsSystem": "false"
  }
}
```

### Таксономия PushType (наблюдалось)
| PushType | Когда | PushTitle |
|---|---|---|
| `CALL_INCOMING` | начало вызова | «Входящий вызов» |
| `CALL_END_ANSWERED_MOBILE` | принят на другом устройстве (тот же `Call-ID`) | «Вызов принят на другом устройстве» |

Сброс с панели / таймаут / открытие двери — **отдельного end-пуша не дают**
(завершение по `CallInvalidated`). Полная таксономия (отклонён/пропущен/
открыто) требует доп. сценариев.

### Открытие двери из события
`AllowOpen:"true"` → `POST /rest/v1/places/{placeId}/accesscontrols/{acId}/actions`
тело `{"name":"accessControlOpen"}` → `{"data":{"status":true}}`.
Полный цикл **звонок → FCM-пуш → программное открытие** проверен вживую.

## SIP (медиа-канал)
- Минт: `POST /rest/v1/places/{placeId}/accesscontrols/{acId}/sipdevices`
  `{installationId}` → `{login, password, realm}`, realm =
  `{acId}.intercom.2090000.ru` (он же registrar `:5060/UDP`).
- REGISTER Digest MD5 → входящий `INVITE` = звонок. NAT на home.server
  проходит (рабочий путь при частом re-REGISTER).
- **Per-домофон**: отдельная регистрация на каждый `accessControlId`.

## Медиа-слой (двусторонний звук) — live-эксперимент 2026-06-22

**Бэкенд оператора — Kazoo (FreeSWITCH `mod_sofia` + Kamailio SBC).** SBC на
`<SBC-IP>:5060`, медиа-серверы — публичные IP облака оператора (меняются
по вызову). Заголовок `X-KAZOO-AOR` в NOTIFY.

### SIP-flow входящего вызова (мы = UAS/отвечающий)
- INVITE использует **компактные заголовки** (`f/t/i/v/m/l/c`). 🔴 Критично:
  валидный `200 OK` должен копировать `From/To/Call-ID` **дословно** (с учётом
  компактных форм) + эхо **всех** `Via` и `Record-Route`. Иначе поля пустые →
  сервер игнорит `200 OK` → нет `ACK` → «нет ответа» (ретрансмит INVITE).
- SDP-offer домофона: **только audio**, `G.711 PCMU(0)/PCMA(8)` + `telephone-event(101)` (DTMF) + `CN(13)`, `ptime:20`. **Видео в SIP НЕТ** (отдельно через go2rtc).
- Цепочка: `INVITE → 200 OK → ACK (🤝 диалог установлен) → RTP оба направления → BYE`.
- SIP-идентичность панели: `sip:000@{realm}` (From входящего INVITE).

### ✅ Двусторонний звук РАБОТАЕТ — **без проброса порта**
- home.server за **symmetric NAT** (STUN отдаёт публичный IP домохозяйства —
  в отчёт не выносим), но **FreeSWITCH делает RTP-latching** (шлёт даунлинк туда,
  откуда получил наш аплинк) → даунлинк доходит. Подтверждено: **877 пакетов PCMU**.
  **Проброс порта НЕ нужен** (как и в приложении).
- STUN (cloudflare/sipnet; Google на этой сети заблокирован) → публичный RTP-адрес в SDP `c=`.
- 🔴 **Фиксированный локальный SIP-порт** обязателен: эфемерные порты при
  рестартах плодят «кладбище» устаревших регистраций → Kazoo форкает вызов на
  мёртвый контакт → «нет ответа».

### ✅ Авто-ответ + открытие двери + завершение — РАБОТАЕТ
- `ANSWER → через N c accessControlOpen (REST) → BYE`. BYE in-dialog:
  Request-URI = remote Contact, `Route` из Record-Route, From=наш+tag, To=remote+tag,
  свежий CSeq. После BYE тон/сессия гаснут. (Без BYE сессия висит — тон продолжается.)
- Открытие двери в разговоре: доступен **DTMF** (PT101) ИЛИ REST `accessControlOpen` (использовали REST — работает).

### ❌ Push-to-talk — НЕ прямой вызов / вероятно недоступен для домофонов
- Исходящий INVITE на `sip:000@{realm}` → **486 «Unable to Comply»** (запрещено).
  Push-to-talk ≠ позвонить на панель.
- ⚠️ По словам пользователя, в приложении **P2T для домофонов отсутствует**
  (флаг `PUSH_TO_TALK` в availableFeatures, вероятно, относится к камерам —
  напр. домашним). Помечаем как **неподтверждённую возможность, вне скоупа**.
  Если когда-то понадобится — снять HAR приложения на работающем P2T.

### ⚠️ Side effects (важно для дизайна фичи)
- Зарегистрированная **авто-отвечающая** SIP-проба делает линию квартиры
  «Занято» для панели → мешает нормальной работе. Вывод: не держать
  авто-ответ постоянно; регистрироваться транзиентно / не блокировать линию.
- Двусторонний звук в проде → брать **настоящий SIP-стек** (PJSIP/baresip/aiortc),
  а не ручной (компакт-заголовки, Record-Route, STUN, BYE, latching — всё это
  библиотеки делают корректно). Это advanced-фича на будущее.

## D-audio-2 — транспорт uplink-микрофона (PoC 2026-06-24)

**Вопрос:** каким механизмом доставить **живой микрофон браузера** в Python (там →
G.711 → RTP, готово). Кандидаты — [uplink-mic-design.md](../../docs/features/intercom-two-way-audio/uplink-mic-design.md)
§4. **Вердикт: #1 HA WS-binary** (см. [ADR-0013](../../docs/decisions/0013-uplink-mic-transport.md)).

### Что проверено
- **Серверный аудио-тракт — доказан (loopback-самотест `probe_loopback.py`):**
  синтетический тон 440Гц @48к → `UplinkSink`-логика (resample 48→8к + G.711 +
  джиттер-буфер + дрейф-компенсированный пейсинг) → RTP → декод. Результат: дрейф
  пейсинга **3мс / 9с**, **0 провалов>45мс**, тон цел (RMS до ~11600). Стартовые
  тихие окна = pre-roll (ожидаемо).
- **Live (через пробу `probe_mic_uplink.py` + cloudflared/traefik-туннель):** микрофон
  дошёл до домофона в 1-й сессии (слышал себя у двери).
- **Заикания — root cause найден и исправлен:** RTP-loop шёл ~12% медленнее realtime
  (наивный `asyncio.sleep(0.02)` копит overhead) → буфер саттурируется → drop ~12%
  кадров → заикания. Фикс — дрейф-компенсированный пейсинг (целиться в абсолютное
  время кадра). **Та же проблема в продакшн `sip/rtp.py:run_uplink` — фикс в Phase C.**

### Что НЕ удалось (и почему это среда, не транспорт)
- На Mac-Docker `downlink=0` и флака INVITE — **Docker-VM IP `192.168.65.3` за тройным
  NAT** (Contact/SDP недостижимы). На home.server (реальный LAN-IP, публичный IP) —
  INVITE доходит.
- На home.server всё равно `downlink=0` — **расхождение пробы с интеграцией** (сравнение
  кодом, субагент): проба анонсировала STUN-адрес (latching рвётся: announced-порт ≠
  source-порт), слала ранний RTP до 200 OK, держала постоянную регистрацию. Привели к
  модели интеграции (локальный SDP + latching, uplink после 200 OK, register-on-answer)
  — но чистый live-замер не довели (пользователь на холоде; конкуренция с прод-
  интеграцией за SIP-leg не снята — guard не дал паузить прод).
- **Вывод:** провалы живого вызова — SIP/latching/NAT/register-модель/конкуренция
  (среда + harness пробы), **не транспорт #1**. Прод-интеграция (register-on-ring,
  локальный SDP, latching) принимает вызовы надёжно — модель верна.

### Решение
**#1 HA WS-binary** — без go2rtc/go2rtc.yaml, без TURN, авторизованный HA-WS (4G),
pure-Python. Продакшн — Phase C (WS-команда + Lovelace-карта + wiring `UplinkSink` +
дрейф-фикс `rtp.py`). Проба/альтернативы #2/#3 — для будущего сравнения. См. ADR-0013.

### Тестовая среда (offline, 2026-06-24) — `test_harness/`
**Door-эмулятор** (`test_harness/door_emulator.py`) — мини-оператор+домофон со
**строгим RTP-latching** по рецепту `app_call.pcap` (`test_harness/PCAP_RECIPE.md`):
registrar (REGISTER→401→200) + caller (INVITE с SDP-offer домофона) + latching-media
(ждёт первый uplink, проверяет symmetric src-порт==SDP-порт, защёлкивает, шлёт downlink
ТОЛЬКО на защёлкнутый src) + BYE. Запуск: `./test_harness/run_loopback.sh`. Проба —
оффлайн-режим (env `SIP_SERVER`/`TEST_LOGIN`/`TEST_REALM` → пропуск mint/FCM, фейк-креды).

**Вердикт по пробе: КОД КОРРЕКТЕН.** Полный вызов localhost↔проба проходит (REGISTER→
INVITE→200→ACK→RTP both ways→BYE), **symmetric OK, downlink=250+, two-way media работает**.
Негативный контроль (uplink из чужого порта) → SYMMETRIC FAIL → downlink=0 (детектор
настоящий). Uplink идёт из того же сокета (`RTP_LOCAL_PORT=40016`), что в SDP-answer;
SDP-offer парсится верно; uplink после ACK; дрейф-пейсинг ок.

**Следствие:** живой `downlink=0` — НЕ баг кода пробы, а **среда**: (а) Mac-Docker —
тройной NAT (Contact/SDP = Docker-VM IP `192.168.65.3`); (б) home.server — конкуренция
с прод-интеграцией за SIP-binding (тот же аккаунт → media-leg уходит проду) и/или
NAT-ремаппинг uplink-порта. Латчинг реального FreeSWITCH защёлкивает фактический
(post-NAT) source — строгий эмулятор СТРОЖЕ (ловит код-баги), реальный NAT — отдельный
сценарий (TODO: NAT-sim режим эмулятора + competition-тест). **Код пробы менять не надо.**

Эта же среда будет валидировать продакшн Phase C end-to-end.

## D-audio-variants — эмпирическая проверка #2/#3 (тестовый go2rtc, 2026-06-24)

**Контекст:** для сравнения с выбранным #1 поднят **изолированный тестовый go2rtc**
(`alexxit/go2rtc` 1.9.14, Basic-auth, отдельный инстанс — продакшн Frigate-go2rtc
не тронут). Это позволило прогнать механизмы #2/#3 на **живом** go2rtc БЕЗ реального
звонка/домофона. Раньше оба были только scaffolding «НЕ ПРОВЕРЕНО LIVE».

### #2 WHIP-pull — ✅ go2rtc-хоп работает end-to-end

- **Стрим-таргет:** пустой `PUT /api/streams?name=…` НЕ персистится — нужен объявленный
  стрим в `go2rtc.yaml` (`eg_mic:`). `?dst=` НЕ авто-создаёт стрим (404 на WHIP-publish).
- **WHIP-ingest (= то, что делает браузер):** headless-публикация тона
  (ffmpeg 8.0 `-f whip`, замена браузера) → `producers: 1`, медиа течёт стабильно.
- **RTSP-out (= то, что тянет проба):** `ffmpeg rtsp://…/eg_mic` → `opus 48k → pcm`,
  **mean −24 dB / max −21 dB** (тон дошёл; тишина была бы −91 dB).
- **Грабли (артефакт теста, не #2):** producer падал `Connection refused` — loopback-ICE
  отдавал ffmpeg недостижимый кандидат (`127.0.0.1`/публичный). Фикс: кандидат = IP
  контейнера. Прежний `streams: unknown error`/404 — симптом **мёртвого producer'а**,
  не лимит go2rtc (гипотеза «go2rtc не отдаёт push→RTSP» — **опровергнута**).

**Вывод #2:** транспорт технически рабочий. Цена (подтверждена): стрим-таргет в yaml +
проброс порта 8555 для WebRTC-медиа + **TURN на 4G** (симметричный NAT оператора) +
лишний хоп (~100–300мс). Сверх #1 ничего не даёт.

### #3 exec-backchannel — ⚠️ механизм живой, но не pull-able

- **exec-source в yaml:** go2rtc принимает (НЕ `insecure producer` — REST-блок только у
  Frigate; в yaml разрешено), спавнит процесс.
- **Forward-медиа exec:** БЕЗ `#backchannel` — `exec:ffmpeg … -f mpegts -` отдаётся по
  RTSP штатно (`aac → pcm`, тон −21 dB).
- **`#backchannel=1` + pull-консьюмер → ❌ `codecs not matched:  => audio:ANY`:** бэкчэннел
  меняет направление аудио на «to-exec», recvonly-консьюмер (RTSP) его не матчит.
  **Воспроизведён upstream send-only (#2084)** — тот же exec ломается ровно от добавления
  `#backchannel`.

**Вывод #3:** exec живой, но бэкчэннел нельзя забрать простой пробой — нужен полный путь:
камера-forward-стрим + WebRTC-консьюмер с two-way audio (advanced-camera-card) +
WebRTC-медиа (8555/TURN). **Строго сложнее #2** + хрупкость из-за send-only бага.

### Сводка реализуемости (на фактах)

| | #1 WS-binary ✅ | #2 WHIP-pull | #3 exec-backchannel |
|---|---|---|---|
| Проверено на живом go2rtc | прод | ✅ хоп (тон −24dB) | ✅ exec; ❌ бэкчэннел не pull-able |
| go2rtc / yaml | не нужен | стрим-таргет | exec + forward-стрим |
| 4G / удалёнка | ✅ 443/WSS | ⚠️ TURN + 8555 | ⚠️ TURN + 8555 |
| Доп. латентность | ~0 | ~100–300мс | ~50–150мс |
| Своя карта | нужна (есть) | WHIP-страница | не нужна (advanced-camera-card) |
| Upstream-баги | нет | нет | send-only #2084 (воспроизведён) |
| Сложность сетапа | низкая | средняя | высокая |

**Итог простыми словами:** оба **реализуемы**, оба **хуже #1**. #2 — «работает, но требует
go2rtc + TURN + проброс порта, и ничего не даёт сверх #1». #3 — «можно, но самая сложная
конструкция (two-way-карта + камера-стрим), и ломается об баг go2rtc». #2 проще #3.
**Эмпирика подтвердила выбор [ADR-0013](../../docs/decisions/0013-uplink-mic-transport.md) (#1).**
Тестовый go2rtc возвращён в чистое состояние; продакшн-go2rtc не тронут.

## Архитектура (предварительно)
- Сигнал вызова → **FCM-приём** (кандидат на sidecar-«push-bridge»: хрупкий
  приватный API Google, persistence creds, бинарный MTalk-сокет — по аналогии
  с go2rtc).
- HA-сущность → `event` `EventDeviceClass.DOORBELL` (тип `RING` на `CALL_INCOMING`).
- Видео → существующий go2rtc по `externalCameraId`.
- Открытие двери → существующий `accessControlOpen` (REST) или DTMF в разговоре.
- Двусторонний звук (ответить/говорить) → SIP-медиа: **доказано рабочим**,
  но heavy — на будущее, отдельным SIP-стеком (advanced-фича).

## Открытые вопросы
1. **Механизм push-to-talk** — прямой вызов на панель запрещён (486). Нужен
   HAR приложения при нажатии push-to-talk (найти HTTP-триггер).
2. Полная таксономия PushType (отклонён / пропущен / открыто).
3. Долговечность FCM-токена и поведение при ротации (по наблюдению — токены
   оператора долгоживущие, валидны недели).

## Артефакты эксперимента (`research/intercom-call-probe/`)
- `common.py` — HTTP/UA/login (зеркало интеграции).
- `login.py` — свежий логин по SMS → `session.json`.
- `probe_stomp.py` / `probe_sip.py` / `probe_fcm.py` — пробы каналов.
- `probe_sip_media.py` — UAS: приём вызова, SDP/RTP, авто-ответ+открытие+BYE, STUN.
- `probe_ptt.py` — UAC: исходящий вызов (push-to-talk эксперимент).
- `open_door.py` — открытие двери по событию.
- `docker-compose.yml` / `Dockerfile` — стек на home.server (5 изолированных проб).
- Секреты (`session.json`, `firebase_config.json`, `fcm_credentials.json`, `logs/`) — в `.gitignore`.
