#!/usr/bin/env bash
# Boots a throwaway server (temp database, stub AI) and runs the end-to-end smoke test against it.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${SMOKE_PORT:-8123}"
TMP="$(mktemp -d)"
trap 'kill "$SERVER_PID" 2>/dev/null || true; rm -rf "$TMP"' EXIT

PORT="$PORT" DATABASE_URL="sqlite:///$TMP/smoke.db" INSTANCE_DIR="$TMP/instance" \
  DEMO_USER_PASSWORD="demo-pass-1" AI_SERVICE_API_KEY=stub_key RATE_LIMIT_PER_MINUTE=0 LOGIN_RATE_LIMIT_PER_MINUTE=0 \
  python3 run.py --no-build >"$TMP/server.log" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 60); do
  curl -fs "http://127.0.0.1:$PORT/api/v1/health" >/dev/null 2>&1 && break
  sleep 0.25
done
curl -fs "http://127.0.0.1:$PORT/api/v1/health" >/dev/null || { echo "Server did not start:"; cat "$TMP/server.log"; exit 1; }

SMOKE_BASE="http://127.0.0.1:$PORT" SMOKE_PASSWORD="demo-pass-1" node frontend/tests/smoke/smoke.mjs
if grep -q -E "smoke@example.com|citizen1@example.com|9876543210" "$TMP/server.log"; then
  echo "FAIL: contact details found in server log"; exit 1
fi
echo "Server log contains no contact details."
