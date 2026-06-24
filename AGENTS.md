# AGENTS.md — Cross-tool agent contract

Это короткий контракт для любых AI-агентов, работающих в репозитории `elektronny-gorod`. Глубокая документация — в [`docs/index.md`](docs/index.md).

## Что это за проект

Home Assistant **custom integration** `elektronny_gorod` (домен) — интеграция с российскими операторами «Электронный город» (Новотелеком) и «Дом.ру» через закрытое API мобильного приложения `myhome.proptech.ru`. Платформы: `camera`, `lock`, `sensor` (баланс). Опциональная проксия видеопотоков через [go2rtc](https://github.com/AlexxIT/go2rtc).

Тип репозитория: HACS-distributed custom integration (`hacs.json` + GitHub Releases zip).

## Стек

- Python 3.12+ (по HA core)
- HomeAssistant ≥ 2024.10.4 (см. `hacs.json` + [`ha-compatibility.md`](docs/architecture/ha-compatibility.md))
- `aiohttp`, `voluptuous`, `yarl`
- Тесты: `pytest` + `pytest-homeassistant-custom-component` (`requirements_test.txt`)

## Setup commands

Локальная разработка пока не зафиксирована скриптом (см. roadmap). Минимально:

```bash
# Симлинк интеграции в HA dev-инстанс
ln -s "$(pwd)/custom_components/elektronny_gorod" \
      ~/.homeassistant/custom_components/elektronny_gorod
```

## Test / lint commands

```bash
# Локальный прогон (зелёный):
PYTHONPATH=. .venv/bin/pytest tests/ -q
# С покрытием:
PYTHONPATH=. .venv/bin/pytest tests/ --cov=custom_components/elektronny_gorod --cov-report=term-missing -q
```

Состояние тестов (актуально — см. [`testing/strategy.md`](docs/testing/strategy.md)
и [`project-audit.md`](docs/audit/project-audit.md)): suite зелёный; есть gap-и
по `config_flow.py`/`api.py`/`helpers.py` (трекаются как findings).

CI на сегодня:

```bash
# python-tests.yaml — pytest matrix (HA min + current)
# hassfest (manifest валидация)
# HACS validate
# release pipeline: zip + GH release + автокоммит версии
# prerelease.yaml — pre-release zip для каждого PR
```

См. [`.github/workflows/`](.github/workflows/).

## Project structure

> Структура описывает **назначение** файлов. Текущее качество/findings —
> в [`project-audit.md`](docs/audit/project-audit.md) (единый источник, ADR-0010).

```
custom_components/elektronny_gorod/
├── __init__.py            # async_setup_entry, async_migrate_entry 1→2→3, visibility sync
├── manifest.json          # version, domain, config_flow, quality_scale, integration_type
├── config_flow.py         # ConfigFlow + OptionsFlow (token/password/SMS + go2rtc)
├── coordinator.py         # DataUpdateCoordinator (update_interval 5 мин)
├── api.py                 # REST-обёртка над myhome.proptech.ru
├── http.py                # низкоуровневый HTTP (shared async_get_clientsession)
├── _logging.py            # redact() + SENSITIVE_KEYS (ADR-0004)
├── camera.py              # Camera entity + go2rtc upsert + auto-recovery (ADR-0009)
├── lock.py                # LockEntity (домофон)
├── sensor.py              # Balance sensor + days-to-block
├── binary_sensor.py       # account_blocked
├── switch.py              # DND switches (intercom / management calls)
├── event.py               # doorbell call event (ADR-0011)
├── fcm.py                 # FCM listener для события вызова (ADR-0011)
├── sip/                   # SIP-стек two-way audio, register-on-ring (ADR-0012, A-81)
│   ├── call_controller.py # HA-glue: трекинг вызова + answer/hangup + AudioBridge lifecycle
│   ├── bridge.py          # AudioBridge: downlink G.711 → ffmpeg → mpegts/aac → go2rtc
│   ├── manager.py         # SipManager (register_and_hold / accept / hangup)
│   ├── protocol.py        # asyncio SIP-транспорт (UDP); CANCEL→487 / BYE→on_bye
│   ├── register.py        # REGISTER + push-params
│   ├── dialog.py          # DialogState + 200 OK + BYE
│   ├── message.py / sdp.py / rtp.py / digest.py / stun.py / audio.py
│   └── __init__.py
├── call_camera.py         # camera.intercom_call: видео+звук гостя, HA-native WebRTC
├── services.yaml          # сервисы answer / hangup (A-81)
├── go2rtc.py              # validate_go2rtc + cleanup + upsert_audio_stream/remove_audio_stream
├── diagnostics.py         # redact-нутая diagnostics-выгрузка (TO_REDACT)
├── entity_migration.py    # стабильные unique_id + registry migration
├── helpers.py             # find, dedupe, hash_password (SHA1+MD5)
├── user_agent.py          # эмуляция Android-клиента (Pixel 6-10)
├── time.py                # таймстемпы для auth
├── const.py               # ключи конфигов, дефолты go2rtc, APP_VERSION
├── strings.json           # источник переводов
└── translations/
    ├── ru.json
    └── en.json
tests/                     # pytest suite (PHC-based)
.github/workflows/         # python-tests / hassfest / hacs / release / prerelease
docs/                      # AIDD-документация (project/architecture/audit/testing/aidd/)
.claude/                   # agents / commands / rules / hooks / settings
```

## Code style

- Python: PEP 8 + HA conventions. Type hints обязательны для публичных методов.
- Async-first. Никаких blocking I/O в event loop.
- Логирование: `%`-форматирование, **никогда не f-string внутри LOGGER.*()**.
- 🔴 **Никогда не логировать**: access_token, refresh_token, headers (содержат Bearer), password, SMS-код, полный `entry.data`.

См. [`conventions.md`](conventions.md).

## Home Assistant rules

- Использовать `async_get_clientsession(hass)` вместо собственного `aiohttp.ClientSession()`.
- Entity должны наследовать `CoordinatorEntity` если используют `DataUpdateCoordinator`.
- `unique_id` — стабилен. Никаких `name`/локализованных строк в id.
- `manifest.json` `iot_class` должен соответствовать реальному поведению.
- Каждый новый config-flow-step требует строки в `strings.json` + `translations/*.json`.
- `version` config entry **только увеличивать** через `async_migrate_entry`.

Чеклист — в [`ha-compatibility.md`](docs/architecture/ha-compatibility.md).

## Safety rules / Boundaries

### Always (можно без подтверждения)

- Читать любые файлы проекта.
- Запускать read-only команды (`git status`, `ls`, `grep`, `find`).
- Создавать и обновлять `docs/**` и AIDD-артефакты.
- Предлагать изменения с evidence.

### Ask first (требуется явное подтверждение)

- Любые изменения в `custom_components/elektronny_gorod/**`.
- Изменения `manifest.json`, `hacs.json`, `version`, `requirements`.
- Изменения config-flow steps, entity unique_id, device_info.
- Изменения CI workflow.
- Удаление файлов.
- Обновление публичной документации (README*, info.md).

### Never (запрещено)

- Логировать токены / пароли / SMS / headers с Bearer.
- Коммитить `.env`, секреты, API ключи.
- Использовать `--no-verify` для bypass хуков.
- Force-push в `master`.
- Менять config-entry `VERSION` без migration step.
- Удалять existing tests/translations без подтверждения.
- Fix-ить тесты, чтобы они «прошли» с сломанным поведением.

## Docs update policy

Когда меняется код — обновлять AIDD docs параллельно. Источник правил — [`docs/project/project-map.md#maintenance-rules`](docs/project/project-map.md#maintenance-rules).

Если изменение задевает несколько источников правды — зафиксировать рассогласование в [`project-audit.md`](docs/audit/project-audit.md).

## Где искать что

| Хочу | Файл |
|---|---|
| Карта проекта | [`docs/project/project-map.md`](docs/project/project-map.md) |
| Source of truth | [`source-of-truth.md`](docs/project/source-of-truth.md) |
| Внешние источники / best practices | [`source-base.md`](docs/aidd/source-base.md) |
| Архитектура | [`architecture/overview.md`](docs/architecture/overview.md) |
| HA-чеклист | [`ha-compatibility.md`](docs/architecture/ha-compatibility.md) |
| Integration Quality Scale | [`quality-scale.md`](docs/architecture/quality-scale.md) |
| Все находки + приоритеты | [`project-audit.md`](docs/audit/project-audit.md) |
| Security findings | [`security.md`](docs/audit/security.md) |
| Testing | [`testing/strategy.md`](docs/testing/strategy.md) |
| Quality gates | [`quality-gates.md`](docs/aidd/quality-gates.md) |
| Roadmap | [`roadmap.md`](docs/roadmap.md) |
| Workflow процесса | [`workflow.md`](workflow.md) |
| Конвенции | [`conventions.md`](conventions.md) |
| Краткое summary | [`docs/summary.md`](docs/summary.md) |

## Tool-specific

- **Claude Code** — см. [`CLAUDE.md`](CLAUDE.md).
- **OpenAI Codex / Copilot / Cursor / Aider** — этот файл является source of truth.
