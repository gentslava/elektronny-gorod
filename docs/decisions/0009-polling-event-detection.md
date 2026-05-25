# ADR-0009: Polling `/events/search` для real-time event detection вместо STOMP/FCM/SIP

- **Status:** accepted
- **Date:** 2026-05-25
- **Owner:** Architecture + Reverse Engineer Agent

## Context

Интеграция должна детектировать события домофона (звонок, открытие двери)
для триггерования HA-автоматизаций («звонок → включи свет в коридоре»,
«открытие двери → запиши видео», и т.п.). Сейчас coordinator polls
основное состояние каждые 5 минут — это **не подходит** для real-time
событий типа звонков (нужна latency < 1 минуты).

Reverse engineering приложения «Мой Дом» (ntk 9.7.0) выявил **три**
независимых канала, через которые приложение получает события в
реальном времени:

| Канал | Транспорт | Что несёт | Доступность для HA |
|---|---|---|---|
| **STOMP** | `wss://myhome.proptech.ru:443/events` | События в открытом приложении | Feature flag `/rest/v1/stomp/available-features` возвращает `{data: null}` для всех наблюдаемых абонентов ЭГ. Backend feature, вероятно платная фича другого оператора (Дом.ру «Умный домофон+»). |
| **FCM** | Google Cloud Messaging | Push уведомления о звонках при свёрнутом приложении | Backend регистрирует FCM token приложения через `POST /rest/v1/subscriberNotifications`. Доставляется в приложение через Google Play Services (отдельный TLS-туннель, не виден в HAR). |
| **SIP** | UDP/TCP по SIP-протоколу | Голосовой канал звонка (INVITE + RTP audio) | Credentials через `POST .../accesscontrols/{ac}/sipdevices`. Регистрация SIP UAC на realm `*.intercom.2090000.ru`. |

Дополнительно: backend даёт **REST-альтернативу** real-time каналам:
`POST /rest/v1/events/search` (Spring Pageable) — universal event log
с pagination (size=20), retention ~6 месяцев (наблюдается). Используется
приложением для backfill истории при scroll.

Возникает вопрос: какой канал использовать для real-time detection в HA?

## Decision

**Реализовать polling `/rest/v1/events/search?page=0` каждые 15-30 секунд
из coordinator.** На обнаружение нового события (id новейшее предыдущего
зафиксированного) — emit HA `event: elektronny_gorod_event` с типом
события и payload (place_id, ac_id, ...).

Реализация (черновик):

```python
# coordinator.py: _async_update_data
async def _async_update_data(self):
    # ... existing polling ...

    # Event detection: poll /events/search для новых событий per place
    events_changed = await self._poll_events_for_place(place_id)
    for event in events_changed:
        self.hass.bus.async_fire(
            f"{DOMAIN}_event",
            {"place_id": place_id, "type": event["type"], **event["data"]},
        )

async def _poll_events_for_place(self, place_id: str) -> list[dict]:
    """Return events that appeared since last poll."""
    response = await self._api.query_events_search(place_ids=[place_id], page=0)
    new_events = []
    last_seen_id = self._last_event_id.get(place_id)
    for event in response["content"]:
        if last_seen_id is None or event["id"] > last_seen_id:
            new_events.append(event)
    if response["content"]:
        self._last_event_id[place_id] = response["content"][0]["id"]
    return new_events
```

`update_interval` для event-polling — **отдельный** от coordinator main
polling (5 мин). Логика: coordinator с `update_interval=30s` для events,
основное состояние (places/balances/cameras/locks) обновляется через
существующий 5-мин interval (отдельным `DataUpdateCoordinator` либо
через `async_track_time_interval`).

**Latency**: 15-30s от реального звонка до HA event. Это **приемлемо**
для типичных бытовых автоматизаций (свет, звук, уведомление), но **не
подходит** для sub-second use cases (intercom answer button — невозможно
из HA через этот path).

## Consequences

### Positive

- **Простота**: чистый REST, никаких WebSocket-клиентов, никаких сторонних
  библиотек. Реализуется через существующий `ElektronnyGorodAPI.query_*`.
- **Не требует внешних зависимостей**: ни APK реверс-инженеринга (FCM
  project_id/sender_key), ни SIP-стека (pjsip/linphone), ни WebSocket-
  библиотек. Всё уже в `aiohttp` через HA-core.
- **Не зависит от backend feature-flags**: `/events/search` работает для
  всех абонентов ЭГ (подтверждено HAR), в отличие от STOMP который
  отключён для абонентов ЭГ.
- **Backfill bonus**: при первом setup можно опционально backfill истории
  до 6 месяцев (`page=0..N` до `last:true`) — пользователь получает
  history событий в HA Recorder сразу.
- **Совместимость с retention**: HA `homeassistant_started` event обычно
  игнорирует события старше нескольких часов в timeline — наш polling
  начинает с `last_seen_id=None` (только новые после первого poll), без
  spam-а старыми событиями.
- **Закрывает [A-58](../audit/project-audit.md)** (events polling).

### Negative

- **Latency 15-30s** vs sub-second у STOMP/FCM. Не подходит для:
  - Intercom answer-from-HA (нужен SIP).
  - Видеозвонок в реальном времени.
  - Time-critical automations типа «открой ворота из машины как только
    я подъехал к камере с распознаванием номера».
- **Polling overhead**: +120-240 HTTP requests/час per place (1 request
  per 15-30s). При нескольких places — кратно. Acceptable, но не free.
- **Backend rate-limits**: пока не наблюдались на этом endpoint, но при
  агрессивном poll'е (1 request/sec) могут появиться. Default 15s — safe.

### Mitigation

- **Configurable interval** в config_flow option (default 30s). Пользователь
  может уменьшить до 15s или увеличить до 60s+ в зависимости от типа
  использования.
- **Exponential backoff на 429** (rate-limit) — добавить в `__request`.
- **Опциональный wake-up**: при HA service call к нашему camera/lock —
  тригернуть один extra event poll out-of-band (low overhead, immediate
  feedback на user action).

## Alternatives considered

### 1. STOMP-клиент (`wss://myhome.proptech.ru:443/events`)

**Отклонено**. `/rest/v1/stomp/available-features` возвращает
`{data: null}` для всех наблюдаемых абонентов ЭГ — backend feature flag
отключён. Реализация STOMP-клиента работала бы только для абонентов
**другого** оператора на той же proptech-платформе (например, Дом.ру
«Умный домофон+», вероятно платная фича). Для нашей целевой аудитории
(абоненты ЭГ) — `null`, никаких real-time события через WS не приходит.
Цена реализации (STOMP-клиент over aiohttp WebSocket + reconnect +
SUBSCRIBE destinations) не оправдана.

См. [audit A-47](../audit/project-audit.md), api-reference §STOMP.

### 2. FCM-bridge через HA Companion

**Отклонено**. Идея: регистрировать FCM token HA Companion app в
proptech backend через `POST /rest/v1/subscriberNotifications`, чтобы
backend слал push не только в «Мой Дом» приложение, но и в HA Companion
устройства пользователя. HA Companion при получении push мог бы
тригернуть event в HA через notification API.

Препятствия:
- Требует APK реверс для FCM `project_id`, `sender_key`, точного payload
  format. APK обфусцирован.
- Backend проверяет device fingerprint (`installationId`, `appId`,
  `deviceManufacturer`, etc.) — нужно эмулировать.
- Зависит от Firebase availability (если у пользователя FCM заблокирован
  или RuStore-only Android — не работает).
- Не работает без HA Companion (только HA-core инстанс).

Альтернатива: **polling /events/search** работает в HA Core без
внешних зависимостей. Победа простоты.

### 3. SIP-клиент для приёма INVITE

**Отклонено для event detection**. SIP подходит для **полного intercom
experience** (answer call from HA + bi-directional audio), но это
огромный scope (PJSIP/linphone integration, audio codec handling, RTP
streaming). Использовать SIP только для **detection звонка** —
overkill. Polling даёт ту же информацию (звонок произошёл) проще.

SIP остаётся открытым для **будущего** ADR если когда-то будем делать
full intercom feature.

См. [audit A-49](../audit/project-audit.md).

### 4. Hybrid (STOMP + polling fallback)

**Отклонено**. Если STOMP feature-flag off — fallback на polling. Но
тогда у 100% наших пользователей работает только fallback path. STOMP
ветка кода — мёртвый код. Сложность тестирования (нужно эмулировать
оба сценария). Чистый polling — KISS.

### 5. Webhook receiver (HA принимает push от backend)

**Отклонено**. Backend оператора не имеет публичного webhook-механизма
(HAR не показывает такого endpoint). Реализовать это нельзя без
кооперации с оператором, что нереально.

## Notes

- **Драйвер для Итерации 4** в [roadmap.md](../roadmap.md).
- **Закрывает** (после implementation): [A-58](../audit/project-audit.md).
- **Понижает приоритет** (после accept ADR): [A-47](../audit/project-audit.md) (STOMP), [A-50](../audit/project-audit.md) (camera events — поглощается общим `/events/search` filter).
- **Не закрывает**: [A-49](../audit/project-audit.md) (SIP) — остаётся для будущей full-intercom feature.
- **Открытые вопросы для implementation**:
  - Event id mono-increasing? (Если да, можно сравнивать как `event["id"] > last_seen_id`. Если нет — нужно сравнивать timestamps.)
  - Backfill on first setup — opt-in через config_flow option или automatic?
  - HA event payload schema — фиксировать сейчас в ADR или итерировать?

## Supersedes / Superseded by

—

## Related ADRs

- [ADR-0002](0002-coordinator-pattern.md) — coordinator pattern, на котором будет строиться event polling (потенциально отдельный `DataUpdateCoordinator` с `update_interval=30s`).
- [ADR-0006](0006-mirror-app-behavior.md) — mirror app behavior. `/events/search` подтверждён в HAR — реализация zaplowa в рамках ADR-0006.
- [ADR-0008](0008-shared-client-session.md) — shared `ClientSession`. Event polling использует тот же session pool, отдельных connections не создаёт.
