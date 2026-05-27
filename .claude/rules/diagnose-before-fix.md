# Rule: Diagnose before fix

**Применимо к:** любой PR претендующий на «закрытие production-bug»
(найдено в production-логах, observed user-pain, runtime issue).

## Правило

🔴 **Запрещено писать fix-код без подтверждённого root cause из
runtime diagnostics.** Hypothesis-driven coding (≈ «попробуем cache, может
быть поможет») без trace-evidence создаёт PR-каскады которые **не
решают проблему** и тратят время на review/revert.

## Quality gate `ROOT_CAUSE_CONFIRMED`

Считается зелёным если для bug-fix PR (тип `fix(*)` в conventional
commit, или PR с прикреплённым audit finding A-NN типа «P0/P1/P2
production bug»):

1. **Hypothesis сформулирована явно** в PR description / audit entry:
   - «Bug X происходит потому что Y вызывает Z с side-effect W».
2. **Diagnostic evidence приложена**:
   - Log excerpt с **точным moment** проявления (timestamps, caller
     chain, state snapshots).
   - Stack trace **caller** (`traceback.extract_stack()` или
     similar) если bug в lifecycle/async/concurrency.
   - go2rtc/operator API state snapshot (`/api/streams`, curl HTTP
     status) если bug связан с external integration.
3. **Минимум один диагностический шаг был сделан до first code
   change**. Просто «читал лог» — не считается; нужен **active
   diagnostic** — patch с trace logging, runtime probe, controlled
   reproduce.
4. **Root cause явно записан** в audit finding или PR description:
   формулировка «Causal chain: A → B → C → observed symptom».

## Какие bug-классы требуют DIAG особенно

| Класс bug | Mandatory diagnostic technique |
|---|---|
| Lifecycle (entity init/unload, HA Stream worker) | `traceback.extract_stack()` в подозреваемом callsite |
| Concurrency (race, dedup, in-flight) | Caller chain + thread/task identifier |
| Cascade reload, infinite loop | Counter с line-source каждого вызова |
| go2rtc / external service interaction | API state snapshot (`/api/streams`, `consumers`/`producers`) до и после |
| Network timeout, retry-storm | HTTP-level log (`http.py` debug) + tcpdump/curl reproduce |
| Cache invalidation, stale data | TS-based logging (`monotonic()`) показывающее actual TTL violations |

## Что НЕ считается diagnostic

- 🔴 «Я думаю что проблема в X, давайте попробуем фикс».
- 🔴 Code-review hypothesis без runtime подтверждения.
- 🔴 Тест который проверяет ожидаемое поведение fix-а (≠ diagnostic root cause).
- 🔴 Прочтение существующего лога **без** дополнительного active
  instrumentation (если лог не даёт прямого ответа «кто/когда/почему»).
- 🔴 «Похоже на bug X, который мы видели раньше» — нужна new evidence
  для **этого** случая.

## Когда DIAG можно skip-нуть

Узкие исключения (с явным обоснованием в PR body):

- **Trivial bugfix**: typo, off-by-one, copy-paste ошибка с очевидным
  diff. Evidence — read of code, не runtime.
- **Cosmetic/docs**: PR без runtime impact (translations, README).
- **Pre-emptive hardening** без observed bug (но это **не** «закрытие
  production-bug», другой класс).
- **Revert PR** уже merged change — diagnostic был у оригинала.

Не исключения:
- ❌ «Logs показывают X, очевидно нужен Y» — нет, нужно показать
  causal chain ДО fix.
- ❌ «Юзер сказал что мигает, я думаю это cache» — нет, нужно
  поймать caller.

## Anti-patterns этого проекта (lessons learned)

Реальные грабли, на которые мы наступили:

1. **A-66 эксперимент** (PR #44 X / #45 Y / #46 Z): 3 параллельных
   PR с 3 разными гипотезами «как лечить мигание видео». **Без
   diagnostic — без понимания root cause**. Из 3 — 2 закрыты, 1
   merged. Потеря ~4 часов работы.

2. **A-69 cache + A-70 revert update_source** (PR #52 / #53): ещё
   2 PR на ту же тему, тоже **без trace-evidence**. Оба закрыты
   без merge после того как finally сделали trace-logging и нашли
   что root cause — HA Stream `preload_stream` toggle на стороне
   юзера, а не cache/restart logic.

3. **Что сработало**: 5-минутный patch с `traceback.extract_stack()`
   в `stream_source()` + restart HA + grep `DIAG` в логе → за
   1 цикл показал caller chain и root cause.

## Связь

- [`.claude/rules/pre-pr-checklist.md`](pre-pr-checklist.md) — gate
  `ROOT_CAUSE_CONFIRMED` встроен в pre-PR sequence для bug-fix PR.
- [`docs/aidd/quality-gates.md`](../../docs/aidd/quality-gates.md) —
  формальное определение gate (TBD при следующей синхронизации).
- Skill [`debugging-and-error-recovery`](../../docs/aidd/) — методология
  trace-driven debugging.
- Skill [`incremental-implementation`](../../docs/aidd/) — slice по slice,
  каждый slice c verification (включая diagnostic для bug-fix slice).
