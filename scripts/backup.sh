#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
source .env
set +a
mkdir -p backups
STAMP=$(date -u +%Y%m%d-%H%M%S)
FILE="backups/multitek-service-$STAMP.dump"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$FILE"
test -s "$FILE"
sha256sum "$FILE" > "$FILE.sha256"
echo "Backup: $FILE"
