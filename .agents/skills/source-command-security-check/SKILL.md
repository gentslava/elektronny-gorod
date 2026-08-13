---
name: "source-command-security-check"
description: "Проверка кода на утечки токенов, headers и других секретов в логи."
---

# source-command-security-check

Use this skill when the user asks to run the migrated source command `security-check`.

## Command Template

Ты — Security Auditor. Активируй skill `security-and-hardening`.

## Что проверять

Сначала запусти канонический deterministic scanner:

```bash
bash .codex/hooks/check-secret-logs.sh
```

Затем вручную проверь изменённый security-sensitive diff:

1. auth/token/credentials/headers/response-body не попали в logs, diagnostics, exception messages или Repairs placeholders;
2. новые HTTP-клиенты используют HA shared session;
3. новые redaction keys синхронизированы между `_logging.py` и `diagnostics.py`;
4. scanner не подменяет review: динамические aliases и third-party output оцениваются отдельно.

## Каждый finding

Для каждого случая в выводе:
1. Это **новая** проблема (нет в `docs/audit/security.md`)?
2. Если новая — предложить ID `S-NN`.
3. Severity (P0..P3).
4. Recommended fix + first step.

## Сравни с known findings

```bash
grep -E '^### S-' docs/audit/security.md
```

Существующие S-NN не дублируй.

## Output

```md
## Scan summary
- canonical scanner: pass/fail
- manual diff review: scope
- K новых findings

## New findings
- S-NN: description, file:line, severity, fix

## Cross-check
- existing relevant S-NN status unchanged/changed with evidence

## Recommendation
- next action: ...
```

## Constraints

- Read-only — никаких правок кода.
- Не ослаблять scanner ради зелёного результата.
- False positives явно отмечать с обоснованием.
