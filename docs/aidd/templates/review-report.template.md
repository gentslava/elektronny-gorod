Status: Template Owner: Code Reviewer Agent Last reviewed: 2026-08-11 (ADR-0015 immutable candidate evidence)

Source files:
- exact clean committed candidate

Related docs:
- `../quality-gates.md`
- `../multi-agent-workflow.md`

Used by agents:
- code/HA/security/QA reviewers, Validator Agent

Quality gates:
- CANDIDATE_FROZEN
- REVIEW_OK

---

# Review Report: <PR / commit>

- **Date:** <YYYY-MM-DD>
- **Reviewer:** code-reviewer agent / @<user>
- **Linked PR:** #N / not created yet
- **Base SHA:** <base>
- **Head SHA:** <head>
- **Tree SHA:** <tree>
- **Reviewer participated in implementation:** no
- **Review scope:** code / HA / security / QA

## Scope

Краткое описание diff. Какие файлы и зачем.

## Review по 5 осям

### 1. Correctness

- [ ] функция делает то, что описано
- [ ] edge cases покрыты
- [ ] нет тихих failures

**Findings:**
- ...

### 2. Readability

- [ ] naming понятен
- [ ] комментарии объясняют WHY (не WHAT)
- [ ] нет dead code

**Findings:**
- ...

### 3. Architecture

- [ ] соответствует паттернам проекта (см. [`overview.md`](../../architecture/overview.md))
- [ ] нет cycles
- [ ] нет god functions / god classes

**Findings:**
- ...

### 4. Security

- [ ] нет логирования токенов / headers / passwords
- [ ] нет hardcoded secrets
- [ ] input validation на границах
- [ ] redaction на diagnostics

**Findings:**
- ...

### 5. Performance

- [ ] нет blocking I/O в event loop
- [ ] нет дублирующих запросов
- [ ] нет утечек ресурсов (ClientSession, listeners)

**Findings:**
- ...

## Решение

- [ ] **Approve** — этот review scope закрыт для указанного candidate
- [ ] **Approve with optional comments** — scope одобрен; комментарии не требуют изменения candidate. Если рекомендация принята, нужен новый freeze/re-review
- [ ] **Changes requested** — нужны изменения
- [ ] **Block** — критичные проблемы (P0 utечка, regression)

## Связь с audit / findings

| Review finding | Audit ID (если есть) |
|---|---|
| ... | A-NN |

## Quality gate

`REVIEW_OK` только если reviewer независим и все Critical/Important findings закрыты и перепроверены на том же base/head/tree. Любой новый содержательный commit делает verdict stale; каждый обязательный reviewer переиздаёт verdict для нового tuple, хотя unchanged scope может быть проверен delta-scoped. Scoped approval сам по себе не означает merge-ready.

## Next reading

- For remaining merge gates: `../quality-gates.md`
- For candidate invalidation: `../multi-agent-workflow.md`
