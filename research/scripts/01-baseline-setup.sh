#!/usr/bin/env bash
# 01-baseline-setup.sh
# Полу-автоматическое создание baseline snapshot.
# Запускается один раз на новую версию APK (или при истечении access_token).
#
# Что автоматизируется:
#   - старт AVD с writable system
#   - установка mitmproxy CA в системные сертификаты
#   - установка пропатченного APK
#   - настройка proxy
# Что НЕ автоматизируется (human required):
#   - SMS login в приложении
#   - подтверждение что главный экран открылся и загрузился
#
# В конце пользователь подтверждает готовность → snapshot save.
#
# См. ADR-0007.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"


if [[ ! -f "$PATCHED_APK" ]]; then
    echo "❌ $PATCHED_APK не найден. Запусти ./research/scripts/00-patch-apk.sh"
    exit 1
fi

# Host IP для AVD (10.0.2.2 — это «хост» с точки зрения AVD)
HOST_IP="10.0.2.2"

echo "=== Step 1/6: Start emulator with writable system ==="
echo "Если AVD уже запущен — остановите его (adb emu kill) и запустите этот скрипт снова."
echo ""
echo "Запустить:"
echo "  emulator -avd $AVD_NAME -writable-system -no-snapshot-load &"
echo ""
read -p "Эмулятор запущен и загрузился? [Enter]"

echo "=== Step 2/6: Wait for device ==="
adb wait-for-device
adb shell 'while [[ -z $(getprop sys.boot_completed) ]]; do sleep 1; done'
echo "✓ Device ready"

echo "=== Step 3/6: Install mitmproxy CA as system cert ==="
if [[ ! -f ~/.mitmproxy/mitmproxy-ca-cert.pem ]]; then
    echo "❌ mitmproxy CA не найден в ~/.mitmproxy/."
    echo "   Запусти mitmproxy один раз, чтобы он создал ключи: mitmproxy"
    exit 1
fi

# Compute Android hashed name for the cert
HASH=$(openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1)
CERT_FILE="${HASH}.0"

cp ~/.mitmproxy/mitmproxy-ca-cert.pem "/tmp/$CERT_FILE"

adb root
adb remount
adb push "/tmp/$CERT_FILE" "/system/etc/security/cacerts/$CERT_FILE"
adb shell chmod 644 "/system/etc/security/cacerts/$CERT_FILE"
rm "/tmp/$CERT_FILE"
echo "✓ mitmproxy CA installed in /system/etc/security/cacerts/"

echo "=== Step 4/6: Install patched APK ==="
adb install -r "$PATCHED_APK"
echo "✓ APK installed: $APP_PACKAGE"

echo "=== Step 5/6: Configure proxy ==="
adb shell settings put global http_proxy "$HOST_IP:$MITM_PORT"
echo "✓ Proxy set to $HOST_IP:$MITM_PORT"

echo "=== Step 6/6: Manual login + snapshot save ==="
echo ""
echo "⚠️  ТВОЯ ЧАСТЬ:"
echo "  1. Запусти mitmdump в отдельном терминале: mitmdump -p $MITM_PORT"
echo "  2. Открой приложение на эмуляторе ($APP_PACKAGE)"
echo "  3. Пройди SMS login (SMS придёт на твой физ номер)"
echo "  4. Дождись загрузки главного экрана"
echo "  5. Останови mitmdump (Ctrl+C) — это был preview, не сохраняем"
echo ""
read -p "Готово? Можем save snapshot? [Enter]"

echo "→ Saving snapshot '$BASELINE_SNAPSHOT'..."
adb emu avd snapshot save "$BASELINE_SNAPSHOT"

cat > "$BASELINE_META" <<EOF
# Baseline metadata
created: $(date -u +%Y-%m-%dT%H:%M:%SZ)
apk_path: $PATCHED_APK
apk_sha256: $(shasum -a 256 "$PATCHED_APK" | awk '{print $1}')
avd: $AVD_NAME
snapshot: $BASELINE_SNAPSHOT
EOF

echo "✓ Baseline saved. Metadata: $BASELINE_META"
echo ""
echo "Дальше: запусти любой capture через ./research/scripts/02-snapshot-load.sh"
