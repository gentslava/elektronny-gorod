# Example feature: Token redaction in logs

- **Status:** EXAMPLE — этот feature **не реализуется** в этой папке. Используется как образец заполнения.
- **Реальный hotfix** — будет в отдельной папке (`token-redaction/`) при выполнении Итерации 1 [`roadmap.md`](../../roadmap.md).

## Что внутри

| Файл | Описание |
|---|---|
| [`idea.md`](idea.md) | стартовая идея |
| [`prd.md`](prd.md) | требование |
| [`research.md`](research.md) | сверка с HA docs |
| [`plan.md`](plan.md) | план реализации |
| [`tasklist.md`](tasklist.md) | задачи |

## Связь

- ADR: [`0004-token-redaction`](../../decisions/0004-token-redaction.md)
- Audit: [`S-01..S-05, S-16`](../../audit/security.md)
- Roadmap: Итерация 1 в [`roadmap.md`](../../roadmap.md)

## Quality gates на момент завершения фичи (целевой)

- [x] SPEC_READY
- [ ] RESEARCH_DONE
- [ ] PLAN_APPROVED
- [ ] TESTS_PASS (после реализации)
- [ ] SECURITY_OK (главный gate этой фичи)
- [ ] DOCS_UPDATED
- [ ] READY_FOR_RELEASE
