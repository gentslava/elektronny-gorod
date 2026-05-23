#!/usr/bin/env bash
# 06-wipe-app-data.sh
# Очищает data приложения. Для класса B (auth-сценарии).
#
# ВНИМАНИЕ: после wipe нужно заново пройти login на эмуляторе.
# Базовый snapshot (logged-in-baseline) при этом НЕ обновляется —
# он восстановит залогиненное состояние при следующем 02-snapshot-load.sh.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var APP_PACKAGE

echo "⚠️  Будет очищен data $APP_PACKAGE на эмуляторе."
echo "    Baseline snapshot НЕ затрагивается."
echo ""
read -p "Продолжить? [y/N] " ans
[[ "$ans" =~ ^[Yy]$ ]] || { echo "Отмена."; exit 0; }

adb shell pm clear "$APP_PACKAGE"
echo "✓ Data $APP_PACKAGE очищена."
echo ""
echo "Дальше: 03-app-start.sh → 04-capture-start.sh login-flow → manual login → 05-capture-stop.sh"
