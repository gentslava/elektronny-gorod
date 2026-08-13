Status: Active Owner: Validator Agent Last reviewed: 2026-08-11 (A-97 candidate freeze/re-attestation and publication/CI evidence lifecycle by ADR-0015)

Source files:
- весь репозиторий

Related docs:
- `../../workflow.md`
- `../audit/project-audit.md`
- `../audit/security.md`
- `../testing/strategy.md`
- `../roadmap.md`

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
| Required evidence | executable plan/tasklist с scope, acceptance, execution mode, concrete implementer/reviewer identities, plan revision, approver/date/evidence |
| Pass | каждый таск конкретен; subagent-driven выбран по умолчанию при доступности; обязательные independent reviewers назначены до implementation; approval относится к записанной revision |
| Fail | план «улучшить документацию» без конкретики; execution mode/review routing оставлены на конец; короткое «го» не было прямым ответом на предъявленный полный план |

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
| Purpose | Локальные тесты зелёные до candidate freeze и реально выполнялись |
| Owner | QA Agent |
| Required commands | `PYTHONPATH=. .venv/bin/pytest tests/ -q` |
| Required evidence | свежий вывод pytest; актуальный baseline и состав suite — в [`testing/strategy.md`](../testing/strategy.md) |
| Pass | все тесты зелёные; config_flow покрыт основными сценариями; новые external API contracts проверяют exact wire shape; background lifecycle имеет unload/backpressure regressions; нет тестов, маскирующих баги |
| Fail | падающие тесты; pytest не запускался; тесты «исправлены» под сломанное поведение |
| Stop | без TESTS_PASS не замораживать candidate; remote checks закрываются отдельным `CI_GREEN` после push |

## CANDIDATE_FROZEN

| Поле | Значение |
|---|---|
| Purpose | Все implementation gates завершены, а review относится к immutable candidate |
| Owner | implementer / Validator Agent |
| Required evidence | пустой `git status --short`; merge-base SHA, head SHA и `HEAD^{tree}`; spec/plan revision |
| Pass | candidate полностью committed; TESTS_PASS, SECURITY_PRECHECK_OK, DOCS_UPDATED и HISTORY_CLEAN завершены; все финальные reviewers получили один base/head/tree |
| Fail | uncommitted changes; reviewer проверяет другой head/tree; после approval появился содержательный commit |
| Stop | не выдавать `REVIEW_OK`; после любого fix повторить затронутые implementation gates, freeze и получить новую candidate-bound аттестацию каждого обязательного reviewer-а |

## REVIEW_OK

| Поле | Значение |
|---|---|
| Purpose | Diff проверен по 5 осям |
| Owner | независимый от implementer-а code-reviewer agent / human reviewer |
| Required evidence | `CANDIDATE_FROZEN`; reviewer identity/independence; base/head/tree; read-only report; новая candidate-bound аттестация каждого обязательного HA/security/QA reviewer-а по routing matrix |
| Pass | correctness ✓ readability ✓ architecture ✓ security ✓ performance ✓; Critical/Important findings закрыты; все обязательные verdicts относятся к одному текущему tuple |
| Fail | только self-review; reviewer участвовал в implementation; хотя бы один verdict относится к старому/другому tuple; нет профильного review; хотя бы один Critical/Important открыт |
| Stop | не merge-ить и не релизить; обычный push/PR запрещён, кроме явно разрешённой review-only branch/draft с красным gate |

## SECURITY_OK

| Поле | Значение |
|---|---|
| Purpose | Нет утечек секретов в логи, есть redaction, нет очевидных уязвимостей |
| Owner | Security & Privacy Agent |
| Required commands | `bash .codex/hooks/check-secret-logs.sh` → `Secret log scan passed` |
| Required evidence | `CANDIDATE_FROZEN` + independent read-only security review того же base/head/tree для auth/token/credentials/FCM-sensitive diff |
| Pass | все Critical/Important security findings закрыты и перепроверены; redaction boundary подтверждена на frozen candidate |
| Fail | хотя бы один Critical/Important finding не закрыт или review относится к другому candidate |
| Stop | без SECURITY_OK не релизить |

## REVIEW_EVIDENCE_PUBLISHED

| Поле | Значение |
|---|---|
| Purpose | Candidate-bound approvals доступны всем участникам PR вне проверяемого tree |
| Owner | Validator/root orchestrator |
| Required evidence | PR comment для текущего head/tree: base/head/tree, plan/spec revision, local gates, identity/independence/scope/verdict каждого обязательного reviewer |
| Pass | comment опубликован после ordinary push и точно соответствует текущему candidate; новый candidate имеет новый comment |
| Fail | evidence осталось только в session transcript; comment относится к старому SHA; отчёт закоммичен внутрь candidate |
| Stop | не merge-ить без durable PR evidence текущего candidate |

## CI_GREEN

| Поле | Значение |
|---|---|
| Purpose | Remote checks подтвердили уже опубликованный и одобренный candidate |
| Owner | Validator / DevOps Agent |
| Required evidence | Required GitHub checks текущего head SHA: Python Tests, Validate with hassfest, HACS Action; PR Pre-Release — когда workflow применим |
| Pass | все применимые required jobs success; корректно skipped conditional job допустим |
| Fail | failure/cancelled/pending required job; checks относятся к старому head |
| Stop | не merge-ить и не релизить до зелёного CI текущего candidate |

## SECURITY_PRECHECK_OK

| Поле | Значение |
|---|---|
| Purpose | До freeze устранены известные security-проблемы и зелёные локальные проверки |
| Owner | Security & Privacy Agent / implementer |
| Required evidence | secret grep/redaction tests; закрытые known Critical/Important findings |
| Pass | candidate можно безопасно commit/freeze без известных blocker-ов |
| Fail | секреты в output; открытый blocker; precheck не запускался |
| Stop | без SECURITY_PRECHECK_OK не закрывать `CANDIDATE_FROZEN` |

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
| Purpose | git-история feature-ветки стабилизирована до candidate freeze и останется чистой перед merge |
| Owner | Git Historian ([Claude](../../.claude/agents/git-historian.md) / [Codex](../../.codex/agents/git-historian.toml)); Validator/root fallback |
| Required evidence | commit list + diff against `<target-ref>`; нет WIP/DIAG/debug/typo-only цепочек; дальнейший rebase/squash не запланирован; при rewrite создан локальный backup ref |
| Pass | `git log --oneline <target-ref>..HEAD` показывает logically-grouped conventional commits; rationale понятен из subject/body; после freeze история не меняется |
| Fail | >3 hotfix-ов подряд на одну фичу; коммиты «WIP», «fix typo», «revert prev»; DIAG/debug код в финальном diff |
| Stop | не закрывать `CANDIDATE_FROZEN` и не merge-ить без cleanup; force-push в master запрещён |

См. [`.claude/rules/git-history.md`](../../.claude/rules/git-history.md) и slash-команду `/git-cleanup`.

## READY_FOR_RELEASE

| Поле | Значение |
|---|---|
| Purpose | Релиз готов к публикации |
| Owner | Lead Architect / разработчик |
| Required gates passed | TESTS_PASS + SECURITY_PRECHECK_OK + DOCS_UPDATED + HISTORY_CLEAN + CANDIDATE_FROZEN + REVIEW_OK + SECURITY_OK + REVIEW_EVIDENCE_PUBLISHED + CI_GREEN + AUDIT_DONE |
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
| SECURITY_PRECHECK_OK | candidate freeze |
| CANDIDATE_FROZEN | независимый review |
| REVIEW_OK | merge |
| SECURITY_OK | merge |
| REVIEW_EVIDENCE_PUBLISHED | merge |
| CI_GREEN | merge + release |
| DOCS_UPDATED | merge |
| HISTORY_CLEAN | candidate freeze + merge |
| READY_FOR_RELEASE | публикация |

> **«Реальное состояние сейчас» намеренно убрано из этой таблицы (ADR-0010,
> D-03).** Live-состояние гниёт внутри методологического документа. Единый
> источник findings/status — [`project-audit.md`](../audit/project-audit.md),
> live test baseline — [`testing/strategy.md`](../testing/strategy.md), а
> [`summary.md`](../summary.md) содержит только качественную сводку без count.
> Здесь — только **определения** гейтов, не их текущий цвет (ADR-0015).

## Принцип

Gate можно «пропустить» только с **записанным waiver** (ADR-0010, D-05): строка в `project-audit.md` / PR body вида «gate X skipped, owner: <…>, причина: <…>». Никаких «потом починим». Если gate красный — фиксить gate, а не идти дальше.

**Исключение ADR-0015:** для нетривиального diff `REVIEW_OK`, обязательные профильные reviews, `REVIEW_EVIDENCE_PUBLISHED` и `CI_GREEN` non-waivable для merge/release. Явное human risk acceptance может разрешить только review-only branch/draft PR; оно не создаёт ни один из этих гейтов и не разрешает merge/release.

### quality_scale ≤ gate-confirmed (D-05)

`manifest.json:quality_scale` **не поднимать выше** уровня, реально подтверждённого гейтами. Пример: Bronze требует `config-flow-test-coverage` (happy path + abort `already_configured` + migrations) — пока этих тестов нет, `bronze` в manifest держится как **открытый finding**, а не как факт. Любое несоответствие manifest↔гейт — finding в `project-audit.md`.

## Next reading

- For workflow: `../../workflow.md`
- For findings: `../audit/project-audit.md`
- For security details: `../audit/security.md`
- For test plan: `../testing/strategy.md`
- For roadmap: `../roadmap.md`
