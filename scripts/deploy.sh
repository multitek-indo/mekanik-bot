#!/usr/bin/env bash
set -Eeuo pipefail

REPO="/home/mekanik/mekanik-bot"
STATE="/home/mekanik/.mekanik-bot-deploy"
TARGET="${1:-}"

cd "$REPO"
mkdir -p "$STATE"

if [ -z "$TARGET" ]; then
    echo "Pemakaian:"
    echo "  mekanik-deploy v0.3.0-beta.1"
    echo "  mekanik-deploy latest"
    echo "  mekanik-deploy main"
    exit 1
fi

echo "=============================================="
echo " MULTITEK SERVICE DEPLOY"
echo " Target: $TARGET"
echo "=============================================="

if [ -n "$(git status --porcelain)" ]; then
    echo "GAGAL: source VPS masih memiliki perubahan lokal."
    echo
    git status --short
    exit 2
fi

echo "[1/7] Fetch GitHub..."
git fetch origin --tags --prune

if [ "$TARGET" = "latest" ]; then
    TARGET="$(
        git tag -l 'v*' --sort=-version:refname |
        head -n 1
    )"

    [ -n "$TARGET" ] || {
        echo "GAGAL: belum ada tag release."
        exit 3
    }
fi

if [ "$TARGET" = "main" ]; then
    REF="origin/main"
elif git rev-parse -q --verify \
    "refs/tags/${TARGET}^{commit}" >/dev/null
then
    REF="$TARGET"
elif git rev-parse -q --verify \
    "origin/${TARGET}^{commit}" >/dev/null
then
    REF="origin/$TARGET"
else
    REF="$TARGET"
fi

TARGET_COMMIT="$(
    git rev-parse --verify "${REF}^{commit}"
)" || {
    echo "GAGAL: target $TARGET tidak ditemukan."
    exit 4
}

CURRENT_COMMIT="$(git rev-parse HEAD)"

echo "Current: $(git rev-parse --short "$CURRENT_COMMIT")"
echo "Target : $(git rev-parse --short "$TARGET_COMMIT")"

if ! docker compose ps --status running db |
    grep -q 'db'
then
    echo "GAGAL: database tidak sedang berjalan."
    exit 5
fi

echo "[2/7] Backup database..."
./scripts/backup.sh

wait_health() {
    local i

    for i in $(seq 1 40); do
        if curl -fsS \
            http://127.0.0.1:8080/health \
            >/dev/null 2>&1
        then
            return 0
        fi

        sleep 2
    done

    return 1
}

rollback_app() {
    echo
    echo "=============================================="
    echo " DEPLOY GAGAL - ROLLBACK OTOMATIS"
    echo "=============================================="

    git checkout --detach "$CURRENT_COMMIT"

    docker compose build \
        --build-arg GIT_COMMIT="$CURRENT_COMMIT" \
        api worker

    docker compose up -d api worker

    if wait_health; then
        echo "Rollback aplikasi berhasil."
    else
        echo "KRITIS: rollback juga gagal."
        docker compose logs --tail=100 api worker
    fi
}

echo "[3/7] Checkout source..."
git checkout --detach "$TARGET_COMMIT"

echo "[4/7] Preflight..."
if ! ./scripts/preflight.sh; then
    git checkout --detach "$CURRENT_COMMIT"
    echo "Deploy dibatalkan. Source dikembalikan."
    exit 6
fi

echo "[5/7] Build API + worker..."
if ! docker compose build \
    --build-arg GIT_COMMIT="$TARGET_COMMIT" \
    api worker
then
    rollback_app
    exit 7
fi

echo "[6/7] Start API + worker..."
if ! docker compose up -d api worker; then
    rollback_app
    exit 8
fi

if ! wait_health; then
    docker compose logs --tail=100 api worker
    rollback_app
    exit 9
fi

EXPECTED_VERSION="$(cat VERSION)"

RUNTIME_JSON="$(
    curl -fsS http://127.0.0.1:8080/health
)"

RUNTIME_VERSION="$(
    printf '%s' "$RUNTIME_JSON" |
    python3 -c '
import json
import sys
print(json.load(sys.stdin).get("version", "unknown"))
'
)"

if [ "$EXPECTED_VERSION" != "$RUNTIME_VERSION" ]; then
    echo "GAGAL: version runtime tidak sesuai."
    echo "Expected: $EXPECTED_VERSION"
    echo "Runtime : $RUNTIME_VERSION"
    rollback_app
    exit 10
fi

echo "[7/7] Simpan deployment state..."

printf '%s\n' "$CURRENT_COMMIT" \
    > "$STATE/previous_commit"

printf '%s\n' "$TARGET_COMMIT" \
    > "$STATE/current_commit"

printf '%s\n' "$TARGET" \
    > "$STATE/current_ref"

printf '%s | %s | %s | SUCCESS\n' \
    "$(date -Is)" \
    "$TARGET" \
    "$TARGET_COMMIT" \
    >> "$STATE/history.log"

echo
echo "=============================================="
echo " DEPLOY BERHASIL"
echo "=============================================="
echo "$RUNTIME_JSON"
echo
