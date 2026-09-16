from app.ai import _fallback


def test_price_question_wins():
    r = _fallback('berapa biaya service mesin obras rusak?')
    assert r['intent'] == 'PRICE_QUESTION'


def test_service_request():
    r = _fallback('mesin obras saya suara kasar dan benang putus')
    assert r['intent'] == 'SERVICE_REQUEST'
