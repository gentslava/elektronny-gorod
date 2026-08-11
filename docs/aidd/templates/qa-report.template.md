Status: Template
Owner: QA Agent
Last reviewed: 2026-08-11 (ADR-0015 immutable candidate evidence)

Source files:
- exact clean committed candidate and its tests

Related docs:
- `../quality-gates.md`
- `../multi-agent-workflow.md`

Used by agents:
- QA reviewers, Validator Agent

Quality gates:
- TESTS_PASS
- CANDIDATE_FROZEN
- REVIEW_OK

---

# QA Report: <feature / PR>

- **Date:** <YYYY-MM-DD>
- **Reviewer:** QA Agent / @<user>
- **Linked PR:** <#N | not created yet>
- **Linked plan:** <path | not created yet>
- **Base SHA:** <base>
- **Head SHA:** <head>
- **Tree SHA:** <tree>
- **Reviewer participated in implementation:** no
- **Verdict:** approve / changes requested / block

## Scope

Что тестировалось. Какие slices / файлы.

## Tests added / updated

| Файл | Что покрыто | Coverage delta |
|---|---|---|
| `tests/test_X.py` | happy path X | +N% |
| `tests/test_Y.py` | error paths Y | +M% |

## Test execution

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Краткий summary вывода (passed / failed / skipped).

## Coverage

- Total: X%
- Изменённые модули: см. таблицу выше.

## Findings

| ID | Severity | Что не работает | Where |
|---|---|---|---|
| F-001 | Critical / Important / Minor | ... | `file:line` |
| ... | ... | ... | ... |

`Critical` и `Important` всегда блокируют approval: нужен fix, новый frozen
candidate и повторный review. Отложить можно только `Minor`, явно записав
evidence, влияние и владельца follow-up; такое решение не должно требовать
изменения проверяемого candidate.

## Manual verification

(если применимо — например, для UI flow)

- [ ] Setup нового entry — happy path
- [ ] Reauth flow
- [ ] Options flow (go2rtc on/off)
- [ ] Open lock в реальном UI

## Quality gate

`TESTS_PASS` — pass / fail.

## Next reading

- For candidate invalidation: `../multi-agent-workflow.md`
- For gate definitions: `../quality-gates.md`
