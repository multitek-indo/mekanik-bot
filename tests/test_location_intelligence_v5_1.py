import asyncio

from app import location_intelligence as li


def _reset_env(monkeypatch):
    monkeypatch.setenv("LOCATION_INTELLIGENCE_ENABLED", "true")
    monkeypatch.setenv("LOCATION_CACHE_TTL_SECONDS", "86400")
    monkeypatch.setenv("LOCATION_CACHE_COORD_DECIMALS", "5")
    monkeypatch.setenv("LOCATION_OVERPASS_MAX_CALLS_PER_DAY", "80")
    monkeypatch.setenv("LOCATION_SHOW_ATTRIBUTION", "true")


def test_resolver_uses_company_and_nearby_landmark(monkeypatch):
    _reset_env(monkeypatch)
    asyncio.run(li.clear_location_cache())

    async def fake_reverse(lat, lon, timeout):
        return {
            "name": "",
            "address": "Jl. Industri No. 10, Ungaran, Jawa Tengah",
            "types": [],
            "provider": "openstreetmap_nominatim",
        }

    async def fake_nearby(lat, lon, timeout, radius_m):
        return [
            {
                "name": "PT Maju Jaya",
                "address": "Jl. Industri No. 10, Ungaran",
                "lat": lat + 0.00003,
                "lon": lon,
                "distance_m": 3.3,
                "types": ["office", "industrial"],
                "type_score": 100,
                "provider": "openstreetmap_overpass",
            },
            {
                "name": "Indomaret Lemah Abang",
                "address": "Jl. Industri, Ungaran",
                "lat": lat + 0.00050,
                "lon": lon,
                "distance_m": 55.0,
                "types": ["shop", "convenience"],
                "type_score": 96,
                "provider": "openstreetmap_overpass",
            },
        ]

    monkeypatch.setattr(li, "_safe_reverse", fake_reverse)
    monkeypatch.setattr(li, "_safe_nearby", fake_nearby)

    resolved = asyncio.run(
        li.resolve_location_intelligence(
            {"lat": -7.12345, "lon": 110.12345, "source": "WHATSAPP_SHARE_LOCATION"}
        )
    )

    assert resolved["name"] == "PT Maju Jaya"
    assert resolved["auto_landmark"] == "Indomaret Lemah Abang"
    assert resolved["auto_landmark_distance_m"] == 55
    assert resolved["location_cache_hit"] is False
    assert resolved["location_attribution"] == "OpenStreetMap contributors"


def test_cache_prevents_second_provider_lookup(monkeypatch):
    _reset_env(monkeypatch)
    asyncio.run(li.clear_location_cache())
    calls = {"reverse": 0, "nearby": 0}

    async def fake_reverse(lat, lon, timeout):
        calls["reverse"] += 1
        return {"name": "", "address": "Jl. Test", "provider": "openstreetmap_nominatim"}

    async def fake_nearby(lat, lon, timeout, radius_m):
        calls["nearby"] += 1
        return []

    monkeypatch.setattr(li, "_safe_reverse", fake_reverse)
    monkeypatch.setattr(li, "_safe_nearby", fake_nearby)

    first = asyncio.run(li.resolve_location_intelligence({"lat": -7.2, "lon": 110.2}))
    second = asyncio.run(li.resolve_location_intelligence({"lat": -7.2, "lon": 110.2}))

    assert calls == {"reverse": 1, "nearby": 1}
    assert first["location_cache_hit"] is False
    assert second["location_cache_hit"] is True


def test_nearby_coordinate_rounding_reuses_cache(monkeypatch):
    _reset_env(monkeypatch)
    monkeypatch.setenv("LOCATION_CACHE_COORD_DECIMALS", "5")
    asyncio.run(li.clear_location_cache())
    calls = {"count": 0}

    async def fake_reverse(lat, lon, timeout):
        calls["count"] += 1
        return {"address": "Jl. Test", "provider": "openstreetmap_nominatim"}

    async def fake_nearby(lat, lon, timeout, radius_m):
        return []

    monkeypatch.setattr(li, "_safe_reverse", fake_reverse)
    monkeypatch.setattr(li, "_safe_nearby", fake_nearby)

    asyncio.run(li.resolve_location_intelligence({"lat": -7.123451, "lon": 110.123451}))
    result = asyncio.run(li.resolve_location_intelligence({"lat": -7.123452, "lon": 110.123452}))

    assert calls["count"] == 1
    assert result["location_cache_hit"] is True


def test_whatsapp_name_has_priority(monkeypatch):
    _reset_env(monkeypatch)
    asyncio.run(li.clear_location_cache())

    async def fake_reverse(lat, lon, timeout):
        return {
            "name": "Gedung Lain",
            "address": "Jl. Ahmad Yani, Semarang",
            "provider": "openstreetmap_nominatim",
        }

    async def fake_nearby(lat, lon, timeout, radius_m):
        return []

    monkeypatch.setattr(li, "_safe_reverse", fake_reverse)
    monkeypatch.setattr(li, "_safe_nearby", fake_nearby)

    resolved = asyncio.run(
        li.resolve_location_intelligence(
            {
                "lat": -7.0,
                "lon": 110.0,
                "name": "CV Sumber Teknik",
                "address": "Jl. Ahmad Yani No. 5",
            }
        )
    )

    assert resolved["name"] == "CV Sumber Teknik"
    assert resolved["address"] == "Jl. Ahmad Yani No. 5"


def test_feature_flag_disables_external_lookup(monkeypatch):
    monkeypatch.setenv("LOCATION_INTELLIGENCE_ENABLED", "false")
    asyncio.run(li.clear_location_cache())

    async def should_not_run(*args, **kwargs):
        raise AssertionError("external lookup should not run")

    monkeypatch.setattr(li, "_safe_reverse", should_not_run)
    monkeypatch.setattr(li, "_safe_nearby", should_not_run)

    resolved = asyncio.run(
        li.resolve_location_intelligence(
            {"lat": -7.0, "lon": 110.0, "name": "Toko ABC", "address": "Jl. Mawar"}
        )
    )

    assert resolved["name"] == "Toko ABC"
    assert resolved["address"] == "Jl. Mawar"
    assert "disabled" in resolved["location_intelligence_version"]


def test_confirmation_never_exposes_coordinates(monkeypatch):
    _reset_env(monkeypatch)
    location = {
        "lat": -7.123456,
        "lon": 110.654321,
        "name": "PT ABC",
        "address": "Jl. Industri",
        "auto_landmark": "Masjid Al Ikhlas",
        "auto_landmark_distance_m": 70,
        "location_attribution": "OpenStreetMap contributors",
    }
    reply = li.format_location_confirmation(location)
    assert "-7.123456" not in reply
    assert "110.654321" not in reply
    assert "PT ABC" in reply
    assert "Masjid Al Ikhlas" in reply
    assert "OpenStreetMap" in reply


def test_short_location_never_returns_coordinates():
    text = li.format_location_short({"lat": -7.1, "lon": 110.2})
    assert text == "titik Share Location yang Anda kirim"


def test_automatic_landmark_falls_back_to_exact_named_place(monkeypatch):
    _reset_env(monkeypatch)
    asyncio.run(li.clear_location_cache())

    async def fake_reverse(lat, lon, timeout):
        return {"name": "Toko Sumber Jaya", "address": "Jl. Raya", "provider": "openstreetmap_nominatim"}

    async def fake_nearby(lat, lon, timeout, radius_m):
        return []

    monkeypatch.setattr(li, "_safe_reverse", fake_reverse)
    monkeypatch.setattr(li, "_safe_nearby", fake_nearby)

    resolved = asyncio.run(li.resolve_location_intelligence({"lat": -7.3, "lon": 110.3}))
    assert resolved["name"] == "Toko Sumber Jaya"
    assert resolved["auto_landmark"] == "Toko Sumber Jaya"
