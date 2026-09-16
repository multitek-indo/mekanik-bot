#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail=0
for cmd in docker git openssl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: $cmd tidak tersedia"
    fail=1
  fi
done

if ! docker compose version >/dev/null 2>&1; then
  echo "FAIL: docker compose plugin tidak tersedia"
  fail=1
fi

if [[ ! -f .env ]]; then
  echo "FAIL: .env belum dibuat (cp .env.example .env)"
  fail=1
else
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  vars=(POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD DATABASE_URL OWNER_WA_NUMBER OWNER_API_TOKEN GOWA_BASIC_AUTH_USER GOWA_BASIC_AUTH_PASSWORD GOWA_WEBHOOK_SECRET PAYMENT_BANK_ACCOUNT)
  for v in "${vars[@]}"; do
    if [[ -z "${!v:-}" || "${!v:-}" == GANTI_* || "${!v:-}" == ISI_* ]]; then
      echo "FAIL: $v belum dikonfigurasi"
      fail=1
    fi
  done
fi

if [[ -n "${OWNER_WA_NUMBER:-}" && ! "${OWNER_WA_NUMBER}" =~ ^62[0-9]{8,15}$ ]]; then
  echo "FAIL: OWNER_WA_NUMBER harus format 62xxxxxxxxxx tanpa + atau 0 depan"
  fail=1
fi

if [[ -n "${QRIS_IMAGE_PATH:-}" && ! -f ./data/qris.png ]]; then
  echo "WARN: ./data/qris.png belum ada; transfer bank tetap dapat dipakai, QRIS tidak akan terkirim."
fi

python_files=$(find app -type f -name '*.py' -print)
python3 -m py_compile $python_files || fail=1

if [[ $fail -ne 0 ]]; then
  echo "PREFLIGHT GAGAL"
  exit 1
fi

echo "PREFLIGHT OK"
