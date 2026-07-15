#!/usr/bin/env bash
# check-app-version.sh
# Сравнивает APP_VERSION в custom_components/.../const.py с версией свежей
# original APK/APKS в research/apk/. Если не совпадает — печатает блок замены.
#
# Поддерживает два APKS-варианта:
# - Apktool M archive с manifest.json (unzip + jq);
# - bundle, снятый через `adb shell pm path` (aapt по вложенному base.apk).

set -euo pipefail

# shellcheck source=research/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_cmd unzip

shopt -s nullglob
APK_CANDIDATES=(
    research/apk/myhome-*-original.apk
    research/apk/myhome-*-original.apks
)

if [[ ${#APK_CANDIDATES[@]} -eq 0 ]]; then
    die "Не найден research/apk/myhome-*-original.{apk,apks}."
fi

APK_FILE=$(printf '%s\n' "${APK_CANDIDATES[@]}" | sort -V | tail -1)
APK_NAME=""
APK_CODE=""

find_aapt() {
    if command -v aapt >/dev/null 2>&1; then
        command -v aapt
        return 0
    fi

    local sdk_root candidate
    for sdk_root in "${ANDROID_HOME:-}" "${ANDROID_SDK_ROOT:-}" "$HOME/Library/Android/sdk"; do
        [[ -d "$sdk_root/build-tools" ]] || continue
        candidate=$(find "$sdk_root/build-tools" -maxdepth 2 -type f -name aapt \
            2>/dev/null | sort -V | tail -1)
        if [[ -n "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

if [[ "$APK_FILE" == *.apks ]]; then
    MANIFEST=$(unzip -p "$APK_FILE" manifest.json 2>/dev/null || true)
else
    MANIFEST=""
fi

if [[ -n "$MANIFEST" ]]; then
    require_cmd jq
    APK_NAME=$(printf '%s' "$MANIFEST" | jq -r '.version_name')
    APK_CODE=$(printf '%s' "$MANIFEST" | jq -r '.version_code')
else
    AAPT=$(find_aapt) || die "Не найден aapt для чтения version из $APK_FILE."
    APK_TO_INSPECT="$APK_FILE"
    if [[ "$APK_FILE" == *.apks ]]; then
        TMP_DIR=$(mktemp -d)
        trap 'rm -rf "$TMP_DIR"' EXIT
        unzip -p "$APK_FILE" base.apk > "$TMP_DIR/base.apk"
        APK_TO_INSPECT="$TMP_DIR/base.apk"
    fi
    BADGING=$("$AAPT" dump badging "$APK_TO_INSPECT")
    APK_NAME=$(printf '%s\n' "$BADGING" | sed -n -E \
        "s/^package:.*versionName='([^']+)'.*/\\1/p" | head -1)
    APK_CODE=$(printf '%s\n' "$BADGING" | sed -n -E \
        "s/^package:.*versionCode='([^']+)'.*/\\1/p" | head -1)
fi

[[ -n "$APK_NAME" && -n "$APK_CODE" ]] || die "Не удалось прочитать version из $APK_FILE."

CONST_FILE="custom_components/elektronny_gorod/const.py"
CONST_NAME=$(awk '/^APP_VERSION/,/^}/' "$CONST_FILE" | grep -oE '"[0-9]+\.[0-9]+\.[0-9]+"' | head -1 | tr -d '"')
CONST_CODE=$(awk '/^APP_VERSION/,/^}/' "$CONST_FILE" | grep -oE '"[0-9]{8,}"' | head -1 | tr -d '"')

echo "APK   $(basename "$APK_FILE"): name=$APK_NAME code=$APK_CODE"
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
