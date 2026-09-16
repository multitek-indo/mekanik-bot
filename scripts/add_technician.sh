#!/usr/bin/env bash
set -Eeuo pipefail
# Fallback administratif. Jalur normal: DAFTAR MEKANIK via WhatsApp.
# Usage:
# ./scripts/add_technician.sh "Pak Agus" 62XXXXXXXXXXX -6.9667 110.4167 25 'JARUM_1=5,OBRAS=5,ELEKTRONIK_SERVO=3'
NAME=${1:?name}
PHONE=${2:?phone}
LAT=${3:?lat}
LON=${4:?lon}
RADIUS=${5:-25}
SKILLS=${6:-}
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
source .env
set +a

python3 - "$NAME" "$PHONE" "$LAT" "$LON" "$RADIUS" "$SKILLS" "$OWNER_API_TOKEN" <<'PY'
import json, sys, urllib.request
name, phone, lat, lon, radius, raw_skills, token = sys.argv[1:]
skills = {}
for part in raw_skills.split(','):
    if '=' not in part:
        continue
    code, level = part.split('=', 1)
    try:
        skills[code.strip().upper()] = int(level)
    except ValueError:
        pass
payload = json.dumps({
    'name': name,
    'wa_number': phone,
    'base_lat': float(lat),
    'base_lon': float(lon),
    'service_radius_km': float(radius),
    'skills': skills,
}).encode()
req = urllib.request.Request(
    'http://127.0.0.1:8080/owner/technicians',
    data=payload,
    headers={'Content-Type':'application/json','Authorization':'Bearer '+token},
    method='POST',
)
print(urllib.request.urlopen(req, timeout=10).read().decode())
PY
