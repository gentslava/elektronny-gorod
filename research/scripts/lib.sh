#!/usr/bin/env bash
# lib.sh
# Общая библиотека для всех скриптов research/scripts/.
# Подключается через `source research/scripts/lib.sh`.
#
# Порядок установки переменных (по приоритету, выше = выигрывает):
#   1. Уже установленные env-переменные (CI / shell export).
#   2. research/scripts/.env (optional override).
#   3. Built-in defaults (ниже в этом файле).
#
# Не запускать напрямую.

set -euo pipefail

# Resolve repo root (один уровень вверх от research/scripts/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# 1) Подгружаем .env, если существует
if [[ -f research/scripts/.env ]]; then
    # shellcheck disable=SC1091
    set -a
    source research/scripts/.env
    set +a
fi

# 2) Built-in defaults (применяются, если не заданы выше)
: "${AVD_NAME:=}"                                       # детектится autodetect-ом, см. 00a-detect.sh
: "${BASELINE_SNAPSHOT:=logged-in-baseline}"
: "${APP_PACKAGE:=}"                                    # детектится из APK
: "${APP_MAIN_ACTIVITY:=}"                              # детектится из APK
: "${ORIGINAL_APK:=research/apk/myhome-original.apk}"
: "${PATCHED_APK:=research/apk/myhome-patched.apk}"
: "${MITM_PORT:=8080}"
: "${MITM_DUMP_DIR:=research/api}"
: "${BASELINE_META:=research/scripts/.baseline-meta}"

# 3) Helpers

die() {
    echo "❌ $*" >&2
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Команда '$1' не найдена в \$PATH"
}

require_file() {
    [[ -f "$1" ]] || die "Файл не найден: $1"
}

require_var() {
    local name="$1"
    if [[ -z "${!name:-}" ]]; then
        die "Переменная $name не задана. Запусти ./research/scripts/00a-detect.sh"
    fi
}

# Доступно вызывающему скрипту
export REPO_ROOT
