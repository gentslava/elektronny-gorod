# Changelog

Все значимые изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/),
проект использует [SemVer](https://semver.org/).

## [Unreleased]

### Security 🔴

> **Внимание пользователям:** если вы когда-либо включали `logger: default: debug` или `info` для `custom_components.elektronny_gorod`, рекомендуется **перевыпустить access_token** (пройти reauth через UI), особенно если вы делились логами в issue / Discord / других публичных местах. В предыдущих версиях access_token и Bearer-headers попадали в логи на уровне debug/info.

- Удалено логирование `access_token` после ввода в advanced-режиме config_flow ([A-01](docs/audit/project-audit.md)).
- Headers с `Authorization: Bearer ...` теперь проходят через `redact()` перед попаданием в логи ([A-02](docs/audit/project-audit.md)).
- Тело запроса/ответа для `/auth/*` endpoints не логируется вообще (там приходят/отправляются токены, пароли, SMS-коды) ([A-03](docs/audit/project-audit.md)).
- В логи попадает `entry.entry_id` вместо целиком `entry.data` (которое содержит токены) ([A-04](docs/audit/project-audit.md)).
- Contract object не дампится в логи целиком — только subscriberId ([S-06](docs/audit/security.md)).
- Добавлен helper `_logging.redact()` с `SENSITIVE_KEYS` (источник правды — [ADR-0004](docs/decisions/0004-token-redaction.md)).

### Fixed

- Исправлен баг в `update_camera_state`: поиск по ключу `"ID"` (верхний регистр) вместо `"id"` — приводил к ложному `Camera not found` при каждом async_update камеры ([A-06](docs/audit/project-audit.md)).
- `coordinator._async_update_data` использует `LOGGER.exception(...)` вместо `traceback.format_exc()` (не блокирует event loop).
- В `sensor.py:async_update` exception теперь логируется с traceback (`LOGGER.exception`).
- `http.py:_log_response` больше **не вычитывает** response body для логирования — это устраняет латентный баг, при котором логгер «съедал» тело и caller получал пустой ответ. Сейчас в лог идут только status + content-length (для не-auth paths).

### Changed

- `import base64` поднят на top of file в `camera.py` (был внутри метода) ([A-43](docs/audit/project-audit.md)).
- Заменён `f"..."`-форматирование на `%`-форматирование в `LOGGER` вызовах (`lock.py`, `sensor.py`, `coordinator.py`).

### Removed

- Удалён нерабочий `tests/test_config_flow.py` — это был stub из HA scaffold, импортирующий несуществующие сущности (`CannotConnect`, `InvalidAuth`, `PlaceholderHub`). Полноценные тесты config_flow появятся в [Итерации 2](docs/roadmap.md) Bronze IQS ([A-07](docs/audit/project-audit.md)).

### Tests

- Добавлен `tests/test_logging_redact.py` — unit-тесты для `_logging.redact()` helper.

### Documentation

- Создан этот `CHANGELOG.md`.

---

## История релизов

Записи до этого Changelog — см. [GitHub Releases](https://github.com/gentslava/HA-ElektronnyGorod/releases).
