"""OpenStreetMap-only Location Intelligence for Multitek Service.

This module is intentionally isolated from the V5 conversation engine.
It turns WhatsApp Share Location coordinates into human-readable location data
using public OpenStreetMap services while keeping raw coordinates internal.

Provider strategy
-----------------
1. Preserve useful WhatsApp-provided place name/address.
2. Check bounded in-memory TTL cache.
3. On cache miss, query public Nominatim reverse geocoding and public Overpass
   POI lookup concurrently. Each public service has its own serializer/rate
   limiter so repeated customer messages cannot create request bursts.
4. Merge only factual map data; never invent place names.
5. Fail open: if public map services are unavailable, service intake continues
   with the original coordinates stored internally.

Important
---------
Public Nominatim/Overpass are suitable only for low-volume/pilot use and their
usage policies must be respected. This module therefore includes caching,
rate limiting, a small Overpass daily call budget, provider cooldowns, and a
feature flag.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import math
import os
import re
import time
from collections import OrderedDict
from datetime import date
from typing import Any

import httpx

log = logging.getLogger("multitek-location")

_NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_GENERIC_NAMES = {
    "lokasi",
    "lokasi customer",
    "lokasi pelanggan",
    "dropped pin",
    "pin",
    "share location",
    "current location",
    "my location",
    "unknown",
    "-",
}

_LOW_VALUE_OSM_NAMES = {
    "yes",
    "no",
    "unnamed road",
}

# Higher means more useful as a human landmark.
_POI_TYPE_PRIORITY = {
    "office": 100,
    "company": 100,
    "factory": 100,
    "industrial": 98,
    "warehouse": 96,
    "shop": 94,
    "supermarket": 96,
    "convenience": 96,
    "mall": 94,
    "hospital": 94,
    "clinic": 92,
    "school": 90,
    "university": 90,
    "mosque": 94,
    "place_of_worship": 92,
    "church": 90,
    "fuel": 92,
    "bank": 88,
    "atm": 82,
    "restaurant": 88,
    "cafe": 86,
    "hotel": 88,
    "police": 90,
    "government": 88,
    "marketplace": 88,
    "building": 74,
}


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _env_float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


def _env_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


def _clean(value: Any, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ,;\t\r\n")
    return text[:limit]


def _looks_like_coordinates(value: str) -> bool:
    value = _clean(value).lower()
    if not value:
        return False
    return bool(
        re.fullmatch(
            r"[-+]?\d{1,3}(?:\.\d+)?\s*[,;/]\s*[-+]?\d{1,3}(?:\.\d+)?",
            value,
        )
    )


def _meaningful_name(value: Any) -> str:
    value = _clean(value, 250)
    if not value:
        return ""
    low = value.lower()
    if low in _GENERIC_NAMES or low in _LOW_VALUE_OSM_NAMES:
        return ""
    if _looks_like_coordinates(value):
        return ""
    if re.fullmatch(r"(?:jalan|jl\.?|street|road|rd\.?)\s*", low):
        return ""
    return value


def _valid_lat_lon(location: dict) -> tuple[float, float] | None:
    try:
        lat = float(location.get("lat"))
        lon = float(location.get("lon"))
    except (TypeError, ValueError, AttributeError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _type_score(types: list[str] | tuple[str, ...] | None) -> int:
    values = [str(x or "").lower() for x in (types or [])]
    score = 0
    for value in values:
        score = max(score, _POI_TYPE_PRIORITY.get(value, 0))
    return score


def _dedupe_candidates(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        name = _meaningful_name(item.get("name"))
        if not name:
            continue
        key = re.sub(r"\W+", "", name.lower())
        if not key or key in seen:
            continue
        seen.add(key)
        copy_item = dict(item)
        copy_item["name"] = name
        out.append(copy_item)
    return out


def _osm_address_text(address: dict | None, fallback: str = "") -> str:
    address = address or {}
    road = _clean(
        address.get("road")
        or address.get("pedestrian")
        or address.get("residential")
    )
    house = _clean(address.get("house_number"))
    village = _clean(
        address.get("village")
        or address.get("suburb")
        or address.get("neighbourhood")
        or address.get("quarter")
    )
    district = _clean(
        address.get("city_district")
        or address.get("district")
        or address.get("county")
    )
    city = _clean(
        address.get("city")
        or address.get("town")
        or address.get("municipality")
    )
    regency = _clean(address.get("regency"))
    state = _clean(address.get("state"))

    pieces: list[str] = []
    if road:
        pieces.append(f"{road}{(' No. ' + house) if house else ''}")
    for value in (village, district, city, regency, state):
        if value and value not in pieces:
            pieces.append(value)
    if pieces:
        return ", ".join(pieces)[:500]
    return _clean(fallback, 500)


def _name_from_osm(data: dict) -> str:
    namedetails = data.get("namedetails") or {}
    address = data.get("address") or {}
    candidates = [
        namedetails.get("name:id"),
        namedetails.get("name"),
        data.get("name"),
        address.get("company"),
        address.get("shop"),
        address.get("office"),
        address.get("amenity"),
        address.get("building"),
    ]
    for value in candidates:
        name = _meaningful_name(value)
        if name and not re.fullmatch(
            r"(?:yes|residential|commercial|industrial|house)",
            name.lower(),
        ):
            return name
    return ""


def _user_agent() -> str:
    return _clean(
        os.getenv(
            "LOCATION_OSM_USER_AGENT",
            "MultitekService/1.0 (WhatsApp customer service)",
        ),
        250,
    ) or "MultitekService/1.0 (WhatsApp customer service)"


# ---------------------------------------------------------------------------
# Bounded in-memory provider cache.
# We cache provider results, not the entire incoming WhatsApp location, so a
# useful name/address supplied directly by WhatsApp can still take precedence.
# ---------------------------------------------------------------------------
_provider_cache: OrderedDict[str, tuple[float, dict, list[dict]]] = OrderedDict()
_cache_lock = asyncio.Lock()


def _cache_key(lat: float, lon: float) -> str:
    digits = _env_int("LOCATION_CACHE_COORD_DECIMALS", 5, 4, 7)
    return f"{lat:.{digits}f},{lon:.{digits}f}"


async def _cache_get(lat: float, lon: float) -> tuple[dict, list[dict]] | None:
    key = _cache_key(lat, lon)
    ttl = _env_int("LOCATION_CACHE_TTL_SECONDS", 86400, 60, 604800)
    now = time.monotonic()
    async with _cache_lock:
        item = _provider_cache.get(key)
        if not item:
            return None
        created_at, reverse, nearby = item
        if now - created_at > ttl:
            _provider_cache.pop(key, None)
            return None
        _provider_cache.move_to_end(key)
        return copy.deepcopy(reverse), copy.deepcopy(nearby)


async def _cache_put(lat: float, lon: float, reverse: dict, nearby: list[dict]) -> None:
    key = _cache_key(lat, lon)
    max_entries = _env_int("LOCATION_CACHE_MAX_ENTRIES", 2000, 10, 20000)
    async with _cache_lock:
        _provider_cache[key] = (time.monotonic(), copy.deepcopy(reverse), copy.deepcopy(nearby))
        _provider_cache.move_to_end(key)
        while len(_provider_cache) > max_entries:
            _provider_cache.popitem(last=False)


async def clear_location_cache() -> None:
    """Testing/maintenance helper. Does not touch service/order data."""
    async with _cache_lock:
        _provider_cache.clear()


# ---------------------------------------------------------------------------
# Service-specific request serialization / throttling.
# ---------------------------------------------------------------------------
_nominatim_lock = asyncio.Lock()
_overpass_lock = asyncio.Lock()
_last_nominatim_started = 0.0
_last_overpass_started = 0.0
_nominatim_cooldown_until = 0.0
_overpass_cooldown_until = 0.0
_overpass_budget_day: date | None = None
_overpass_budget_count = 0


async def _wait_interval(last_started: float, minimum_interval: float) -> float:
    now = time.monotonic()
    wait_for = minimum_interval - (now - last_started)
    if wait_for > 0:
        await asyncio.sleep(wait_for)
    return time.monotonic()


def _consume_overpass_budget() -> bool:
    global _overpass_budget_day, _overpass_budget_count
    today = date.today()
    if _overpass_budget_day != today:
        _overpass_budget_day = today
        _overpass_budget_count = 0
    limit = _env_int("LOCATION_OVERPASS_MAX_CALLS_PER_DAY", 80, 0, 10000)
    if limit == 0:
        return False
    if _overpass_budget_count >= limit:
        return False
    _overpass_budget_count += 1
    return True


async def _osm_reverse(lat: float, lon: float, timeout: float) -> dict:
    """Public Nominatim reverse lookup, serialized to <= configured rate."""
    global _last_nominatim_started, _nominatim_cooldown_until

    now = time.monotonic()
    if now < _nominatim_cooldown_until:
        return {}

    params = {
        "lat": f"{lat:.7f}",
        "lon": f"{lon:.7f}",
        "format": "jsonv2",
        "zoom": 18,
        "addressdetails": 1,
        "namedetails": 1,
        "accept-language": "id",
    }
    headers = {"User-Agent": _user_agent()}
    interval = _env_float("LOCATION_NOMINATIM_MIN_INTERVAL_SECONDS", 1.1, 1.0, 10.0)

    async with _nominatim_lock:
        if time.monotonic() < _nominatim_cooldown_until:
            return {}
        _last_nominatim_started = await _wait_interval(
            _last_nominatim_started,
            interval,
        )
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = await client.get(_NOMINATIM_REVERSE_URL, params=params)
                if response.status_code == 429:
                    _nominatim_cooldown_until = time.monotonic() + 10.0
                    return {}
                response.raise_for_status()
                data = response.json()
        except Exception:
            raise

    return {
        "name": _name_from_osm(data),
        "address": _osm_address_text(
            data.get("address"),
            data.get("display_name") or "",
        ),
        "types": [
            _clean(data.get("category"), 80),
            _clean(data.get("type"), 80),
        ],
        "provider": "openstreetmap_nominatim",
    }


def _osm_types(tags: dict) -> list[str]:
    values: list[str] = []
    for key in (
        "office",
        "shop",
        "amenity",
        "tourism",
        "industrial",
        "building",
        "craft",
        "leisure",
        "healthcare",
    ):
        value = _clean(tags.get(key), 80).lower()
        if value:
            values.append(value)
            values.append(key)

    # Normalize several common OSM values into landmark priority classes.
    aliases = {
        "convenience": "convenience",
        "supermarket": "supermarket",
        "fuel": "fuel",
        "mosque": "mosque",
        "place_of_worship": "place_of_worship",
        "school": "school",
        "university": "university",
        "hospital": "hospital",
        "clinic": "clinic",
        "restaurant": "restaurant",
        "cafe": "cafe",
        "hotel": "hotel",
        "bank": "bank",
        "atm": "atm",
        "police": "police",
        "warehouse": "warehouse",
        "factory": "factory",
        "company": "company",
    }
    for value in list(values):
        if value in aliases:
            values.append(aliases[value])
    return list(dict.fromkeys(values))


async def _osm_nearby(lat: float, lon: float, timeout: float, radius_m: float) -> list[dict]:
    """Public Overpass named-POI lookup with serialization and daily budget."""
    global _last_overpass_started, _overpass_cooldown_until

    if time.monotonic() < _overpass_cooldown_until:
        return []
    if not _consume_overpass_budget():
        log.info("Overpass daily pilot budget reached; nearby landmark lookup skipped")
        return []

    query = (
        f'[out:json][timeout:{max(5, int(timeout))}];'
        "("
        f'nwr(around:{int(radius_m)},{lat:.7f},{lon:.7f})["amenity"]["name"];'
        f'nwr(around:{int(radius_m)},{lat:.7f},{lon:.7f})["shop"]["name"];'
        f'nwr(around:{int(radius_m)},{lat:.7f},{lon:.7f})["office"]["name"];'
        f'nwr(around:{int(radius_m)},{lat:.7f},{lon:.7f})["tourism"]["name"];'
        f'nwr(around:{int(radius_m)},{lat:.7f},{lon:.7f})["industrial"]["name"];'
        f'nwr(around:{int(radius_m)},{lat:.7f},{lon:.7f})["building"]["name"];'
        f'nwr(around:{int(radius_m)},{lat:.7f},{lon:.7f})["craft"]["name"];'
        f'nwr(around:{int(radius_m)},{lat:.7f},{lon:.7f})["leisure"]["name"];'
        ");out center tags;"
    )
    headers = {"User-Agent": _user_agent()}
    interval = _env_float("LOCATION_OVERPASS_MIN_INTERVAL_SECONDS", 1.0, 0.2, 30.0)

    async with _overpass_lock:
        if time.monotonic() < _overpass_cooldown_until:
            return []
        _last_overpass_started = await _wait_interval(
            _last_overpass_started,
            interval,
        )
        async with httpx.AsyncClient(
            timeout=timeout + 3,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.post(_OVERPASS_URL, content=query)
            if response.status_code in {429, 502, 503, 504}:
                # Do not make the customer wait 30 seconds. Skip POI lookup and
                # temporarily cool down Overpass for subsequent requests.
                _overpass_cooldown_until = time.monotonic() + 30.0
                return []
            response.raise_for_status()
            data = response.json()

    out: list[dict] = []
    for element in data.get("elements") or []:
        tags = element.get("tags") or {}
        name = _meaningful_name(
            tags.get("name")
            or tags.get("brand")
            or tags.get("operator")
        )
        if not name:
            continue
        center = element.get("center") or {}
        try:
            plat = float(
                element.get("lat")
                if element.get("lat") is not None
                else center.get("lat")
            )
            plon = float(
                element.get("lon")
                if element.get("lon") is not None
                else center.get("lon")
            )
        except (TypeError, ValueError):
            continue

        types = _osm_types(tags)
        address_parts = [
            _clean(tags.get("addr:street")),
            _clean(tags.get("addr:housenumber")),
            _clean(tags.get("addr:suburb")),
            _clean(tags.get("addr:city")),
        ]
        address = ", ".join(x for x in address_parts if x)
        out.append(
            {
                "name": name,
                "address": address[:500],
                "lat": plat,
                "lon": plon,
                "distance_m": _distance_m(lat, lon, plat, plon),
                "types": types,
                "type_score": _type_score(types),
                "provider": "openstreetmap_overpass",
            }
        )
    return out


async def _safe_reverse(lat: float, lon: float, timeout: float) -> dict:
    try:
        return await _osm_reverse(lat, lon, timeout)
    except Exception as exc:
        log.warning("Nominatim reverse unavailable: %s", type(exc).__name__)
        return {}


async def _safe_nearby(lat: float, lon: float, timeout: float, radius_m: float) -> list[dict]:
    try:
        return await _osm_nearby(lat, lon, timeout, radius_m)
    except Exception as exc:
        log.warning("Overpass nearby unavailable: %s", type(exc).__name__)
        return []


def _select_place_and_landmark(
    direct_name: str,
    direct_address: str,
    reverse: dict,
    nearby: list[dict],
) -> tuple[str, str, str, int | None, str]:
    exact_place_max_m = _env_float(
        "LOCATION_EXACT_PLACE_MAX_METERS",
        35,
        5,
        100,
    )
    nearby = _dedupe_candidates(nearby)

    # For exact-place inference, proximity is the strongest signal. Type score
    # breaks ties. We do not infer anything beyond exact_place_max_m.
    nearby.sort(
        key=lambda item: (
            float(item.get("distance_m") or 999999),
            -int(item.get("type_score") or 0),
        )
    )

    name = _meaningful_name(direct_name)
    address = _clean(direct_address, 500)
    provider = "whatsapp" if (name or address) else ""

    reverse_name = _meaningful_name(reverse.get("name"))
    reverse_address = _clean(reverse.get("address"), 500)

    primary_candidate: dict | None = None
    if not name:
        for item in nearby:
            if float(item.get("distance_m") or 999999) <= exact_place_max_m:
                candidate_name = _meaningful_name(item.get("name"))
                if candidate_name:
                    primary_candidate = item
                    name = candidate_name
                    provider = str(item.get("provider") or provider)
                    if not address:
                        address = _clean(item.get("address"), 500)
                    break

    if not name and reverse_name:
        name = reverse_name
        provider = str(reverse.get("provider") or provider)

    if not address and reverse_address:
        address = reverse_address
        provider = provider or str(reverse.get("provider") or "")

    # Pick a different nearby named object as landmark. Prefer closer places;
    # among roughly equal distances, prefer higher-value POI types.
    landmark = ""
    landmark_distance: int | None = None
    landmark_candidates = []
    for item in nearby:
        candidate = _meaningful_name(item.get("name"))
        if not candidate:
            continue
        if name and re.sub(r"\W+", "", candidate.lower()) == re.sub(
            r"\W+", "", name.lower()
        ):
            continue
        landmark_candidates.append(item)

    landmark_candidates.sort(
        key=lambda item: (
            int(float(item.get("distance_m") or 999999) // 25),
            -int(item.get("type_score") or 0),
            float(item.get("distance_m") or 999999),
        )
    )
    if landmark_candidates:
        item = landmark_candidates[0]
        landmark = _meaningful_name(item.get("name"))
        landmark_distance = int(round(float(item.get("distance_m") or 0)))

    if not landmark and name:
        landmark = name
        if primary_candidate:
            landmark_distance = int(
                round(float(primary_candidate.get("distance_m") or 0))
            )

    return name, address, landmark, landmark_distance, provider


async def resolve_location_intelligence(location: dict | None) -> dict:
    """Enrich a location without ever making map failure block intake."""
    base = dict(location or {})
    coords = _valid_lat_lon(base)
    if not coords:
        return base

    lat, lon = coords
    base["lat"] = lat
    base["lon"] = lon

    direct_name = _meaningful_name(base.get("name"))
    direct_address = _clean(base.get("address"), 500)

    if not _env_bool("LOCATION_INTELLIGENCE_ENABLED", True):
        if direct_name:
            base["name"] = direct_name
        elif _looks_like_coordinates(str(base.get("name") or "")):
            base["name"] = ""
        if direct_address:
            base["address"] = direct_address
        elif _looks_like_coordinates(str(base.get("address") or "")):
            base["address"] = ""
        base["location_intelligence_version"] = "5.1-osm-public-disabled"
        return base

    cached = await _cache_get(lat, lon)
    if cached is not None:
        reverse, nearby = cached
        cache_hit = True
    else:
        timeout = _env_float("LOCATION_LOOKUP_TIMEOUT_SECONDS", 7, 2, 20)
        radius_m = _env_float("LOCATION_LANDMARK_RADIUS_METERS", 150, 30, 500)
        # Different public services can be queried concurrently. Each service
        # still serializes its own requests globally to avoid bursts.
        reverse, nearby = await asyncio.gather(
            _safe_reverse(lat, lon, timeout),
            _safe_nearby(lat, lon, timeout, radius_m),
        )
        await _cache_put(lat, lon, reverse, nearby)
        cache_hit = False

    name, address, landmark, landmark_distance, provider = _select_place_and_landmark(
        direct_name,
        direct_address,
        reverse,
        nearby,
    )

    if name:
        base["name"] = name
    elif _looks_like_coordinates(str(base.get("name") or "")):
        base["name"] = ""

    if address:
        base["address"] = address
    elif _looks_like_coordinates(str(base.get("address") or "")):
        base["address"] = ""

    if landmark:
        base["auto_landmark"] = landmark[:500]
    if landmark_distance is not None:
        base["auto_landmark_distance_m"] = max(0, int(landmark_distance))
    if provider:
        base["resolved_provider"] = provider

    base["location_cache_hit"] = cache_hit
    base["location_attribution"] = "OpenStreetMap contributors"
    base["location_intelligence_version"] = "5.1-osm-public"
    return base


def automatic_landmark(location: dict | None) -> str:
    location = location or {}
    return _meaningful_name(location.get("auto_landmark"))[:500]


def _distance_suffix(location: dict | None) -> str:
    location = location or {}
    try:
        distance = int(location.get("auto_landmark_distance_m"))
    except (TypeError, ValueError):
        return ""
    if distance <= 5:
        return ""
    return f" (sekitar {distance} m)"


def format_location_short(location: dict | None) -> str:
    """Short human-readable location; never returns raw coordinates."""
    location = location or {}
    name = _meaningful_name(location.get("name"))
    address = _clean(location.get("address"), 500)
    landmark = automatic_landmark(location)

    if name and address:
        return f"{name}, {address}"
    if name:
        return name
    if address:
        return address
    if landmark:
        return f"dekat {landmark}{_distance_suffix(location)}"
    return "titik Share Location yang Anda kirim"


def format_location_confirmation(location: dict | None) -> str:
    """Customer-facing confirmation text without raw lat/lon."""
    location = location or {}
    name = _meaningful_name(location.get("name"))
    address = _clean(location.get("address"), 500)
    landmark = automatic_landmark(location)
    landmark_suffix = _distance_suffix(location)

    lines: list[str] = []
    if name:
        lines.append(f"Lokasinya sudah saya temukan: *{name}*.")
    elif address:
        lines.append("Lokasinya sudah saya temukan dari titik yang Anda kirim.")
    else:
        lines.append(
            "Share Location sudah saya terima. Nama tempatnya belum terbaca di peta, "
            "tetapi titiknya tetap tersimpan untuk pencarian mekanik."
        )

    if address:
        lines.append(f"Alamat: {address}.")

    if landmark and (not name or landmark.lower() != name.lower()):
        lines.append(f"Patokan terdekat: *{landmark}*{landmark_suffix}.")
    elif landmark and name and landmark.lower() == name.lower():
        lines.append(f"Patokan lokasi: *{landmark}*.")

    lines.append(
        "Apakah benar mesin yang akan diservis berada di lokasi ini? "
        "Boleh jawab *iya/betul/nggih*, atau kirim Share Location ulang jika salah."
    )

    if _env_bool("LOCATION_SHOW_ATTRIBUTION", True) and location.get("location_attribution"):
        lines.append("_Data lokasi: OpenStreetMap contributors._")

    return "\n".join(lines)
