#!/usr/bin/env bash
# 07-auth-flow.sh <password|sms>
# Вводит постоянные auth-данные из gitignored research/scripts/auth.env
# в уже запущенное приложение на AVD. Значения не печатаются.
# SMS-код остаётся ручным одноразовым вводом и нигде не сохраняется.

set -euo pipefail

# shellcheck source=research/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

AUTH_ENV="research/scripts/auth.env"
SERIAL="${ADB_SERIAL:-emulator-5554}"
MODE="${1:-}"

[[ "$MODE" == "password" || "$MODE" == "sms" ]] || {
    echo "Usage: $0 <password|sms>" >&2
    exit 2
}

require_cmd adb
require_file "$AUTH_ENV"
require_var APP_PACKAGE
require_var APP_MAIN_ACTIVITY

set -a
# shellcheck disable=SC1090
source "$AUTH_ENV"
set +a

require_auth_var() {
    local name="$1"
    [[ -n "${!name:-}" ]] || die "$name не задан в $AUTH_ENV"
}

UI_XML=$(mktemp)
trap 'rm -f "$UI_XML"' EXIT

dump_ui() {
    adb -s "$SERIAL" shell uiautomator dump /sdcard/eg-auth-window.xml >/dev/null
    adb -s "$SERIAL" exec-out cat /sdcard/eg-auth-window.xml > "$UI_XML"
}

bounds_for() {
    local resource="$1"
    sed 's/></>\n</g' "$UI_XML" \
        | grep -m1 "resource-id=\"$APP_PACKAGE:id/$resource\"" \
        | sed -n -E \
            's/.*bounds="\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]".*/\1 \2 \3 \4/p'
}

has_resource() {
    local resource="$1"
    grep -q "resource-id=\"$APP_PACKAGE:id/$resource\"" "$UI_XML"
}

tap_resource() {
    local resource="$1" bounds x1 y1 x2 y2
    dump_ui
    bounds=$(bounds_for "$resource") || die "UI resource не найден: $resource"
    read -r x1 y1 x2 y2 <<< "$bounds"
    adb -s "$SERIAL" shell input tap "$(((x1 + x2) / 2))" "$(((y1 + y2) / 2))"
}

wait_resource() {
    local resource="$1" attempts="${2:-15}"
    local _
    for ((_=0; _<attempts; _++)); do
        dump_ui || true
        has_resource "$resource" && return 0
        sleep 1
    done
    die "Timeout waiting for UI resource: $resource"
}

type_resource() {
    local resource="$1" value="$2"
    tap_resource "$resource"
    adb -s "$SERIAL" shell input text "$value"
}

adb -s "$SERIAL" shell am start -n "$APP_PACKAGE/$APP_MAIN_ACTIVITY" >/dev/null
sleep 3
dump_ui
if has_resource skipButton; then
    tap_resource skipButton
    wait_resource inputEditText
fi

if [[ "$MODE" == "password" ]]; then
    require_auth_var AUTH_LOGIN
    require_auth_var AUTH_PASSWORD
    type_resource inputEditText "$AUTH_LOGIN"
    tap_resource loginButton
    wait_resource confirmButton
    type_resource inputEditText "$AUTH_PASSWORD"
    tap_resource confirmButton
    echo "Password auth submitted in $SERIAL."
    exit 0
fi

require_auth_var AUTH_PHONE
PHONE_DIGITS=$(printf '%s' "$AUTH_PHONE" | tr -cd '0-9')
[[ -n "$PHONE_DIGITS" ]] || die "AUTH_PHONE не содержит цифр"
type_resource inputEditText "$PHONE_DIGITS"
tap_resource loginButton

for _ in {1..15}; do
    dump_ui || true
    if has_resource codeInput; then
        echo "SMS code screen ready in $SERIAL; enter the one-time code directly in AVD."
        exit 0
    fi
    if has_resource addressListRecyclerView; then
        tap_resource addressListRecyclerView
        wait_resource codeInput
        echo "SMS code screen ready in $SERIAL; enter the one-time code directly in AVD."
        exit 0
    fi
    sleep 1
done

die "SMS code screen not reached"
