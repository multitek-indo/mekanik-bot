#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
source .env
set +a

BASE="http://127.0.0.1:3000"
AUTH="$GOWA_BASIC_AUTH_USER:$GOWA_BASIC_AUTH_PASSWORD"

echo "=== GOWA server ==="
curl -fsS -u "$AUTH" "$BASE/app/info" | jq . || true

echo "=== device list before ==="
curl -fsS -u "$AUTH" "$BASE/devices" | jq . || true

echo "=== create device slot: $GOWA_DEVICE_ID ==="
HTTP=$(curl -sS -o /tmp/multitek-gowa-device.json -w '%{http_code}' \
  -u "$AUTH" -H 'Content-Type: application/json' \
  -X POST "$BASE/devices" \
  -d "{\"device_id\":\"$GOWA_DEVICE_ID\"}")
cat /tmp/multitek-gowa-device.json | jq . 2>/dev/null || cat /tmp/multitek-gowa-device.json
if [[ "$HTTP" != "200" && "$HTTP" != "201" && "$HTTP" != "400" && "$HTTP" != "409" ]]; then
  echo "Gagal membuat device slot (HTTP $HTTP)" >&2
  exit 1
fi

echo
echo "Device slot siap atau sudah ada. Pair WhatsApp melalui UI tunnel SSH atau jalankan ./scripts/gowa_login.sh"
