Status: Active (заполнен на основе HAR-снимков, owner-discoverable)
Owner: Reverse Engineer Agent + HA Expert Agent
Last reviewed: 2026-05-23

Source files:
- `research/api/*.har` (local-only HAR-снимки; конкретные имена не фиксируются в публичных docs — см. ADR-0006)
- `custom_components/elektronny_gorod/api.py` (текущая реализация)
- `custom_components/elektronny_gorod/http.py` (headers, user-agent)
- `custom_components/elektronny_gorod/const.py` (BASE_API_URL, APP_VERSION)
- `custom_components/elektronny_gorod/user_agent.py` (формат UA)
- `custom_components/elektronny_gorod/helpers.py` (auth hashing)

Related docs:
- `../decisions/0006-mirror-app-behavior.md`
- `../decisions/0007-stateful-emulator-baseline.md`
- `../aidd/runbooks/har-collection.md`
- `overview.md`
- `../audit/project-audit.md` (A-47..A-54 — gaps между HAR и нашим кодом)

Used by agents:
- HA Expert, Architecture, Security, Reverse Engineer

Quality gates:
- AUDIT_DONE

---

# API Reference — `myhome.proptech.ru`

Документация API мобильных приложений «Мой Дом» (Электронный город / Новотелеком) и «Умный Дом.ру», получена через HAR-снимки реального приложения. Правила заполнения — [ADR-0006: Mirror application behavior](../decisions/0006-mirror-app-behavior.md): **только** endpoints, реально наблюдаемые в HAR.

🔴 **Конкретные значения (account_id, place_id, tokens, адреса, телефоны) хранятся ТОЛЬКО в .har файлах (gitignored). В этом документе — placeholders.**

## Backends — separate ecosystems

У оператора «Электронный город» (Новотелеком, Новосибирск) **два независимых
мобильных приложения и два независимых бэкенда**:

| Приложение | Package | Backend | Auth |
|---|---|---|---|
| **«Мой Дом»** (наша цель) | `ru.proptech.myhome` (?) | `myhome.proptech.ru` | Signed-request (sha1+md5 hashes) |
| «Электронный город» (старое) | `com.electronnijgorod.novosibirsk` | `my.2090000.ru` (`api.novotelecom.ru` для OAuth) | Keycloak OAuth2 (`client_id=mlk:android`) |

**Наша HA integration реализует только «Мой Дом»** (`myhome.proptech.ru`).
Старое приложение использует совсем другой DTO (`{id, type, category,
objectId, title, isMain, address, model, mac, ip}` через
`/api/ntk-video-equipment/rest/v1/devices`) и Keycloak — реализация
параллельного backend-клиента — отдельная задача.

**Важное общее знание из reverse engineering обоих приложений:**
- Ни один из бэкендов **не различает на API-уровне** «домовая камера»
  vs «городская». Оба возвращают плоский список.
- Оба используют **user-side preferences** для UX-фильтрации:
  - «Мой Дом» — `/settings/screens` (`entities` vs `hidden`)
  - «Электронный город» — `PUT /rest/v1/devices/{id}` с `isMain: bool`
- Оба show «only domovaya cameras» решают через юзерский выбор в
  приложении, не через server categorization. Это значит интеграция
  не должна изобретать heuristic-категории — только уважать user
  preferences (что мы делаем через `_attr_entity_registry_enabled_default`).

## Общие свойства

- **Base URL:** `https://myhome.proptech.ru`.
- **WebSocket:** `wss://myhome.proptech.ru:443/events` (STOMP-over-WebSocket).
- **Транспорт:** HTTPS (HTTP/2 для REST, HTTP/1.1 для WebSocket upgrade).
- **Формат:** JSON.
- **Кодировка:** UTF-8.
- **Аутентификация:** `Authorization: Bearer <access_token>` (формат токена: `MHAT<uuid>`).

## Стандартные headers (для всех аутентифицированных запросов)

```
accept-encoding: gzip
authorization: Bearer <access_token>
content-type: application/json; charset=UTF-8   ← только для POST
operator: <operator_id>                          ← обычно "1"
traceparent: 00-<32hex>-<16hex>-01               ← W3C distributed tracing
user-agent: <UA-pattern>
```

### User-Agent формат

```
<Manufacturer> <Model> | Android <ver> | ntk | <app_version> (<app_version_code>) | <account_id> | <operator_id> | <uuid> | <place_id>
```

Пример:

```
Nothing A065 | Android 16 | ntk | 9.1.0 (90100000) | <account_id> | 1 | <uuid> | <place_id>
```

Замечания:
- На устройстве владельца — **Nothing Phone A065**. Наш `user_agent.py` использует пул Pixel — это отличие от реального трафика.
- Для WebSocket handshake user-agent содержит `null` в полях account_id и place_id.
- UUID стабилен per-install (один на одно устройство).

### `traceparent` header

В HAR-сессиях приложение **отправляет** W3C trace context: `traceparent: 00-<32hex traceid>-<16hex spanid>-01`. Наш [`http.py`](../../custom_components/elektronny_gorod/http.py) этот header не отправляет. Гэп: [audit A-52](../audit/project-audit.md).

## Auth flow

### Phone → contracts

```
GET /auth/v2/login/{phone}
```

Возможные ответы:
- **200** — password-flow требуется.
- **300** — список контрактов в теле: `[{accountId, subscriberId, operatorId, placeId, address}, ...]`.
- **204** — `unregistered`.
- **400** — `invalid_login`.

### Password auth

```
POST /auth/v2/auth/{phone}/password
Body: {"login": "<phone>", "timestamp": "<ISO>", "hash1": "<sha1-b64>", "hash2": "<md5>"}
```

Crypto — см. [`helpers.py:35-47`](../../custom_components/elektronny_gorod/helpers.py#L35-L47). Ответ: `{accessToken, refreshToken, operatorId}`. На 400 — `invalid_password`.

### SMS auth

```
POST /auth/v2/confirmation/{phone}
Body: {accountId, address, operatorId, subscriberId, placeId}
```

Возможные ответы: 200 (SMS отправлен), 429 (`limit_exceeded`).

```
POST /auth/v3/auth/{phone}/confirmation
Body: {accountId, confirm1, confirm2 (оба = code), login, operatorId, subscriberId}
```

Ответ: `{accessToken, refreshToken, operatorId}`. На 406 — `invalid_format`.

### Refresh access_token

**Status: unknown.** В HAR не наблюдался. См. [ADR-0006](../decisions/0006-mirror-app-behavior.md), [audit A-22](../audit/project-audit.md).

## Bootstrap / startup endpoints

### `GET /public/v1/operators`

Список доступных операторов (Электронный город, Дом.ру и т.д.).

Response shape:
```json
{ "data": [ /* operator objects */ ] }
```

Используется приложением при первом запуске. **У нас не реализован** — см. [audit A-53](../audit/project-audit.md).

### `POST /api/mh-customer-device/mobile/public/v1/customers/device-installations`

🎯 **Bootstrap endpoint** — конфигурация клиента после установки/каждого запуска.

Response shape:
```json
{
  "data": {
    "AUTH_PROVIDER": {
      "erid": { "url": "string", "clientId": "string" }
    },
    "MOBILE_URL": {
      "domain": {
        "backend": "string",       // backend URL (для будущих запросов)
        "genesys": "string",       // Genesys CCaaS (customer support)
        "stomp": "string",         // 🎯 STOMP server URL для real-time
        "expiredAt": "number"      // когда обновить конфигурацию
      },
      "policy": "string"
    }
  }
}
```

**У нас не реализован.** Используя этот endpoint, можно динамически получать STOMP URL вместо hardcoded — см. [audit A-51](../audit/project-audit.md).

### `GET /rest/v1/subscribers/profiles`

Профиль владельца аккаунта.

Response shape (наблюдалось в нашем коде, но не в этих HAR — приложение делает редко):
```json
{ "data": { "subscriber": { "id, accountId, name, ... } } }
```

Используется в [`api.py:query_profile`](../../custom_components/elektronny_gorod/api.py#L146).

### `GET /rest/v1/stomp/available-features`

🎯 **STOMP feature probe**. Используется перед открытием WebSocket.

Response: `{ "data": null }` или `{ "data": [features...] }` — точная форма зависит от поддержки фич.

**У нас не реализован** — необходим для подключения к [`wss://.../events`](../audit/project-audit.md).

## Places / subscriber

### `GET /rest/v3/subscriber-places[?placeId={id}]`

Список квартир/мест подписчика.

Response shape:
```json
{
  "data": [
    {
      "id": "number",                    // subscriberId
      "subscriberType": "string",
      "subscriberState": "string",
      "place": {
        "id": "number",                  // 🎯 place_id
        "address": {
          "index", "region", "district", "city", "locality", "street",
          "house", "building", "apartment",
          "visibleAddress", "groupName": "string"
          // ⚠️ это dict, не строка. Для UI используй visibleAddress.
          // index/district/locality часто = null в наблюдаемых HAR.
        },
        "location": { "longitude", "latitude": "number" },
        "operatorId": "number",
        "autoArmingState": "boolean",
        "autoArmingRadius": "number"
      },
      "subscriber": { "id", "name", "accountId", "nickName" },
      "guardCallOut": { "active": "boolean", "phoneNumber": "string" },
      "payment": { "useLink": "boolean" },
      "provider": "string",
      "blocked": "boolean"
    }
  ]
}
```

**У нас:** [`api.py:query_places`](../../custom_components/elektronny_gorod/api.py#L175) — используем только базовое. Не используем `address`, `location`, `payment`, `blocked`, `guardCallOut`.

### `GET /api/mh-customer/mobile/v1/customers/places/{place_id}/settings/screens`

🎯 **Пользовательские настройки видимости** для экрана камер/домофонов в
приложении оператора. Используется в [`api.py:query_screens_settings`](../../custom_components/elektronny_gorod/api.py).

Response shape:
```json
{
  "screens": [
    {
      "type": "ACCESS_CONTROLS",
      "entities": [                          // видимые
        {"id": 5137, "type": "ACCESS_CONTROL_ENTRANCE", "order": 0},
        ...
      ],
      "hidden": [                            // скрытые пользователем
        {"id": 5138, "type": "ACCESS_CONTROL_ENTRANCE"}
      ]
    },
    {
      "type": "PUBLIC_CAMERAS",
      "entities": [{"id": 5593590, "type": "PUBLIC_CAMERA", "order": 0}, ...],
      "hidden":   [{"id": 5593568, "type": "PUBLIC_CAMERA"}, ...]
    }
  ]
}
```

Если пользователь не настраивал — возвращается `{}` (пустой объект).

**Использование в интеграции:** `hidden` IDs прокидываются в camera/lock
dicts через флаг `hidden`. Entity для них получает
`_attr_entity_registry_enabled_default = False` — новые установки уважают
пользовательский выбор. Existing entities сохраняют выбор юзера в HA.

## Access controls (домофоны)

### `GET /rest/v1/places/{place_id}/accesscontrols`

Response shape:
```json
{
  "data": [
    {
      "id": "number",                       // access_control_id
      "operatorId": "number",
      "name": "string",
      "forpostGroupId": "string",
      "forpostAccountId": "null|string",    // в наблюдаемых HAR — null
      "type": "string",                     // observed: "SIP"
      "allowOpen": "boolean",
      "openMethod": "string",               // observed: "ACCESS_CONTROL"
      "allowVideo": "boolean",              // ← мы не используем
      "allowCallMobile": "boolean",         // 🎯 ← связано с SIP
      "allowSlideshow": "boolean",
      "previewAvailable": "boolean",        // ← мы не используем
      "videoDownloadAvailable": "boolean",
      "timeZone": "number",
      "quota": "number",
      "externalCameraId": "string",         // см. ⚠️ ниже
      "externalDeviceId": "null|string",
      "entrances": [
        {
          "id": "number",                   // entrance_id
          "name": "string",
          "forpostGroupId": "string",
          "allowOpen, openMethod, allowVideo, allowCallMobile,
           allowSlideshow, previewAvailable, videoDownloadAvailable": "...",
          "timeZone, quota": "number",
          "externalCameraId": "string",     // 🎯 ПЕРВИЧНЫЙ — см. ⚠️ ниже
          "externalDeviceId": "null|string" // в наблюдаемых HAR — null
        }
      ]
    }
  ]
}
```

⚠️ **`externalCameraId` существует на двух уровнях** (ac.* и entrances[*].*).
Во всех наблюдаемых HAR (11 уникальных AC, по 1 entrance на AC) значения
**совпадают**. Multi-entrance кейс не пойман — но schema допускает их различие,
и пользовательский bug (camera показывает другую entrance) подтверждает, что
**приоритет должен быть entrance-level**: маппить camera→entrance, не camera→ac.
AC-level `externalCameraId` следует трактовать как shortcut для случая
ac-без-entrances, либо вообще игнорировать.

**У нас:** [`api.py:query_access_controls`](../../custom_components/elektronny_gorod/api.py#L188) — используем только id/name/allowOpen/entrances. Не используем `previewAvailable`, `allowVideo`, `allowCallMobile` — это потенциал для дополнительной функциональности (см. audit).

### `POST /rest/v1/places/{place_id}/accesscontrols/{ac_id}[/entrances/{e_id}]/actions`

Открыть домофон. Body: `{"name": "accessControlOpen"}`. У нас реализован — [`api.py:open_lock`](../../custom_components/elektronny_gorod/api.py#L294).

### `POST /rest/v1/places/{place_id}/accesscontrols/{ac_id}/sipdevices`

🎯 **SIP devices** — регистрация SIP-клиента для приёма входящих звонков от домофона.

Response shape:
```json
{
  "data": {
    "id": "string",         // SIP user ID
    "realm": "string",      // SIP realm (домен)
    "login": "string",      // SIP login
    "password": "string"    // SIP password
  }
}
```

Это **один из** потенциальных путей для real-time звонков в HA — поднять SIP UAC, регистрироваться этими credentials, ловить INVITE. Но: SIP-трафик в HAR не виден (другой транспорт). Полная картина (что именно приходит через SIP vs через WS vs через FCM) требует доп. capture-сессий. См. [audit A-49](../audit/project-audit.md).

### `GET /rest/v1/places/{place_id}/accesscontrols/{ac_id}/snapshots`

🎯 **Snapshot домофона** (отдельно от forpost-камер). Возвращает JPEG bytes.

**У нас не реализован.** В коде есть только snapshot для forpost-камер ([`api.py:query_camera_snapshot`](../../custom_components/elektronny_gorod/api.py#L275)). См. [audit A-48](../audit/project-audit.md).

## Cameras (forpost — стандартные камеры)

### `GET /rest/v1/places/{place_id}/cameras`

Базовый список камер. Response: `{"data": [...]}`. Используется в [`api.py:query_cameras`](../../custom_components/elektronny_gorod/api.py#L215).

### `GET /rest/v2/places/{place_id}/public/cameras`

Публичные камеры (двор / подъезд). Используется в [`api.py:query_public_cameras`](../../custom_components/elektronny_gorod/api.py#L230).

### `GET /rest/v1/places/{place_id}/screen-sections`

Структура экрана с группами камер. Response: `{"sections": [...]}`. Используется в [`api.py:query_sections`](../../custom_components/elektronny_gorod/api.py#L245), но результат **игнорируется**. См. [audit A-18](../audit/project-audit.md).

### `GET /rest/v1/forpost/cameras/{id}/snapshots?width=&height=`

JPEG snapshot камеры. Используется в [`api.py:query_camera_snapshot`](../../custom_components/elektronny_gorod/api.py#L275).

### `GET /rest/v1/forpost/cameras/{id}/video?LightStream=0`

Stream URL.

Response shape:
```json
{
  "data": {
    "URL": "string",            // FLV/RTSP URL
    "Error": "null|string",     // ← бизнес-ошибка даже при HTTP 200
    "ErrorCode": "null|number",
    "Status": "null|string"
  }
}
```

Важно: даже **HTTP 200** может содержать `Error != null`. Наш [`api.py:query_camera_stream`](../../custom_components/elektronny_gorod/api.py#L260) проглатывает через `except Exception → None`, что прячет бизнес-ошибки.

### `GET /api/mh-camera/mobile/v1/places/{place_id}/cameras/features/info`

Список поддерживаемых фич камер места. Response: `{"data": [strings]}`. **У нас не реализован.** Можно использовать для feature-detection (включать ли определённые entity).

### `GET /api/mh-camera-personal/mobile/v1/cameras/{camera_id}/events`

🎯 **История событий камеры** (записи, motion-events).

Response shape:
```json
{
  "externalEvents": [
    {
      "ID": "number",
      "Time": "number",         // unix timestamp
      "Duration": "number",     // seconds
      "isAvailable": "boolean"
    }
  ],
  "recordingDisabledEvents": []
}
```

**У нас не реализован.** Можно использовать для HA `event` entity (история движений). См. [audit A-50](../audit/project-audit.md).

### `GET /rest/v2/forpost/cameras/{id}/events`

Альтернативный (v2) endpoint для событий камер. Структура аналогична.

## Финансы / баланс

### `GET /api/mh-payment/mobile/v1/finance?placeId={place_id}`

Баланс лицевого счёта. **В этих HAR-сессиях не наблюдался** (пользователь не открывал экран баланса в момент записи).

В нашем коде — [`api.py:query_balance`](../../custom_components/elektronny_gorod/api.py#L164). Должен быть пересобран HAR с открытием экрана баланса, чтобы зафиксировать response shape тут.

## Real-time каналы (несколько одновременно)

🟡 **Важно:** в HAR зафиксирован WebSocket handshake, но **не зафиксировано содержимое STOMP-фреймов** (Charles `.chlz` обычно не сохраняет тело WebSocket-сообщений). Какие именно события идут через WS и какие через другие каналы — **открытый вопрос**, требующий доп. HAR-сессий с активными сценариями (входящий звонок в домофон, motion на камере, действие на ESPF-домофоне).

Из HAR-снимков идентифицировано **минимум три** потенциальных канала real-time доставки:

### 1. WebSocket (STOMP) — `wss://myhome.proptech.ru:443/events`

Handshake headers:

```
Connection: Upgrade
Upgrade: websocket
Sec-WebSocket-Version: 13
Sec-WebSocket-Key: <generated>
Sec-WebSocket-Protocol: v12.stomp, v11.stomp, v10.stomp
Sec-WebSocket-Extensions: permessage-deflate
User-Agent: <UA с null account_id, null place_id>
Accept-Encoding: gzip
Host: myhome.proptech.ru
```

Response: `101 Switching Protocols`. Дальше — STOMP frames over WebSocket.

**Что неизвестно (до доп. HAR):**
- Какие именно типы событий уходят по WS, а какие — нет.
- Точки подписки (STOMP `SUBSCRIBE destination:/...`).
- Сообщения keep-alive vs реальные события.
- Поведение reconnect.

См. [audit A-47](../audit/project-audit.md) — research-фаза перед реализацией.

### 2. SIP (через `sipdevices` endpoint)

`POST /rest/v1/places/{p}/accesscontrols/{ac}/sipdevices` возвращает SIP credentials — приложение поднимает SIP UAC и принимает **INVITE** от sip-сервера оператора. Это вероятный канал для **входящих звонков в домофон** (как минимум audio-stream).

См. [audit A-49](../audit/project-audit.md). SIP-трафик идёт вне HTTP — Charles его не зафиксирует, для исследования нужен отдельный capture (Wireshark / `mitmproxy` с TCP mode).

### 3. FCM push (через `subscriberNotifications`)

В `POST /rest/v1/subscriberNotifications` отправляется `pushToken` (FCM). Это означает, что есть **secondary push-канал** через серверы Google. Какие события идут именно через FCM (а не WS) — неизвестно. Возможно — фоновая wake-up нотификация, после которой приложение само ходит за деталями по REST.

### Резюме на сегодня

| Канал | Зафиксирован handshake? | Зафиксировано содержимое? | Требуется доп. HAR? |
|---|---|---|---|
| WebSocket / STOMP | ✅ | ❌ | да — со сценарием активного события |
| SIP | ⚠️ только endpoint выдачи credentials | ❌ — другой транспорт | да — отдельный capture (не HAR) |
| FCM | ⚠️ только регистрация push token | ❌ | требует APK reverse engineering для FCM credentials |

**Вывод:** не строить spec для real-time фичи до получения как минимум одного HAR с реальным звонком в домофон. См. [audit A-47](../audit/project-audit.md).

## Notifications

### `POST /rest/v1/subscriberNotifications`

Подписка/регистрация уведомлений.

Request body shape:
```json
{
  "appVersionCode": "number",
  "installationId": "string",
  "appId": "number",
  "appVersion": "string",
  "platform": "string",           // "android"
  "pushToken": "string",          // 🎯 FCM push token
  "isDevelop": "boolean",
  "deviceManufacturer": "string",
  "deviceModelName": "string",
  "osVersion": "string",
  "deviceId": "string",
  "deviceType": "string"
}
```

В HAR ответ не пойман (вероятно 200 без тела или 4xx — нужен дополнительный анализ). **У нас не реализован** — потенциально нужно, если хотим использовать FCM-канал (но требует реверса APK для FCM project_id / sender_id).

## Что **не в нашем коде**, но в HAR (сводка для audit)

| Endpoint | Назначение | Priority |
|---|---|---|
| `wss://.../events` + STOMP probe | Real-time события | **P1** — основа для push-фичи [A-47] |
| `POST .../accesscontrols/{ac}/sipdevices` | SIP credentials | P1 — альт. путь для звонков [A-49] |
| `GET .../accesscontrols/{ac}/snapshots` | Snapshot домофона | P2 [A-48] |
| `GET /api/mh-camera-personal/.../cameras/{id}/events` | События камер | P2 [A-50] |
| `GET /rest/v2/forpost/cameras/{id}/events` | События forpost-камер v2 | P2 [A-50] |
| `POST .../device-installations` | Bootstrap config (STOMP URL) | P2 [A-51] |
| `POST /rest/v1/subscriberNotifications` | Регистрация FCM | P3 [A-54] |
| `GET /api/mh-camera/.../cameras/features/info` | Camera features | P3 |
| `GET .../settings/screens` | UI настройки | n/a — игнорируем |
| `GET /public/v1/operators` | Операторы | P3 [A-53] |
| Header `traceparent` | W3C tracing | P3 [A-52] |

## Известные отклонения нашего кода от приложения

| Что | Где | Решение |
|---|---|---|
| User-Agent: Pixel pool вместо Nothing A065 | [`const.py:41-106`](../../custom_components/elektronny_gorod/const.py#L41-L106) | приемлемо (приложение принимает любой Android-формат) |
| Нет `traceparent` header | [`http.py`](../../custom_components/elektronny_gorod/http.py) | [audit A-52] |
| Бизнес-ошибка в `forpost/.../video` response игнорируется | [`api.py:query_camera_stream`](../../custom_components/elektronny_gorod/api.py#L260) | проверять `data.Error`/`ErrorCode` явно |
| `query_old_cameras` (`/rest/v1/forpost/cameras`) — в HAR не наблюдался | [`api.py:query_old_cameras`](../../custom_components/elektronny_gorod/api.py#L200) | приложение этот endpoint **не использует** — наш fallback можно удалять |
| Поля `previewAvailable`, `allowVideo`, `allowCallMobile` в accesscontrols | не используем | потенциал для feature-driven entity |

## Что **не зафиксировано** в текущих HAR (требует доп. сбора)

- Сценарий **истечения access_token** — поведение приложения при 401.
- Сценарий **входящего звонка в домофон** — STOMP frame contents + SIP INVITE.
- Сценарий **открытия экрана баланса** — refresh финансов.
- Сценарий **первого запуска после установки** — bootstrap последовательность.
- Сценарий **background polling** — какие endpoints приложение зовёт в фоне.

Каждый из этих сценариев — отдельная HAR-сессия, см. [`runbooks/har-collection.md`](../aidd/runbooks/har-collection.md).

## Source HAR

Этот документ построен на основе **трёх HAR-снимков**, собранных в **январе 2026**. Конкретные имена файлов не фиксируем (см. [ADR-0006](../decisions/0006-mirror-app-behavior.md), правила в [conventions.md](../../conventions.md#версии-sha-и-другая-короткоживущая-информация) и [memory: har-sources-priority]).

Покрытие сценариев:

| # | Date | Account | Сценарии |
|---|---|---|---|
| 1 | 2026-01-07 | A | password auth + общий обзор + WebSocket handshake |
| 2 | 2026-01-11 | A | SMS reauth (4 дня спустя) |
| 3 | 2026-01-11 | B (с разрешением владельца) | SMS auth + просмотр камер + camera events + открытие домофона |

🟢 **Между 2026-01-07 и 2026-01-11 API контракт не менялся** — те же endpoints, те же shapes. Различия только в сценариях, которые пользователи выполняли.

🟡 **При расхождениях между сессиями — приоритет за самой свежей**. То же правило для будущих HAR.

HAR-файлы хранятся локально в `research/api/` (gitignored). Содержат реальные tokens / addresses / phones — никогда не попадают в репозиторий.

## Next reading

- [ADR-0006: Mirror application behavior](../decisions/0006-mirror-app-behavior.md)
- [ADR-0007: Stateful emulator baseline](../decisions/0007-stateful-emulator-baseline.md)
- [`overview.md`](overview.md) — current implementation
- [`../audit/project-audit.md`](../audit/project-audit.md) — A-47..A-54 (gaps)
- [`../roadmap.md`](../roadmap.md) — план интеграции новых endpoints
