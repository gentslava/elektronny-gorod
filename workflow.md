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
QA / tests
  ↓
security precheck (для auth/logs/diagnostics — обязательно)
  ↓
docs update
  ↓
history cleanup + freeze clean committed candidate
  ↓
independent code/profile reviews (включая SECURITY_OK)
  ├─ findings → fixes → gates → new freeze/re-review
  └─ approved
  ↓
ordinary push / PR → publish review evidence → CI_GREEN
  ↓
merge → merged-state reconciliation / release
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
| Outputs | список тасков с порядком/evidence + execution mode + reviewer matrix |
| Gate | `PLAN_APPROVED` |
| Stop | не начинать implementation без явного approval |

Для Claude Code — использовать TodoWrite. Каждая таска — verifiable.

**Default execution policy:** если доступны subagents, нетривиальный план исполняется subagent-driven. После явной рекомендации короткий ответ пользователя «го» / «да» / «начинай» принимает рекомендованный режим. Inline execution — только по прямому выбору пользователя либо при отсутствии subagents. План заранее маршрутизирует обязательные независимые review: `code-reviewer` всегда; `ha-expert`, `security-auditor` и `qa-engineer` — по затронутым областям.

Такой короткий ответ закрывает `PLAN_APPROVED` только если он дан прямо на полный план со scope, acceptance, execution mode и reviewer matrix. План сохраняет approver, дату, revision и назначенных исполнителей/reviewers (ADR-0015).

### 5. Implementation

| Поле | Значение |
|---|---|
| Owner | implementer subagent(s) по умолчанию / разработчик при explicit inline |
| Inputs | plan |
| Outputs | code changes + tests + docs updates |
| Gate | `IMPLEMENTATION_STEP_OK` |

Правила:
- одна таска — один логический commit;
- тесты пишутся вместе с кодом (TDD не строго требуется, но желателен);
- documentation update — часть definition of done.

### 6. QA / Tests

| Поле | Значение |
|---|---|
| Owner | QA agent / разработчик |
| Inputs | code + tests |
| Outputs | log выполнения pytest, coverage |
| Gate | `TESTS_PASS` |
| Required | Локально `PYTHONPATH=. .venv/bin/pytest tests/ -q` зелёный; дополнительные локальные проверки — по test plan. Remote matrix/hassfest/HACS относятся к post-push `CI_GREEN` |

QA участвует в reviewer matrix, если diff добавляет/меняет тесты, fixtures или test plan. TDD остаётся частью implementation; этот этап подтверждает весь candidate после завершения slices.

### 7. Security precheck

| Поле | Значение |
|---|---|
| Owner | security agent / implementer |
| Inputs | diff |
| Outputs | precheck log и исправленные known security findings |
| Gate | `SECURITY_PRECHECK_OK` |
| Required | локальные secret/redaction checks зелёные; нет известных открытых Critical/Important security findings |

Обязательно для diff, который трогает:
- `http.py`, `api.py`;
- `config_flow.py` (логи около `access_token`, `entry.data`);
- `fcm.py` и любые FCM credentials / Repairs placeholders;
- `helpers.py` (crypto);
- `diagnostics.py`.

### 8. Docs update

| Поле | Значение |
|---|---|
| Owner | documentation agent / разработчик |
| Inputs | code changes |
| Outputs | updated `docs/**`, README, CHANGELOG |
| Gate | `DOCS_UPDATED` |

Что обновлять (maintenance rules — см. [`project-map.md`](docs/project/project-map.md#maintenance-rules)):

| Если изменён | Обновить |
|---|---|
| `manifest.json` | `project-map.md`, `ha-compatibility.md`, `source-of-truth.md` |
| `config_flow.py` | `architecture/overview.md`, `testing/strategy.md`, `ha-compatibility.md` |
| `coordinator.py` | `architecture/overview.md`, `testing/strategy.md`, `project-audit.md` |
| `camera.py`, `lock.py`, `sensor.py` | `architecture/overview.md`, `testing/strategy.md` |
| `strings.json` / `translations/*` | `ha-compatibility.md` |
| тесты | `testing/strategy.md`; `quality-gates.md` только при изменении определения gate |
| CI workflows | `contributing.md`, `quality-gates.md` |
| README | `summary.md`, `index.md` |
| security-чувствительный код | `security.md`, `project-audit.md` |

Плюс **ось B (событие состояния → docs)** — ADR-0010, см. [`project-map.md#maintenance-rules`](docs/project/project-map.md#maintenance-rules): finding→RESOLVED ⇒ `summary.md` риски + release-state CHANGELOG + снять метку в `AGENTS.md`; finding→resolved-in-branch ⇒ только `project-audit.md` (не трогать риски до merge). Candidate-bound feature docs и `CHANGELOG.md` `[Unreleased]` входят в тот же PR, но не утверждают availability в `master` (ADR-0015). 🔴 Не дублировать состояние: findings/status — `project-audit.md`, live test baseline — только `testing/strategy.md`, краткая качественная сводка без count — `summary.md` (ADR-0015).

### 9. Candidate freeze and independent review

| Поле | Значение |
|---|---|
| Freeze owner | implementer / Validator Agent |
| Review owners | независимый code-reviewer и обязательные profile reviewers |
| Inputs | approved spec/plan + clean committed candidate |
| Outputs | список замечаний или scoped approval |
| Gates | `CANDIDATE_FROZEN`, затем `REVIEW_OK` |
| Required | 5 осей code review; профильные HA/security/QA reviews по matrix; Critical/Important закрыты и перепроверены |

До freeze завершить `HISTORY_CLEAN`: commit structure/rebase/squash больше не должны менять будущий head. Затем зафиксировать evidence (ADR-0015):

```bash
git status --short
git merge-base <target-ref> HEAD
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
```

`git status --short` должен быть пустым. Reviewer получает base SHA, head SHA, tree SHA и проверяет exact `base..head` diff в read-only режиме. Все финальные reviewers проверяют один candidate. Self-review implementer-а выполняется до freeze, но не является evidence для `REVIEW_OK`.

Любое содержательное изменение после approval создаёт новый candidate: затронутые implementation gates запускаются повторно, SHA обновляются, а каждый обязательный reviewer выдаёт новый candidate-bound verdict/attestation. Re-review неизменившегося scope может сверить blob IDs и быть delta-scoped, но его итоговый verdict всегда относится к новому tuple (ADR-0015). Для HA-sensitive diff обязателен HA review; для secret/token/FCM-sensitive — security review; для tests/test plan — QA review. Именно post-freeze security review закрывает `SECURITY_OK`; pre-freeze этап закрывает только `SECURITY_PRECHECK_OK`, поэтому циклической зависимости нет.

По умолчанию локальные subagents завершают review до push/PR. Если независимому человеку нужен remote diff, владелец может явно разрешить только review branch или draft PR: `REVIEW_OK` остаётся красным, merge/release запрещены. Уже открытый PR переводится в тот же recovery flow: freeze → review → fixes → новый freeze → re-attestation всех обязательных reviewers. Обычный waiver не заменяет независимый review.

### 10. Publication and CI

| Поле | Значение |
|---|---|
| Owner | Validator/root + разработчик |
| Inputs | approved frozen candidate |
| Outputs | ordinary push/PR, durable PR evidence comment, remote check results |
| Gates | `REVIEW_EVIDENCE_PUBLISHED`, `CI_GREEN` |
| Required | PR comment и required checks относятся к текущему head/tree |

После approvals Validator выполняет обычный push/PR и публикует validation comment с base/head/tree, plan/spec revision, local gates и candidate-bound verdicts всех обязательных reviewers. Этот комментарий — канонический off-tree журнал evidence; session transcript до публикации является provisional.

Затем дождаться GitHub checks для текущего head: Python Tests, hassfest и HACS. PR Pre-Release обязателен, только когда workflow применим к diff; корректно skipped job не является failure. Новый commit требует нового freeze/reviews, нового evidence comment и нового CI run. Без `CI_GREEN` merge запрещён (ADR-0015).

### 11. Release

| Поле | Значение |
|---|---|
| Owner | разработчик |
| Inputs | merged master |
| Outputs | GitHub Release + zip |
| Gate | `READY_FOR_RELEASE` |

Процедура (на сегодня):
1. Создать GitHub Release с тегом `X.Y.Z` (без префикса `v`).
2. `release.yaml` workflow: обновит `manifest.json`, упакует zip, прикрепит к релизу, закоммитит изменение версии.
3. HACS подхватит автоматически.

См. [`.github/workflows/release.yaml`](.github/workflows/release.yaml).

## Quality gates

Подробности по каждому gate — в [`quality-gates.md`](docs/aidd/quality-gates.md).

## Когда что-то идёт не так

- Тест падает → не «исправлять» тест. Фиксить root cause через [`agent-skills:debugging-and-error-recovery`](https://developers.home-assistant.io/) или skill `systematic-debugging`.
- Migration ломает entry → откатить через увеличение VERSION (только вперёд) и компенсирующую миграцию.
- Security incident (утечка токена) → описать в `docs/audit/security.md`, выпустить hotfix-релиз, рекомендовать пользователям ре-аутентификацию.
