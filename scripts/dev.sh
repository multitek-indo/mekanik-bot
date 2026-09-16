#!/usr/bin/env bash
set -Eeuo pipefail

REPO="/home/mekanik/mekanik-bot"
cd "$REPO"

export GIT_PAGER=cat
export PAGER=cat

MODE="${1:-status}"
shift || true

ensure_main() {
    BRANCH="$(git branch --show-current)"

    if [ "$BRANCH" != "main" ]; then
        if [ -n "$(git status --porcelain)" ]; then
            echo "GAGAL: ada perubahan lokal."
            git status --short
            exit 2
        fi

        git checkout main
    fi
}

check_remote() {
    git fetch origin --prune --tags

    read -r REMOTE_ONLY LOCAL_ONLY <<< \
        "$(git rev-list --left-right --count origin/main...main)"

    if [ "$REMOTE_ONLY" != "0" ]; then
        echo "GitHub mempunyai perubahan lebih baru."
        echo "Jalankan:"
        echo "  mekanik-dev pull"
        exit 3
    fi
}

safety() {
    git diff --cached --name-only > /tmp/mekanik-stage-check.txt

    python3 - <<'PY'
from pathlib import Path
import re
import subprocess
import sys

files = Path("/tmp/mekanik-stage-check.txt").read_text().splitlines()

bad_names = []

for f in files:
    low = f.lower()

    if f == ".env":
        bad_names.append(f)
    elif f.startswith(".env.") and f != ".env.example":
        bad_names.append(f)
    elif f.startswith("backups/"):
        bad_names.append(f)
    elif f.startswith("data/media/"):
        bad_names.append(f)
    elif low.endswith((".dump", ".pem", ".p12", ".pfx")):
        bad_names.append(f)

if bad_names:
    print("GAGAL: file sensitif terdeteksi:")
    for f in bad_names:
        print(" -", f)
    sys.exit(1)

patterns = {
    "Gemini key": re.compile(r"AIza[0-9A-Za-z_-]{25,}"),
    "Groq key": re.compile(r"gsk_[0-9A-Za-z_-]{20,}"),
    "OpenAI key": re.compile(r"sk-[0-9A-Za-z_-]{20,}"),
    "GitHub token": re.compile(
        r"(?:gh[pousr]_[0-9A-Za-z]{20,}|github_pat_[0-9A-Za-z_]{20,})"
    ),
    "Private key": re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    ),
}

found = []

for f in files:
    try:
        data = subprocess.check_output(
            ["git", "show", ":" + f],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="ignore")
    except Exception:
        continue

    for label, rx in patterns.items():
        if rx.search(data):
            found.append((label, f))

if found:
    print("GAGAL: kemungkinan credential terdeteksi:")
    for label, f in found:
        print(f" - {label}: {f}")
    sys.exit(1)

print("Safety scan: OK")
PY
}

case "$MODE" in

status)
    echo "===== GIT ====="
    git status -sb
    echo
    mekanik-version
    ;;

pull)
    ensure_main

    if [ -n "$(git status --porcelain)" ]; then
        echo "GAGAL: simpan/commit perubahan lokal terlebih dahulu."
        git status --short
        exit 2
    fi

    git fetch origin --prune --tags
    git pull --ff-only origin main

    echo
    echo "GitHub -> VPS selesai."
    ;;

save)
    MSG="${*:-update development}"

    ensure_main
    check_remote

    git add -A
    safety

    python3 -m py_compile app/*.py

    for f in scripts/*.sh; do
        bash -n "$f"
    done

    if git diff --cached --quiet; then
        echo "Tidak ada perubahan untuk disimpan."
        exit 0
    fi

    git commit -m "$MSG"
    git push origin main

    echo
    echo "Perubahan sudah tersimpan di GitHub."
    ;;

release)
    NEW_VERSION="${1:-}"

    if [ -z "$NEW_VERSION" ]; then
        echo "Contoh:"
        echo '  mekanik-dev release 0.3.0-beta.2 "media forwarding verified"'
        exit 1
    fi

    shift || true
    MSG="${*:-release v$NEW_VERSION}"

    ensure_main
    check_remote

    printf '%s\n' "$NEW_VERSION" > VERSION

    git add -A
    safety

    python3 -m py_compile app/*.py

    for f in scripts/*.sh; do
        bash -n "$f"
    done

    git commit -m "release: v$NEW_VERSION - $MSG"

    TAG="v$NEW_VERSION"

    if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
        echo "GAGAL: tag $TAG sudah ada."
        exit 4
    fi

    git tag -a "$TAG" -m "Release $TAG"

    git push origin main
    git push origin "$TAG"

    echo
    echo "Release selesai:"
    echo "  $TAG"
    echo
    echo "Deploy dengan:"
    echo "  mekanik-deploy $TAG"
    ;;

*)
    echo "Pemakaian:"
    echo
    echo "  mekanik-dev status"
    echo "  mekanik-dev pull"
    echo '  mekanik-dev save "pesan perubahan"'
    echo '  mekanik-dev release 0.3.0-beta.2 "keterangan"'
    exit 1
    ;;
esac
