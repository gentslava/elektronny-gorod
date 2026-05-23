#!/usr/bin/env bash
# 03-app-start.sh
# Запускает приложение на эмуляторе.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_var APP_PACKAGE
require_var APP_MAIN_ACTIVITY

echo "→ Forcing stop $APP_PACKAGE (если запущено)..."
adb shell am force-stop "$APP_PACKAGE" || true

echo "→ Запуск $APP_PACKAGE/$APP_MAIN_ACTIVITY..."
adb shell am start -n "$APP_PACKAGE/$APP_MAIN_ACTIVITY"

echo "✓ App started. Дальше: 04-capture-start.sh"
