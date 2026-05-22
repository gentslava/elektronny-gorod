Status: Active
Owner: Home Assistant Expert Agent
Last reviewed: 2026-05-22

Source files:
- `custom_components/elektronny_gorod/**`
- `manifest.json`

Related docs:
- `ha-compatibility.md`
- `project-audit.md`
- `roadmap.md`

Used by agents:
- HA Expert, QA, Lead Architect

Quality gates:
- AUDIT_DONE
- READY_FOR_RELEASE

External reference:
- https://developers.home-assistant.io/docs/core/integration-quality-scale/
- https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/

---

# Integration Quality Scale Assessment

Текущая оценка проекта по официальной [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/).

## Текущая оценка

**No score** (нет `quality_scale` в `manifest.json`).

Реальная позиция: ниже Bronze — основные блокеры:
- нет реальных тестов;
- нет diagnostics;
- entity нарушают паттерн `CoordinatorEntity`.

## Bronze

Минимальный уровень. Цель **Итерации 2** в [`roadmap.md`](../roadmap.md).

| Правило | Статус | Файл |
|---|---|---|
| `action-setup` (если есть свои services) | n/a | — |
| `appropriate-polling` | 🔴 НЕТ `update_interval` | `coordinator.py` |
| `brands` | ⚠️ проверить наличие в home-assistant/brands | — |
| `common-modules` | ✅ структура соответствует | — |
| `config-flow` | ✅ есть | `config_flow.py` |
| `config-flow-test-coverage` | 🔴 нет реальных тестов | `tests/` |
| `dependency-transparency` | ✅ requirements пусты | `manifest.json` |
| `docs-actions` | n/a | — |
| `docs-high-level-description` | ✅ README | — |
| `docs-installation-instructions` | ✅ README | — |
| `docs-removal-instructions` | ⚠️ нет в README | — |
| `entity-event-setup` | ✅ платформы forward-нуты | `__init__.py` |
| `entity-unique-id` | ⚠️ unique_id частично содержит локализованное имя | `camera.py:122`, `lock.py:48` |
| `has-entity-name` | 🔴 не используется `_attr_has_entity_name` | все entity |
| `runtime-data` | ⚠️ используется `hass.data[DOMAIN][entry_id]` — допустимо, но `entry.runtime_data` рекомендован | `__init__.py:38` |
| `test-before-configure` | ⚠️ Частично: профиль фетчится перед `create_entry`; go2rtc валидируется | `config_flow.py` |
| `test-before-setup` | ✅ `async_config_entry_first_refresh` | `__init__.py:37` |
| `unique-config-entry` | ✅ проверка дубликата | `config_flow.py:281-310` |

**Bronze blockers (что нужно для зачёта):**
1. Реальные тесты config_flow (минимум: happy path + abort already_configured).
2. `update_interval` в coordinator (или `iot_class != cloud_polling`).
3. `_attr_has_entity_name = True` + стабильные `unique_id`.
4. `quality_scale: "bronze"` в manifest.

## Silver

Цель **Итерации 3**.

| Правило | Статус | Что нужно |
|---|---|---|
| `action-exceptions` | n/a | — |
| `config-entry-unloading` | ✅ есть | — |
| `docs-configuration-parameters` | ⚠️ README поверхностный | расширить |
| `docs-installation-parameters` | ⚠️ есть | детализировать |
| `entity-unavailable` | 🔴 нет обработки unavailable | sensor должен ставить state=unavailable при ошибке API |
| `integration-owner` | ✅ `codeowners` | — |
| `log-when-unavailable` | 🔴 нет | LOGGER.warning при недоступности |
| `parallel-updates` | 🔴 нет `parallel_updates` атрибута | добавить |
| `reauthentication-flow` | ⚠️ работает, но без `async_step_reauth_confirm` | переписать в HA-нативный паттерн |
| `test-coverage` | 🔴 нет | покрытие основных модулей |

**Silver blockers:**
1. Нативный reauth (`async_step_reauth_confirm`).
2. Полная обработка unavailable/unknown.
3. `parallel_updates` для всех platforms.
4. Тесты coordinator/api с mock-ами.
5. `log-when-unavailable` паттерн.

## Gold

Дальняя цель (после Silver). Ключевые требования:

| Правило | Статус |
|---|---|
| `devices` (`device_info`) | 🔴 нет |
| `entity-category` | 🔴 не используются |
| `entity-device-class` | 🔴 нет (balance должен быть MONETARY) |
| `entity-translations` | 🔴 нет (хардкод имена) |
| `discovery` (если применимо) | n/a (нет zeroconf/SSDP) |
| `discovery-update-info` | n/a |
| `docs-data-update` | ⚠️ нет описания update flow |
| `docs-examples` | ✅ есть пример автоматизации в README |
| `docs-known-limitations` | 🔴 нет |
| `docs-supported-devices` | ⚠️ нечётко |
| `dynamic-devices` | 🔴 нет (places загружаются 1 раз) |
| `entity-disabled-by-default` | n/a |
| `exception-translations` | 🔴 нет |
| `icon-translations` | n/a |
| `reconfiguration-flow` | 🔴 нет |
| `repair-issues` | 🔴 нет |
| `stale-devices` | 🔴 — |

## Platinum

После Gold. Требует:
- 100% type hints;
- async dependency (n/a — нет внешней зависимости);
- websocket (n/a — оператор предоставляет только REST);
- strict typing;
- очень высокий test coverage.

Реалистично — не цель в обозримом будущем.

## Дорожная карта по уровням

| Уровень | Итерация | Главные блокеры |
|---|---|---|
| No score → Bronze | Итерация 2 | тесты, coordinator, unique_id, has_entity_name |
| Bronze → Silver | Итерация 3 | reauth, unavailable, parallel_updates, coverage |
| Silver → Gold | Будущее | device_info, entity_category, translations, repairs |
| Gold → Platinum | Дальнее будущее | strict typing, 100% coverage |

## Принцип

Не пытаться достичь Bronze «формально» — каждое правило соответствует реальной пользовательской ценности (надёжность, понятность, восстанавливаемость).

## Next reading

- For HA-checklist: `ha-compatibility.md`
- For roadmap: `roadmap.md`
- For prioritized fixes: `project-audit.md`
- For testing: `testing/strategy.md`
