---
name: "source-command-security-check"
description: "Проверка кода на утечки токенов, headers и других секретов в логи."
---

# source-command-security-check

Use this skill when the user asks to run the migrated source command `security-check`.

## Command Template

Ты — Security Auditor. Активируй skill `agent-skills:security-and-hardening`.

## Что проверять

Запусти команды поочерёдно и зафиксируй результаты:

```bash
# 1. Прямое логирование токенов / секретов
grep -rE 'LOGGER\..*(token|password|sms|headers|entry\.data|api_key|secret)' \
    custom_components/elektronny_gorod/

# 2. f-string в LOGGER (плохая практика + риск секретов)
grep -rE 'LOGGER\.[a-z]+\(f["'\'']' custom_components/elektronny_gorod/

# 3. Логирование response body
grep -rE '_log_response|response\.text\(\)' custom_components/elektronny_gorod/

# 4. Жёсткие конкретные классы / ключи (в Russian docs API)
grep -rE 'accessToken|refreshToken|Authorization' custom_components/elektronny_gorod/

# 5. Hardcoded secrets / API keys
grep -rE '["'\''][A-Za-z0-9+/]{20,}["'\'']' custom_components/elektronny_gorod/ | \
    grep -v 'test\|example'

# 6. ClientSession per-request (anti-pattern)
grep -rE 'ClientSession\(\)' custom_components/elektronny_gorod/
```

## Каждое совпадение

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
- N matches total
- M уже known
- K новых findings

## New findings
- S-NN: description, file:line, severity, fix

## Cross-check
- S-01..S-05 still present? (yes/no)
- S-16 still present? (yes/no)

## Recommendation
- next action: ...
```

## Constraints

- Read-only — никаких правок кода.
- Не «упрощать» grep — точный паттерн важен.
- Не игнорировать False Positives, если они вообще возможны: явно отметить «FP: ...» с обоснованием.
