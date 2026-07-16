Status: Active
Owner: Home Assistant Expert Agent
Last reviewed: 2026-07-16 (diagnostic RTSP entity category and manager
lifecycle tests reconciled; declared scale unchanged)

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

**Bronze** — заявлен в `manifest.json` и подтверждается текущей архитектурой:
реальный polling, `CoordinatorEntity`, stable `unique_id`, diagnostics с
redaction и тесты config flow/миграций присутствуют. Актуальный test baseline
ведётся только в [`testing/strategy.md`](../testing/strategy.md).

## Bronze

Минимальный уровень, shipped. История реализации — в
[`roadmap.md`](../roadmap.md); ниже только актуальный snapshot.

| Правило | Статус | Файл |
|---|---|---|
| `action-setup` (если есть свои services) | ✅ `answer` / `hangup` описаны | `services.yaml` |
| `appropriate-polling` | ✅ `update_interval=5 min` | `coordinator.py` |
| `brands` | ⚠️ проверить наличие в home-assistant/brands | — |
| `common-modules` | ✅ структура соответствует | — |
| `config-flow` | ✅ есть | `config_flow.py` |
| `config-flow-test-coverage` | ✅ password/SMS/token + reauth/abort | `tests/test_config_flow.py` |
| `dependency-transparency` | ✅ runtime requirements объявлены | `manifest.json` |
| `docs-actions` | ✅ сервисы документированы | `services.yaml`, release docs |
| `docs-high-level-description` | ✅ README | — |
| `docs-installation-instructions` | ✅ README | — |
| `docs-removal-instructions` | ⚠️ нет в README | — |
| `entity-event-setup` | ✅ платформы forward-нуты | `__init__.py` |
| `entity-unique-id` | ✅ стабильные UID + registry migration | `entity_migration.py` |
| `has-entity-name` | ✅ HA entity naming pattern | entity platforms |
| `runtime-data` | ⚠️ используется `hass.data[DOMAIN][entry_id]` — допустимо, но `entry.runtime_data` рекомендован | `__init__.py:38` |
| `test-before-configure` | ✅ профиль и go2rtc проверяются до create entry | `config_flow.py` |
| `test-before-setup` | ✅ `async_config_entry_first_refresh` | `__init__.py:37` |
| `unique-config-entry` | ✅ проверка дубликата | `config_flow.py` |

**Bronze blockers:** подтверждённых блокеров нет. Перед формальной внешней
подачей остаётся перепроверить brand и добавить явную removal-инструкцию в
пользовательскую документацию.

## Silver

Цель **Итерации 3**.

| Правило | Статус | Что нужно |
|---|---|---|
| `action-exceptions` | n/a | — |
| `config-entry-unloading` | ✅ есть | — |
| `docs-configuration-parameters` | ⚠️ README поверхностный | расширить |
| `docs-installation-parameters` | ⚠️ есть | детализировать |
| `entity-unavailable` | ✅ через `CoordinatorEntity.available` + data presence | — |
| `integration-owner` | ✅ `codeowners` | — |
| `log-when-unavailable` | ⚠️ coordinator error path есть; правило отдельно не аудировано | проверить по rule text |
| `parallel-updates` | ⚠️ явный атрибут не задан | проверить по platform semantics |
| `reauthentication-flow` | ⚠️ работает, но без `async_step_reauth_confirm` | переписать в HA-нативный паттерн |
| `test-coverage` | ⚠️ suite широкий; свежий coverage-процент не заявлен | coverage-run перед Silver claim |

**Silver blockers:**
1. Нативный reauth (`async_step_reauth_confirm`).
2. Перепроверить `parallel_updates` и `log-when-unavailable` по актуальным rules.
3. Закрыть оставшиеся Silver documentation gaps.
4. Зафиксировать свежий coverage evidence.

## Gold

Дальняя цель (после Silver). Ключевые требования:

| Правило | Статус |
|---|---|
| `devices` (`device_info`) | ✅ есть у основных entity |
| `entity-category` | 🟡 diagnostic category используется для external RTSP readiness sensor; остальные entity не аудированы под это правило |
| `entity-device-class` | ✅ balance/duration/problem классы заданы |
| `entity-translations` | ✅ `strings.json` + ru/en |
| `discovery` (если применимо) | n/a (нет zeroconf/SSDP) |
| `discovery-update-info` | n/a |
| `docs-data-update` | ⚠️ нет описания update flow |
| `docs-examples` | ✅ есть пример автоматизации в README |
| `docs-known-limitations` | ⚠️ есть в feature/release docs; сверить canonical README |
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
| Bronze | Shipped | перед внешней подачей: brands + removal docs re-check |
| Bronze → Silver | Итерация 3 | native reauth, rule re-check, documentation, coverage evidence |
| Silver → Gold | Будущее | entity_category audit beyond RTSP diagnostics, dynamic devices, repairs |
| Gold → Platinum | Дальнее будущее | strict typing, 100% coverage |

## Принцип

Не пытаться достичь Bronze «формально» — каждое правило соответствует реальной пользовательской ценности (надёжность, понятность, восстанавливаемость).

## Next reading

- For HA-checklist: `ha-compatibility.md`
- For roadmap: `roadmap.md`
- For prioritized fixes: `project-audit.md`
- For testing: `testing/strategy.md`
