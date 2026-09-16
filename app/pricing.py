from .config import settings


def rupiah(value: int | float | None) -> str:
    amount = int(value or 0)
    return "Rp" + f"{amount:,}".replace(",", ".")


def booking_fee_for_distance(distance_km: float) -> int | None:
    if distance_km <= 5:
        return settings.booking_fee_0_5km
    if distance_km <= 10:
        return settings.booking_fee_5_10km
    if distance_km <= 20:
        return settings.booking_fee_10_20km
    if distance_km <= settings.booking_manual_over_km:
        return settings.booking_fee_20_30km
    return None


def booking_tier_text() -> str:
    return (
        f"0-5 km {rupiah(settings.booking_fee_0_5km)}, "
        f">5-10 km {rupiah(settings.booking_fee_5_10km)}, "
        f">10-20 km {rupiah(settings.booking_fee_10_20km)}, "
        f">20-{int(settings.booking_manual_over_km)} km {rupiah(settings.booking_fee_20_30km)}; "
        f"di atas {int(settings.booking_manual_over_km)} km dikonfirmasi manual."
    )


def successful_bill(booking_fee: int, labour_and_inspection: int, parts: int) -> dict:
    # Booking is a minimum visit/travel payment and also a credit toward labour.
    effective_labour = max(int(booking_fee), int(labour_and_inspection))
    total = effective_labour + int(parts)
    additional_due = max(0, int(labour_and_inspection) - int(booking_fee)) + int(parts)
    return {
        "booking_fee": int(booking_fee),
        "labour_and_inspection": int(labour_and_inspection),
        "parts": int(parts),
        "effective_labour": effective_labour,
        "total": total,
        "additional_due": additional_due,
    }


def success_settlement(booking_fee: int, labour_and_inspection: int, parts: int) -> dict:
    bill = successful_bill(booking_fee, labour_and_inspection, parts)
    platform_fee = round(bill["effective_labour"] * settings.success_platform_percent / 100)
    technician_payout = bill["effective_labour"] - platform_fee + bill["parts"]
    return {
        **bill,
        "customer_refund": 0,
        "platform_fee": platform_fee,
        "technician_payout": technician_payout,
    }


def unrepaired_settlement(booking_fee: int) -> dict:
    gross = int(booking_fee)
    customer_refund = round(gross * settings.fail_customer_refund_percent / 100)
    technician_payout = round(gross * settings.fail_technician_percent / 100)
    platform_fee = gross - customer_refund - technician_payout
    return {
        "gross": gross,
        "customer_refund": customer_refund,
        "technician_payout": technician_payout,
        "platform_fee": platform_fee,
    }
