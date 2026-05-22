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

## Про «битые» ссылки внутри шаблонов

Шаблоны содержат ссылки вида `[idea.md](idea.md)` / `[prd.md](prd.md)` / `[plan.md](plan.md)`. **В папке `templates/` эти ссылки заведомо «битые»** — соответствующих файлов рядом нет.

Это **by design**: после копирования шаблона в `docs/features/<id>/` рядом окажутся реальные `idea.md`, `prd.md`, ... и все ссылки начнут работать. Образец — в [`../../features/example/`](../../features/example/).

При автоматической проверке link-validator-ом эти 6 ссылок ожидаемо помечаются как broken — это исключение из правила.
