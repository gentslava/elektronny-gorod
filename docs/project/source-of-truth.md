Status: Active
Owner: Project Cartographer Agent
Last reviewed: 2026-07-16 (4.0.0 RU/EN README and derived HACS info reconciled
with opt-in camera-history polling)

Source files:
- весь репозиторий (это карта)

Related docs:
- `project-map.md`
- `architecture/overview.md`
- `project-audit.md`

Used by agents:
- Все агенты при разрешении конфликтов

Quality gates:
- SOURCE_OF_TRUTH_READY

---

# Source of Truth Map

Где находится первичный источник правды для каждого типа знания. При конфликте — побеждает источник правды; рассогласования фиксируются в [`project-audit.md`](../audit/project-audit.md).

## Основное правило

> **Если документация противоречит коду — код считается первичным источником.**
> **Если код противоречит официальной документации Home Assistant — это compatibility gap (см. `ha-compatibility.md`).**

## Таблица

| Знание | Source of truth | Кто пишет | Кто читает |
|---|---|---|---|
| Domain интеграции | [`manifest.json:2`](../../custom_components/elektronny_gorod/manifest.json#L2) | разработчик | HA core, тесты, весь код |
| Version интеграции | [`manifest.json:13`](../../custom_components/elektronny_gorod/manifest.json#L13) | release workflow | HACS, HA core |
| `iot_class` | [`manifest.json:10`](../../custom_components/elektronny_gorod/manifest.json#L10) | разработчик | HA core |
| Min HA version | [`hacs.json:3`](../../hacs.json#L3) | разработчик | HACS |
| Codeowners | [`manifest.json:5`](../../custom_components/elektronny_gorod/manifest.json#L5) | разработчик | GitHub, HA QS |
| Документация ссылка | [`manifest.json:9`](../../custom_components/elektronny_gorod/manifest.json#L9) | разработчик | пользователь, HA |
| Issue tracker | [`manifest.json:11`](../../custom_components/elektronny_gorod/manifest.json#L11) | разработчик | пользователь, HA |
| Platforms | [`__init__.py:25-29`](../../custom_components/elektronny_gorod/__init__.py#L25-L29) | разработчик | `async_forward_entry_setups` |
| Entry point | [`__init__.py:async_setup_entry`](../../custom_components/elektronny_gorod/__init__.py#L32) | разработчик | HA core |
| Config entry VERSION | [`config_flow.py:46`](../../custom_components/elektronny_gorod/config_flow.py#L46) | разработчик | `async_migrate_entry` |
| Миграции | [`__init__.py:async_migrate_entry`](../../custom_components/elektronny_gorod/__init__.py#L47) | разработчик | HA при загрузке entry |
| UI flow steps | [`config_flow.py:65-365`](../../custom_components/elektronny_gorod/config_flow.py#L65-L365) | разработчик | HA UI |
| Options flow | [`config_flow.py:374-421`](../../custom_components/elektronny_gorod/config_flow.py#L374-L421) | разработчик | HA UI |
| API base URL | [`const.py:7`](../../custom_components/elektronny_gorod/const.py#L7) | разработчик | `http.py` |
| App emulation версии | [`const.py:APP_VERSION`](../../custom_components/elektronny_gorod/const.py#L98) | разработчик | `user_agent.py` |
| Android device pool | [`const.py:ANDROID_DEVICES`](../../custom_components/elektronny_gorod/const.py#L105) | разработчик | `user_agent.py` |
| Coordinator state | `ElektronnyGorodUpdateCoordinator.data` | `_async_update_data` | все `CoordinatorEntity` |
| Cameras/Locks/Balances данные | runtime snapshot в `coordinator.data` | API → coordinator | entity setup/update |
| go2rtc config (runtime) | `entry.options ↑ entry.data` (fallback) | OptionsFlow → entry | `camera.py:_get_go2rtc_cfg` |
| UI-строки (source) | [`strings.json`](../../custom_components/elektronny_gorod/strings.json) | разработчик | HA, переводы |
| Переводы | [`translations/*.json`](../../custom_components/elektronny_gorod/translations/) | разработчик / переводчик | HA UI |
| Crypto-«соль» auth | [`helpers.py:43-44`](../../custom_components/elektronny_gorod/helpers.py#L43-L44) | reverse engineering | API verify_password |
| HACS-публикация | [`hacs.json`](../../hacs.json) + GitHub Releases | release workflow | HACS |
| Release pipeline | [`.github/workflows/release.yaml`](../../.github/workflows/release.yaml) | разработчик | GitHub Actions |
| Brand assets | brands.home-assistant.io/elektronny_gorod/ | разработчик (через PR в brands repo) | HA UI, README badge |
| Пользовательская документация | [`README.md`](../../README.md) + [`README.en_EN.md`](../../README.en_EN.md) | разработчик | пользователь |
| Краткая HACS feature card | [`info.md`](../../info.md), производна от README | разработчик | HACS-пользователь |

## Известные конфликты

См. также [`project-audit.md`](../audit/project-audit.md).

### Конфликт 1: minimum HA version

| Источник | Значение |
|---|---|
| `hacs.json:3` | `2024.10.4` |
| `info.md` | (производный от hacs.json) |
| `README.md` badge | `2024.10+` ✅ |
| Код (`ConfigFlowResult`, `LockState`) | ≥ 2024.10 ✅ совпадает с hacs.json |

**Резолюция:** ✅ закрыт. Все источники синхронизированы на `2024.10.4` — первая stable HA с `LockState` enum, который импортирует `lock.py`. См. audit [A-11](../audit/project-audit.md#a-11-hacsjson-minimum-ha--202280).

### Конфликт 2: iot_class vs реальная модель

| Источник | Значение |
|---|---|
| `manifest.json:10` | `cloud_polling` |
| `coordinator.py` | `update_interval=5 min`, реальный polling |

**Резолюция:** ✅ закрыт. Polling реализован, `cloud_polling` соответствует
поведению; решение закреплено в [ADR-0003](../decisions/0003-iot-class-strategy.md).

### Конфликт 3: README.md ↔ файловая система

| Источник | Значение |
|---|---|
| `README.md` языковая ссылка | `/README.en_EN.md` существует |
| Пример установки | `custom_components/elektronny_gorod` |
| Реальный домен | `elektronny_gorod` — совпадает |
| `info.md` | краткое подмножество актуальных возможностей RU/EN README |

**Резолюция:** ✅ закрыт. Языковые ссылки и путь ручной установки совпадают с
файловой системой.

### Конфликт 4: тесты ↔ реальный config_flow

| Источник | Значение |
|---|---|
| `tests/test_config_flow.py` | реальные PHC-тесты password/SMS/token, reauth и abort |
| `tests/test_init.py` | миграции config entry v1→v2→v3 |

**Резолюция:** ✅ закрыт. Scaffold-stub заменён реальными тестами; актуальный
baseline — в [`testing/strategy.md`](../testing/strategy.md).

## Принципы при разрешении

1. **Код > документация** — для фактического состояния.
2. **Официальная HA-документация > наша интерпретация** — для best practices.
3. **`source-of-truth.md` ≠ `source-base.md`**: первый отвечает «где правда внутри проекта», второй — «какие внешние источники мы используем».
4. Любое выявленное рассогласование → запись в `project-audit.md` с приоритетом.

## Next reading

- For project map: `project-map.md`
- For external sources: `source-base.md`
- For architecture: `architecture/overview.md`
- For audit findings (with conflicts): `project-audit.md`
