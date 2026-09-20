import asyncio

from app import customer, location_intelligence as li
from app.types import IncomingMessage


def _msg(text: str = "", location=None, phone: str = "6200000000000") -> IncomingMessage:
    return IncomingMessage(
        message_id="location-v5-1-test",
        phone=phone,
        sender_name="Customer Test",
        text=text,
        location=location,
        image=None,
        video=None,
        document=None,
        media_type=None,
        media_path=None,
        raw_payload={},
    )


def test_resolver_uses_exact_company_and_nearby_landmark(monkeypatch):
    monkeypatch.setattr(li, "_google_key", lambda: "")

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
                "types": ["shop", "convenience_store"],
                "type_score": 96,
                "provider": "openstreetmap_overpass",
            },
        ]

    monkeypatch.setattr(li, "_osm_reverse", fake_reverse)
    monkeypatch.setattr(li, "_osm_nearby", fake_nearby)

    resolved = asyncio.run(
        li.resolve_location_intelligence(
            {"lat": -7.12345, "lon": 110.12345, "source": "WHATSAPP_SHARE_LOCATION"}
        )
    )

    assert resolved["name"] == "PT Maju Jaya"
    assert resolved["auto_landmark"] == "Indomaret Lemah Abang"
    assert resolved["auto_landmark_distance_m"] == 55
    assert resolved["lat"] == -7.12345
    assert resolved["lon"] == 110.12345

    reply = li.format_location_confirmation(resolved)
    assert "PT Maju Jaya" in reply
    assert "Indomaret Lemah Abang" in reply
    assert "-7.12345" not in reply
    assert "110.12345" not in reply


def test_resolver_preserves_whatsapp_place_name(monkeypatch):
    monkeypatch.setattr(li, "_google_key", lambda: "")

    async def fake_reverse(lat, lon, timeout):
        return {
            "name": "Gedung Lain",
            "address": "Jl. Ahmad Yani, Semarang",
            "types": [],
            "provider": "openstreetmap_nominatim",
        }

    async def fake_nearby(lat, lon, timeout, radius_m):
        return [
            {
                "name": "Masjid Al Ikhlas",
                "address": "Jl. Ahmad Yani, Semarang",
                "lat": lat,
                "lon": lon + 0.0004,
                "distance_m": 42.0,
                "types": ["amenity", "mosque"],
                "type_score": 92,
                "provider": "openstreetmap_overpass",
            }
        ]

    monkeypatch.setattr(li, "_osm_reverse", fake_reverse)
    monkeypatch.setattr(li, "_osm_nearby", fake_nearby)

    resolved = asyncio.run(
        li.resolve_location_intelligence(
            {
                "lat": -7.0,
                "lon": 110.0,
                "name": "CV Sumber Teknik",
                "address": "Jl. Ahmad Yani No. 5",
                "source": "WHATSAPP_SHARE_LOCATION",
            }
        )
    )

    assert resolved["name"] == "CV Sumber Teknik"
    assert resolved["address"] == "Jl. Ahmad Yani No. 5"
    assert resolved["auto_landmark"] == "Masjid Al Ikhlas"


def test_confirmation_never_falls_back_to_raw_coordinates():
    location = {
        "lat": -7.123456,
        "lon": 110.654321,
        "source": "WHATSAPP_SHARE_LOCATION",
    }
    reply = li.format_location_confirmation(location)
    assert "-7.123456" not in reply
    assert "110.654321" not in reply
    assert "Share Location" in reply


def test_short_location_never_returns_coordinates():
    text = li.format_location_short({"lat": -7.1, "lon": 110.2})
    assert text == "titik Share Location yang Anda kirim"


def test_customer_location_state_uses_resolved_human_location(monkeypatch):
    payload = {
        "customer_id": "c",
        "machine_count": 1,
        "items": [{"machine": "Juki", "problem": "sering loncat"}],
    }
    saved = {}

    async def fake_get_state(phone):
        return {"state": "cust_location", "payload": payload}

    async def fake_resolve(location):
        return {
            **location,
            "name": "PT Maju Jaya",
            "address": "Jl. Industri No. 10, Ungaran",
            "auto_landmark": "Indomaret Lemah Abang",
            "auto_landmark_distance_m": 55,
        }

    async def fake_set_state(phone, state, new_payload):
        saved["state"] = state
        saved["payload"] = dict(new_payload)

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "resolve_location_intelligence", fake_resolve)
    monkeypatch.setattr(customer, "set_state", fake_set_state)

    reply = asyncio.run(
        customer.handle_customer_state(
            _msg(location={"lat": -7.1, "lon": 110.2, "source": "WHATSAPP_SHARE_LOCATION"})
        )
    )

    assert saved["state"] == "cust_location_confirm"
    assert saved["payload"]["location"]["name"] == "PT Maju Jaya"
    assert "PT Maju Jaya" in reply
    assert "Indomaret Lemah Abang" in reply
    assert "-7.1" not in reply
    assert "110.2" not in reply


def test_landmark_benar_uses_automatic_landmark(monkeypatch):
    phone = "6200000000000"
    payload = {
        "customer_id": "customer-id",
        "items": [{"machine": "Juki", "problem": "sering loncat"}],
        "location": {
            "lat": -7.0,
            "lon": 110.0,
            "name": "PT Maju Jaya",
            "address": "Jl. Industri No. 10",
            "auto_landmark": "Indomaret Lemah Abang",
            "auto_landmark_distance_m": 55,
            "source": "WHATSAPP_SHARE_LOCATION",
        },
        "customer_media": [],
    }
    captured = {}

    async def fake_get_state(value):
        return {"state": "cust_landmark", "payload": payload}

    async def fake_understand(text, state="", context=None):
        return {
            "intent": "GENERAL_QUESTION",
            "control": "YES",
            "machines": [],
            "fields": {"name": None, "machine_description": None, "problem": None, "landmark": None},
            "questions": [],
            "corrections": [],
            "provider": "local",
        }

    async def fake_get_customer(value, name=None):
        return {"id": "customer-id", "name": "Customer"}

    async def fake_create_order(customer_id, location, landmark, items):
        captured["landmark"] = landmark
        captured["location"] = location
        return {"id": "order-id", "order_no": "MTK-TEST-LOC"}

    async def fake_persist(*args, **kwargs):
        return 0

    async def fake_clear(*args, **kwargs):
        return None

    async def fake_offer(order_id, notify_customer=True):
        return False

    monkeypatch.setattr(customer, "get_state", fake_get_state)
    monkeypatch.setattr(customer, "understand_customer_message", fake_understand)
    monkeypatch.setattr(customer, "quick_customer_signals", lambda text, state="": {"control": "YES", "machine_count": None})
    monkeypatch.setattr(customer, "get_or_create_customer", fake_get_customer)
    monkeypatch.setattr(customer, "create_order", fake_create_order)
    monkeypatch.setattr(customer, "_persist_customer_media", fake_persist)
    monkeypatch.setattr(customer, "clear_state", fake_clear)
    monkeypatch.setattr(customer, "start_offer_batch", fake_offer)

    reply = asyncio.run(customer.handle_customer_state(_msg("BENAR", phone=phone)))

    assert captured["landmark"] == "Indomaret Lemah Abang"
    assert captured["location"]["name"] == "PT Maju Jaya"
    assert "MTK-TEST-LOC" in reply
