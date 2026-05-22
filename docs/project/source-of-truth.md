Status: Active
Owner: Project Cartographer Agent
Last reviewed: 2026-05-22

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
| App emulation версии | [`const.py:34-37`](../../custom_components/elektronny_gorod/const.py#L34-L37) | разработчик | `user_agent.py` |
| Android device pool | [`const.py:41-106`](../../custom_components/elektronny_gorod/const.py#L41-L106) | разработчик | `user_agent.py` |
| Coordinator state | `coordinator._subscriber_places` (in-memory) | `_async_update_data` | геттеры coordinator |
| Cameras/Locks/Balances данные | runtime через `coordinator.get_*_info()` | API → coordinator | entity setup |
| go2rtc config (runtime) | `entry.options ↑ entry.data` (fallback) | OptionsFlow → entry | `camera.py:_get_go2rtc_cfg` |
| UI-строки (source) | [`strings.json`](../../custom_components/elektronny_gorod/strings.json) | разработчик | HA, переводы |
| Переводы | [`translations/*.json`](../../custom_components/elektronny_gorod/translations/) | разработчик / переводчик | HA UI |
| Crypto-«соль» auth | [`helpers.py:43-44`](../../custom_components/elektronny_gorod/helpers.py#L43-L44) | reverse engineering | API verify_password |
| HACS-публикация | [`hacs.json`](../../hacs.json) + GitHub Releases | release workflow | HACS |
| Release pipeline | [`.github/workflows/release.yaml`](../../.github/workflows/release.yaml) | разработчик | GitHub Actions |
| Brand assets | brands.home-assistant.io/elektronny_gorod/ | разработчик (через PR в brands repo) | HA UI, README badge |
| Пользовательская документация | [`README.md`](../../README.md) | разработчик | пользователь |

## Известные конфликты

См. также [`project-audit.md`](../audit/project-audit.md).

### Конфликт 1: minimum HA version

| Источник | Значение |
|---|---|
| `hacs.json:3` | `2022.8.0` |
| `info.md` | (производный от hacs.json) |
| `README.md` badge | `2023.x` |
| Код (`ConfigFlowResult`, `LockState.LOCKED`) | требует ≥ 2024.x |

**Резолюция:** код — источник реальной минимальной версии. Требуется обновить `hacs.json` и README до фактической `2024.1.0` (минимально).

### Конфликт 2: iot_class vs реальная модель

| Источник | Значение |
|---|---|
| `manifest.json:10` | `cloud_polling` |
| `coordinator.py` | НЕТ `update_interval`, нет реального polling |

**Резолюция:** либо вводим polling (`update_interval`) и оставляем `cloud_polling`, либо меняем на корректный класс. ADR требуется.

### Конфликт 3: README.md ↔ файловая система

| Источник | Значение |
|---|---|
| `README.md:1` ссылается на | `/README.ru_RU.md` |
| Файловая система | файла НЕТ |
| `README.md:41` пример установки | `cp -r custom_components/electronic_city` |
| Реальный домен | `elektronny_gorod` |

**Резолюция:** удалить битую ссылку, исправить пример имени домена. Или создать `README.ru_RU.md` (раз ссылка есть).

### Конфликт 4: тесты ↔ реальный config_flow

| Источник | Значение |
|---|---|
| `tests/test_config_flow.py:5-7` | импортирует `CannotConnect`, `InvalidAuth`, `PlaceholderHub` |
| `config_flow.py` | ничего из этого не экспортирует |

**Резолюция:** тесты — заведомо нерабочий stub. Переписать с нуля. См. [`testing/strategy.md`](../testing/strategy.md).

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
