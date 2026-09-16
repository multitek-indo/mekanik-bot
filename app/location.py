import math
import re
from datetime import datetime, timezone


def normalize_location_payload(payload: dict) -> dict | None:
    loc = payload.get("location") or payload.get("live_location")
    if not isinstance(loc, dict):
        return None
    lat = loc.get("degreesLatitude", loc.get("latitude"))
    lon = loc.get("degreesLongitude", loc.get("longitude"))
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return {
        "lat": lat,
        "lon": lon,
        "name": str(loc.get("name") or "").strip(),
        "address": str(loc.get("address") or "").strip(),
        "source": "WHATSAPP_LIVE_LOCATION" if payload.get("live_location") else "WHATSAPP_SHARE_LOCATION",
    }


def parse_latlon(text: str | None) -> dict | None:
    m = re.search(r"(-?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)", text or "")
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return {"lat": lat, "lon": lon, "name": "", "address": "", "source": "TEXT_LATLON"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def location_label(location: dict | None) -> str:
    if not location:
        return "lokasi tidak tersedia"
    label = location.get("address") or location.get("name")
    if label:
        return str(label)
    return f"{location['lat']:.6f}, {location['lon']:.6f}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
