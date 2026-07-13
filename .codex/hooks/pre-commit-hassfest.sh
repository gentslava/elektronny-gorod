#!/usr/bin/env bash
# Hook: pre-commit-hassfest.sh
# Запускает HA hassfest валидацию manifest.json локально перед commit.
# (Не подключён по умолчанию в settings.json — опционально активируется разработчиком.)
#
# Использование: добавить в settings.json PreToolUse matcher: Bash(git commit:*).

set -euo pipefail

if [[ ! -f custom_components/elektronny_gorod/manifest.json ]]; then
    exit 0
fi

# Простая локальная JSON-валидация (без полного hassfest, который требует HA core).
python3 -m json.tool custom_components/elektronny_gorod/manifest.json > /dev/null || {
    echo "❌ manifest.json is not valid JSON"
    exit 1
}

python3 -m json.tool hacs.json > /dev/null || {
    echo "❌ hacs.json is not valid JSON"
    exit 1
}

# Проверка обязательных полей manifest.json
python3 - <<'PY'
import json, sys
with open("custom_components/elektronny_gorod/manifest.json") as f:
    m = json.load(f)
required = ["domain", "name", "version", "codeowners", "documentation", "issue_tracker", "iot_class"]
missing = [k for k in required if k not in m]
if missing:
    print(f"❌ manifest.json missing required keys: {missing}")
    sys.exit(1)
PY

exit 0
