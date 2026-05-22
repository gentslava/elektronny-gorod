# Rule: Home Assistant best practices

**Применимо к:** `custom_components/elektronny_gorod/**.py`, `manifest.json`, `strings.json`, `translations/*.json`.

## Правила

### Manifest

- `iot_class` соответствует реальной модели (см. ADR-0003).
- `quality_scale` присутствует, если интеграция претендует на уровень (Bronze+).
- `integration_type: "hub"` (один entry = один аккаунт = много устройств).
- `requirements` пуст, если зависимости в HA core.
- `version` обновляется release workflow, **не вручную**.

### Config flow

- Каждый step имеет соответствующую translation key в `strings.json`.
- `errors` и `abort` — все translation keys существуют в `strings.json`.
- `VERSION` config_entry увеличивается только через `async_migrate_entry`.
- Native `async_step_reauth` (а не reauth внутри `get_account`).
- Native `async_step_reconfigure` для существующих entries.

### Entity

- Наследуют `CoordinatorEntity[ElektronnyGorodUpdateCoordinator]` (см. coordinator-pattern.md).
- `unique_id` — стабильный, без локализованных строк (`name`).
- `_attr_has_entity_name = True` + `_attr_translation_key`.
- `device_info` для группировки по place.
- `device_class` / `state_class` где применимо.
- `_attr_available` определяется по факту, а не fake-timer.

### HTTP / API

- `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)` — единственный способ.
- `ClientTimeout(total=N)` на все запросы.
- Retry/backoff для 5xx / connection errors.
- Auto-refresh access_token на 401 (если есть refresh_token).

### Translations

- Любая user-facing строка — через `strings.json`.
- `ru.json` и `en.json` синхронизированы.
- Никаких хардкод-строк по-русски в entity (`_attr_name = "Баланс"` — ❌).

### Diagnostics

- `diagnostics.py` существует.
- Использует `homeassistant.components.diagnostics.async_redact_data`.
- `TO_REDACT` включает SENSITIVE_KEYS (см. ADR-0004).

## Что запрещено

- 🔴 Изменения `manifest.json:version` вручную.
- 🔴 Создание `aiohttp.ClientSession()` per-request.
- 🔴 Локализованные имена в `unique_id`.
- 🔴 Несинхронизированные translations.
- 🔴 `iot_class: cloud_polling` без `update_interval`.

## Связь

- [HA developer docs](https://developers.home-assistant.io/)
- [IQS rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
- docs/architecture/ha-compatibility.md
- docs/architecture/quality-scale.md
