from app.location import normalize_location_payload, parse_latlon, haversine_km


def test_static_location_payload():
    payload = {
        'location': {
            'degreesLatitude': -6.2,
            'degreesLongitude': 106.8,
            'name': 'Factory',
            'address': 'Jl. Test',
        }
    }
    loc = normalize_location_payload(payload)
    assert loc['lat'] == -6.2
    assert loc['lon'] == 106.8
    assert loc['address'] == 'Jl. Test'
    assert loc['source'] == 'WHATSAPP_SHARE_LOCATION'


def test_live_location_payload_supported_but_marked():
    payload = {'live_location': {'degreesLatitude': -7.8, 'degreesLongitude': 110.4}}
    loc = normalize_location_payload(payload)
    assert loc['source'] == 'WHATSAPP_LIVE_LOCATION'


def test_latlon_fallback():
    loc = parse_latlon('-6.9667,110.4167')
    assert loc['lat'] == -6.9667
    assert loc['lon'] == 110.4167


def test_haversine_zero():
    assert haversine_km(-6.9, 110.4, -6.9, 110.4) == 0
