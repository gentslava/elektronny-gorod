# Tasklist: Token redaction in logs

- **Date:** 2026-05-22
- **Owner:** Security & Privacy Agent
- **Linked plan:** [`plan.md`](plan.md)

## Tasks

### Slice 1 — `_logging.py`

- [ ] **T-001** Создать `custom_components/elektronny_gorod/_logging.py` с `SENSITIVE_KEYS` (frozenset) и `redact(value)`. _Acceptance:_ модуль импортируется без ошибок. _Audit:_ S-01..S-05 (helper).
- [ ] **T-002** `tests/test_logging_redact.py`: тест dict/list/nested/non-dict. _Acceptance:_ pytest зелёный.

### Slice 2 — `http.py` redaction

- [ ] **T-003** `_log_request`: заменить логирование `headers` на `redact(headers)`; для auth-paths (`/auth/v2/`, `/auth/v3/`) не логировать `data` вовсе. _Acceptance:_ grep на staged diff не находит `LOGGER\.\w+\(.*headers=`. _Audit:_ S-02.
- [ ] **T-004** `_log_response`: для auth-paths логировать только status + длину; для остальных — полное body (как сейчас). _Acceptance:_ unit test проверяет, что для `/auth/v3/...` body не появляется в caplog. _Audit:_ S-03.

### Slice 3 — `config_flow.py`

- [ ] **T-005** Удалить строку `LOGGER.debug("Access token is %s", self.access_token)` ([`config_flow.py:77`](../../../custom_components/elektronny_gorod/config_flow.py#L77)). _Audit:_ S-01.
- [ ] **T-006** Заменить `entry.data` на `entry.entry_id` ([`config_flow.py:283,291`](../../../custom_components/elektronny_gorod/config_flow.py#L283)). _Audit:_ S-04.
- [ ] **T-007** Обезличить `LOGGER.debug("Selected contract is %s. Contract object is %s", ...)` ([`config_flow.py:201`](../../../custom_components/elektronny_gorod/config_flow.py#L201)) — оставить только `selected_id`. _Audit:_ S-06.

### Slice 4 — `diagnostics.py`

- [ ] **T-008** Создать `custom_components/elektronny_gorod/diagnostics.py` с `async_get_config_entry_diagnostics`, используя `homeassistant.components.diagnostics.async_redact_data` + `TO_REDACT = SENSITIVE_KEYS` (+ `go2rtc_password`/`go2rtc_username`). _Audit:_ S-08, S-16.
- [ ] **T-009** `tests/test_diagnostics.py`: проверка, что результат содержит `**REDACTED**` для каждого sensitive ключа.

### Slice 5 — Pre-commit hook

- [ ] **T-010** Создать `.claude/hooks/pre-commit-redaction-check.sh` (см. [ADR-0004](../../decisions/0004-token-redaction.md)).
- [ ] **T-011** Зарегистрировать hook в `.claude/settings.json` для events `PreToolUse: Bash(git commit:*)` или эквивалентного.
- [ ] **T-012** Ручной dry-run: создать локальный коммит с заведомой утечкой → hook блокирует.

### Финал

- [ ] **T-013** Обновить docs: `audit/security.md` (S-01..S-05, S-16 → RESOLVED), `audit/project-audit.md` (A-01..A-04 → RESOLVED), `roadmap.md` (Итерация 1 — частично).
- [ ] **T-014** Создать `CHANGELOG.md` (если ещё нет) с записью «security: redact tokens in logs».
- [ ] **T-015** Создать GitHub Release с patch-bump.

## Зависимости

```text
T-001 ─► T-002 (test)
T-001 ─► T-003 ─► T-004 (зависит от helper)
T-001 ─► T-005..T-007 (правки config_flow)
T-001 ─► T-008 ─► T-009 (diagnostics)
T-010..T-012 (hook) ◄── независим
T-013..T-015 (финал) ◄── только после всех остальных
```

## Estimation

| Task | Estimate |
|---|---|
| T-001..T-002 | 30m |
| T-003..T-004 | 1h |
| T-005..T-007 | 15m |
| T-008..T-009 | 45m |
| T-010..T-012 | 30m |
| T-013..T-015 | 30m |
| **Всего** | ~3.5h |

## Progress

| Status | Count |
|---|---|
| done | 0 |
| in progress | 0 |
| pending | 15 |

## Quality gates

- `PLAN_APPROVED` ✅
- `IMPLEMENTATION_STEP_OK` — за каждую таску
- `TESTS_PASS` — перед merge
- `SECURITY_OK` — главное для этой фичи
- `DOCS_UPDATED` — T-013
- `READY_FOR_RELEASE` — после всех 15
