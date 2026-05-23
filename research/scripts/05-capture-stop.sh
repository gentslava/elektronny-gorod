#!/usr/bin/env bash
# 05-capture-stop.sh <scenario-name>
# Останавливает mitmdump, конвертирует .flow → .har, валидирует.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_cmd mitmdump

SCENARIO="${1:-}"
if [[ -z "$SCENARIO" ]]; then
    echo "Usage: $0 <scenario-name>"
    exit 1
fi

DATE=$(date +%Y-%m-%d)
FLOW_FILE="$MITM_DUMP_DIR/$DATE-$SCENARIO.flow"
HAR_FILE="$MITM_DUMP_DIR/$DATE-$SCENARIO.har"
PID_FILE="$MITM_DUMP_DIR/.$DATE-$SCENARIO.pid"

if [[ ! -f "$PID_FILE" ]]; then
    echo "❌ PID-файл не найден ($PID_FILE). Возможно capture не был запущен."
    exit 1
fi

PID=$(cat "$PID_FILE")
echo "→ Останавливаю mitmdump (PID $PID)..."
kill "$PID" 2>/dev/null || echo "  процесс уже завершён"
rm -f "$PID_FILE"

# mitmdump должен записать .flow до завершения
sleep 1

if [[ ! -f "$FLOW_FILE" ]]; then
    echo "❌ $FLOW_FILE не создан. Capture не зафиксировал ни одного запроса?"
    exit 1
fi

FLOW_SIZE=$(stat -f%z "$FLOW_FILE" 2>/dev/null || stat -c%s "$FLOW_FILE")
echo "✓ Flow file: $FLOW_FILE ($FLOW_SIZE bytes)"

if [[ "$FLOW_SIZE" -lt 100 ]]; then
    echo "⚠️  Flow file подозрительно мал. Скорее всего capture не поймал трафик."
    echo "    Проверь, что proxy настроен (adb shell settings get global http_proxy)."
fi

echo "→ Конвертация в HAR..."
mitmdump -nr "$FLOW_FILE" --set hardump="$HAR_FILE"

if [[ -f "$HAR_FILE" ]]; then
    HAR_SIZE=$(stat -f%z "$HAR_FILE" 2>/dev/null || stat -c%s "$HAR_FILE")
    ENTRIES=$(jq '.log.entries | length' "$HAR_FILE" 2>/dev/null || echo "?")
    echo "✓ HAR: $HAR_FILE ($HAR_SIZE bytes, $ENTRIES entries)"
else
    echo "❌ HAR не создан. Проверь, есть ли в .flow реальные запросы."
    exit 1
fi

# Quick smoke: показываем уникальные хосты
echo ""
echo "Уникальные хосты в HAR:"
jq -r '.log.entries[].request.url' "$HAR_FILE" 2>/dev/null | awk -F/ '{print $3}' | sort -u | sed 's/^/  /' || true

echo ""
echo "Дальше: передай $HAR_FILE агенту reverse-engineer для анализа."
echo "       (HAR не коммитится автоматически — .gitignore блокирует.)"
