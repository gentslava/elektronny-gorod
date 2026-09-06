Status: Active Owner: Home Assistant Expert Agent Last reviewed: 2026-09-06 (пять правил Silver закрыты; заявка отозвана — `test-coverage` и `action-exceptions` не выполнены)

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

**Bronze** — заявлен в `manifest.json`. Заявка Silver была поднята 2026-09-06 и в тот же день отозвана: два правила уровня не выполнены (см. блокеры ниже). Bronze подтверждается архитектурой: реальный polling, `CoordinatorEntity`, stable `unique_id`, diagnostics с redaction, координатор в `entry.runtime_data`. К Silver закрыты пять правил из семи: нативная переавторизация с автозапуском по 401, `parallel-updates` во всех платформах, сообщение о недоступности по фронту, документация параметров и инструкция по удалению.

Оговорка на будущее: Home Assistant поле `quality_scale` у кастомных интеграций не читает — `loader.py:854-859` возвращает для них `custom`. Заявка адресована людям, а не ядру, поэтому и держится этим документом.

## Bronze

Минимальный уровень, shipped. История реализации — в [`roadmap.md`](../roadmap.md); ниже только актуальный snapshot.

| Правило | Статус | Файл |
|---|---|---|
| `action-setup` (если есть свои services) | ✅ `answer` / `hangup` описаны | `services.yaml` |
| `appropriate-polling` | ✅ `update_interval=5 min` | `coordinator.py` |
| `brands` | ✅ опубликован: `custom_integrations/elektronny_gorod` в home-assistant/brands (icon, icon@2x, logo, logo@2x) | — |
| `common-modules` | ✅ структура соответствует | — |
| `config-flow` | ✅ есть | `config_flow.py` |
| `config-flow-test-coverage` | ✅ password/SMS/token + reauth/abort | `tests/test_config_flow.py` |
| `dependency-transparency` | ✅ runtime requirements объявлены | `manifest.json` |
| `docs-actions` | ✅ сервисы документированы | `services.yaml`, release docs |
| `docs-high-level-description` | ✅ README | — |
| `docs-installation-instructions` | ✅ README | — |
| `docs-removal-instructions` | ✅ раздел «Удаление»: что удаляется, что остаётся в go2rtc | README (ru/en) |
| `entity-event-setup` | ✅ платформы forward-нуты | `__init__.py` |
| `entity-unique-id` | ✅ стабильные UID + registry migration | `entity_migration.py` |
| `has-entity-name` | ✅ HA entity naming pattern | entity platforms |
| `runtime-data` | ✅ координатор в `entry.runtime_data` с типизированным алиасом; реестры FCM, SIP и stream-manager остаются в `hass.data` (FCM — намеренно, см. ниже) | `coordinator.py`, `__init__.py` |
| `test-before-configure` | ✅ профиль и go2rtc проверяются до create entry | `config_flow.py` |
| `test-before-setup` | ✅ `async_config_entry_first_refresh` | `__init__.py:async_setup_entry` |
| `unique-config-entry` | ✅ проверка дубликата | `config_flow.py` |

> **Почему реестр FCM не в `runtime_data`.** `runtime_data` — один слот, и `async_setup_entry` занимает его координатором безусловно первой строкой. Удержанный listener, положенный туда, был бы затёрт следующей же попыткой загрузки — а именно ради неё удержание и существует. Реестры SIP и stream-manager перенести можно, они просто отложены отдельным изменением.

**Bronze blockers:** нет. Бренд опубликован (проверено 2026-09-06), removal-инструкция добавлена в оба README.

## Silver

Не заявлен: два правила не выполнены.

| Правило | Статус | Что нужно |
|---|---|---|
| `action-exceptions` | 🔴 сервис `answer` без активного вызова молча пишет в лог вместо ошибки; `hangup` не сигнализирует вовсе | `__init__.py:289-298` |
| `config-entry-unloading` | ✅ есть | — |
| `docs-configuration-parameters` | ✅ таблица параметров go2rtc с умолчаниями и назначением | README (ru/en) |
| `docs-installation-parameters` | ✅ что нужно до начала + таблица полей каждого шага настройки | README (ru/en) |
| `entity-unavailable` | ✅ через `CoordinatorEntity.available` + data presence | — |
| `integration-owner` | ✅ `codeowners` | — |
| `log-when-unavailable` | ✅ отказ подзапроса логируется по фронту: одна строка на пропажу, одна на возвращение | `coordinator.py:_note_failure` |
| `parallel-updates` | ✅ `PARALLEL_UPDATES = 0` во всех шести платформах (данные из координатора) | платформы |
| `reauthentication-flow` | ✅ `async_step_reauth` / `async_step_reauth_confirm`; 401 поднимает `ConfigEntryAuthFailed` | `config_flow.py`, `coordinator.py` |
| `test-coverage` | 🔴 общий **85%** при требовании «above 95% for all integration modules»; ниже порога 19 модулей, в том числе `api.py` 44%, `sip/bridge.py` 30%, `sip/protocol.py` 43% | замер 2026-09-06 |

**Silver blockers:**
1. `test-coverage` — поднять общее покрытие выше 95%. Главные дыры: `api.py` 44%, SIP-транспорт 30-48%.
2. `action-exceptions` — `answer`/`hangup` должны отказывать внятно, как это уже сделано для `lock.lock`.

> Заявка была поднята и отозвана 2026-09-06. Причина ошибки: Silver-правило `test-coverage` (общее покрытие выше 95%) спутано с Bronze-правилом `config-flow-test-coverage` (100% на `config_flow.py`) — второе закрыто, первое нет. Нашёл независимый `ha-expert`.

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
| `repair-issues` | 🟡 есть для подтверждённого FCM-degraded; остальные recovery edge-cases не аудированы |
| `stale-devices` | 🔴 — |

## Platinum

После Gold. Требует:
- 100% type hints;
- async dependency rule: 🟡 `firebase-messaging` async и получает shared HA session; полный Platinum-аудит всех pip dependencies ещё не выполнен;
- websocket API rule: applicability нужно переоценить с учётом HA history/uplink commands и provider transport REST/FCM/SIP;
- strict typing;
- очень высокий test coverage.

Реалистично — не цель в обозримом будущем.

## Дорожная карта по уровням

| Уровень | Итерация | Главные блокеры |
|---|---|---|
| Bronze | Shipped | нет |
| Bronze → Silver | Ближайшая итерация | `test-coverage` (85% → 95%), `action-exceptions` |
| Silver → Gold | Будущее | entity_category audit beyond RTSP diagnostics, dynamic devices, расширение Repairs на остальные recovery edge-cases |
| Gold → Platinum | Дальнее будущее | strict typing, 100% coverage |

## Принцип

Не пытаться достичь Bronze «формально» — каждое правило соответствует реальной пользовательской ценности (надёжность, понятность, восстанавливаемость).

## Next reading

- For HA-checklist: `ha-compatibility.md`
- For roadmap: `roadmap.md`
- For prioritized fixes: `project-audit.md`
- For testing: `testing/strategy.md`
