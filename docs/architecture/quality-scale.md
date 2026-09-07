Status: Active Owner: Home Assistant Expert Agent Last reviewed: 2026-09-07 (Silver заявлен: все правила уровня закрыты, все 42 модуля выше порога 95%, порог держит CI)

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

**Silver** — заявлен в `manifest.json` (2026-09-07). Первые две попытки были отозваны: в первый раз не выполнялись `test-coverage` и `action-exceptions`, во второй — `test-coverage` читался как средний, а не помодульный порог. Третья заявка пришла после того, как ревью нашло и закрыло регрессию `action-setup`. Bronze подтверждается архитектурой: реальный polling, `CoordinatorEntity`, stable `unique_id`, diagnostics с redaction, координатор в `entry.runtime_data`. Silver: нативная переавторизация с автозапуском по 401, `parallel-updates` во всех платформах, сообщение о недоступности по фронту, документация параметров и инструкция по удалению, внятный отказ действий и покрытие выше 95% в каждом модуле.

Оговорка: Home Assistant поле `quality_scale` у кастомных интеграций не читает — `loader.py:854-859` возвращает для них `custom`, а `hassfest` выходит из IQS-валидатора для не-core. Заявка адресована людям и держится этим документом плюс порогом покрытия в CI.

## Bronze

Минимальный уровень, shipped. История реализации — в [`roadmap.md`](../roadmap.md); ниже только актуальный snapshot.

| Правило | Статус | Файл |
|---|---|---|
| `action-setup` | ✅ действия регистрируются в `async_setup`, до загрузки записей, и не снимаются на выгрузке: `async_setup` HA зовёт один раз за запуск, поэтому снятие означало бы пропажу действий после первого же reload | `__init__.py:async_setup`, `async_unload_entry` |
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
| `entity-event-setup` | ✅ подписки заводятся в `async_added_to_hass` и снимаются парно — через `async_on_remove` (`event.py`, `sensor.py`, `call_camera.py`) либо `async_will_remove_from_hass` (`camera.py`). У `lock` своей подписки нет: слушатель приходит от `CoordinatorEntity` | платформы |
| `entity-unique-id` | ✅ стабильные UID + registry migration | `entity_migration.py` |
| `has-entity-name` | ✅ HA entity naming pattern | entity platforms |
| `runtime-data` | ✅ координатор в `entry.runtime_data` с типизированным алиасом; реестры FCM, SIP и stream-manager остаются в `hass.data` (FCM — намеренно, см. ниже) | `coordinator.py`, `__init__.py` |
| `test-before-configure` | ✅ профиль и go2rtc проверяются до create entry | `config_flow.py` |
| `test-before-setup` | ✅ `async_config_entry_first_refresh` | `__init__.py:async_setup_entry` |
| `unique-config-entry` | ✅ проверка дубликата | `config_flow.py` |

> **Почему реестр FCM не в `runtime_data`.** `runtime_data` — один слот, и `async_setup_entry` занимает его координатором безусловно первой строкой. Удержанный listener, положенный туда, был бы затёрт следующей же попыткой загрузки — а именно ради неё удержание и существует. Реестры SIP и stream-manager перенести можно, они просто отложены отдельным изменением.

**Bronze blockers:** нет. Бренд опубликован (проверено 2026-09-06), removal-инструкция добавлена в оба README.

## Silver

Заявлен в манифесте 2026-09-06.

| Правило | Статус | Что нужно |
|---|---|---|
| `action-exceptions` | ✅ отказывают внятно: `answer`/`hangup` без вызова и при незагруженной записи, замок на «Закрыть» и на неудавшемся открытии, переключатели «не беспокоить» при отказе оператора | `__init__.py`, `lock.py`, `switch.py` |
| `config-entry-unloading` | ✅ есть | — |
| `docs-configuration-parameters` | ✅ таблица параметров go2rtc с умолчаниями и назначением | README (ru/en) |
| `docs-installation-parameters` | ✅ что нужно до начала + таблица полей каждого шага настройки | README (ru/en) |
| `entity-unavailable` | ✅ через `CoordinatorEntity.available` + data presence | — |
| `integration-owner` | ✅ `codeowners` | — |
| `log-when-unavailable` | ✅ по фронту, одна строка на пропажу и одна на возвращение, с гранулярностью «вид данных + место»: баланс, домофоны, настройки экранов, камеры места, общедомовые камеры, сборка камер, замки, режим «не беспокоить» и пустой список адресов. О полной недоступности пишет ядро (`Error fetching … data` / `… recovered`), своего лога рядом нет; транспорт об отказах говорит только на `debug` — значимость определяет вызывающий | `coordinator.py:_note_failure`, `_note_success` |
| `parallel-updates` | ✅ задано во всех шести платформах: `1` у `lock`/`switch` (координатор централизует входящие данные, но не ограничивает исходящие вызовы действий), `0` у остальных — у `camera` осознанно, потому что превью идёт мимо семафора и наплыв держат кэш снимка и `_snapshot_retry_after` | платформы |
| `reauthentication-flow` | ✅ `async_step_reauth` / `async_step_reauth_confirm`; 401 поднимает `ConfigEntryAuthFailed` | `config_flow.py`, `coordinator.py` |
| `test-coverage` | ✅ «above 95% for all integration modules»: **все 42 модуля выше 95%** | помодульный порог держит шаг CI «Enforce the per-module coverage floor»; живые цифры — в [`testing/strategy.md`](../testing/strategy.md) |

**Silver blockers:** нет.

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
| `exception-translations` | 🟡 частично: отказы `lock.lock`, `answer` и `hangup` переведены через `translation_key`; остальные исключения — нет |
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
| Silver | Заявлен 2026-09-06 | нет |
| Silver → Gold | Будущее | entity_category audit beyond RTSP diagnostics, dynamic devices, расширение Repairs на остальные recovery edge-cases |
| Gold → Platinum | Дальнее будущее | strict typing, 100% coverage |

## Принцип

Не пытаться достичь Bronze «формально» — каждое правило соответствует реальной пользовательской ценности (надёжность, понятность, восстанавливаемость).

## Next reading

- For HA-checklist: `ha-compatibility.md`
- For roadmap: `roadmap.md`
- For prioritized fixes: `project-audit.md`
- For testing: `testing/strategy.md`
