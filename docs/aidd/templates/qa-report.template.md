# QA Report: <feature / PR>

- **Date:** <YYYY-MM-DD>
- **Owner:** QA Agent / @<user>
- **Linked PR:** #N
- **Linked plan:** [`plan.md`](plan.md)

## Scope

Что тестировалось. Какие slices / файлы.

## Tests added / updated

| Файл | Что покрыто | Coverage delta |
|---|---|---|
| `tests/test_X.py` | happy path X | +N% |
| `tests/test_Y.py` | error paths Y | +M% |

## Test execution

```bash
$ pytest tests/ -v
```

Краткий summary вывода (passed / failed / skipped).

## Coverage

- Total: X%
- Изменённые модули: см. таблицу выше.

## Findings

| ID | Severity | Что не работает | Where |
|---|---|---|---|
| F-001 | P1 | ... | `file:line` |
| ... | ... | ... | ... |

Если findings есть — таска не считается завершённой; либо фикс, либо явное «accepted as future work».

## Manual verification

(если применимо — например, для UI flow)

- [ ] Setup нового entry — happy path
- [ ] Reauth flow
- [ ] Options flow (go2rtc on/off)
- [ ] Open lock в реальном UI

## Quality gate

`TESTS_PASS` — pass / fail.
