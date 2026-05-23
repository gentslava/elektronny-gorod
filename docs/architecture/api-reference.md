Status: Draft (stub — заполняется после первого анализа HAR)
Owner: HA Expert Agent + owner
Last reviewed: 2026-05-23

Source files:
- `research/api/*.har` (local-only HAR-снимки)
- `custom_components/elektronny_gorod/api.py` (текущая реализация endpoints)
- `custom_components/elektronny_gorod/http.py` (headers, user-agent)
- `custom_components/elektronny_gorod/const.py` (`BASE_API_URL`, `APP_VERSION`, `ANDROID_DEVICES`)
- `custom_components/elektronny_gorod/user_agent.py` (формат User-Agent)
- `custom_components/elektronny_gorod/helpers.py` (auth hashing)

Related docs:
- `../decisions/0006-mirror-app-behavior.md` (как и почему zerkalim приложение)
- `../aidd/runbooks/har-collection.md` (как собирать HAR)
- `../aidd/runbooks/har-analysis.md` (будет создан) — как разбирать HAR в этот документ
- `overview.md`

Used by agents:
- HA Expert, Architecture, Security при любой работе с API

Quality gates:
- AUDIT_DONE (после первого HAR-анализа)

---

# API Reference — `myhome.proptech.ru`

> **Status: Draft.** Этот документ будет содержательно заполнен **только** после первого HAR-снимка реального приложения (см. [`../aidd/runbooks/har-collection.md`](../aidd/runbooks/har-collection.md)). До этого момента описание API строится из реверс-инжиниринга, зафиксированного в коде [`api.py`](../../custom_components/elektronny_gorod/api.py).
>
> Правила заполнения — в [ADR-0006: Mirror application behavior](../decisions/0006-mirror-app-behavior.md). Никаких «гипотез» — только то, что подтверждено в HAR.

## Общие свойства

- **Base URL:** `https://myhome.proptech.ru` (см. [`const.py:7`](../../custom_components/elektronny_gorod/const.py#L7)).
- **Транспорт:** HTTPS.
- **Формат:** JSON (request body для POST с `Content-Type: application/json; charset=UTF-8`).
- **Кодировка:** UTF-8.
- **Аутентификация:** Bearer token в header `Authorization: Bearer <access_token>` (для всех endpoints кроме `/auth/*`).

## User-Agent emulation

Формат — см. [`user_agent.py:43-52`](../../custom_components/elektronny_gorod/user_agent.py#L43-L52):

```
{phone_manufacturer} {phone_model} | Android {android_ver} | ntk | {app_ver_name} ({app_ver_code}) | {account_id} | {operator_id} | {uuid} | {place_id}
```

Пример:

```
Google Pixel 8 | Android 16 | ntk | 9.1.0 (90100000) | 1234567 | 1 | a1b2c3d4-... | 9876543
```

Источник параметров:
- `phone_manufacturer`, `phone_model` — случайный Pixel из [`const.py:41-106`](../../custom_components/elektronny_gorod/const.py#L41-L106).
- `android_ver` — [`const.py:39`](../../custom_components/elektronny_gorod/const.py#L39).
- `app_version` — [`const.py:34-37`](../../custom_components/elektronny_gorod/const.py#L34-L37). **Требует периодического обновления** под текущую версию приложения (через HAR).
- `account_id`, `operator_id`, `place_id` — runtime, из текущей сессии.
- `uuid` — сгенерированный per-entry, сохраняется в `entry.data`.

## Дополнительные headers

См. [`http.py:38-54`](../../custom_components/elektronny_gorod/http.py#L38-L54):

- `accept-encoding: gzip`
- `operator: <operator_id>` — добавляется, если `operator_id` известен.
- `authorization: Bearer <access_token>` — добавляется автоматически в `__request`.
- `content-type: application/json; charset=UTF-8` — для POST.

## Auth flow

### Сценарий 1: SMS authentication

1. `GET /auth/v2/login/{phone}` — query contracts. Возможные ответы:
   - **300 Multiple Choices** — список контрактов в body (`accountId`, `subscriberId`, `operatorId`, `placeId`, `address`).
   - **200 OK** — требуется password.
   - **204 No Content** — `unregistered`.
   - **400 Bad Request** — `invalid_login`.
2. `POST /auth/v2/confirmation/{phone}` — запрос SMS-кода. Body: `{accountId, address, operatorId, subscriberId, placeId}`. Возможные ответы:
   - **429 Too Many Requests** — `limit_exceeded`.
3. `POST /auth/v3/auth/{phone}/confirmation` — verify SMS. Body: `{accountId, confirm1, confirm2 (оба = code), login, operatorId, subscriberId}`. Ответ: `{accessToken, refreshToken, operatorId}`. Возможные ошибки:
   - **406 Not Acceptable** — `invalid_format`.

### Сценарий 2: Password authentication

1. `GET /auth/v2/login/{phone}` → если 200, то password flow.
2. `POST /auth/v2/auth/{phone}/password` — Body: `{login: phone, timestamp, hash1, hash2}`. Ответ: `{accessToken, refreshToken, operatorId}`. Ошибки:
   - **400 Bad Request** — `invalid_password`.

#### Crypto

См. [`helpers.py:35-47`](../../custom_components/elektronny_gorod/helpers.py#L35-L47):

- `hash1 = base64(sha1(password))`.
- `hash2 = md5("DigitalHomeNTKpassword" + login + password + simpletime + "789sdgHJs678wertv34712376")`.
- `simpletime = strftime("%Y%m%d%H%M%S")`.
- `timestamp = isoformat()[:-3] + "Z"`.

Reverse-engineered «соль» (`789sdgHJs678wertv34712376`) — часть протокола приложения, не наш секрет.

### Сценарий 3: Refresh access_token

**Status: unknown.** В наблюдавшихся HAR-сессиях использование refresh не зафиксировано. До получения HAR со сценарием истечения — не реализуем (см. [ADR-0006](../decisions/0006-mirror-app-behavior.md), [audit A-22](../audit/project-audit.md)).

## Endpoints — данные

Список из [`api.py`](../../custom_components/elektronny_gorod/api.py):

| Method | Path | Назначение | Auth | См. |
|---|---|---|---|---|
| GET | `/rest/v1/subscribers/profiles` | профиль подписчика | Bearer | `query_profile` |
| GET | `/rest/v3/subscriber-places` | список мест/квартир | Bearer | `query_places` |
| GET | `/rest/v3/subscriber-places?placeId={id}` | конкретное место | Bearer | `query_places(id)` |
| GET | `/api/mh-payment/mobile/v1/finance?placeId={id}` | баланс / финансы | Bearer | `query_balance` |
| GET | `/rest/v1/places/{place_id}/accesscontrols` | домофоны | Bearer | `query_access_controls` |
| GET | `/rest/v1/forpost/cameras` | старые камеры (deprecated в коде) | Bearer | `query_old_cameras` |
| GET | `/rest/v1/places/{place_id}/cameras` | камеры по месту | Bearer | `query_cameras` |
| GET | `/rest/v2/places/{place_id}/public/cameras` | публичные камеры | Bearer | `query_public_cameras` |
| GET | `/rest/v1/places/{place_id}/screen-sections` | секции экрана | Bearer | `query_sections` |
| GET | `/rest/v1/forpost/cameras/{id}/video?LightStream=0` | URL потока | Bearer | `query_camera_stream` |
| GET | `/rest/v1/forpost/cameras/{id}/snapshots?width=&height=` | JPEG snapshot | Bearer | `query_camera_snapshot` |
| POST | `/rest/v1/places/{p}/accesscontrols/{ac}/actions` | открыть AC (без entrance) | Bearer | `open_lock` (entrance=None) |
| POST | `/rest/v1/places/{p}/accesscontrols/{ac}/entrances/{e}/actions` | открыть конкретный вход | Bearer | `open_lock` |

Body для open: `{"name": "accessControlOpen"}`.

## HTTP status codes

Сводно по тому, что встречается в коде:

| Код | Значение в проекте | Где |
|---|---|---|
| 200 | OK / password-flow требуется | `query_contracts` |
| 204 | unregistered | `query_contracts` |
| 300 | список контрактов | `query_contracts` |
| 400 | invalid_login / invalid_password | auth endpoints |
| 401 | unauthorized | большинство endpoints |
| 406 | invalid_format (SMS) | `verify_sms_code` |
| 429 | limit_exceeded (SMS) | `request_sms_code` |

## Что **не подтверждено** через HAR (требуется research)

> Список ниже — это **не TODO** и **не гипотезы** для реализации. Это перечень вопросов, на которые ответит **только** HAR-анализ. До получения HAR — игнорировать.

- Точная частота background polling в приложении.
- Использование `refresh_token` (см. выше).
- Endpoints для истории звонков / визитов / событий.
- Push-channel (FCM) — какой FCM project, как регистрируется token.
- Параметры в headers, которые есть в приложении, но отсутствуют у нас.
- Что отправляется при первом запуске после долгого простоя.
- Что отправляется при reauth.
- Endpoints для платежей.
- Endpoints для управления услугами.

## Текущие отклонения от приложения (известные)

> Заполнить после первого HAR-сравнения. На сегодня:

- Возможно нерегулярная частота snapshot-запросов (в коде нет кэша).
- Возможно отсутствуют какие-то headers, которые отправляет приложение.

## Связь

- [ADR-0006](../decisions/0006-mirror-app-behavior.md) — обязательность зеркалирования.
- [`har-collection.md`](../aidd/runbooks/har-collection.md) — как собирать HAR.
- [`research/api/README.md`](../../research/api/README.md) — где лежат HAR-снимки.
- [`audit/project-audit.md`](../audit/project-audit.md) — A-22 и связанные пункты.

## Next reading

- For methodology: `../decisions/0006-mirror-app-behavior.md`
- For collection process: `../aidd/runbooks/har-collection.md`
- For current implementation: `overview.md`
