# Review Report: <PR / commit>

- **Date:** <YYYY-MM-DD>
- **Reviewer:** code-reviewer agent / @<user>
- **Linked PR:** #N

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

- [ ] **Approve** — merge готов
- [ ] **Approve with comments** — merge после fix мелких findings
- [ ] **Changes requested** — нужны изменения
- [ ] **Block** — критичные проблемы (P0 utечка, regression)

## Связь с audit / findings

| Review finding | Audit ID (если есть) |
|---|---|
| ... | A-NN |

## Quality gate

`REVIEW_OK`
