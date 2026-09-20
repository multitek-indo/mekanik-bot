"""Location Intelligence for Multitek Service.

Purpose
-------
Turn a WhatsApp Share Location (lat/lon) into customer-friendly place data
without ever inventing a place name.

Resolution order:
1. Preserve useful WhatsApp-provided name/address.
2. Google Maps/Places when GOOGLE_MAPS_API_KEY or LOCATION_GOOGLE_API_KEY exists.
3. OpenStreetMap Nominatim + Overpass fallback.
4. Keep coordinates internally, but never expose raw coordinates in customer text.

All external lookups are best-effort. Failure never blocks service intake.
"""

from __future__ import annotations

import logging
import math
import os
import re
from typing import Any

import httpx

log = logging.getLogger("multitek-location")

_GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_GOOGLE_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
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

_POI_TYPE_PRIORITY = {
    # Google Places primary types / OSM-derived categories we value for landmarks.
    "corporate_office": 100,
    "office": 100,
    "factory": 100,
    "industrial": 98,
    "store": 96,
    "shopping_mall": 94,
    "supermarket": 94,
    "convenience_store": 94,
    "restaurant": 90,
    "cafe": 88,
    "hotel": 88,
    "hospital": 92,
    "doctor": 88,
    "pharmacy": 88,
    "school": 88,
    "university": 88,
    "place_of_worship": 90,
    "mosque": 92,
    "church": 90,
    "bank": 88,
    "atm": 80,
    "gas_station": 90,
    "police": 88,
    "government_office": 88,
    "warehouse": 92,
    "premise": 82,
    "establishment": 80,
    "point_of_interest": 75,
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


def _google_key() -> str:
    return (
        os.getenv("LOCATION_GOOGLE_API_KEY")
        or os.getenv("GOOGLE_MAPS_API_KEY")
        or ""
    ).strip()


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


def _candidate_sort_key(item: dict) -> tuple:
    # Prefer high-value POIs, then proximity.
    score = int(item.get("type_score") or 0)
    distance = float(item.get("distance_m") or 999999)
    return (-score, distance)


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
        copy = dict(item)
        copy["name"] = name
        out.append(copy)
    return out


def _osm_address_text(address: dict | None, fallback: str = "") -> str:
    address = address or {}
    road = _clean(address.get("road") or address.get("pedestrian") or address.get("residential"))
    house = _clean(address.get("house_number"))
    village = _clean(
        address.get("village")
        or address.get("suburb")
        or address.get("neighbourhood")
        or address.get("quarter")
    )
    district = _clean(address.get("city_district") or address.get("district") or address.get("county"))
    city = _clean(address.get("city") or address.get("town") or address.get("municipality"))
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
        if name and not re.fullmatch(r"(?:yes|residential|commercial|industrial|house)", name.lower()):
            return name
    return ""


async def _google_reverse(lat: float, lon: float, key: str, timeout: float) -> dict:
    params = {
        "latlng": f"{lat:.7f},{lon:.7f}",
        "key": key,
        "language": "id",
        "region": "id",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(_GOOGLE_GEOCODE_URL, params=params)
        response.raise_for_status()
        data = response.json()

    if data.get("status") != "OK" or not data.get("results"):
        return {}

    result = data["results"][0]
    address = _clean(result.get("formatted_address"), 500)
    types = [str(x) for x in result.get("types") or []]

    # Reverse Geocoding often gives an address rather than a business name.
    # We only use its first address component as a name when it is not numeric/road-like.
    name = ""
    components = result.get("address_components") or []
    if components:
        first = _meaningful_name(components[0].get("long_name"))
        first_types = {str(x) for x in components[0].get("types") or []}
        if first and not first_types.intersection({"street_number", "route", "postal_code"}):
            name = first

    return {
        "name": name,
        "address": address,
        "types": types,
        "provider": "google_geocoding",
    }


async def _google_nearby(lat: float, lon: float, key: str, timeout: float, radius_m: float) -> list[dict]:
    body = {
        "maxResultCount": 15,
        "rankPreference": "DISTANCE",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius_m,
            }
        },
        "languageCode": "id",
        "regionCode": "ID",
    }
    headers = {
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": (
            "places.displayName,places.formattedAddress,places.location,"
            "places.primaryType,places.types"
        ),
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.post(_GOOGLE_NEARBY_URL, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    out: list[dict] = []
    for place in data.get("places") or []:
        loc = place.get("location") or {}
        try:
            plat = float(loc.get("latitude"))
            plon = float(loc.get("longitude"))
        except (TypeError, ValueError):
            continue
        display = place.get("displayName") or {}
        name = _meaningful_name(display.get("text"))
        if not name:
            continue
        types = [str(x) for x in place.get("types") or []]
        primary = str(place.get("primaryType") or "")
        if primary and primary not in types:
            types.insert(0, primary)
        out.append(
            {
                "name": name,
                "address": _clean(place.get("formattedAddress"), 500),
                "lat": plat,
                "lon": plon,
                "distance_m": _distance_m(lat, lon, plat, plon),
                "types": types,
                "type_score": _type_score(types),
                "provider": "google_places",
            }
        )
    return out


async def _osm_reverse(lat: float, lon: float, timeout: float) -> dict:
    params = {
        "lat": f"{lat:.7f}",
        "lon": f"{lon:.7f}",
        "format": "jsonv2",
        "zoom": 18,
        "addressdetails": 1,
        "namedetails": 1,
        "accept-language": "id",
    }
    headers = {
        "User-Agent": os.getenv(
            "LOCATION_OSM_USER_AGENT",
            "MultitekService/1.0 (customer-location-resolver)",
        )
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        response = await client.get(_NOMINATIM_REVERSE_URL, params=params)
        response.raise_for_status()
        data = response.json()

    return {
        "name": _name_from_osm(data),
        "address": _osm_address_text(data.get("address"), data.get("display_name") or ""),
        "types": [
            _clean(data.get("category"), 80),
            _clean(data.get("type"), 80),
        ],
        "provider": "openstreetmap_nominatim",
    }


async def _osm_nearby(lat: float, lon: float, timeout: float, radius_m: float) -> list[dict]:
    # Request only named objects. This avoids returning every anonymous building.
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
    headers = {
        "User-Agent": os.getenv(
            "LOCATION_OSM_USER_AGENT",
            "MultitekService/1.0 (customer-location-resolver)",
        )
    }
    async with httpx.AsyncClient(timeout=timeout + 3, follow_redirects=True, headers=headers) as client:
        response = await client.post(_OVERPASS_URL, content=query)
        response.raise_for_status()
        data = response.json()

    out: list[dict] = []
    for element in data.get("elements") or []:
        tags = element.get("tags") or {}
        name = _meaningful_name(tags.get("name") or tags.get("brand") or tags.get("operator"))
        if not name:
            continue
        center = element.get("center") or {}
        try:
            plat = float(element.get("lat") if element.get("lat") is not None else center.get("lat"))
            plon = float(element.get("lon") if element.get("lon") is not None else center.get("lon"))
        except (TypeError, ValueError):
            continue

        types: list[str] = []
        for key in ("office", "shop", "amenity", "tourism", "industrial", "building", "leisure"):
            value = _clean(tags.get(key), 80)
            if value:
                types.append(value)
                if key in {"office", "shop", "industrial"}:
                    types.append(key)
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


def _select_place_and_landmark(
    lat: float,
    lon: float,
    direct_name: str,
    direct_address: str,
    reverse: dict,
    nearby: list[dict],
) -> tuple[str, str, str, int | None, str]:
    exact_place_max_m = _env_float("LOCATION_EXACT_PLACE_MAX_METERS", 35, 5, 100)
    nearby = _dedupe_candidates(nearby)

    # Sort by a balanced priority. Very close named objects are still favored.
    nearby.sort(key=lambda item: (float(item.get("distance_m") or 999999), -int(item.get("type_score") or 0)))

    name = _meaningful_name(direct_name)
    address = _clean(direct_address, 500)
    provider = "whatsapp" if (name or address) else ""

    reverse_name = _meaningful_name(reverse.get("name"))
    reverse_address = _clean(reverse.get("address"), 500)

    primary_candidate: dict | None = None
    if not name:
        for item in nearby:
            if float(item.get("distance_m") or 999999) <= exact_place_max_m:
                primary_candidate = item
                name = _meaningful_name(item.get("name"))
                if name:
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

    # Landmark should ideally be a different named object nearby.
    landmark = ""
    landmark_distance: int | None = None
    for item in nearby:
        candidate = _meaningful_name(item.get("name"))
        if not candidate:
            continue
        if name and re.sub(r"\W+", "", candidate.lower()) == re.sub(r"\W+", "", name.lower()):
            continue
        distance = int(round(float(item.get("distance_m") or 0)))
        landmark = candidate
        landmark_distance = distance
        break

    # If there is no second landmark, the exact named place itself is useful
    # as an automatic landmark for the mechanic (PT/CV/store/etc.).
    if not landmark and name:
        landmark = name
        if primary_candidate:
            landmark_distance = int(round(float(primary_candidate.get("distance_m") or 0)))

    return name, address, landmark, landmark_distance, provider


async def resolve_location_intelligence(location: dict | None) -> dict:
    """Return the same location plus human-readable place/address/landmark.

    This function is deliberately fail-open: external map errors never block
    intake. Coordinates are preserved for matching and distance calculations.
    """
    base = dict(location or {})
    coords = _valid_lat_lon(base)
    if not coords:
        return base

    lat, lon = coords
    direct_name = _meaningful_name(base.get("name"))
    direct_address = _clean(base.get("address"), 500)
    timeout = _env_float("LOCATION_LOOKUP_TIMEOUT_SECONDS", 8, 2, 20)
    radius_m = _env_float("LOCATION_LANDMARK_RADIUS_METERS", 150, 30, 500)

    reverse: dict = {}
    nearby: list[dict] = []
    provider_errors: list[str] = []

    key = _google_key()
    if key:
        try:
            reverse = await _google_reverse(lat, lon, key, timeout)
        except Exception as exc:
            provider_errors.append("google_reverse")
            log.warning("Google reverse geocoding unavailable: %s", type(exc).__name__)
        try:
            nearby = await _google_nearby(lat, lon, key, timeout, radius_m)
        except Exception as exc:
            provider_errors.append("google_nearby")
            log.warning("Google nearby places unavailable: %s", type(exc).__name__)

    # OSM fallback fills only missing data; Google stays preferred when present.
    if _env_bool("LOCATION_OSM_FALLBACK_ENABLED", True):
        if not reverse:
            try:
                reverse = await _osm_reverse(lat, lon, timeout)
            except Exception as exc:
                provider_errors.append("osm_reverse")
                log.warning("OSM reverse geocoding unavailable: %s", type(exc).__name__)
        if not nearby:
            try:
                nearby = await _osm_nearby(lat, lon, timeout, radius_m)
            except Exception as exc:
                provider_errors.append("osm_nearby")
                log.warning("OSM nearby lookup unavailable: %s", type(exc).__name__)

    name, address, landmark, landmark_distance, provider = _select_place_and_landmark(
        lat,
        lon,
        direct_name,
        direct_address,
        reverse,
        nearby,
    )

    base["lat"] = lat
    base["lon"] = lon
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
    if provider_errors:
        base["resolver_fallbacks"] = provider_errors[:4]
    base["location_intelligence_version"] = "5.1"
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
    return "\n".join(lines)
