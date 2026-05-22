# Features

Каталог feature-specific документации. Каждая значимая фича получает свою папку `<feature-id>/` с idea / PRD / research / plan / tasklist / reports.

## Структура

```
docs/features/
├── README.md                              ← этот файл
├── example/                               ← образец, не настоящая фича
│   ├── README.md
│   ├── idea.md
│   ├── prd.md
│   ├── research.md
│   ├── plan.md
│   └── tasklist.md
└── <feature-id>/                          ← реальные фичи (создаются по мере появления)
```

## Когда заводить feature folder

- Любое изменение, требующее PRD (см. [`workflow.md`](../../workflow.md)).
- Любая фича с множеством vertical slices.
- Любое изменение public API (config flow, entity types).
- Migration версии config-entry.

## Когда **не** заводить

- Bug fix с очевидным root cause (одна строка → commit + ссылка на audit ID).
- Опечатка / документация.
- Косметический рефакторинг.

## Naming

`<short-kebab-id>` — например:
- `coordinator-pattern` (для реализации [ADR-0002](../decisions/0002-coordinator-pattern.md))
- `token-redaction` (для S-01..S-05 hotfix)
- `lock-to-button` (для [ADR-0005](../decisions/0005-lock-vs-button.md))

## Жизненный цикл

1. **Idea** (`idea.md`) → discussion → принять или отклонить.
2. **PRD** (`prd.md`) → approval owner.
3. **Research** (`research.md`) → опционально, если требуется внешняя сверка.
4. **Plan** (`plan.md`) → vertical slices.
5. **Tasklist** (`tasklist.md`) → конкретные задачи.
6. **Implementation** (через PR-ы).
7. **QA report** (`qa-report.md`).
8. **Review report** (`review-report.md`).
9. **Done**: переместить feature folder в `archive/` или пометить status в README фичи.

Шаблоны — в [`docs/aidd/templates/`](../aidd/templates/).
