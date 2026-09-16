from .db import pool
from .orders import find_order, order_items
from .pricing import rupiah
from .skills import SKILL_BY_NUMBER


async def ticket_list() -> str:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT o.order_no,o.status,o.booking_payment_status,o.final_payment_status,o.created_at,
                      c.name customer_name,t.name technician_name
               FROM service_orders o
               JOIN customers c ON c.id=o.customer_id
               LEFT JOIN technicians t ON t.id=o.assigned_technician_id
               ORDER BY o.created_at DESC LIMIT 30"""
        )
    if not rows:
        return "Belum ada service order."
    lines = ["*SERVICE ORDER TERBARU*"]
    for r in rows:
        lines.append(
            f"{r['order_no']} | {r['status']} | {r['customer_name'] or '-'} | mekanik {r['technician_name'] or '-'}"
        )
    return "\n".join(lines)


async def order_detail(order_no: str) -> str:
    order = await find_order(order_no)
    if not order:
        return "Nomor service tidak ditemukan."
    items = await order_items(order["id"])
    lines = [
        f"*DETAIL {order_no}*",
        f"Status: {order['status']}",
        f"Customer: {order['customer_name'] or '-'} ({order['customer_wa']})",
        f"Mekanik: {order['technician_name'] or '-'}",
        f"Jarak pilihan: {order['selected_distance_km'] or '-'} km",
        f"Booking: {rupiah(order['booking_fee'])} / {order['booking_payment_status']}",
        f"Pelunasan: {rupiah(order['final_amount_due'])} / {order['final_payment_status']}",
        f"Lokasi: {order['location_address'] or order['location_name'] or '-'}",
        f"Patokan: {order['location_landmark'] or '-'}",
        "",
        "*MESIN*",
    ]
    for item in items:
        lines.append(
            f"{item['item_no']}. {item['machine_text']} | {item['status']} | {item['difficulty'] or '-'}\n"
            f"   Keluhan: {item['complaint']}\n"
            f"   Diagnosis: {item['diagnosis'] or '-'}\n"
            f"   Jasa {rupiah(item['repair_fee'])}, cek {rupiah(item['inspection_fee'])}, part {rupiah(item['parts_fee'])}"
        )
    return "\n".join(lines)


def skill_code_from_number(number: int) -> str | None:
    item = SKILL_BY_NUMBER.get(number)
    return item["code"] if item else None


def owner_help() -> str:
    return (
        "*OWNER COMMAND*\n"
        "TIKET\n"
        "RINCI MTK-...\n"
        "CALON MEKANIK\n"
        "DETAIL MEKANIK MKN-...\n"
        "SETUJUI MEKANIK MKN-...\n"
        "TOLAK MEKANIK MKN-... <alasan>\n"
        "KONFIRMASI BAYAR MTK-...\n"
        "KONFIRMASI PELUNASAN MTK-...\n"
        "SET BOOKING MTK-... <nominal>\n"
        "SETUJUI SETTLEMENT MTK-...\n"
        "PAYOUT MTK-...\n"
        "TARIF\n"
        "SET TARIF <no skill> <INSPEKSI|RINGAN|SEDANG|BERAT> <nominal>"
    )
