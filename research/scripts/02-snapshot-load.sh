#!/usr/bin/env bash
# 02-snapshot-load.sh
# Загружает baseline snapshot. Запускает emulator, если нужно.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"


if [[ ! -f "$BASELINE_META" ]]; then
    echo "❌ Baseline не найден ($BASELINE_META). Запусти ./research/scripts/01-baseline-setup.sh"
    exit 1
fi

# Проверка: запущен ли эмулятор
if ! adb devices | grep -q "emulator-"; then
    echo "→ Эмулятор не запущен. Запускаю с writable system..."
    emulator -avd "$AVD_NAME" -writable-system -no-snapshot-load >/tmp/emulator.log 2>&1 &
    EMULATOR_PID=$!
    echo "  emulator PID: $EMULATOR_PID (логи в /tmp/emulator.log)"

    echo "→ Ожидание boot completed..."
    adb wait-for-device
    adb shell 'while [[ -z $(getprop sys.boot_completed) ]]; do sleep 1; done'
    echo "✓ Device ready"
fi

echo "→ Loading snapshot '$BASELINE_SNAPSHOT'..."
adb emu avd snapshot load "$BASELINE_SNAPSHOT"
echo "✓ Snapshot loaded"

echo ""
echo "Метаданные baseline:"
cat "$BASELINE_META" | sed 's/^/  /'
