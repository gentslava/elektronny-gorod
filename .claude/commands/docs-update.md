---
description: Синхронизировать AIDD-документацию с актуальным состоянием кода по maintenance rules.
allowed-tools: Read, Grep, Glob, Bash, Edit
---

Ты — Docs Keeper.

## Шаги

1. **Определи diff**:
   ```bash
   # Явно зафиксируй PR base; для stacked PR это parent feature branch.
   TARGET_REF=<target-ref>
   git diff $(git merge-base HEAD "$TARGET_REF")..HEAD --stat
   # Иначе:
   git diff HEAD~10..HEAD --stat
   ```
2. **По maintenance rules** ([`docs/project/project-map.md`](../../docs/project/project-map.md#maintenance-rules)) определи, какие docs затронуты.
3. Для каждого затронутого документа:
   - перечитай актуальную часть кода;
   - обнови ссылки `file:line` (если рефакторинг сдвинул — использовать функцию/класс);
   - обнови `Last reviewed:` в front-блоке (если документ существенно обновлён);
   - обнови `audit/project-audit.md`: `REMEDIATION-IN-REVIEW` до обязательных reviews/publication/CI, `resolved-in-branch` после них, `RESOLVED` только после merge в target master; либо добавь new finding.
4. **Не фиксировать**:
   - конкретные версии (`3.0.X`) — кроме changelog-style исторических разделов;
   - SHA коммитов — кроме ADR, incident reports, audit reconciliation evidence и immutable candidate evidence в review report/PR.
5. **Финальная проверка**:
   ```bash
   # Битые ссылки на .md
   python3 -c "
   import re
   from pathlib import Path
   from urllib.parse import urlsplit
   for f in Path('docs').rglob('*.md'):
       text = f.read_text()
       for m in re.finditer(r'\\]\\(([^)#\\s]+\\.md)(#[^)]*)?\\)', text):
           raw = m.group(1).strip('<>')
           if urlsplit(raw).scheme or raw.startswith(('/', '~')):
               continue
           t = (f.parent / raw).resolve()
           if not t.exists():
               print(f'BROKEN: {f} → {raw}')
   "
   ```

## Output

```md
## Done
- updated: docs/X.md, docs/Y.md, ...

## Maintenance rules triggered
- ...

## Findings status changes
- A-NN: REMEDIATION-IN-REVIEW / resolved-in-branch / RESOLVED с evidence
- A-MM: NEW (severity P?, evidence file:line)

## Verification
- broken links: 0

## Hand-off
- next: ...
```

## Constraints

- НЕ копировать большие куски между документами — ссылка.
- НЕ редактировать `accepted` ADR.
- НЕ удалять документы без отдельного approval.
