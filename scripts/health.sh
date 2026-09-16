#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
source .env
set +a

echo "=== containers ==="
docker compose ps
echo
echo "=== api health ==="
curl -fsS http://127.0.0.1:8080/health
echo
echo
echo "=== db ==="
docker compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
echo
echo "=== gowa local ==="
curl -fsS -u "$GOWA_BASIC_AUTH_USER:$GOWA_BASIC_AUTH_PASSWORD" http://127.0.0.1:3000/app/info || true
echo
