# Tasklist: <название>

- **Date:** <YYYY-MM-DD>
- **Owner:** @<user>
- **Linked plan:** [`plan.md`](plan.md)

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
- `TESTS_PASS`, `SECURITY_OK`, `DOCS_UPDATED` — перед merge.
