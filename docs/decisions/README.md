# Architecture Decision Records

Журнал архитектурных решений проекта. Каждое ADR — отдельный файл `NNNN-kebab-title.md`.

## Зачем

- ADR фиксирует **контекст** решения и его **последствия**, чтобы будущий разработчик / AI-агент мог понять, почему сейчас именно так.
- ADR не редактируется после `accepted`. Чтобы изменить решение — новый ADR со ссылкой `supersedes NNNN`.

## Формат

См. [`../aidd/templates/adr.template.md`](../aidd/templates/adr.template.md).

## Список

| # | Title | Status | Date |
|---|---|---|---|
| [0001](0001-aidd-adoption.md) | Принятие AIDD | accepted | 2026-05-22 |
| [0002](0002-coordinator-pattern.md) | Переход на CoordinatorEntity + update_interval | **accepted** (slice 3a реализован) | 2026-05-22 |
| [0003](0003-iot-class-strategy.md) | Стратегия `iot_class` и polling | **accepted** (slice 3a реализован) | 2026-05-22 |
| [0004](0004-token-redaction.md) | Token redaction в логах | **accepted** (реализован в hotfix PR #31) | 2026-05-22 |
| [0005](0005-lock-vs-button.md) | Lock vs Button для домофона | proposed | 2026-05-22 |
| [0006](0006-mirror-app-behavior.md) | Mirror application behavior | accepted | 2026-05-23 |
| [0007](0007-stateful-emulator-baseline.md) | Stateful emulator baseline для HAR-сбора | accepted | 2026-05-23 |
| [0008](0008-shared-client-session.md) | Shared `ClientSession` через `async_get_clientsession(hass)` | accepted | 2026-05-24 |
| [0009](0009-camera-stream-auto-recovery.md) | Camera stream auto-recovery при истечении operator session | accepted | 2026-05-27 |
| [0010](0010-aidd-state-reconciliation.md) | AIDD state-management + reconciliation findings↔git | accepted | 2026-05-30 |
| [0011](0011-doorbell-fcm-channel.md) | Realtime-канал вызова домофона через FCM | accepted | 2026-06-22 |
| [0012](0012-register-on-ring.md) | Register-on-ring для SIP-вызова | accepted | 2026-06-23 |
| [0013](0013-uplink-mic-transport.md) | Uplink-микрофон через HA WebSocket | accepted | 2026-06-24 |
| [0014](0014-go2rtc-stream-manager.md) | Единый go2rtc stream manager для внешнего RTSP | accepted | 2026-07-16 |

## Когда писать ADR

- Смена архитектурного паттерна (например, переход на CoordinatorEntity).
- Breaking change в config-flow (новые required-поля, изменение VERSION).
- Изменение domain / minimum HA version.
- Security-стратегия (redaction, storage, auth).
- Изменение пакетной структуры.

## Когда не писать ADR

- Bug-fix с очевидным root cause.
- Опечатка / документация.
- Косметический рефакторинг.
- Добавление теста для существующего кода.
