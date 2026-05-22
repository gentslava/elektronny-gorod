Status: Active
Owner: Documentation / AIDD Agent
Last reviewed: 2026-05-22

Source files:
- этот документ
- `../../.claude/settings.json`

Related docs:
- `skills.md`
- `multi-agent-workflow.md`
- `../../AGENTS.md`

Used by agents:
- Любой агент при выборе инструмента

Quality gates:
- AUDIT_DONE

---

# MCP & Tools map

Карта внешних инструментов, прав доступа, ограничений. Какой tool для какой задачи, и где границы.

## Принципы

1. **Минимально достаточные права.** Каждый инструмент работает только в нужной области.
2. **Read-only по умолчанию.** Write-операции требуют явного разрешения.
3. **Никаких секретов в инструментах.** API-ключи — в env, не в коде / промптах.
4. **Tool ≠ конечная истина.** Tool возвращает данные; интерпретация — на агенте.

## Built-in Claude Code tools

| Tool | Назначение | Используется в этом проекте |
|---|---|---|
| `Read` | чтение файлов | да, для всего |
| `Edit` | точечная правка | да, при подтверждении user |
| `Write` | создание/перезапись | да, при подтверждении user; не для `manifest.json`/`hacs.json` без согласования |
| `Bash` | выполнение shell-команд | да, read-only по умолчанию; write — с подтверждением |
| `Grep` | поиск по содержимому | да |
| `Glob` | поиск файлов по паттерну | да |
| `TodoWrite` | планирование задач | да, для нетривиальных задач |
| `Agent` | запуск subagent | да, для параллельной работы / отдельных ролей |
| `WebFetch` / `WebSearch` | внешняя информация | да, для проверки актуальности HA docs |
| `Skill` | вызов skill из плагина | да, по необходимости |

## Внешние MCP-серверы

### context7

| Поле | Значение |
|---|---|
| Назначение | актуальная документация библиотек (HA, aiohttp, etc.) |
| Когда использовать | работа с API, в котором нет уверенности; перед использованием новой фичи |
| Trust level | high (официальные docs) |
| Permissions | read-only |
| Запрет | не использовать для бизнес-логики и debugging |

Примеры:
- "HA DataUpdateCoordinator examples" → `mcp__context7__query-docs`
- "aiohttp BasicAuth usage" → context7 перед заменой ручного base64 в `camera.py`

### chrome-devtools-mcp

| Поле | Значение |
|---|---|
| Назначение | браузерная отладка / Lighthouse / screenshots |
| Когда использовать | не используется в этом проекте (UI integration test пока не плана) |
| Permissions | n/a |

### playwright

| Поле | Значение |
|---|---|
| Назначение | автоматизация браузера |
| Когда использовать | n/a |
| Permissions | n/a |

### claude_ai_Google_Drive

| Поле | Значение |
|---|---|
| Назначение | работа с Google Drive |
| Когда использовать | n/a — проект не связан с Drive |
| Permissions | n/a |

### pencil

| Поле | Значение |
|---|---|
| Назначение | .pen design files |
| Когда использовать | n/a — проект не имеет дизайн-файлов |
| Permissions | n/a |

## Запреты по умолчанию

| Tool / MCP | Запрет |
|---|---|
| `Bash` | `rm -rf`, `git push --force`, `git reset --hard`, `--no-verify` — только с явным approval |
| `Write` | `manifest.json` / `hacs.json` / `version` / `requirements` — обязательно ADR/spec до |
| Any MCP | передача `entry.data` / токенов вовне |
| `WebFetch` | загрузка external scripts для execution |
| browser MCP | автоматизация на чужих сайтах |

## Когда tool не доступен

Если задача требует инструмент, которого нет:
1. Зафиксировать в issue.
2. Не «угадывать» функционал из памяти LLM.
3. Если возможно — заменить чем-то существующим (например, `WebFetch` вместо отсутствующего `mcp__http-client`).

## Конфигурация

`.claude/settings.json` хранит allow-list разрешённых команд / MCP-серверов на уровне проекта.
Не коммитить `.claude/settings.local.json` (пользовательские настройки).

## Hooks

В Claude Code hooks — это shell-команды, привязанные к events.

Запланированные для этого проекта:
- `PreToolUse` для `Bash` — блокировать `rm -rf custom_components/`.
- `PostToolUse` для `Edit` / `Write` — `pre-commit-redaction-check.sh` для измененных `.py` файлов.

См. [`../../.claude/hooks/`](../../.claude/hooks/).

## Skills (повтор)

См. [`skills.md`](skills.md). Skills — не tools, но активируются явно в начале задачи.

## Безопасность

### Что НЕ передавать в tools

- `access_token`, `refresh_token`, headers с Bearer.
- `password`, SMS-код.
- `entry.data` целиком.
- Содержимое `.storage/core.config_entries` без redaction.

### Что МОЖНО

- `entry_id`, `account_id`, `place_id` (для отладки, если контекст требует).
- Имена файлов, классы, функции.
- Стек-трейсы (но не значения переменных в них, если те могут содержать secrets).

## Next reading

- For skills: `skills.md`
- For agents: `../../.claude/agents/`
- For settings: `../../.claude/settings.json`
- For hooks: `../../.claude/hooks/`
