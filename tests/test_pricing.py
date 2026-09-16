from app.pricing import booking_fee_for_distance, successful_bill, unrepaired_settlement


def test_booking_tiers():
    assert booking_fee_for_distance(1) == 20000
    assert booking_fee_for_distance(5) == 20000
    assert booking_fee_for_distance(7) == 30000
    assert booking_fee_for_distance(15) == 40000
    assert booking_fee_for_distance(25) == 50000
    assert booking_fee_for_distance(31) is None


def test_booking_is_credit_against_labour():
    bill = successful_bill(30000, 100000, 0)
    assert bill['total'] == 100000
    assert bill['additional_due'] == 70000


def test_light_repair_below_booking_has_no_extra_labour():
    bill = successful_bill(30000, 20000, 0)
    assert bill['total'] == 30000
    assert bill['additional_due'] == 0


def test_parts_are_added_after_booking_credit():
    bill = successful_bill(30000, 100000, 50000)
    assert bill['total'] == 150000
    assert bill['additional_due'] == 120000


def test_unrepairable_60_30_10():
    s = unrepaired_settlement(30000)
    assert s['customer_refund'] == 18000
    assert s['technician_payout'] == 9000
    assert s['platform_fee'] == 3000
