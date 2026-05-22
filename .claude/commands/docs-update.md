---
description: Синхронизировать AIDD-документацию с актуальным состоянием кода по maintenance rules.
allowed-tools: Read, Grep, Glob, Bash, Edit
---

Ты — Docs Keeper.

## Шаги

1. **Определи diff**:
   ```bash
   # Если на ветке с PR:
   git diff $(git merge-base HEAD master)..HEAD --stat
   # Иначе:
   git diff HEAD~10..HEAD --stat
   ```
2. **По maintenance rules** ([`docs/project/project-map.md`](../../docs/project/project-map.md#maintenance-rules)) определи, какие docs затронуты.
3. Для каждого затронутого документа:
   - перечитай актуальную часть кода;
   - обнови ссылки `file:line` (если рефакторинг сдвинул — использовать функцию/класс);
   - обнови `Last reviewed:` в front-блоке (если документ существенно обновлён);
   - обнови `audit/project-audit.md` (RESOLVED / new finding).
4. **Не фиксировать**:
   - конкретные версии (`3.0.X`) — кроме changelog-style исторических разделов;
   - SHA коммитов — кроме ADR и incident reports.
5. **Финальная проверка**:
   ```bash
   # Битые ссылки на .md
   python3 -c "
   import re
   from pathlib import Path
   for f in Path('docs').rglob('*.md'):
       text = f.read_text()
       for m in re.finditer(r'\\]\\(([^)#\\s]+\\.md)(#[^)]*)?\\)', text):
           t = (f.parent / m.group(1)).resolve()
           if not t.exists():
               print(f'BROKEN: {f} → {m.group(1)}')
   "
   ```

## Output

```md
## Done
- updated: docs/X.md, docs/Y.md, ...

## Maintenance rules triggered
- ...

## Findings status changes
- A-NN: RESOLVED (см. <PR/commit>)
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
