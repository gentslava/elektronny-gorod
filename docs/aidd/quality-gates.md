Status: Active
Owner: Validator Agent
Last reviewed: 2026-07-16 (TESTS_PASS: 548 backend + 62 frontend; external
RTSP preload/producer lifecycle regressions added)

Source files:
- весь репозиторий

Related docs:
- `../../workflow.md`
- `project-audit.md`
- `security.md`
- `testing/strategy.md`
- `roadmap.md`

Used by agents:
- Validator, Lead Architect, QA

---

# Quality Gates

Стоп-сигналы по этапам [workflow](../../workflow.md). Каждый gate имеет purpose, evidence, pass/fail-критерии.

## PROJECT_MAP_READY

| Поле | Значение |
|---|---|
| Purpose | Зафиксирована карта файлов и их назначения |
| Owner | Project Cartographer |
| Inputs | репозиторий |
| Required evidence | актуальный [`project-map.md`](../project/project-map.md) с evidence по каждой строке |
| Pass | все файлы, существующие в `custom_components/elektronny_gorod/`, упомянуты |
| Fail | новый файл в коде, не отражённый в карте |
| Stop | при fail — обновить `project-map.md` до выполнения следующих этапов |

## SOURCE_OF_TRUTH_READY

| Поле | Значение |
|---|---|
| Purpose | Каждый тип знания имеет первичный источник |
| Owner | Project Cartographer |
| Required evidence | [`source-of-truth.md`](../project/source-of-truth.md) актуален |
| Pass | конфликты задокументированы в `project-audit.md` с приоритетами |
| Fail | расхождения между кодом и документацией не задокументированы |

## ARCHITECTURE_UNDERSTOOD

| Поле | Значение |
|---|---|
| Purpose | Архитектура описана понятно для нового агента |
| Owner | Architecture Agent |
| Required evidence | [`architecture/overview.md`](../architecture/overview.md) с lifecycle, data flow, layer breakdown |
| Pass | агент с нуля может ответить: «что произойдёт при добавлении entry?», «как идёт snapshot?» |
| Fail | пропущен критичный поток (auth, migration, unlock, stream) |

## AUDIT_DONE

| Поле | Значение |
|---|---|
| Purpose | Проведён аудит код / HA-compat / security / reliability / testing |
| Owner | Lead Architect Agent |
| Required evidence | заполненный [`project-audit.md`](../audit/project-audit.md), [`security.md`](../audit/security.md), [`ha-compatibility.md`](../architecture/ha-compatibility.md) |
| Pass | каждая находка имеет priority + evidence + recommended fix + first step |
| Fail | находки без evidence; рекомендации без файла:строки |
| Stop | без AUDIT_DONE нельзя начинать planning |

## PLAN_APPROVED

| Поле | Значение |
|---|---|
| Purpose | План работ имеет порядок и acceptance |
| Owner | Lead Architect / разработчик |
| Required evidence | [`roadmap.md`](../roadmap.md) с итерациями + TodoWrite-список |
| Pass | каждый таск ссылается на конкретную находку из audit |
| Fail | план «улучшить документацию» / «добавить тесты» без конкретики |

## IMPLEMENTATION_STEP_OK

| Поле | Значение |
|---|---|
| Purpose | Один шаг (commit / PR / merge) выполнен корректно |
| Owner | разработчик / implementer agent |
| Required evidence | diff, тесты на новый код, обновлённые docs |
| Pass | scope шага не вырос; docs синхронизированы |
| Fail | «попутный рефакторинг» без явного approval; docs отстают |

## TESTS_PASS

| Поле | Значение |
|---|---|
| Purpose | Тесты зелёные, реально выполнялись |
| Owner | QA Agent |
| Required commands | `PYTHONPATH=. .venv/bin/pytest tests/ -q` |
| Required evidence | свежий вывод pytest; актуальный baseline и состав suite — в [`testing/strategy.md`](../testing/strategy.md) |
| Pass | все тесты зелёные; config_flow покрыт основными сценариями; новые external API contracts проверяют exact wire shape; background lifecycle имеет unload/backpressure regressions; нет тестов, маскирующих баги |
| Fail | падающие тесты; pytest не запускался; тесты «исправлены» под сломанное поведение |
| Stop | без TESTS_PASS не релизить |

## REVIEW_OK

| Поле | Значение |
|---|---|
| Purpose | Diff проверен по 5 осям |
| Owner | code-reviewer agent / human reviewer |
| Required evidence | review-комментарии или approval |
| Pass | correctness ✓ readability ✓ architecture ✓ security ✓ performance ✓ |
| Fail | хотя бы одна ось — fail |

## SECURITY_OK

| Поле | Значение |
|---|---|
| Purpose | Нет утечек секретов в логи, есть redaction, нет очевидных уязвимостей |
| Owner | Security & Privacy Agent |
| Required commands | `grep -rE "LOGGER\..*token\|LOGGER\..*headers\|LOGGER\..*entry\.data" custom_components/` → пусто |
| Required evidence | закрытые P0 пункты из [`security.md`](../audit/security.md) |
| Pass | все P0 security-findings закрыты; `diagnostics.py` с redaction; pre-commit hook (Итерация 3) |
| Fail | хотя бы один P0 не закрыт |
| Stop | без SECURITY_OK не релизить |

## DOCS_UPDATED

| Поле | Значение |
|---|---|
| Purpose | Документы синхронизированы с кодом |
| Owner | Documentation Agent |
| Required evidence | maintenance rules из [`project-map.md`](../project/project-map.md#maintenance-rules) выполнены |
| Pass | для каждого изменённого `Source files:` обновлены связанные docs |
| Fail | новый flow без обновления `architecture/overview.md`; новый source of truth без обновления `source-of-truth.md` |

## HISTORY_CLEAN

| Поле | Значение |
|---|---|
| Purpose | git-история feature-ветки чистая перед merge в master |
| Owner | [Git Historian Agent](../../.claude/agents/git-historian.md) |
| Required evidence | каждый коммит — substantive (нет hotfix-цепочек, DIAG-логов, typo-правок); commit messages conventional-стиля с body; diff vs master сохранён после rebase; backup-ветка создана |
| Pass | `git log --oneline master..HEAD` показывает короткую серию logically-grouped коммитов; каждое сообщение читается отдельно |
| Fail | >3 hotfix-ов подряд на одну фичу; коммиты «WIP», «fix typo», «revert prev»; DIAG/debug код в финальном diff |
| Stop | merge feature-ветки без cleanup'а; force-push в master |

См. [`.claude/rules/git-history.md`](../../.claude/rules/git-history.md) и
slash-команду `/git-cleanup`.

## READY_FOR_RELEASE

| Поле | Значение |
|---|---|
| Purpose | Релиз готов к публикации |
| Owner | Lead Architect / разработчик |
| Required gates passed | TESTS_PASS + SECURITY_OK + REVIEW_OK + DOCS_UPDATED + AUDIT_DONE + HISTORY_CLEAN |
| Required evidence | CHANGELOG entry; обновлённый README, если есть user-facing изменения; брендинг |
| Pass | все обязательные gates зелёные; нет открытых P0 |
| Fail | хотя бы один обязательный gate красный |
| Stop | не создавать GitHub Release без всех зелёных gates |

## Сводная таблица

| Gate | Обязателен для |
|---|---|
| PROJECT_MAP_READY | старт работы |
| SOURCE_OF_TRUTH_READY | старт работы |
| ARCHITECTURE_UNDERSTOOD | планирование |
| AUDIT_DONE | планирование |
| PLAN_APPROVED | implementation |
| IMPLEMENTATION_STEP_OK | каждый commit |
| TESTS_PASS | merge |
| REVIEW_OK | merge |
| SECURITY_OK | merge |
| DOCS_UPDATED | merge |
| HISTORY_CLEAN | merge |
| READY_FOR_RELEASE | публикация |

> **«Реальное состояние сейчас» намеренно убрано из этой таблицы (ADR-0010,
> D-03).** Live-состояние гниёт внутри методологического документа. Единый
> источник «что зелёное / что красное» — [`project-audit.md`](../audit/project-audit.md)
> (findings со `Status:`) + [`summary.md`](../summary.md) (таблица «Состояние»).
> Здесь — только **определения** гейтов, не их текущий цвет.

## Принцип

Gate можно «пропустить» только с **записанным waiver** (ADR-0010, D-05):
строка в `project-audit.md` / PR body вида «gate X skipped, owner: <…>,
причина: <…>». Никаких «потом починим». Если gate красный — фиксить gate,
а не идти дальше.

### quality_scale ≤ gate-confirmed (D-05)

`manifest.json:quality_scale` **не поднимать выше** уровня, реально
подтверждённого гейтами. Пример: Bronze требует `config-flow-test-coverage`
(happy path + abort `already_configured` + migrations) — пока этих тестов нет,
`bronze` в manifest держится как **открытый finding**, а не как факт. Любое
несоответствие manifest↔гейт — finding в `project-audit.md`.

## Next reading

- For workflow: `../../workflow.md`
- For findings: `project-audit.md`
- For security details: `security.md`
- For test plan: `testing/strategy.md`
- For roadmap: `roadmap.md`
