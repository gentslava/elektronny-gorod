# Gate Check: <GATE_NAME>

- **Date:** <YYYY-MM-DD>
- **Owner:** Validator Agent / @<user>
- **Linked PR / context:** #N

## Gate

Какой gate проверяется. См. [`quality-gates.md`](../quality-gates.md).

## Required evidence

Согласно описанию gate.

| Требование | Statu | Evidence |
|---|---|---|
| ... | ✅/❌ | `path:line` / команда / ссылка |

## Required commands

```bash
pytest tests/ -v
ruff check .
hassfest
```

Их вывод (или ссылка на CI run).

## Pass / Fail

- [ ] **Pass** — все требования выполнены.
- [ ] **Fail** — что не выполнено и почему.

### Если Fail

- Какие действия нужны для прохождения.
- К кому/чему вернуться (skill, agent, документ).

## Связь с roadmap / audit

- Audit ID, которые этот gate касается: A-NN, ...

## Quality gate

`<GATE_NAME>` — pass / fail.
