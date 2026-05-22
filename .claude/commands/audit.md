---
description: Провести глубокий аудит проекта elektronny-gorod (Lead Architect + параллельные subagents).
allowed-tools: Read, Grep, Glob, Bash, Agent, TodoWrite
---

Ты — Lead Architect. Проведи полный аудит проекта по методологии этого репозитория.

## Шаги

1. **Проверь git state.** Не пытайся работать на устаревшем snapshot — `git log --oneline -5`.
2. **Перечитай ключевые документы:**
   - `docs/index.md`
   - `docs/summary.md`
   - `docs/audit/project-audit.md`
   - `docs/audit/security.md`
3. **Параллельно запусти subagents** для независимых проверок:
   - `ha-expert` — manifest, config_flow, coordinator, entity, IQS.
   - `security-auditor` — utечки, headers, diagnostics.
   - `qa-engineer` — test plan vs реальные тесты, coverage.
4. **Сравни** результаты с предыдущим audit:
   - Что закрыто (RESOLVED)?
   - Что новое (новые A-NN)?
   - Что осталось неизменным?
5. **Обнови `docs/audit/project-audit.md`** с новыми findings.
6. **Обнови `docs/audit/security.md`** если есть security изменения.
7. **Обнови `docs/summary.md`** — главные риски / прогресс.
8. **Не правь код** — только аудит.

## Output

```md
## Audit summary
- что нового / что закрылось
- общий статус P0 / P1 / P2 / P3

## Updated documents
- docs/audit/project-audit.md
- docs/audit/security.md
- docs/summary.md

## Recommended next actions
- 3-5 пунктов priority order
```

## Constraints

- Не модифицировать `custom_components/*` без отдельного approval.
- Не закрывать findings без evidence.
- Не фиксировать версии в тексте (см. conventions.md).
