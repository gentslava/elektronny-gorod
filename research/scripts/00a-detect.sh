#!/usr/bin/env bash
# 00a-detect.sh
# Автодетект окружения: AVD_NAME, APP_PACKAGE, APP_MAIN_ACTIVITY.
# Пишет research/scripts/.env с обнаруженными значениями.
#
# Безопасно перезапускать. Если .env уже существует — спросит подтверждение overwrite.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"

cd "$REPO_ROOT"

ENV_FILE="research/scripts/.env"

# ---------- AVD detection ----------
require_cmd avdmanager

echo "→ Detecting AVDs..."
AVDS=$(avdmanager list avd 2>/dev/null | grep -E '^\s*Name:' | awk -F': ' '{print $2}')
AVD_COUNT=$(echo "$AVDS" | grep -c . || true)

DETECTED_AVD=""
if [[ "$AVD_COUNT" -eq 0 ]]; then
    die "Не найден ни один AVD. Создай через 'avdmanager create avd' или Android Studio."
elif [[ "$AVD_COUNT" -eq 1 ]]; then
    DETECTED_AVD="$AVDS"
    echo "  ✓ Один AVD: $DETECTED_AVD"
else
    echo "  Найдено несколько AVD:"
    echo "$AVDS" | sed 's/^/    - /'
    if [[ -n "${AVD_NAME:-}" ]] && echo "$AVDS" | grep -qFx "$AVD_NAME"; then
        DETECTED_AVD="$AVD_NAME"
        echo "  ✓ Использую существующий из .env: $DETECTED_AVD"
    else
        echo ""
        read -rp "  Введи имя AVD (точно как выше): " DETECTED_AVD
        echo "$AVDS" | grep -qFx "$DETECTED_AVD" || die "AVD '$DETECTED_AVD' не найден"
    fi
fi

# ---------- APK / app detection ----------
APK_FOR_DETECTION=""
if [[ -f "$PATCHED_APK" ]]; then
    APK_FOR_DETECTION="$PATCHED_APK"
elif [[ -f "$ORIGINAL_APK" ]]; then
    APK_FOR_DETECTION="$ORIGINAL_APK"
fi

DETECTED_PACKAGE=""
DETECTED_ACTIVITY=""
if [[ -n "$APK_FOR_DETECTION" ]]; then
    require_cmd aapt
    echo "→ Detecting package from $APK_FOR_DETECTION..."
    DETECTED_PACKAGE=$(aapt dump badging "$APK_FOR_DETECTION" 2>/dev/null | awk -F"'" '/package: name/{print $2}')
    DETECTED_ACTIVITY=$(aapt dump badging "$APK_FOR_DETECTION" 2>/dev/null | awk -F"'" '/launchable-activity: name/{print $2}')
    echo "  ✓ package: $DETECTED_PACKAGE"
    echo "  ✓ main activity: $DETECTED_ACTIVITY"
else
    echo "  ⚠️  APK не найден ($ORIGINAL_APK или $PATCHED_APK)."
    echo "     Положи APK и перезапусти этот скрипт для детекта package/activity."
fi

# ---------- Write .env ----------
if [[ -f "$ENV_FILE" ]]; then
    echo ""
    echo "$ENV_FILE уже существует. Текущее содержимое:"
    cat "$ENV_FILE" | sed 's/^/  /'
    echo ""
    read -rp "Перезаписать? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { echo "Не перезаписываю. Готово."; exit 0; }
fi

cat > "$ENV_FILE" <<EOF
# Автогенерирован 00a-detect.sh ($(date -u +%Y-%m-%dT%H:%M:%SZ))
# Можно редактировать вручную.

AVD_NAME=$DETECTED_AVD
BASELINE_SNAPSHOT=${BASELINE_SNAPSHOT}

APP_PACKAGE=${DETECTED_PACKAGE:-}
APP_MAIN_ACTIVITY=${DETECTED_ACTIVITY:-}

ORIGINAL_APK=${ORIGINAL_APK}
PATCHED_APK=${PATCHED_APK}

MITM_PORT=${MITM_PORT}
MITM_DUMP_DIR=${MITM_DUMP_DIR}

BASELINE_META=${BASELINE_META}
EOF

echo ""
echo "✓ Записан $ENV_FILE"
cat "$ENV_FILE" | sed 's/^/  /'

if [[ -z "${DETECTED_PACKAGE:-}" ]]; then
    echo ""
    echo "⚠️  APP_PACKAGE/APP_MAIN_ACTIVITY пустые — положи APK и перезапусти."
fi
