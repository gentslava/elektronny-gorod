Status: Template
Owner: Lead Architect Agent
Last reviewed: 2026-08-11 (ADR-0015 reviewer matrix and publication evidence)

Source files:
- copied plan/task scope

Related docs:
- `plan.template.md`
- `../quality-gates.md`

Used by agents:
- implementers, reviewers, Validator Agent

Quality gates:
- PLAN_APPROVED
- IMPLEMENTATION_STEP_OK
- CANDIDATE_FROZEN
- REVIEW_OK

---

# Tasklist: <название>

- **Date:** <YYYY-MM-DD>
- **Owner:** @<user>
- **Linked plan:** `docs/features/<feature>/plan.md`
- **Plan revision / approval evidence:** <revision + link>
- **Execution mode:** subagent-driven (default) / explicit inline
- **Implementation owners:** @<agent-or-user> per slice
- **Independent reviewer:** @<agent-or-user>
- **HA review:** @<reviewer> / not required
- **Security review:** @<reviewer> / not required
- **QA review:** @<reviewer> / not required

## Tasks

> Каждая таска должна:
> - быть verifiable (тест / observable);
> - ссылаться на audit ID или slice из plan.md;
> - размер < 200 строк diff.

### Slice 1

- [ ] **T-001** Описание задачи. _Acceptance:_ ... _Evidence:_ ...
- [ ] **T-002** ...

### Slice 2

- [ ] **T-003** ...

## Зависимости

```text
T-001 ─► T-002
T-002 ─► T-003
```

## Estimation

Опционально. Если делаем — в часах или количестве PR.

| Task | Estimate |
|---|---|
| T-001 | 1h |
| T-002 | 30m |

## Progress

| Status | Count |
|---|---|
| done | 0 |
| in progress | 0 |
| pending | N |

## Quality gates

- `PLAN_APPROVED` — необходим перед началом.
- `IMPLEMENTATION_STEP_OK` — за каждую отдельную таску.
- `TESTS_PASS`, `SECURITY_PRECHECK_OK`, `DOCS_UPDATED`, `HISTORY_CLEAN` — до
  candidate freeze.
- `CANDIDATE_FROZEN`, `REVIEW_OK`, `SECURITY_OK` — перед обычным push /
  ready-for-review PR / merge.
- После любого candidate change все обязательные reviewers переиздают verdict
  для нового base/head/tree; глубина unchanged scope может быть delta-scoped.

## Next reading

- For the approved scope: `plan.md`
- For gate definitions: `../quality-gates.md`
