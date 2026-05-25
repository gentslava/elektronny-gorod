#!/usr/bin/env bash
# check-app-version.sh
# Сравнивает APP_VERSION в custom_components/.../const.py с версией свежей
# .apks в research/apk/. Если не совпадает — печатает блок для замены.
#
# Apktool M кладёт manifest.json внутрь .apks рядом с base.apk → достаточно
# unzip + jq. Не требует aapt / Android SDK / androguard.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_cmd unzip
require_cmd jq

APKS_GLOB="research/apk/myhome-*-original.apks"
# shellcheck disable=SC2086
APKS_FILE=$(ls -1 $APKS_GLOB 2>/dev/null | sort -V | tail -1 || true)

if [[ -z "${APKS_FILE:-}" ]]; then
    die "Не найден $APKS_GLOB. Скачай свежий .apks (Aurora Store / APKPure / APKMirror)."
fi

MANIFEST=$(unzip -p "$APKS_FILE" manifest.json 2>/dev/null || true)
if [[ -z "$MANIFEST" ]]; then
    die ".apks без manifest.json (формат не Apktool M). Используй aapt: aapt dump badging base.apk"
fi

APK_NAME=$(echo "$MANIFEST" | jq -r '.version_name')
APK_CODE=$(echo "$MANIFEST" | jq -r '.version_code')

CONST_FILE="custom_components/elektronny_gorod/const.py"
CONST_NAME=$(awk '/^APP_VERSION/,/^}/' "$CONST_FILE" | grep -oE '"[0-9]+\.[0-9]+\.[0-9]+"' | head -1 | tr -d '"')
CONST_CODE=$(awk '/^APP_VERSION/,/^}/' "$CONST_FILE" | grep -oE '"[0-9]{8,}"' | head -1 | tr -d '"')

echo "APK   $(basename "$APKS_FILE"): name=$APK_NAME code=$APK_CODE"
echo "const.py:                       name=$CONST_NAME code=$CONST_CODE"

if [[ "$APK_NAME" == "$CONST_NAME" && "$APK_CODE" == "$CONST_CODE" ]]; then
    echo "✓ APP_VERSION актуален."
    exit 0
fi

cat <<EOF

❌ APP_VERSION устарел. Замени в $CONST_FILE:

APP_VERSION: Final = {
    "name": "$APK_NAME",
    "code": "$APK_CODE"
}
EOF
exit 1
