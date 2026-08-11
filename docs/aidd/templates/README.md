Status: Active
Owner: Documentation / AIDD Agent
Last reviewed: 2026-08-11 (placeholder paths made link-validator safe)

Source files:
- `*.template.md` in this directory

Related docs:
- `../quality-gates.md`
- `../../features/example/`

Used by agents:
- planners, implementers, reviewers

Quality gates:
- DOCS_UPDATED

---

# Templates

Шаблоны для повторяющихся артефактов проекта. Используются человеком и AI-агентами.

## Список

| Шаблон | Когда |
|---|---|
| [`idea.template.md`](idea.template.md) | первая фиксация идеи / feature request |
| [`prd.template.md`](prd.template.md) | требование к новой фиче |
| [`research.template.md`](research.template.md) | research-фаза перед реализацией |
| [`plan.template.md`](plan.template.md) | план реализации |
| [`tasklist.template.md`](tasklist.template.md) | разбивка плана на задачи |
| [`qa-report.template.md`](qa-report.template.md) | отчёт после QA-фазы |
| [`review-report.template.md`](review-report.template.md) | code review результат |
| [`adr.template.md`](adr.template.md) | architecture decision record |
| [`gate-check.template.md`](gate-check.template.md) | проверка прохождения quality gate |

## Принципы

- Шаблон — стартовая точка, не догма. Удаляйте секции, которые не применимы.
- Не редактируйте сами шаблоны для конкретной задачи — копируйте в `docs/features/<id>/` и заполняйте там.
- В commit message — ссылка на скопированный документ, а не на шаблон.

## Placeholder paths внутри шаблонов

Связанные артефакты записаны как literal paths вида
`docs/features/<feature>/prd.md`. После копирования шаблона замени `<feature>`
на реальный каталог и при желании преврати path в Markdown link. Так сами
templates остаются совместимы с link-validator без специальных исключений.
Готовый образец — в [`../../features/example/`](../../features/example/).
