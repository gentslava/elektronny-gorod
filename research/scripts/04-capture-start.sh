#!/usr/bin/env bash
# 04-capture-start.sh <scenario-name>
# Запускает mitmdump в фоне и пишет дамп в research/api/<date>-<scenario>.flow.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_cmd mitmdump

SCENARIO="${1:-}"
if [[ -z "$SCENARIO" ]]; then
    echo "Usage: $0 <scenario-name>"
    echo "  Например: $0 home-screen-refresh"
    exit 1
fi

# Валидация имени сценария (kebab-case)
if [[ ! "$SCENARIO" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "❌ Имя сценария должно быть kebab-case (a-z, 0-9, '-'). Получено: $SCENARIO"
    exit 1
fi

# Проверка, что mitmdump не запущен уже
if pgrep -f 'mitmdump.*'"$MITM_PORT" >/dev/null; then
    echo "❌ mitmdump уже запущен на порту $MITM_PORT. Останови через 05-capture-stop.sh."
    exit 1
fi

mkdir -p "$MITM_DUMP_DIR"
DATE=$(date +%Y-%m-%d)
FLOW_FILE="$MITM_DUMP_DIR/$DATE-$SCENARIO.flow"
PID_FILE="$MITM_DUMP_DIR/.$DATE-$SCENARIO.pid"

if [[ -f "$FLOW_FILE" ]]; then
    echo "⚠️  $FLOW_FILE уже существует. Будет перезаписан."
fi

echo "→ Старт mitmdump → $FLOW_FILE"
nohup mitmdump -p "$MITM_PORT" -w "$FLOW_FILE" >/tmp/mitmdump.log 2>&1 &
echo $! > "$PID_FILE"

# Дать mitmdump время подняться
sleep 1
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "❌ mitmdump не стартовал. Логи: /tmp/mitmdump.log"
    cat /tmp/mitmdump.log
    rm -f "$PID_FILE"
    exit 1
fi

echo "✓ mitmdump PID $(cat "$PID_FILE") пишет в $FLOW_FILE"
echo ""
echo "Теперь выполни сценарий '$SCENARIO' в приложении."
echo "Когда закончил — ./research/scripts/05-capture-stop.sh $SCENARIO"
