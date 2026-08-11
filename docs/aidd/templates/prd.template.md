Status: Template
Owner: Product / Architecture Agent
Last reviewed: 2026-08-11 (ADR-0015 plan approval contract)

---

# PRD: <название фичи>

- **Date:** <YYYY-MM-DD>
- **Owner:** @<user>
- **Status:** Draft / Review / Approved / Implemented / Cancelled
- **Linked idea:** `docs/features/<feature>/idea.md`

## Problem

Что не работает / какая боль у пользователя. С evidence: issue ID, отзыв, baseline-метрика.

## Users / use cases

Кто и в каком контексте использует это? 1-3 ключевых сценария:

1. ...
2. ...

## Goals

1. ...
2. ...

## Non-goals

(что **не** делаем в рамках этой фичи)

## Solution

Высокоуровневое описание. Без deep technical detail — это в `plan.md`.

## Acceptance criteria

- [ ] критерий 1 (verifiable)
- [ ] критерий 2
- ...

## Затронутые модули

- `custom_components/elektronny_gorod/<file>.py`
- ...

## Влияние на existing entries

- Migration нужна? Какая VERSION?
- Breaking change? Какой?

## Влияние на HA QS

- Помогает достичь Bronze / Silver / Gold?
- Какие правила?

## Открытые вопросы

- [ ] ...

## Quality gate

`SPEC_READY` → требуется approval от @gentslava
