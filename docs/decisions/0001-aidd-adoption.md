# ADR-0001: Принятие AIDD

- **Status:** accepted
- **Date:** 2026-05-22
- **Owner:** [@gentslava](https://github.com/gentslava) + Lead Architect Agent

## Context

Проект — Home Assistant custom integration, поддерживаемая одним codeowner-ом. Темп разработки умеренный (релизы примерно раз в месяц), но при этом:

- Растёт количество feature-веток (go2rtc auth, camera fixes).
- В коде накопились P0 utечки токенов в логи.
- Тесты — фиктивный stub из HA scaffold-а.
- Нет фиксированного процесса для AI-агентов, которые помогают вносить изменения.

Без структурированного процесса:
- Каждый новый агент тратит время на восстановление контекста.
- Решения теряются между PR.
- Security-утечки повторно появляются после рефакторинга.
- Документация рассинхронизируется с кодом.

## Decision

Принять методологию **AI-Driven Development (AIDD)** в полном объёме:

1. **Корневые контракты:** `AGENTS.md`, `CLAUDE.md`, `conventions.md`, `workflow.md`.
2. **`docs/` со структурой:**
   - `docs/index.md` — точка входа;
   - `docs/summary.md` — быстрый обзор;
   - `docs/roadmap.md` — план;
   - `docs/project/` — карта + source of truth;
   - `docs/architecture/` — архитектура + HA-compat + IQS;
   - `docs/audit/` — все findings + security;
   - `docs/testing/` — test plan;
   - `docs/aidd/` — агентская методология (gates, sources, contributing, prompts, mcp, skills, multi-agent);
   - `docs/decisions/` — ADR (этот каталог);
   - `docs/aidd/templates/` — шаблоны для повторяющихся артефактов;
   - `docs/aidd/runbooks/` — практические руководства;
   - `docs/features/<id>/` — feature-specific specs.
3. **`.claude/`:** agents, commands, rules, hooks, settings.
4. **`.cursor/rules/`** + **`.github/copilot-instructions.md`** — для Cursor/Copilot.

Структура — **тематические подпапки + lowercase имена** (а не плоский `docs/aidd/` с КАПС-именами, как в исходной AIDD-методологии). См. [`conventions.md`](../../conventions.md#documentation-expectations) для обоснования.

## Consequences

### Positive

- AI-агенты могут восстановить контекст за 15 минут (через `summary.md`).
- Findings не теряются: одно место — `docs/audit/project-audit.md`.
- Security-правила формализованы — pre-commit hook предотвратит повторные утечки.
- Roadmap привязан к audit ID; каждая задача имеет evidence.

### Negative

- Овер-инжиниринг для проекта с одним codeowner-ом.
- 25+ markdown-файлов требуют поддержки.
- Maintenance rules легко проигнорировать без CI-проверки.

### Mitigation

- Использовать `Last reviewed:` + регулярный re-audit раз в N месяцев.
- В Итерации 3 добавить pre-commit hook на synchronization (`docs/aidd/quality-gates.md`).

## Alternatives considered

1. **Минимальный AIDD MVP** (12 файлов). Отклонено — пользователь явно попросил Full AIDD.
2. **Без формального процесса.** Отклонено — повторяющиеся проблемы с security-utечками и потерей контекста.
3. **Использовать GitHub Wiki вместо `docs/`.** Отклонено — Wiki не версионируется вместе с кодом, не доступна агентам через файловую систему.

## Supersedes / Superseded by

— (первое ADR в проекте)

## Notes

Структура AIDD — не догма. Если станет ясно, что какой-то файл не приносит пользы — отдельный ADR на удаление.
