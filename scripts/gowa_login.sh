#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
source .env
set +a

BASE="http://127.0.0.1:3000"
AUTH="$GOWA_BASIC_AUTH_USER:$GOWA_BASIC_AUTH_PASSWORD"

echo "=== QR login request for $GOWA_DEVICE_ID ==="
curl -fsS -u "$AUTH" "$BASE/devices/$GOWA_DEVICE_ID/login" | jq .
echo
echo "Alternatif paling mudah: dari PC buat tunnel SSH ke port 3000 lalu buka http://127.0.0.1:3000"
