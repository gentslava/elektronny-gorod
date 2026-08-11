Status: Template
Owner: Lead Architect Agent
Last reviewed: 2026-08-11 (ADR-0015 approval, review and publication lifecycle)

Source files:
- approved spec / research for the copied plan

Related docs:
- `../quality-gates.md`
- `../multi-agent-workflow.md`

Used by agents:
- Lead Architect, implementers, reviewers

Quality gates:
- PLAN_APPROVED
- CANDIDATE_FROZEN
- REVIEW_OK

---

# Plan: <название>

- **Date:** <YYYY-MM-DD>
- **Owner:** @<user>
- **Linked PRD:** `docs/features/<feature>/prd.md`
- **Linked research:** `docs/features/<feature>/research.md`
- **Plan revision:** <commit SHA or immutable revision ID>
- **Approved by / at:** @<approver>, <timestamp>
- **Approval evidence:** <conversation / issue / review link>

## High-level approach

3-7 предложений: как именно решаем.

## Execution mode and reviewer matrix

- **Execution mode:** subagent-driven (default when available) / explicit inline.
- **Implementation owners:** concrete @<agent-or-user> per independent slice.
- **Independent code review:** concrete @<reviewer>, не участвовавший в implementation.
- **HA review:** @<reviewer> / not required, с причиной.
- **Security review:** @<reviewer> / not required, с причиной.
- **QA review:** @<reviewer> / not required, с причиной.

Короткое подтверждение пользователя после рекомендации («го», «да», «начинай»)
принимает mode и закрывает `PLAN_APPROVED` только как прямой ответ на этот полный
план. Записать approver/date/revision/evidence. Self-review не закрывает
`REVIEW_OK`.

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

## Candidate freeze and independent review

- [ ] Завершить `TESTS_PASS`, `SECURITY_PRECHECK_OK`, `DOCS_UPDATED` и
  `HISTORY_CLEAN`; создать clean committed candidate.
- [ ] Записать merge-base/head/tree SHA и пустой `git status --short`.
- [ ] Перед обычным push / ready-for-review PR / merge передать exact candidate
  независимому code-reviewer.
- [ ] Запустить read-only HA/security/QA reviews из reviewer matrix; независимый
  security reviewer закрывает `SECURITY_OK` только для frozen candidate.
- [ ] Исправить и повторно проверить все Critical/Important findings.
- [ ] После fixes повторить gates/freeze и получить candidate-bound
  re-attestation каждого обязательного reviewer-а; unchanged scope может быть
  проверен delta-scoped.
- [ ] Сохранить reviewer identity/independence/SHA evidence для `REVIEW_OK`.

## Migration plan

Если требуется. Иначе — раздел удалить.

## Rollback plan

Если применимо.

## Open questions

- [ ] ...

## Quality gate

`PLAN_APPROVED`

## Next reading

- For execution roles: `../multi-agent-workflow.md`
- For gate definitions: `../quality-gates.md`
