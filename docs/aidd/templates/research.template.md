Status: Template Owner: Research Agent Last reviewed: 2026-08-11 (standard metadata and link-safe placeholder paths)

Source files:
- evidence listed in the copied research document

Related docs:
- `../source-base.md`
- `../quality-gates.md`

Used by agents:
- Research Agent, Lead Architect Agent

Quality gates:
- RESEARCH_COMPLETE
- PLAN_APPROVED

---

# Research: <название>

- **Date:** <YYYY-MM-DD>
- **Owner:** @<user> / Research Agent
- **Linked PRD:** `docs/features/<feature>/prd.md`

## Вопрос исследования

Что хотим узнать перед тем, как начать строить?

## Источники

Использовать Context7 / WebFetch для актуальной документации.

| Источник | Trust | Что взято |
|---|---|---|
| HA developer docs / <link> | high | ... |
| HACS docs / <link> | high | ... |
| Похожая интеграция / <link> | medium | ... |

См. также [`docs/aidd/source-base.md`](../source-base.md).

## Что нашли

Структурированно. С цитатами / ссылками.

1. ...
2. ...

## Применимо к нашему проекту?

- Что подходит как-есть.
- Что требует адаптации.
- Что не подходит и почему.

## Risk / unknowns

- [ ] ...

## Рекомендация

Что делать дальше. Не «улучшить архитектуру», а конкретно:
- использовать паттерн X из ссылки Y;
- переписать модуль Z по схеме W.

## Quality gate

`RESEARCH_DONE`
