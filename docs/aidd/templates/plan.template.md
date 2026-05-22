# Plan: <название>

- **Date:** <YYYY-MM-DD>
- **Owner:** @<user>
- **Linked PRD:** [`prd.md`](prd.md)
- **Linked research:** [`research.md`](research.md)

## High-level approach

3-7 предложений: как именно решаем.

## Vertical slices

Каждый slice — отдельный verifiable шаг (commit / PR).

### Slice 1: ...

- **Файлы:** `path/to/file.py`
- **Что меняется:** ...
- **Acceptance:** конкретный тест / observable.
- **Risk:** низкий / средний / высокий.

### Slice 2: ...

...

## Зависимости между slices

```text
Slice 1 ─┬─► Slice 2
         └─► Slice 3
Slice 2 ─► Slice 4
```

## Тесты

Какие тесты нужны для каждого slice. См. также [`docs/testing/strategy.md`](../../testing/strategy.md).

## Docs update

Какие AIDD-документы нужно обновить (см. [`maintenance rules`](../../project/project-map.md#maintenance-rules)).

## Migration plan

Если требуется. Иначе — раздел удалить.

## Rollback plan

Если применимо.

## Open questions

- [ ] ...

## Quality gate

`PLAN_APPROVED`
