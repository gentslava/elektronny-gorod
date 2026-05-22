# Workflow — процесс работы

Стандартный путь любого изменения в проекте `elektronny-gorod`. Применяется и к agent-driven, и к human-driven работе.

## Lifecycle

```text
idea
  ↓
spec / PRD (для нетривиальных изменений)
  ↓
research (проверка HA docs, аналогов, breaking changes)
  ↓
plan / tasklist
  ↓
implementation (slice by slice)
  ↓
review (self + code-reviewer agent)
  ↓
QA / tests
  ↓
security check (для auth/logs/diagnostics — обязательно)
  ↓
docs update (parallel)
  ↓
release (через GitHub Release → workflow `release.yaml`)
```

## По этапам

### 1. Idea

| Поле | Значение |
|---|---|
| Owner | пользователь / разработчик |
| Inputs | проблема, issue, feature request |
| Outputs | устное/письменное описание |
| Gate | `IDEA_CAPTURED` |
| Stop condition | если идея неясна — не начинать spec |

### 2. Spec / PRD

| Поле | Значение |
|---|---|
| Owner | разработчик + Architecture agent |
| Inputs | идея, контекст из [`docs/`](docs/index.md) |
| Outputs | issue / PR description / `docs/features/<id>/prd.md` (Full AIDD) |
| Gate | `SPEC_READY` |
| Required | проблема, целевой пользователь, ожидаемое поведение, критерии приёмки |

Когда нужен spec:
- любое изменение в `config_flow.py` (новые поля, шаги);
- любое изменение в `manifest.json` (`iot_class`, `version`, `integration_type`, `requirements`);
- любое изменение entity-структуры (`unique_id`, `device_info`, `platforms`);
- любая migration версии config-entry.

Когда **не** нужен spec:
- исправление опечатки;
- обновление документации;
- bug-fix с очевидным root cause (одна строка).

### 3. Research

| Поле | Значение |
|---|---|
| Owner | разработчик / HA-expert agent |
| Inputs | spec |
| Outputs | резюме исследования (HA docs, IQS rules, аналогичные интеграции) |
| Gate | `RESEARCH_DONE` |
| Required | ссылка на актуальную HA-документацию, проверка через Context7 для новых API |

Обязательно сверяться с:
- [HA Developer Docs](https://developers.home-assistant.io/);
- [Integration Quality Scale Rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/);
- [`source-base.md`](docs/aidd/source-base.md).

### 4. Plan / Tasklist

| Поле | Значение |
|---|---|
| Owner | разработчик |
| Inputs | spec + research |
| Outputs | список тасков с порядком и evidence |
| Gate | `PLAN_APPROVED` |
| Stop | не начинать implementation без явного approval |

Для Claude Code — использовать TodoWrite. Каждая таска — verifiable.

### 5. Implementation

| Поле | Значение |
|---|---|
| Owner | разработчик / implementer agent |
| Inputs | plan |
| Outputs | code changes + tests + docs updates |
| Gate | `IMPLEMENTATION_STEP_OK` |

Правила:
- одна таска — один логический commit;
- тесты пишутся вместе с кодом (TDD не строго требуется, но желателен);
- documentation update — часть definition of done.

### 6. Review

| Поле | Значение |
|---|---|
| Owner | code-reviewer agent / self-review |
| Inputs | diff |
| Outputs | список замечаний или approval |
| Gate | `REVIEW_OK` |
| Required | проверка по 5 осям: correctness, readability, architecture, security, performance |

### 7. QA / Tests

| Поле | Значение |
|---|---|
| Owner | QA agent / разработчик |
| Inputs | code + tests |
| Outputs | log выполнения pytest, coverage |
| Gate | `TESTS_PASS` |
| Required | pytest зелёный, hassfest зелёный, HACS validate зелёный |

### 8. Security check

| Поле | Значение |
|---|---|
| Owner | security agent |
| Inputs | diff |
| Outputs | security report |
| Gate | `SECURITY_OK` |
| Required | нет логирования токенов / headers / паролей |

Обязательно для diff, который трогает:
- `http.py`, `api.py`;
- `config_flow.py` (логи около `access_token`, `entry.data`);
- `helpers.py` (crypto);
- `diagnostics.py` (когда появится).

### 9. Docs update

| Поле | Значение |
|---|---|
| Owner | documentation agent / разработчик |
| Inputs | code changes |
| Outputs | updated `docs/**`, README, CHANGELOG |
| Gate | `DOCS_UPDATED` |

Что обновлять (maintenance rules — см. [`project-audit.md`](docs/project/project-map.md#maintenance-rules)):

| Если изменён | Обновить |
|---|---|
| `manifest.json` | `project-map.md`, `ha-compatibility.md`, `source-of-truth.md` |
| `config_flow.py` | `architecture/overview.md`, `testing/strategy.md`, `ha-compatibility.md` |
| `coordinator.py` | `architecture/overview.md`, `testing/strategy.md`, `project-audit.md` |
| `camera.py`, `lock.py`, `sensor.py` | `architecture/overview.md`, `testing/strategy.md` |
| `strings.json` / `translations/*` | `ha-compatibility.md` |
| тесты | `testing/strategy.md`, `quality-gates.md` |
| CI workflows | `contributing.md`, `quality-gates.md` |
| README | `summary.md`, `index.md` |
| security-чувствительный код | `security.md`, `project-audit.md` |

### 10. Release

| Поле | Значение |
|---|---|
| Owner | разработчик |
| Inputs | merged master |
| Outputs | GitHub Release + zip |
| Gate | `READY_FOR_RELEASE` |

Процедура (на сегодня):
1. Создать GitHub Release с тегом `vX.Y.Z`.
2. `release.yaml` workflow: обновит `manifest.json`, упакует zip, прикрепит к релизу, закоммитит изменение версии.
3. HACS подхватит автоматически.

См. [`.github/workflows/release.yaml`](.github/workflows/release.yaml).

## Quality gates

Подробности по каждому gate — в [`quality-gates.md`](docs/aidd/quality-gates.md).

## Когда что-то идёт не так

- Тест падает → не «исправлять» тест. Фиксить root cause через [`agent-skills:debugging-and-error-recovery`](https://developers.home-assistant.io/) или skill `systematic-debugging`.
- Migration ломает entry → откатить через увеличение VERSION (только вперёд) и компенсирующую миграцию.
- Security incident (утечка токена) → описать в `docs/audit/security.md`, выпустить hotfix-релиз, рекомендовать пользователям ре-аутентификацию.
