Status: Active
Owner: Reverse Engineer Agent + HA Expert Agent
Last reviewed: 2026-06-23 (A-81: sipdevices теперь используется — mint_sip_device, register-on-ring ADR-0012)

Source files:
- `custom_components/elektronny_gorod/api.py` (текущая реализация)
- `custom_components/elektronny_gorod/http.py` (headers, user-agent)
- `custom_components/elektronny_gorod/const.py` (BASE_API_URL, APP_VERSION)
- `custom_components/elektronny_gorod/user_agent.py` (формат UA)
- `custom_components/elektronny_gorod/helpers.py` (auth hashing)
- `custom_components/elektronny_gorod/fcm.py` (FCM-приём события вызова)

Related docs:
- `../decisions/0006-mirror-app-behavior.md`
- `../decisions/0007-stateful-emulator-baseline.md`
- `../aidd/runbooks/har-collection.md`
- `overview.md`
- `../audit/project-audit.md`

Used by agents:
- HA Expert, Architecture, Security, Reverse Engineer

Quality gates:
- AUDIT_DONE

---

# API Reference — `myhome.proptech.ru`

Reverse-engineered API reference для бэкенда `myhome.proptech.ru`, обслуживающего мобильные приложения «Мой Дом» (Электронный город / Новотелеком) и «Умный Дом.ру». Правила заполнения — [ADR-0006: Mirror application behavior](../decisions/0006-mirror-app-behavior.md).

🔴 **Конкретные значения (account_id, place_id, tokens, адреса, телефоны) — placeholders в этом документе.**

## Backends — separate ecosystems

Бэкенд `myhome.proptech.ru` обслуживает **три разных мобильных приложения**
(один backend, три фронтенда), плюс существует отдельный legacy-бэкенд
`my.2090000.ru` старого приложения «Электронный город»:

| Приложение | Package | Brand-code (UA) | Backend | Auth |
|---|---|---|---|---|
| **«Мой Дом»** (наша цель) | `ru.inetra.intercom` | `ntk` | `myhome.proptech.ru` | Signed-request (sha1+md5 hashes) → `MHAT<uuid>` token |
| «Умный дом» (Дом.ру) | `com.ertelecom.smarthome` | `erth` | `myhome.proptech.ru` (+ `api-mobile.dom.ru` для biller) | **Keycloak OAuth2 PKCE** через `id.dom.ru/realms/b2c`, `client_id=proptech-client` → **JWT** Bearer |
| «Электронный город» (старое) | `com.electronnijgorod.novosibirsk` | — | `my.2090000.ru` (`api.novotelecom.ru` для OAuth) | Keycloak OAuth2 (`client_id=mlk:android`) |

🎯 **`myhome.proptech.ru` принимает оба формата** Bearer-токенов:
- `MHAT<uuid>` (issued endpoint'ами `/auth/v[23]/auth/...`) — для «Мой Дом».
- Standard **JWT RS256** от Keycloak Дом.ру (`iss: https://id.dom.ru/realms/b2c`,
  `azp: proptech-client`) — для «Умный дом» Дом.ру.

UA-поле `brand-code` (4-е по счёту) — `ntk` для «Мой Дом», `erth` для «Умный
дом» Дом.ру. Это **operator/brand discriminator**, а не feature-flag.

**Наша HA integration реализует только «Мой Дом»** (`myhome.proptech.ru`).
Старое приложение использует совсем другой DTO (`{id, type, category,
objectId, title, isMain, address, model, mac, ip}` через
`/api/ntk-video-equipment/rest/v1/devices`) и Keycloak — реализация
параллельного backend-клиента — отдельная задача.

⚠️ **Capture HAR от ЭГ через MITM-proxy не работает.** Сервер `my.2090000.ru`
имеет anti-MITM WAF: 403 на первый же `GET /api/appVersionCheck` с
response header `x-sp-crid` (correlation id WAF). Patched через apk-mitm
APK НЕ помогает — header `ntk-user-agent: MLK/3.6.6 (...)` приложение
шлёт правильно (interceptor работает), но WAF блокирует по **TLS
fingerprint (JA3)**: handshake Charles/mitmproxy ≠ handshake OkHttp
Android. Решение существует только через **in-process Frida**
(frida-gadget injected в APK, hook OkHttp до encryption — TLS handshake
делает приложение само, свой JA3 сохраняется). Для нашей integration
ЭГ не нужен, в scope не входит.

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
<Manufacturer> <Model> | Android <ver> | <brand-code> | <app_version> (<app_version_code>) | <account_id> | <operator_id> | <uuid> | <place_id>
```

Поле `<brand-code>` — discriminator оператора:
- `ntk` — «Мой Дом» (Электронный город / Новотелеком), наш target.
- `erth` — «Умный дом» (Дом.ру / ЭР-Телеком).

Примеры:

```
Nothing A065 | Android 16 | ntk  | 9.7.0 (90700000)  | <account_id> | 1 | <uuid> | <place_id>
Nothing A065 | Android 16 | erth | 9.3.0 (90300010)  | <account_id> | 1 | <uuid> | <place_id>
```

Замечания:
- Наш `user_agent.py` использует пул Pixel — backend принимает любой Android-формат.
- Для **WebSocket handshake** user-agent содержит `null` в полях account_id и place_id (поля пустые до выбора place).
- Для **pre-auth** запросов (`device-installations`, `subscriberNotifications`-DELETE, public endpoints) — account_id пустой, place_id может быть пустым или текущим, operator_id может быть `null`.
- UUID стабилен per-install (один на одно устройство).
- Актуальная версия приложения «Мой Дом»: **9.7.0 (90700000)** — `APP_VERSION` в `const.py` может отставать.

### `traceparent` header

Приложение **отправляет** W3C trace context: `traceparent: 00-<32hex traceid>-<16hex spanid>-01`. Наш [`http.py`](../../custom_components/elektronny_gorod/http.py) этот header не отправляет. Гэп: [audit A-52](../audit/project-audit.md).

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

Crypto — см. [`helpers.py:35-47`](../../custom_components/elektronny_gorod/helpers.py#L35-L47).

Response shape:
```json
{
  "operatorId": 1,
  "operatorName": "string",            // "Новосибирск"
  "tokenType": "Bearer",
  "accessToken": "MHAT<uuid>",
  "expiresIn": null,                   // schema-поле присутствует, значение null
  "refreshToken": null,                // для password-flow refreshToken = null
  "refreshExpiresIn": null
}
```

На 400 — `invalid_password`.

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

Response shape:
```json
{
  "operatorId": 1,
  "operatorName": "Новосибирск",
  "tokenType": "Bearer",
  "accessToken": "MHAT<uuid>",
  "expiresIn": null,
  "refreshToken": "MHAT<uuid>",        // refreshToken == accessToken (одинаковое значение)
  "refreshExpiresIn": null
}
```

⚠️ **`refreshToken == accessToken`** в SMS-flow — это не баг парсинга, а реальный response. Бэкенд отдаёт один и тот же opaque token и в качестве access, и в качестве refresh — поэтому «refresh» сводится к переиспользованию того же токена. В password-flow `refreshToken = null` вообще.

На 406 — `invalid_format`.

### Refresh access_token

**Status: unknown.** При `refreshToken == accessToken` поведении refresh-flow, вероятно, существует, но триггерится только по явному 401. См. [ADR-0006](../decisions/0006-mirror-app-behavior.md), [audit A-22](../audit/project-audit.md).

### Альтернатива: Keycloak OAuth2 (брендинг Дом.ру)

Приложение «Умный дом» Дом.ру (`com.ertelecom.smarthome`) использует
**Keycloak OAuth2 Authorization Code + PKCE** flow:

```
GET  https://id.dom.ru/realms/b2c/.well-known/openid-configuration
GET  https://id.dom.ru/realms/b2c/protocol/openid-connect/auth?...
POST https://id.dom.ru/realms/b2c/login-actions/authenticate    ← username/password form
POST https://id.dom.ru/realms/b2c/protocol/openid-connect/token
     Body: code=<>&grant_type=authorization_code&redirect_uri=smarthome://com.ertelecom.smarthome/success-auth&code_verifier=<>
```

Token response: standard OIDC `{access_token: <JWT RS256>, ...}`. JWT
содержит `iss: https://id.dom.ru/realms/b2c`, `azp: proptech-client`. Этот
JWT **принимается напрямую** `myhome.proptech.ru` как Bearer-токен — то есть
backend поддерживает **bridge** между MHAT-токенами и Keycloak-JWT.

После получения JWT приложение делает:

1. **`GET /api/mh-customer-device/mobile/public/v1/customers/device-installations`** — bootstrap (см. ниже).
2. **`GET /api/mh-auth/mobile/v1/address`** — получить список адресов/контрактов, привязанных к Keycloak-юзеру (см. ниже).
3. **`POST /api/mh-auth/mobile/v1/customers/{customer_id}`** — select customer (см. ниже).
4. После этого — обычные `/rest/v3/subscriber-places`, `/rest/v1/places/...` запросы.

🔵 **Для нашей integration этот путь не реализуем** — но факт того, что
backend принимает JWT, оставляет дверь открытой на случай, если Электронный
город когда-нибудь перейдёт на тот же Keycloak.

🟢 **Cross-brand identity:** пользователь со своим **ЭГ-аккаунтом** (логин / телефон, выданные Электронным городом) **успешно логинится в приложение Дом.ру «Умный дом»** через Keycloak `id.dom.ru/realms/b2c`. Это означает:

- Keycloak `id.dom.ru/realms/b2c` — **общий identity provider для всех
  абонентов proptech-платформы**, включая ЭГ, Дом.ру, и других операторов
  на ЭР-Телеком-стеке. Пользователи биллингов разных брендов
  «перетекают» в один Keycloak-realm.
- Это подтверждает hint `AUTH_PROVIDER.erid` в bootstrap `device-installations`
  (см. ниже): даже клиент «Мой Дом» получает указание на Keycloak Дом.ру,
  потому что бекенд готов к **единому identity** через Keycloak.
- Гипотеза: миграция «Мой Дом» с MHAT-flow на Keycloak — вопрос времени,
  а не наличия инфраструктуры. После миграции наш auth-код может тоже
  перейти на OAuth2/PKCE, как у `com.ertelecom.smarthome` сегодня.

### `GET /api/mh-auth/mobile/v1/address`

🎯 **Только Keycloak-flow.** Список адресов для текущей сессии (Keycloak
JWT в Bearer). Используется ВМЕСТО `/auth/v2/login/{phone}` (которая
работает только для MHAT-flow).

Response shape:
```json
{
  "availableOperation": {
    "SHOW_ADDRESS_LIST": true,
    "ADD_ADDRESS": true,
    "SEARCH_ACCOUNT_IDS": true
  },
  "address": [
    {
      "subscriberId": "number",
      "accountId": "string",
      "placeId": "number",
      "address": "string",                // полный, не замаскированный
      "defaultLogin": "null|string",
      "operatorId": "number",
      "subscriberType": "number"          // observed: 1 = owner
    }
  ]
}
```

🔵 Для «Мой Дом» MHAT-flow эта функциональность реализована через 300-ответ
на `/auth/v2/login/{phone}` — содержимое то же, формат немного другой.

### `POST /api/mh-auth/mobile/v1/customers/{customer_id}`

🎯 **Только Keycloak-flow.** Body: пустой. Response: пустой (200). Скорее
всего «select active customer in session» — bind Keycloak-сессии к
конкретному subscriberId, после чего place-scoped endpoints начинают работать.

## Bootstrap / startup endpoints

### `GET /public/v1/operators`

Список доступных операторов (Электронный город, Дом.ру и т.д.).

Response shape:
```json
{
  "data": [
    {
      "id":              1,
      "dispName":        "Новосибирск",
      "location":        null,                                         // null для оператора 1 — определяется явно
      "authUrl":         "https://billing.novotelecom.ru/user/v1/",
      "infoUrl":         "https://2090000.ru",
      "mobileFeatures":  []
    },
    {
      "id":              2,
      "dispName":        "Санкт-Петербург",
      "location": {
        "coordinates": {
          "minPoint": { "longitude": 30.0896894, "latitude": 59.7761714 },
          "maxPoint": { "longitude": 30.5677067, "latitude": 60.0921253 }
        },
        "accountIdPrefix":   "780",
        "accountIdPrefixes": []
      },
      "authUrl":         "https://spb.db.ertelecom.ru/cgi-bin/ppo/es_webface/open_auth.authorize_password",
      "infoUrl":         "https://domru.ru",
      "mobileFeatures":  ["ALLOW_NEW_ADDRESS"]
    }
    // ... ещё N городов Дом.ру
  ]
}
```

🎯 **Открытия:**
- Оператор `id=1` («Новосибирск» / Электронный город) использует **billing.novotelecom.ru** для auth, остальные — **db.ertelecom.ru** (Дом.ру).
- `location.coordinates` — bounding box города (для auto-detect города по GPS).
- `accountIdPrefix` — первые цифры account_id (помогает в SEARCH_ACCOUNT_IDS).
- `mobileFeatures` — feature flags для UI (`ALLOW_NEW_ADDRESS` — можно добавить новый адрес из приложения).

Используется приложением при первом запуске. **У нас не реализован** — см. [audit A-53](../audit/project-audit.md).

### `POST /api/mh-customer-device/mobile/public/v1/customers/device-installations`

🎯 **Bootstrap endpoint** — конфигурация клиента после установки/каждого запуска.

Request body shape:
```json
{
  "appVersionCode": 90700000,
  "installationId": "<uuid>",          // тот же UUID, что и в UA
  "appId": 2,                          // 2 для «Мой Дом»
  "appVersion": "9.7.0",
  "platform": "google",                // именно "google", не "android"
  "isDevelop": false,
  "deviceManufacturer": "Nothing",
  "deviceModelName": "A065",
  "osVersion": "16",
  "deviceId": "<android_id 16hex>"
}
```

Response shape (с реальными значениями оператора Дом.ру):
```json
{
  "data": {
    "AUTH_PROVIDER": {
      "erid": {
        "url": "https://id.dom.ru/realms/b2c/",   // ← Keycloak Дом.ру (см. backends section)
        "clientId": "proptech-client"
      }
    },
    "MOBILE_URL": {
      "domain": {
        "backend": "myhome.proptech.ru",
        "genesys": "genesys.domru.ru",            // Genesys CCaaS (Дом.ру customer support)
        "stomp": "myhome.proptech.ru",            // 🎯 STOMP URL = тот же хост, что REST
        "expiredAt": 1780300042665                // unix-ms — когда обновить config
      },
      "policy": "https://static.proptech.ru/files/documents/politika-moydom.html"
    }
  }
}
```

🎯 **Ключевые открытия:**
- `stomp == backend` — STOMP server и REST backend на одном хосте; динамический discovery не даст другого URL.
- `AUTH_PROVIDER.erid` указывает **на Keycloak Дом.ру** даже для приложения «Мой Дом» — это hint, что backend готов к миграции на единый Keycloak (но пока «Мой Дом» использует свой MHAT-flow).
- Имя поля `erid` — вероятно, отсылка к российскому требованию рекламной маркировки (ERID), но используется здесь как identifier provider config.
- `appId: 2` для «Мой Дом» (для других приложений значение может отличаться).

**Частично используется:** интеграция шлёт этот POST в рамках привязки
push-токена (см. [Push-регистрация (FCM)](#push-регистрация-fcm), ADR-0011), но
**не** для динамического discovery URLs из ответа — `BASE_API_URL` пока
hardcoded. Динамический discovery поможет при миграции бэкенда. См. [audit A-51](../audit/project-audit.md).

### `GET /rest/v1/subscribers/profiles`

Профиль владельца аккаунта.

Response shape:
```json
{ "data": { "subscriber": { "id, accountId, name, ... } } }
```

Используется в [`api.py:query_profile`](../../custom_components/elektronny_gorod/api.py#L146).

### `GET /rest/v1/stomp/available-features`

🎯 **STOMP feature probe**. Приложение вызывает **перед** открытием WebSocket и периодически во время работы.

Response:
```json
{ "data": null }
```

🟡 **`data: null`** для абонентов «Электронного города» — STOMP-фичи **системно выключены** на уровне оператора (подтверждено: в личном кабинете <https://2090000.ru/> у ЭГ-абонента **нет** UI-опции, связанной со STOMP / real-time push / расширенными уведомлениями). Backend `proptech.ru` мультитенантный — STOMP может быть включён для других операторов на той же платформе (Дом.ру «Умный домофон+» и др.), но **не** для ЭГ. Это **не значит, что STOMP не нужен** — поведение при включённых фичах требует отдельной проверки (юзер другого оператора либо приёмочное тестирование вслепую).

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
          // index/district/locality часто = null.
        },
        "location": { "longitude", "latitude": "number" },
        "operatorId": "number",
        "autoArmingState": "boolean",
        "autoArmingRadius": "number"
      },
      "subscriber": { "id", "name", "accountId", "nickName" },
      "guardCallOut": { "active": "boolean", "phoneNumber": "string" },
      "payment": { "useLink": "boolean" },
      "provider": "string",                 // observed: "NTK" для оператора 1
      "blocked": "boolean"
    }
  ]
}
```

**У нас:** [`api.py:query_places`](../../custom_components/elektronny_gorod/api.py#L175) — используем только базовое. Не используем `address`, `location`, `payment`, `blocked`, `guardCallOut`.

🟡 **`subscriberState`** принимает значения вида `"out"` (вне дома). Это **runtime-состояние юзера** (auto-arming зависит от него), не статус контракта.

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
        {"id": <ENTRANCE_ID_1>, "type": "ACCESS_CONTROL_ENTRANCE", "order": 0},
        ...
      ],
      "hidden": [                            // скрытые пользователем
        {"id": <ENTRANCE_ID_2>, "type": "ACCESS_CONTROL_ENTRANCE"}
      ]
    },
    {
      "type": "PUBLIC_CAMERAS",
      "entities": [{"id": <CAMERA_ID_1>, "type": "PUBLIC_CAMERA", "order": 0}, ...],
      "hidden":   [{"id": <CAMERA_ID_2>, "type": "PUBLIC_CAMERA"}, ...]
    },
    {
      "type": "FAVORITES",
      "entities": [
        {"id": <CAMERA_ID_3>, "type": "PUBLIC_CAMERA", "order": 0},
        {"id": <ENTRANCE_ID_1>,    "type": "ACCESS_CONTROL_ENTRANCE", "order": 4}
      ],
      "hidden": []
    }
  ]
}
```

🎯 **Три секции** возможны на главном экране: `ACCESS_CONTROLS`,
`PUBLIC_CAMERAS`, `FAVORITES`. Последняя — пользовательское «избранное»
со смешанным содержимым (и подъезды, и камеры в одной секции). Детали
shape и поведения POST-варианта — см. ниже.

Если пользователь не настраивал — возвращается `{}` (пустой объект).

**Использование в интеграции:** `hidden` IDs прокидываются в camera/lock
dicts через флаг `hidden`. Entity для них получает
`_attr_entity_registry_enabled_default = False` — новые установки уважают
пользовательский выбор. Existing entities сохраняют выбор юзера в HA.

### `POST /api/mh-customer/mobile/v1/customers/places/{place_id}/settings/screens`

🎯 **Запись** настроек экрана (drag-and-drop / hide/show / favorites).
Body — массив объектов секций, **каждый POST = full replace** конфигурации
включённых секций (не diff). Backend перезаписывает целиком только те
секции, чьи `type` упомянуты в payload; не упомянутые не трогает.

**Enum типов секций** (`type` верхнего уровня):
- `ACCESS_CONTROLS` — раздел домофонов / подъездов.
- `PUBLIC_CAMERAS` — раздел камер (лифт + общедомовые + придомовые — все
  они классифицируются backend как `PUBLIC_CAMERA`, см. retention-таблицу выше).
- `FAVORITES` — отдельная секция «избранное» на главном экране, **может
  содержать смешанные типы** entity (и `ACCESS_CONTROL_ENTRANCE`, и
  `PUBLIC_CAMERA` одновременно).

**Enum типов entity** (`type` внутри `entities`/`hidden`):
- `ACCESS_CONTROL_ENTRANCE` — подъезд/entrance (НЕ accesscontrol_id, а
  именно entrance_id внутри AC).
- `PUBLIC_CAMERA` — все типы forpost-камер.

Request body shape:
```json
[
  {
    "type": "ACCESS_CONTROLS",
    "entities": [
      {"id": <ENTRANCE_ID_1>, "order": 0, "type": "ACCESS_CONTROL_ENTRANCE"},
      {"id": <ENTRANCE_ID_3>, "order": 1, "type": "ACCESS_CONTROL_ENTRANCE"},
      {"id": <ENTRANCE_ID_4>, "order": 2, "type": "ACCESS_CONTROL_ENTRANCE"}
    ],
    "hidden": []
  },
  {
    "type": "PUBLIC_CAMERAS",
    "entities": [
      {"id": <CAMERA_ID_5>, "order": 11, "type": "PUBLIC_CAMERA"},
      {"id": <CAMERA_ID_6>, "order": 12, "type": "PUBLIC_CAMERA"}
    ],
    "hidden": [
      {"id": <CAMERA_ID_2>, "type": "PUBLIC_CAMERA"}
    ]
  },
  {
    "type": "FAVORITES",
    "entities": [
      {"id": <CAMERA_ID_3>, "order": 0, "type": "PUBLIC_CAMERA"},
      {"id": <CAMERA_ID_4>, "order": 1, "type": "PUBLIC_CAMERA"},
      {"id": <ENTRANCE_ID_1>,    "order": 4, "type": "ACCESS_CONTROL_ENTRANCE"}
    ],
    "hidden": []
  }
]
```

**Поведенческие нюансы:**
- `order` — **глобально нумерованный**, не индекс-в-секции. В FAVORITES
  приложение использует `order: 0..2` для камер и `order: 3..5` для
  entrances — визуальная группировка внутри FAVORITES (сначала камеры,
  потом домофоны).
- Допустимы **gaps в order** между видимыми элементами (например, `11, 12, 13` без `0..10`) — backend gaps принимает.
- Удаление из FAVORITES = пропуск элемента в `entities` без добавления
  в `hidden`. Если секция целиком пропущена в POST — backend трактует
  как «не трогай».
- Hidden элементы из `PUBLIC_CAMERAS` могут сохранять `id` без `order`
  (`order` обязателен только для `entities`).

Response: пустое тело (HTTP 200).

🔵 **Применение для нашей integration:** **не используем для записи**
(HA имеет свой entity registry — дублировать UI оператора анти-паттерн).
GET-вариант (см. выше) используется для **чтения `hidden` IDs** →
`_attr_entity_registry_enabled_default = False`. Также: FAVORITES-секция
из GET (если присутствует) могла бы быть мапнута на HA labels/areas как
hint от пользователя — но это далеко не приоритет.

### `GET|POST /api/mh-customer/mobile/v1/customers/places/{place_id}/settings/do_not_disturb`

🎯 **Do Not Disturb** настройки уведомлений (звонки с домофона, новости от
УК).

GET response:
```json
{
  "do_not_disturb": [
    {"type": "DO_NOT_DISTURB_ROOT",       "name": "Не беспокоить",                          "status": false, "hint": "",                                                "editable": true},
    {"type": "INTERCOM_CALLS",            "name": "Звонки с домофона",                      "status": false, "hint": "",                                                "editable": true},
    {"type": "MANAGEMENT_COMPANY_CALLS",  "name": "Информирование от Управляющей компании", "status": false, "hint": "Звонки от Управляющей компании с новостями",     "editable": true}
  ]
}
```

POST body — массив объектов того же shape (без обёртки `{do_not_disturb: ...}`),
с обновлённым `status`. Response: пустое тело (200).

#### Семантика: master + 2 dependent

Структура **иерархическая** — один root-флаг управляет двумя зависимыми:

```
DO_NOT_DISTURB_ROOT         ← мастер (по умолчанию OFF, скрыт «collapsed»)
├── INTERCOM_CALLS            ← зависимый (виден в UI только когда root=ON)
└── MANAGEMENT_COMPANY_CALLS  ← зависимый (виден в UI только когда root=ON)
```

В UI приложения «Мой Дом» это работает так:
- По умолчанию `DO_NOT_DISTURB_ROOT.status = false` — на экране настроек
  виден **только** master-switch «Не беспокоить».
- При включении master (POST `[{type: DO_NOT_DISTURB_ROOT, status: true}]`)
  в UI **появляются** два дополнительных switch — `INTERCOM_CALLS` и
  `MANAGEMENT_COMPANY_CALLS`, изначально оба `false`.
- При выключении master зависимые switch скрываются из UI; их сохранённый
  status в backend, **похоже**, при этом сбрасывается (требует отдельной
  проверки сценарием toggle off→on→off).

🔵 **Дизайн для HA-интеграции** (это **уточнение semantics, не код**):

Лучший mapping в HA — **3 switch entity**:
- `switch.dnd_root` (master, всегда available).
- `switch.dnd_intercom_calls` (`_attr_available = root.status`).
- `switch.dnd_management_company_calls` (`_attr_available = root.status`).

Альтернативы:
- 1 master switch + 2 select entity внутри — более «компактно», но
  плохо ложится на automation.
- 3 независимых switch без зависимости — нарушает mirror-pattern, см.
  [ADR-0006](../decisions/0006-mirror-app-behavior.md): приложение это
  именно как master + dependent рисует.

Реальный effect — на канале входящих звонков: когда
`INTERCOM_CALLS.status=true` **и** `DO_NOT_DISTURB_ROOT.status=true`,
серверный SIP-INVITE / push не приходит. Это **полностью server-side
feature** — клиент только переключает флаг, всё применение на бэкенде.

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
      "forpostAccountId": "null|string",    // типично null
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
          "externalDeviceId": "null|string" // типично null
        }
      ]
    }
  ]
}
```

⚠️ **`externalCameraId` существует на двух уровнях** (ac.* и entrances[*].*).
В типичной single-entrance конфигурации значения совпадают, но schema
допускает их различие. Multi-entrance bug (camera показывает другую
entrance) подтверждает, что **приоритет должен быть entrance-level**:
маппить camera→entrance, не camera→ac. AC-level `externalCameraId`
следует трактовать как shortcut для случая ac-без-entrances, либо вообще
игнорировать.

**У нас:** [`api.py:query_access_controls`](../../custom_components/elektronny_gorod/api.py#L188) — используем только id/name/allowOpen/entrances. Не используем `previewAvailable`, `allowVideo`, `allowCallMobile` — это потенциал для дополнительной функциональности (см. audit).

### `POST /rest/v1/places/{place_id}/accesscontrols/{ac_id}[/entrances/{e_id}]/actions`

Открыть домофон. Body: `{"name": "accessControlOpen"}`. У нас реализован — [`api.py:open_lock`](../../custom_components/elektronny_gorod/api.py#L294).

### `POST /rest/v1/places/{place_id}/accesscontrols/{ac_id}/sipdevices`

🎯 **SIP devices** — минт SIP-кред для приёма входящих звонков от домофона.

**У нас:** [`api.py:mint_sip_device`](../../custom_components/elektronny_gorod/api.py#L399) — реализован (A-81). Зеркало приложения: запрос несёт `installationId` (та же device-identity, что у FCM-привязки — `user_agent.uuid`).

Request body:
```json
{ "installationId": "<UA.uuid>" }
```

Response shape:
```json
{
  "data": {
    "id":       "32hex",                              // SIP user ID (hex-string)
    "realm":    "<ac_id>.intercom.2090000.ru",        // 🎯 SIP server по доменной схеме
    "login":    "12hex",                              // SIP login (12-char hex)
    "password": "12hex"                               // SIP password (12-char hex)
  }
}
```

🎯 **Ключевые открытия:**
- **`realm` — на домене `2090000.ru`**, не на `proptech.ru`. SIP infrastructure
  привязана к бренду оператора (Электронный город / 2090000), а не к
  бэкенду «Мой Дом». Это совпадает с `infoUrl` оператора 1 в `/public/v1/operators`
  (`"infoUrl": "https://2090000.ru"`).
- **`realm` детерминированно зависит от ac_id**: `{ac_id}.intercom.2090000.ru`.
  Это даёт нам формулу для SIP endpoint **без** запроса `sipdevices` (но
  credentials всё равно нужно получать).
- Каждый вызов `POST .../sipdevices` возвращает **одинаковые** credentials
  для одного и того же `ac_id` (idempotent — повторный POST не ротирует
  пароль). Это значит credentials можно кэшировать.

Это реализовано в SIP-стеке `sip/` (A-81): по модели **register-on-ring (ADR-0012)**
интеграция минтит эти credentials при FCM `CALL_INCOMING`, регистрируется
`sip:<login>@<realm>` и принимает форкнутый сервером INVITE (100 Trying → held
до нажатия «Ответить» → 200 OK). Полная картина
SIP-флоу (FCM → REGISTER → INVITE → 200 OK → RTP-latching, доказано pcap) — в
[`call-answer-model.md`](../features/intercom-two-way-audio/call-answer-model.md).
SIP-трафик идёт вне HTTPS (UDP-транспорт), `realm` содержит acId →
в `SENSITIVE_KEYS`. См. [audit A-49](../audit/project-audit.md) (исходный
research) и [A-81](../audit/project-audit.md) (реализация).

### `GET /rest/v1/places/{place_id}/accesscontrols/{ac_id}/snapshots`

🎯 **Snapshot домофона** (отдельно от forpost-камер). Возвращает JPEG bytes.

Query parameters:
- `entranceId={entrance_id}` — обязателен (multi-entrance AC: каждая
  entrance имеет свою preview).
- `width={px}` — типично `320`.
- `height={px}` — типично `180`.

Полный URL: `/rest/v1/places/{p}/accesscontrols/{ac}/snapshots?entranceId={e}&width=320&height=180`.

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

Query: `width={px}&height={px}` (observed: 320x180).

🎯 **HTTP 500 error shape:**
```json
{
  "errorCode": "-1",
  "errorMessage": "Произошла техническая ошибка"
}
```

Это **общий формат для forpost-endpoints**: `{errorCode: string, errorMessage: string}`.
Может быть transient (одна и та же камера иногда 200, иногда 500).
**Наш `api.py:query_camera_snapshot` сейчас на 500 возвращает что попало
через `e.args[0]`** — нужно парсить JSON-тело явно.

### `GET /rest/v1/forpost/cameras/{id}/video`

Stream URL.

**Live stream** — `?LightStream=0` (используется нашим кодом).

**Video archive playback:**
```
?TS=<unix>&TZ=<tz_seconds>&LightStream=0&Format=H264&Speed=-1.0
```

Параметры:
- `TS` — unix timestamp (seconds, точка возобновления записи).
- `TZ` — смещение TZ в секундах (например `25200` = UTC+7 / Новосибирск).
- `LightStream=0` — то же что для live (битрейт).
- `Format=H264` — codec.
- `Speed=-1.0` — при перемотке назад.

Приложение использует тот же endpoint и для live, и для playback — разница только в параметрах. Это **функциональность видеоархива** (просмотр прошлых записей).

Response shape (success):
```json
{
  "data": {
    "URL":       "string",       // FLV/RTSP URL
    "Error":     "null|string",  // ← бизнес-ошибка даже при HTTP 200
    "ErrorCode": "null|number",
    "Status":    "null|string"
  }
}
```

🎯 **HTTP 500 — business error** (playback):
```json
{
  "errorCode": "11005",
  "errorMessage": "Архив доступен с <DD.MM.YYYY HH:MM:SS>"
}
```

Это **бизнес-ошибка с HTTP 500** (не technical 500): когда юзер просит
архив за пределами retention окна. `errorCode 11005` = «archive out of
range», `errorMessage` содержит локализованную дату начала retention.

🟢 **Video retention зависит от типа камеры** (НЕ от тарифа). Дефолты
оператора:

| Тип камеры | Retention |
|---|---|
| Домофоны (`accessControl`) | **14 дней** |
| Камеры лифтов / общедомовые / публичные | **7 дней** |

⚠️ **Различие «лифт» vs «публичная/придомовая»** по retention отсутствует — у обеих категорий окно 7 дней. В `/cameras` listing'е тип камеры указывается отдельным полем (см. ниже), но retention зависит **только** от двух классов: `accessControl source` vs всё остальное.

Дополнительные тарифы / опции расширения retention для абонентов ЭГ
не доступны.

🟡 **Rolling-window**: граница retention выражается в `errorMessage` как
абсолютный timestamp начала окна и **«ползёт» по wall-clock в реальном
времени**. Запрос на `TS = граница + ΔT` сначала проходит, через ΔT
времени тот же `TS` уже возвращает 11005 со сдвинутой вперёд границей.
**Близко к границе окна запросы могут случайно проваливаться** —
клиентский код должен либо отступать на 1-2 минуты от теоретической
границы, либо повторять с увеличенным TS на 11005.

Для нашей интеграции это значит: при выборе типа камеры в HA UI или
валидации timestamp range — учитывать тип источника (домофон vs forpost
camera типа лифт/общедомовая), чтобы не плодить ложные 500-ошибки.

⚠️ Даже **HTTP 200** может содержать `Error != null` (top-level json
поле). Наш [`api.py:query_camera_stream`](../../custom_components/elektronny_gorod/api.py#L260) проглатывает через `except Exception → None`, что прячет бизнес-ошибки.

### `GET /rest/v1/forpost/events/{event_id}/downloads?container=mp4`

🎯 **Скачивание видеозаписи события** (motion event с одной из camera).
Используется приложением после клика на конкретный event в истории.

Response:
```json
{
  "data": "https://myhome-savevideo.ertelecom.ru/?<32hex>=<hex>.mp4"
}
```

🎯 **Особенности:**
- `data` — **строка-URL**, не объект (в отличие от других endpoint'ов).
- Хост `myhome-savevideo.ertelecom.ru` — отдельный сервер видеохранилища
  («ertelecom» = ЭР-Телеком, материнская компания Дом.ру). URL содержит
  hex-токены — вероятно одноразовый signed-link.
- Query `container=mp4` — формат контейнера; возможны и другие форматы (не подтверждено).

🔵 Для нашей integration — потенциал для `media_source` / event-driven
recording в HA, но требует UX-фичи «история событий». См. [audit A-50](../audit/project-audit.md).

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

Альтернативный (v2) endpoint для событий камер. **Основной** в современном клиенте «Мой Дом» (приложение часто и активно его поллит).

Query parameters:
- `UpperDate=<ISO Z>` — верхняя граница времени (формат: `YYYY-MM-DDTHH:MM:SSZ`).
- `LowerDate=<ISO Z>` — нижняя граница.
- `Count=100` — лимит записей.
- `orderByTime=DESC` — сортировка.

Response shape (отличается от `mh-camera-personal/.../events` !):
```json
{
  "data": [
    {
      "isAvailable":    true,
      "ID":             21346035251,    // event_id (для downloads endpoint)
      "Time":           1779437099,     // unix timestamp
      "Duration":       44,             // seconds
      "EventSubjectID": 126,            // event type code (126 = motion observed)
      "Message":        "► 15:04:59 - 15:05:43",  // forматированная строка
      "IsGotoEnabled":  1,              // 1 = есть запись для скачивания
      "CameraID":       5119293         // 🟡 внутренний forpost-id, отличается от {id} в URL
    }
  ]
}
```

🟡 **Важное расхождение**: response содержит `CameraID: 5119293`, но запрос
делается к `/cameras/<CAMERA_ID_1>/events` — внутренний forpost-id отличается от
camera-id из `/rest/v2/places/.../public/cameras`. Это два разных
идентификатора одной физической камеры в разных подсистемах forpost.

⚠️ **HTTP 200 + IsGotoEnabled=0** — записи нет (она не сохранилась /
истекло retention). На `IsGotoEnabled=1` можно идти за video URL через
`/rest/v1/forpost/events/{ID}/downloads`.

## Финансы / баланс

### `GET /api/mh-payment/mobile/v1/finance?placeId={place_id}`

Баланс лицевого счёта.

Response shape:
```json
{
  "data": {
    "balance":        738.8731,                       // 🎯 текущий баланс (rubles, float, до 4 знаков)
    "blockType":      "NOT_BLOCKED",                  // строка enum (observed: "NOT_BLOCKED")
    "amountSum":      907.0,                          // 🟡 сумма очередного платежа? («рекомендуемый платёж»)
    "targetDate":     "2026-06-08T07:49:16.941400545Z",  // 🟡 дата следующего списания
    "paymentLink":    "https://2090000.ru/oplata/",   // ссылка на оплату через биллинг
    "daysToBlock":    null,                           // дней до блокировки (null когда NOT_BLOCKED)
    "daysToWarning":  null,                           // дней до предупреждения
    "company":        null,                           // вероятно: УК / провайдер
    "blocked":        false                           // bool-shortcut для blockType
  }
}
```

🎯 **Новые поля для интеграции:** `amountSum`, `targetDate`, `daysToBlock`,
`daysToWarning`, `paymentLink` — потенциал для дополнительных entity:
- `sensor.balance_next_payment_amount` (MONETARY).
- `sensor.balance_next_payment_date` (TIMESTAMP).
- `binary_sensor.balance_blocked`.
- `sensor.balance_days_to_block` (когда `blockType != NOT_BLOCKED`).
- `button` для открытия `paymentLink` в браузере.

В нашем коде — [`api.py:query_balance`](../../custom_components/elektronny_gorod/api.py#L164) — используем только `balance`.

## Event log (история действий)

### `POST /rest/v1/events/search?page={n}&sort=occurredAt,DESC`

🎯 **История событий** (вызовы домофона, motion-события и т.д.) — **поиск
с фильтром**. Используется приложением для экрана «История».

Request body:
```json
{ "placeIds": [<PLACE_ID>] }
```

Query: `page=<0..N>` (pagination), `sort=occurredAt,DESC` (URL-encoded запятая, `sort=occurredAt%2CDESC`).

Response shape (Spring Pageable):
```json
{
  "content": [
    {
      "id":              "<EVENT_ID>",                                     // event_id
      "placeId":         <PLACE_ID>,
      "eventTypeName":   "accessControlCallAccepted",                      // 🎯 тип события
      "timestamp":       "<UNIX_TS>",                                      // unix seconds (string)
      "message":         "Вызов с домофона <gate name>",                   // локализованный
      "source": {
        "type": "accessControl",                                           // 🎯 тип источника
        "id":   <AC_ID>                                                      // ac_id / camera_id и т.д.
      },
      "header":           null,
      "value": {
        "type":  "boolean",
        "value": true
      },
      "eventStatusValue": null,
      "actions":          []
    }
  ],
  "pageable": { "sort": {"empty": false, "sorted": true, "unsorted": false},
                "offset": 0, "pageNumber": 0, "pageSize": 20,
                "paged": true, "unpaged": false },
  "last":            false,
  "totalPages":      2,
  "totalElements":   21,
  "size":            20,
  "number":          0,
  "sort":            { "empty": false, "sorted": true, "unsorted": false },
  "first":           true,
  "numberOfElements": 20,
  "empty":           false
}
```

#### Pagination behaviour

- **Page size = 20** (фиксированный — `size`, `pageSize` всегда 20). Параметр
  `size=` в запросах **не передаётся** — backend применяет default.
- **`totalElements` и `totalPages` растут постранично** — backend не знает
  точное количество элементов заранее, увеличивает счётчик «найдено вплоть
  до текущей страницы + 1 запас». Это **anti-pattern для polling**: чтобы
  узнать реальный размер log, придётся читать все страницы.
- **`last=true` означает реальное исчерпание данных**, а не лимит UI.
  Неполная последняя страница (`numberOfElements < 20`) сопровождается
  `last: true` — больше данных нет.
- **Лимита 10 страниц в API нет.** Клиент сам не ставит лимит на скролл,
  он останавливается, когда сервер вернул `last: true`.
- **Retention окно: ~6 месяцев истории событий.** Старее — backend возвращает
  `last: true` на соответствующей странице.

🎯 **Применение для интеграции:**
- Универсальный event log — потенциально может содержать **больше типов
  событий**, чем только `accessControlCallAccepted`. Каждый тип события
  требует отдельной проверки (motion, дверь открыта вручную, баланс пополнен и т.д.).
- Это **REST-альтернатива WebSocket-каналу** — приложение использует
  и WS для real-time, и `/events/search` для backfill / истории.
- **Backfill при первой настройке HA:** при первом setup интеграции можно
  одноразово загрузить до 6 месяцев истории (страница за страницей до
  `last:true`) → импортировать в HA logbook / event entity. Дальше — только
  инкрементальное обновление (polling page=0 раз в N минут, дедуп по `id`).
- Для HA: возможен `event` entity, который polls этот endpoint раз в N
  минут и публикует новые события (но дублирует STOMP-канал — лучше
  использовать STOMP, когда он будет реализован).

🔵 **У нас не реализован.**

## Real-time каналы (несколько одновременно)

🟡 **Важно:** WebSocket handshake пойман, но **содержимое STOMP-фреймов недоступно** для capture через стандартные HTTPS-тоннели (Charles `.chlz` обычно не сохраняет тело WebSocket-сообщений). Какие именно события идут через WS, а какие через другие каналы — **открытый вопрос**, требующий non-HTTP capture.

Идентифицировано **минимум три** потенциальных канала real-time доставки:

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

**Что неизвестно:**
- Какие именно типы событий уходят по WS, а какие — нет.
- Точки подписки (STOMP `SUBSCRIBE destination:/...`).
- Сообщения keep-alive vs реальные события.
- Поведение reconnect.

См. [audit A-47](../audit/project-audit.md) — research-фаза перед реализацией.

### 2. SIP (через `sipdevices` endpoint)

`POST /rest/v1/places/{p}/accesscontrols/{ac}/sipdevices` возвращает SIP credentials — приложение поднимает SIP UAC и принимает **INVITE** от sip-сервера оператора. Это вероятный канал для **входящих звонков в домофон** (как минимум audio-stream).

См. [audit A-49](../audit/project-audit.md). SIP-трафик идёт вне HTTP — для исследования нужен отдельный capture (Wireshark / `mitmproxy` с TCP mode).

### 3. FCM push (через `subscriberNotifications`) — ✅ подтверждён как канал вызова

🟢 **Разрешено экспериментом** (`research/intercom-call-probe/FINDINGS.md`,
ADR-0011): событие «вызов с домофона» приходит **именно по FCM**
(`CALL_INCOMING` / `CALL_END_ANSWERED_MOBILE`), латентность ~0.5–1 c, богатый
payload (gate / place / apartment / call-id / allow_open). `pushToken`
регистрируется через `subscriberNotifications` + `device-installations`, сам
data-message идёт через серверы Google. Структура payload и таксономия —
[Push-регистрация (FCM)](#push-регистрация-fcm). Реализовано в интеграции
([`fcm.py`](../../custom_components/elektronny_gorod/fcm.py) + `event` entity).

### Резюме

| Канал | Несёт событие вызова | Уровень | Латентность | Статус |
|---|---|---|---|---|
| **FCM** | ✅ да (`CALL_INCOMING` / `CALL_END_…`) | аккаунт (все домофоны разом) | ~0.5–1 c | **реализован** (ADR-0011) |
| SIP | ✅ да (`INVITE`) | per-домофон | ~0.5 c | медиа-канал разговора, future (PRD-two-way-audio) |
| WebSocket / STOMP | ❌ нет (только `availableFeatures`) | аккаунт | — | не несёт вызов; backend feature-flag null для ЭГ ([A-47](../audit/project-audit.md)) |

**Вывод:** FCM — основной и достаточный канал сигнала вызова. SIP ценен только
как медиа-канал (разговор) — отдельная будущая фича. STOMP `/events` не несёт
событие вызова.

## Post-push pattern (что приложение делает после FCM-push о звонке)

🟡 **Сам FCM-push идёт вне HTTPS** (через Google Play Services / GCM-сокет), поэтому не доступен через стандартные MITM-инструменты. Но паттерн восстанавливается **по тому, что приложение делает сразу после wake-up**, до того как пользователь нажмёт «открыть дверь».

### Canonical post-push sequence (~ 8 секунд)

```
T+0.0s   POST /api/mh-customer-device/mobile/public/v1/customers/device-installations
         → re-register FCM token (приложение проснулось)
T+0.2s   WSS  /events                                  → 101 Switching Protocols (re-open STOMP)
T+0.4s   GET  /rest/v3/subscriber-places               → refresh places list
T+0.5s   POST /rest/v1/subscriberNotifications         → notify backend о live-session
T+0.5s   GET  /rest/v1/places/{p}/accesscontrols/{ac1}/snapshots  ┐
T+0.5s   GET  /rest/v1/places/{p}/accesscontrols/{ac2}/snapshots  ├ parallel
T+0.5s   GET  /rest/v1/places/{p}/accesscontrols/{ac3}/snapshots  ┘
T+0.5s   GET  /rest/v1/forpost/cameras/{cam1}/snapshots           ┐
T+0.5s   GET  /rest/v1/forpost/cameras/{cam2}/snapshots           ┤ parallel — все
T+0.5s   GET  /rest/v1/forpost/cameras/{cam3}/snapshots           ┤ camera previews
T+0.5s   GET  /rest/v1/forpost/cameras/{cam4}/snapshots           ┘
T+0.7s   GET  /rest/v1/stomp/available-features        → STOMP probe (всегда null)
T+0.8s   GET  /rest/v1/places/{p}/accesscontrols       → refresh AC list
T+0.8s   GET  /rest/v1/places/{p}/screen-sections      → UI layout
T+0.8s   GET  /rest/v1/places/{p}/cameras              → refresh cameras list
T+1.0s   GET  /api/mh-customer/.../settings/screens    → UI customisation
T+1.0s   GET  /rest/v2/places/{p}/public/cameras       → forpost-camera details
T+3-5s   GET  /rest/v1/places/{p}/accesscontrols/{active_ac}/snapshots
         → повторный snapshot АКТИВНОГО домофона (того, с которого звонок)
T+8s     POST /rest/v1/places/{p}/accesscontrols/{ac}/entrances/{e}/actions
         → пользователь нажал «открыть»
```

### Стабильные маркеры post-push wake-up

| Маркер | Описание |
|---|---|
| POST `device-installations` | re-register FCM token при wake-up |
| WSS `/events` 101 | re-open STOMP (даже если STOMP-фичи `data:null`) |
| GET `subscriber-places` | refresh places |
| POST `subscriberNotifications` | server-side notify |
| GET всех `accesscontrols/{ac}/snapshots` parallel | preview каждой двери в списке |
| GET всех `forpost/cameras/{id}/snapshots` parallel | preview всех камер |
| Повторный GET snapshot активного `ac` через 3-5s | UI обновляет картинку звонка |

### Что это даёт для нашей HA-интеграции

🎯 **Рецепт для будущей real-time / push-фичи (Roadmap итерация 4):**

Поскольку у нас **нет** прямого канала FCM/STOMP, мы можем имитировать
post-push поведение приложения **через polling**:

1. **Detect:** coordinator замечает новое событие в `/rest/v1/events/search?page=0`
   с `eventTypeName == "accessControlCall*"` и `timestamp > last_seen`.
2. **React (повторить canonical sequence):**
   - GET snapshot активного `accesscontrol/{source.id}` → обновить
     `camera.intercom_<ac>` entity (snapshot).
   - GET общий список `accesscontrols` → обновить state всех door-button.
   - Эмитить HA-event типа `elektronny_gorod_intercom_call`
     с `{ac_id, event_id, timestamp, message}` → пользователь может
     повесить automation (notify через mobile, светильник, sounded alert).
3. **Backfill:** через 30-60s сделать второй GET snapshot активного ac
   (как приложение) — на случай задержки apparition картинки в forpost.

🟡 **Что НЕ делать в imitation:**
- POST `subscriberNotifications` — это server-side hook, не имеет смысла
  для HA (мы не получаем FCM в принципе).
- POST `device-installations` — то же самое.
- WSS `/events` — отдельная research-фаза, см. [audit A-47](../audit/project-audit.md).

🔵 **Лимиты polling-imitation:** задержка detect = `update_interval` coordinator
(сейчас 5 минут — ADR-0003). Для real-time-feature нужен либо более
частый polling endpoint `/events/search?page=0`, либо WS-канал. См.
[audit A-47](../audit/project-audit.md).

## Push-регистрация (FCM)

Канал доставки события «вызов с домофона» — **FCM data-push**, а не
эти REST-эндпоинты. REST лишь **регистрирует** push-токен у оператора;
сам пуш приходит через серверы Google (вне HTTPS, см. ниже). Реализовано
в интеграции — [`api.py:register_push_device` / `unregister_push_device`](../../custom_components/elektronny_gorod/api.py),
приём FCM — [`fcm.py`](../../custom_components/elektronny_gorod/fcm.py). Решение
зафиксировано в [ADR-0011](../decisions/0011-doorbell-fcm-channel.md).

🔴 **Все значения (`pushToken`, `installationId`, `deviceId`, `appId`,
`apiKey`/`senderId` Firebase, account/place) — placeholders.**

### `POST /api/mh-customer-device/mobile/public/v1/customers/device-installations`

🎯 **Регистрация device-installation** (тот же эндпоинт, что и bootstrap, см.
выше — приложение шлёт его и для bind push-токена). При регистрации push
тело включает `pushToken`.

### `POST /rest/v1/subscriberNotifications`

Привязка push-токена у оператора. Приложение шлёт **тот же body-shape**, что и
на `device-installations`. Оба POST идут с одинаковым телом (зеркало приложения).

Request body shape (оба POST):
```json
{
  "appVersionCode": "number",
  "installationId": "string",       // тот же UUID, что и в UA (per-install)
  "appId": "number",                // 2 для «Мой Дом»
  "appVersion": "string",
  "platform": "string",             // "google" (не "android")
  "isDevelop": "boolean",
  "deviceManufacturer": "string",
  "deviceModelName": "string",
  "osVersion": "string",
  "deviceId": "string",             // стабильный hex, производный от installationId
  "deviceType": "string",           // "MOBILE_APPLICATION"
  "pushToken": "string"             // 🎯 FCM push token (<sender>:<opaque>)
}
```

Response: 200 (тело отсутствует).

### `DELETE /rest/v1/subscriberNotifications`

Request body — **тот же shape, что POST, но без `pushToken`** (наблюдалось в
HAR: приложение шлёт DELETE с телом device-регистрации без поля токена).

Response: 200.

🎯 **Назначение:** unregister push token. Приложение вызывает при **logout /
uninstall**. Интеграция вызывает при **unload / disabling config_entry** —
чтобы корректно отписать токен и не получать уведомления от мёртвой HA-сессии.

### FCM data-push: событие вызова (вне HTTPS)

Само событие вызова приходит **по FCM** (Firebase data-message), не через REST
выше. Чтобы принять его без Android-устройства, интеграция эмулирует
регистрацию FCM-клиента приложения (`firebase-messaging`: checkin → register →
MTalk-сокет) с публичным Firebase-конфигом приложения (`project_id`, `app_id`,
`sender_id`, `api_key`, `bundle_id` — общие для всех пользователей, не секреты;
см. [ADR-0011](../decisions/0011-doorbell-fcm-channel.md)). Per-device FCM-токен
и FCM-creds генерятся в рантайме, в этом документе — placeholders.

🟢 Эмпирически (`research/intercom-call-probe/FINDINGS.md`) подтверждено, что
вызов несёт **именно FCM**, а не STOMP `/events` (только `availableFeatures`)
и не SIP (медиа-канал самого разговора).

Data-payload (структура, плейсхолдеры):
```jsonc
{
  "from": "<senderId>",
  "fcmOptions": { "analyticsLabel": "<PushType>" },
  "data": {
    "PushType":         "<CALL_INCOMING | CALL_END_ANSWERED_MOBILE>",
    "PushTitle":        "<локализованный заголовок>",
    "PlaceId":          "<place_id>",
    "AccessControlId":  "<ac_id>",            // какой домофон
    "GateName":         "<имя двери>",
    "Apartment":        "<квартира>",
    "Sender":           "<apartment>@<ac_id>.intercom.<...>",
    "Call-ID":          "<call_id>",          // связывает start ↔ end
    "CallStarted":      "<ISO8601>",
    "CallInvalidated":  "<ISO8601>",          // окно ~30 c; авто-сброс по нему
    "AllowOpen":        "<true|false>",       // можно открыть дверь из события
    "IsSystem":         "<true|false>"
  }
}
```

⚠️ `Apartment` / `Sender` у **калиток** (общих на комплекс) приходят
**gate-кодированными** с префиксом корпуса/секции (подтверждено сырым
FCM-захватом в `research/intercom-call-probe/`); у подъездов — уже чистый номер.
Канонический номер квартиры жильца берётся из `place.address.apartment`
(subscriber-places), **не** из `Apartment`/`Sender` пуша.

Таксономия `PushType` (наблюдалось):

| `PushType` | Когда | event-тип в HA |
|---|---|---|
| `CALL_INCOMING` | начало вызова | `ring` |
| `CALL_END_ANSWERED_MOBILE` | вызов **отвечен на другом устройстве** пользователя (тот же `Call-ID`) | `ended` (`reason: answered_elsewhere`) |

⚠️ `CALL_END_ANSWERED_MOBILE` означает ровно **«ответили на другом устройстве»** —
это **не** отказ/отклонение со стороны оператора и **не** фантомное событие. Других
end-пушей оператор не шлёт: сброс с панели / истечение времени ответа / открытие
двери **отдельного пуша не дают** — вызов завершается молча по `CallInvalidated`
(окно ~30 c).

Поэтому event-сущность сама закрывает «зависший» вызов по таймеру. Атрибут
`reason` у `ended` различает три случая:

| `reason` | Что значит | Источник |
|---|---|---|
| `answered_elsewhere` | ответили на другом устройстве | реальный пуш `CALL_END_ANSWERED_MOBILE` |
| `timeout` | никто не ответил, окно истекло | синтетический — таймер по `CallInvalidated` ([`event.py`](../../custom_components/elektronny_gorod/event.py)) |
| _(отсутствует)_ | нет активного вызова, idle | стартовый baseline при первом запуске |

**Открытие двери из события:** `AllowOpen: "true"` → существующий
`POST /rest/v1/places/{place_id}/accesscontrols/{ac_id}/actions`
с телом `{"name": "accessControlOpen"}` (см. раздел Access controls). Видео —
go2rtc по `externalCameraId`. Полный цикл «звонок → FCM-пуш → программное
открытие» проверен вживую.

## Next reading

- [ADR-0006: Mirror application behavior](../decisions/0006-mirror-app-behavior.md)
- [ADR-0007: Stateful emulator baseline](../decisions/0007-stateful-emulator-baseline.md)
- [`overview.md`](overview.md) — current implementation
- [`../audit/project-audit.md`](../audit/project-audit.md) — A-47..A-54 (gaps)
- [`../roadmap.md`](../roadmap.md) — план интеграции новых endpoints
