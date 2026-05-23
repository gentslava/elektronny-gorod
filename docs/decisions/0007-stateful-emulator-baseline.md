# ADR-0007: Stateful emulator baseline для HAR-сбора

- **Status:** accepted
- **Date:** 2026-05-23
- **Owner:** @gentslava + reverse-engineer agent

## Context

Реализация принципа [ADR-0006: Mirror application behavior](0006-mirror-app-behavior.md) требует регулярного сбора HAR-снимков мобильного приложения. Приложение обновляется → API контракты могут меняться → нужен повторяемый процесс сбора и сравнения.

При проектировании pipeline возник вопрос: должен ли эмулятор начинать каждый сбор «с чистого листа» (stateless) или сохранять состояние после первого login (stateful)?

Stateless имеет проблемы:
- SMS-код требует физическое устройство / SIM — **не автоматизируется** AI-агентом.
- Каждый login = вариативность: разный access_token, разный uuid, разный timestamp в trafficке. Это мешает diff-сравнению между сессиями.
- Login сам по себе генерирует ~20-30 запросов; они **зашумляют** trafficке, относящийся к собственно изучаемому сценарию (open intercom, view camera, refresh balance).
- Большую часть времени реальный пользователь приложения **залогинен** — stateless не отражает «нормальное» поведение приложения.

Stateful (с baseline snapshot) даёт:
- Один SMS login раз → AVD snapshot save → дальше любой сценарий поднимается за секунды.
- Стабильный baseline для diff-анализа.
- Точное отражение «обычной» работы приложения.

## Decision

**HAR-сбор работает поверх stateful AVD baseline snapshot.**

Дизайн:

### Два класса сценариев

| Класс | Когда | Старт |
|---|---|---|
| **A — logged-in** | 95% сбора. Любые user-flows внутри приложения: открыть домофон, посмотреть камеру, баланс, история, background polling. | `snapshot load logged-in-baseline` → app start |
| **B — auth** | 5% сбора. Только когда работаем над auth-логикой: login flow, reauth, token refresh, logout. | `pm clear <package>` → app start → manual login |

### Baseline lifecycle

1. **Создание baseline (manual, один раз на версию APK):**
   - Запустить чистый AVD.
   - Установить mitmproxy CA cert в системные сертификаты (writable system).
   - Установить пропатченный APK (см. [ADR-0006](0006-mirror-app-behavior.md), runbook [`har-collection.md`](../aidd/runbooks/har-collection.md)).
   - Запустить приложение, пройти SMS login руками.
   - Дойти до главного экрана, дождаться загрузки.
   - `adb emu avd snapshot save logged-in-baseline`.
2. **Использование baseline (каждый сбор):**
   - `adb emu avd snapshot load logged-in-baseline`.
   - Не нужно: SMS, login, cert install, proxy setup.
3. **Обновление baseline:**
   - **Триггер:** обновилась версия приложения (новый APK) или истёк access_token и приложение требует reauth при старте.
   - **Процедура:** повторить шаг 1.
   - **Не автоматизируется** — это редкое осознанное действие.

### Что НЕ делает pipeline

- Не пытается обойти SMS-step через SMS-gateway / Android sim — это отдельная инфраструктура, оправдает себя только при частом auth-сборе.
- Не пытается «умно» рестейтить baseline — при ошибке (snapshot corrupt, token expired в snapshot) — manual rebuild.
- Не делает headless рекординг без human-in-loop для класса B.

## Consequences

### Positive

- Сбор HAR класса A → секунды между сценариями.
- AI-агент `reverse-engineer` может запустить полную партию сценариев класса A без human action.
- Diff-анализ между HAR-сессиями становится осмысленным (baseline стабилен).
- Класс B явно отделён — там, где нужен human-in-loop, он не маскируется попыткой автоматизации.

### Negative

- Snapshot файл AVD большой (~1-2 GB) — занимает место на машине разработчика.
- Baseline «протухает»: access_token истекает, APK устаревает — требует periodic rebuild.
- При обновлении АPK мы временно теряем baseline, пока вручную не создан новый.

### Mitigation

- Хранить только один активный baseline (`logged-in-baseline`). При rebuild — overwrite, не плодить snapshots.
- Документировать дату создания baseline + версию APK + срок действия access_token в `research/scripts/.baseline-meta` (gitignored).
- При regular maintenance — проверять валидность baseline (одиночный «smoke» сбор главного экрана).

## Alternatives considered

1. **Stateless + SMS gateway** (Twilio / virtual SIM). Отклонено — стоимость + сложность infrastructure не окупается частотой использования.
2. **Stateless + mocked auth response** (mitmproxy intercept + replay). Отклонено — нарушает [ADR-0006](0006-mirror-app-behavior.md): мы должны эмулировать реальный поток, а не подсовывать приложению фиктивные данные.
3. **Live device вместо emulator.** Отклонено как primary — не воспроизводимо между разработчиками, не делится между AI-агентом и человеком, USB-debugging requires physical access.
4. **One snapshot per scenario.** Отклонено — взрыв количества snapshot, сложность синхронизации, не даёт diff-baseline.

## Supersedes / Superseded by

— (новое решение, дополняет [ADR-0006](0006-mirror-app-behavior.md))

## Notes

- Связано с [`research/scripts/`](../../research/scripts/) — pipeline реализации.
- Реализация: [`runbooks/har-collection.md`](../aidd/runbooks/har-collection.md).
- Роль: [`.claude/agents/reverse-engineer.md`](../../.claude/agents/reverse-engineer.md).
