#!/usr/bin/env bash
set -u

REPO="/home/mekanik/mekanik-bot"
STATE="/home/mekanik/.mekanik-bot-deploy"

cd "$REPO" || exit 1

SOURCE_VERSION="$(cat VERSION 2>/dev/null || echo unknown)"
SOURCE_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
GIT_DESC="$(git describe --tags --always --dirty 2>/dev/null || echo unknown)"

BRANCH="$(git branch --show-current 2>/dev/null)"

if [ -z "$BRANCH" ]; then
    BRANCH="detached/tag"
fi

RUNTIME_JSON="$(
    curl -fsS \
    http://127.0.0.1:8080/health \
    2>/dev/null || true
)"

if [ -n "$RUNTIME_JSON" ]; then
    RUNTIME_VERSION="$(
        printf '%s' "$RUNTIME_JSON" |
        python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("version", "unknown"))
except Exception:
    print("unknown")
'
    )"

    RUNTIME_COMMIT="$(
        printf '%s' "$RUNTIME_JSON" |
        python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("commit", "unknown"))
except Exception:
    print("unknown")
'
    )"
else
    RUNTIME_VERSION="offline"
    RUNTIME_COMMIT="offline"
fi

DEPLOY_REF="$(
    cat "$STATE/current_ref" 2>/dev/null ||
    echo "belum tercatat"
)"

DEPLOY_COMMIT="$(
    cat "$STATE/current_commit" 2>/dev/null |
    cut -c1-12
)"

[ -n "$DEPLOY_COMMIT" ] || DEPLOY_COMMIT="belum tercatat"

echo "=================================================="
echo " MULTITEK SERVICE - VERSION"
echo "=================================================="
echo "Source version : $SOURCE_VERSION"
echo "Git describe   : $GIT_DESC"
echo "Source commit  : $SOURCE_COMMIT"
echo "Git branch     : $BRANCH"
echo "Runtime API    : $RUNTIME_VERSION"
echo "Runtime commit : $RUNTIME_COMMIT"
echo "Deploy ref     : $DEPLOY_REF"
echo "Deploy commit  : $DEPLOY_COMMIT"

if [ "$SOURCE_VERSION" = "$RUNTIME_VERSION" ]; then
    echo "Status         : SOURCE = RUNTIME"
else
    echo "Status         : SOURCE != RUNTIME"
fi

echo
docker compose ps
