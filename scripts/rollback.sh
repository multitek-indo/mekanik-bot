#!/usr/bin/env bash
set -Eeuo pipefail

REPO="/home/mekanik/mekanik-bot"
STATE="/home/mekanik/.mekanik-bot-deploy"

TARGET="${1:-}"

if [ -z "$TARGET" ]; then
    if [ ! -f "$STATE/previous_commit" ]; then
        echo "Belum ada versi sebelumnya yang tercatat."
        echo
        echo "Gunakan:"
        echo "  mekanik-rollback <tag-atau-commit>"
        exit 1
    fi

    TARGET="$(cat "$STATE/previous_commit")"
fi

echo "Rollback menuju:"
echo "$TARGET"
echo

exec "$REPO/scripts/deploy.sh" "$TARGET"
