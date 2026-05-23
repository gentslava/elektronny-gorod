#!/usr/bin/env bash
# 00-patch-apk.sh
# Патчит APK через apk-mitm: отключает certificate pinning + добавляет user-cert trust.
# Запускается один раз на новую версию APK.
#
# См. ADR-0006 и docs/aidd/runbooks/har-collection.md.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_cmd apk-mitm


if [[ ! -f "$ORIGINAL_APK" ]]; then
    echo "❌ $ORIGINAL_APK не найден."
    echo "   Скачай APK вручную (apkmirror / apkpure) и положи как $ORIGINAL_APK."
    echo "   См. research/apk/README.md."
    exit 1
fi

if ! command -v apk-mitm &>/dev/null; then
    echo "❌ apk-mitm не установлен. Установка: npm install -g apk-mitm"
    exit 1
fi

echo "→ Patching $ORIGINAL_APK ..."
apk-mitm "$ORIGINAL_APK"

# apk-mitm создаёт <name>-patched.apk рядом с оригиналом
PATCHED_SUGGESTED="${ORIGINAL_APK%.apk}-patched.apk"

if [[ -f "$PATCHED_SUGGESTED" ]]; then
    mv "$PATCHED_SUGGESTED" "$PATCHED_APK"
    echo "✓ Patched APK: $PATCHED_APK"
else
    echo "❌ Ожидался $PATCHED_SUGGESTED, не найден. Проверь вывод apk-mitm выше."
    exit 1
fi

echo ""
echo "Дальше: ./research/scripts/01-baseline-setup.sh"
