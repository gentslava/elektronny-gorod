#!/usr/bin/env bash
# Hook: post-edit-redaction-check.sh
# Срабатывает после Edit / Write в custom_components/.
# Блокирует, если в файле есть прямое логирование sensitive ключей.
#
# Установка: автоматическая через .claude/settings.json (PostToolUse matcher: Edit|Write).
# См. также: docs/decisions/0004-token-redaction.md
# См. также: .claude/rules/no-secret-logs.md

set -uo pipefail

# Берём путь файла из аргументов Claude Code hook (передаётся как $1)
FILE="${1:-}"

# Триггер только на .py в custom_components/elektronny_gorod/
if [[ ! "$FILE" =~ custom_components/elektronny_gorod/.*\.py$ ]]; then
    exit 0
fi

if [[ ! -f "$FILE" ]]; then
    exit 0
fi

# Паттерн: прямое логирование sensitive значений.
# Маркер `# noqa: redaction-ok` явно отключает проверку с обоснованием.
PATTERN='LOGGER\.(debug|info|warning|error|exception|critical)\([^)]*(access_token|refresh_token|password|sms|headers|entry\.data|api_key|secret|Authorization)'

LEAKS=$(grep -nE "$PATTERN" "$FILE" | grep -v 'noqa: redaction-ok' || true)

if [[ -n "$LEAKS" ]]; then
    echo "❌ Direct secret logging detected in $FILE:"
    echo "$LEAKS"
    echo ""
    echo "→ Use redact() helper (см. _logging.py / ADR-0004) or remove the log."
    echo "→ Если ложное срабатывание — добавить '# noqa: redaction-ok <reason>' в конец строки."
    exit 1
fi

exit 0
