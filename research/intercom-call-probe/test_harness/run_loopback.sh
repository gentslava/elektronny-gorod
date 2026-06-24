#!/usr/bin/env bash
# Оффлайн loopback-тест two-way audio: door_emulator.py (мини-оператор+домофон)
# ↔ probe_push_answer.py (проба) на localhost. БЕЗ физического домофона/оператора.
#
# Поток: проба REGISTER → 401 → REGISTER(auth) → 200 → эмулятор INVITE → проба
# 200 OK+SDP → эмулятор ACK → проба uplink RTP → эмулятор latching+downlink → BYE.
# Вердикт печатает door_emulator (exit-code 0 = полный двусторонний вызов).
#
# Запуск:  ./run_loopback.sh
# Идемпотентно: чистит свои процессы/сокеты до и после.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PY="${PYTHON:-python3}"

# --- параметры (совпадают на обеих сторонах) ---
SIP_IP=127.0.0.1
SIP_PORT=5060          # == probe_sip.SIP_PORT (проба шлёт SIP на этот порт)
DOOR_RTP_PORT=39000
REALM=test.local
TEST_LOGIN=testuser
TEST_PASSWORD=testpass
TALK_SEC="${TALK_SEC:-8}"
STRICT_SYMMETRIC="${STRICT_SYMMETRIC:-1}"
WAIT_SEC="${WAIT_SEC:-40}"

DOOR_LOG="$ROOT/logs/door_emulator.log"
PROBE_LOG="$ROOT/logs/loopback_probe.log"
mkdir -p "$ROOT/logs"

cleanup() {
  [ -n "${PROBE_PID:-}" ] && kill "$PROBE_PID" 2>/dev/null
  [ -n "${DOOR_PID:-}" ] && kill "$DOOR_PID" 2>/dev/null
  # добиваем по имени, если остались зомби
  pkill -f "probe_push_answer.py" 2>/dev/null
  pkill -f "door_emulator.py" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

# на старте — снять прежние инстансы (идемпотентность)
pkill -f "probe_push_answer.py" 2>/dev/null
pkill -f "door_emulator.py" 2>/dev/null
sleep 0.5

echo "=== [run_loopback] старт door_emulator (SIP $SIP_IP:$SIP_PORT, RTP :$DOOR_RTP_PORT) ==="
DOOR_SIP_IP="$SIP_IP" DOOR_SIP_PORT="$SIP_PORT" DOOR_RTP_PORT="$DOOR_RTP_PORT" \
  REALM="$REALM" TALK_SEC="$TALK_SEC" STRICT_SYMMETRIC="$STRICT_SYMMETRIC" WAIT_SEC="$WAIT_SEC" \
  "$PY" -u "$HERE/door_emulator.py" 2>&1 | tee "$DOOR_LOG" &
DOOR_PID=$!
sleep 1   # дать эмулятору забиндить сокеты

echo "=== [run_loopback] старт probe_push_answer (PERSIST_REG, ANSWER, MIRROR_APP, оффлайн) ==="
# Проба: оффлайн-режим (TEST_LOGIN/REALM → mint_sip/FCM пропущены), SIP_SERVER → эмулятор.
# PERSIST_REG=1 — софтфон-регистрация (без FCM). RTP_EARLY=0 — uplink после ACK (по рецепту).
cd "$ROOT"
PERSIST_REG=1 ANSWER=1 MIRROR_APP=1 RTP_EARLY=0 ANSWER_DELAY=2 TALK_SEC="$TALK_SEC" \
  SIP_SERVER="$SIP_IP" TEST_LOGIN="$TEST_LOGIN" TEST_PASSWORD="$TEST_PASSWORD" TEST_REALM="$REALM" \
  "$PY" -u "$ROOT/probe_push_answer.py" 2>&1 | tee "$PROBE_LOG" &
PROBE_PID=$!

# ждём завершения эмулятора (он держит общий бюджет WAIT_SEC + downlink)
wait "$DOOR_PID"
DOOR_RC=$?

# проба может остаться в persistent_register — гасим
kill "$PROBE_PID" 2>/dev/null
pkill -f "probe_push_answer.py" 2>/dev/null

echo ""
echo "=== [run_loopback] door_emulator exit-code = $DOOR_RC ==="
if [ "$DOOR_RC" -eq 0 ]; then
  echo "=== [run_loopback] ✅ TWO-WAY MEDIA РАБОТАЕТ (symmetric latching пройден) ==="
else
  echo "=== [run_loopback] ❌ вызов НЕ полный — см. отчёт door_emulator выше и логи:"
  echo "    door : $DOOR_LOG"
  echo "    probe: $PROBE_LOG"
fi
exit "$DOOR_RC"
