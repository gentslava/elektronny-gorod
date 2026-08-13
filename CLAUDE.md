# CLAUDE.md — Claude Code adapter

Этот файл — адаптер для Claude Code. Базовый контракт — в [`AGENTS.md`](AGENTS.md), его необходимо прочитать **до** любых действий.

## Порядок чтения для Claude

При старте новой сессии:

1. [`AGENTS.md`](AGENTS.md) — общий контракт.
2. [`docs/index.md`](docs/index.md) — точка входа в AIDD-документацию.
3. [`docs/summary.md`](docs/summary.md) — быстрый контекст за 2 минуты.
4. [`docs/project/project-map.md`](docs/project/project-map.md) — карта файлов.
5. [`source-of-truth.md`](docs/project/source-of-truth.md) — где правда о каждом куске.

Для специфичных задач — см. таблицу в [`docs/index.md`](docs/index.md).

## Claude-specific workflow

### Plan Mode

Включать plan mode (через `ExitPlanMode` контракт), если задача:
- задевает > 1 файл в `custom_components/`;
- меняет config-flow steps или entity unique_id;
- меняет `manifest.json` / `hacs.json` / `version`;
- удаляет существующий код;
- касается security-чувствительных областей (логи, токены, headers, diagnostics).

### Subagents

Использовать subagents для:
- выполнения нетривиального утверждённого плана по независимым задачам (default, если пользователь явно не выбрал inline);
- параллельного независимого исследования (Explore agent — поиск по коду);
- code review независимым агентом перед merge;
- security audit (security-auditor) при работе с auth/токенами/логами;
- QA review (qa-engineer) при изменении tests/fixtures/test plan.

Короткое подтверждение после рекомендации subagent-driven режима («го», «да», «начинай») принимает эту рекомендацию. Правило «не использовать subagent для задачи до 3 tool-calls» относится только к implementation/research и **никогда не отменяет** независимый `REVIEW_OK` для risk-bearing diff. Финальный review идёт read-only по clean committed base/head/tree после tests/security prechecks, docs и history cleanup; fixes создают новый candidate и требуют candidate-bound re-attestation каждого обязательного reviewer-а (ADR-0015).

### Hooks

`.claude/hooks/` настроены:
- `post-edit-redaction-check.sh` — проверяет, что в diff нет логирования токенов;
- `pre-commit-hassfest.sh` — валидация manifest перед коммитом;
- `check-audit-reconciliation.sh` — сверяет `RESOLVED` findings с git master + ловит stale-маркеры в контрактах (ADR-0010); обязателен в `/release-check`.

Wiring — в [`.claude/settings.json`](.claude/settings.json). Roadmap новых хуков — [`roadmap.md`](docs/roadmap.md).

### Skills

Глобально доступные skills из агентского плагина (`agent-skills:*`) — использовать в качестве методологии:
- `agent-skills:security-and-hardening` — обязательно при работе с `http.py`, `config_flow.py:logging`, `helpers.py:hash_password`, `fcm.py`, credentials/tokens;
- `agent-skills:test-driven-development` — при переписывании тестов config-flow;
- `agent-skills:code-review-and-quality` — независимым reviewer-ом clean committed candidate после tests/security prechecks/docs/history cleanup.

## Big changes — only with plan

Запрещены без плана:
- Полный переход entity на `CoordinatorEntity` (трогает 3 платформы);
- Замена `aiohttp.ClientSession` per-request на shared session (трогает API/HTTP);
- Перезапись `tests/` (полная пересборка test suite);
- Любые изменения crypto в `helpers.py` (auth ломается молча).

Для каждого — сначала ADR в [`docs/decisions/`](docs/decisions/README.md).

## Boundaries (повтор из AGENTS.md)

- **Always:** чтение, AIDD-документы, predposlozhenia с evidence.
- **Ask first:** правки `custom_components/**`, manifest/hacs, CI, удаления.
- **Never:** логирование токенов, force-push на master, `--no-verify`, fix-тестов под сломанное поведение.

## Memory

При обнаружении устойчивых паттернов проекта — записывать в `~/.claude/projects/-Users-gentslava-Developer-elektronny-gorod/memory/` (см. встроенный auto memory). Не дублировать сюда того, что уже есть в `docs/`.
