#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
source .env
set +a

curl -fsS \
  -u "$GOWA_BASIC_AUTH_USER:$GOWA_BASIC_AUTH_PASSWORD" \
  -H "X-Device-Id: $GOWA_DEVICE_ID" \
  http://127.0.0.1:3000/app/status | jq .
