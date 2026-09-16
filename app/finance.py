from .config import settings
from .db import pool
from .orders import find_order, order_items, change_status, add_attachment
from .pricing import rupiah, successful_bill, success_settlement, unrepaired_settlement
from .wa import send_text, send_image


def payment_instructions(order_no: str, amount: int, kind: str = "BOOKING") -> str:
    title = "Biaya kunjungan awal" if kind == "BOOKING" else "Pelunasan service"
    bank = (
        f"Bank: *{settings.payment_bank_name}*\n"
        f"No. Rekening: *{settings.payment_bank_account or '[ISI DI .env]'}*\n"
        f"a.n. *{settings.payment_bank_holder}*"
    )
    return (
        f"*{title} — {order_no}*\n"
        f"Total: *{rupiah(amount)}*\n\n"
        f"Transfer bank:\n{bank}\n\n"
        "Atau gunakan QRIS yang dikirim setelah pesan ini.\n\n"
        "Setelah pembayaran, kirim *foto/screenshot bukti pembayaran* di chat ini. "
        "Pembayaran diverifikasi manual oleh owner Multitek."
    )


async def send_payment_request(customer_wa: str, order_no: str, amount: int, kind: str):
    await send_text(customer_wa, payment_instructions(order_no, amount, kind))
    try:
        if settings.qris_image_path:
            await send_image(customer_wa, settings.qris_image_path, f"QRIS Multitek — {order_no} — {rupiah(amount)}")
    except Exception:
        pass


async def submit_payment_proof(phone: str, order_no: str, kind: str, media_path: str, media_type: str, message_id: str) -> str:
    order = await find_order(order_no)
    if not order or order["customer_wa"] != phone:
        return "Nomor service tidak ditemukan atau bukan milik nomor ini."
    kind = kind.upper()
    async with pool().acquire() as conn:
        payment = await conn.fetchrow(
            """SELECT * FROM payments WHERE order_id=$1 AND kind=$2 AND status IN ('PENDING','PROOF_SUBMITTED')
               ORDER BY created_at DESC LIMIT 1""",
            order["id"], kind,
        )
        if not payment:
            return "Tidak ada pembayaran yang sedang menunggu bukti."
        await conn.execute(
            """UPDATE payments SET status='PROOF_SUBMITTED',proof_path=$2,proof_submitted_at=now()
               WHERE id=$1""",
            payment["id"], media_path,
        )
        if kind == "BOOKING":
            await conn.execute(
                "UPDATE service_orders SET status='BOOKING_PROOF_SUBMITTED',booking_payment_status='PROOF_SUBMITTED',updated_at=now() WHERE id=$1",
                order["id"],
            )
        else:
            await conn.execute(
                "UPDATE service_orders SET status='FINAL_PROOF_SUBMITTED',final_payment_status='PROOF_SUBMITTED',updated_at=now() WHERE id=$1",
                order["id"],
            )
    await add_attachment(order["id"], None, "CUSTOMER", phone, f"{kind}_PAYMENT_PROOF", media_type, media_path, message_id)
    await send_text(
        settings.owner_wa_number,
        f"💳 *BUKTI PEMBAYARAN {kind}*\n{order_no}\nCustomer: {order['customer_name'] or order['customer_wa']}\n"
        f"Nominal sistem: {rupiah(payment['amount'])}\n\n"
        + (f"Konfirmasi: *KONFIRMASI BAYAR {order_no}*" if kind == "BOOKING" else f"Konfirmasi: *KONFIRMASI PELUNASAN {order_no}*"),
    )
    try:
        await send_image(settings.owner_wa_number, media_path, f"Bukti pembayaran {kind} — {order_no}")
    except Exception:
        pass
    return "Bukti pembayaran sudah diterima dan sedang diverifikasi oleh Multitek. Mohon tunggu konfirmasi."


async def owner_confirm_booking(order_no: str) -> str:
    order = await find_order(order_no)
    if not order:
        return "Nomor service tidak ditemukan."
    async with pool().acquire() as conn:
        payment = await conn.fetchrow(
            "SELECT * FROM payments WHERE order_id=$1 AND kind='BOOKING' ORDER BY created_at DESC LIMIT 1",
            order["id"],
        )
        if not payment:
            return "Record pembayaran booking tidak ditemukan."
        await conn.execute("UPDATE payments SET status='PAID',paid_at=now() WHERE id=$1", payment["id"])
        await conn.execute(
            """UPDATE service_orders SET booking_payment_status='PAID',status='WAITING_FINAL_LOCATION_CONFIRMATION',updated_at=now()
               WHERE id=$1""",
            order["id"],
        )
    location_text = order["location_address"] or order["location_name"] or f"{order['location_lat']},{order['location_lon']}"
    await send_text(
        order["customer_wa"],
        f"Pembayaran *{rupiah(payment['amount'])}* untuk {order_no} sudah terverifikasi.\n\n"
        f"Sebelum mekanik berangkat, pastikan lokasi mesin masih benar:\n"
        f"{location_text}\n"
        f"Patokan: {order['location_landmark'] or '-'}\n\n"
        f"Balas: *LOKASI BENAR {order_no}*\n"
        f"Jika salah: *UBAH LOKASI {order_no}*",
    )
    if order["technician_wa"]:
        await send_text(order["technician_wa"], f"Pembayaran {order_no} sudah terverifikasi. Tunggu customer mengonfirmasi lokasi final sebelum berangkat.")
    return f"Booking {order_no} dikonfirmasi PAID. Customer diminta konfirmasi lokasi final."


async def owner_confirm_final(order_no: str) -> str:
    order = await find_order(order_no)
    if not order:
        return "Nomor service tidak ditemukan."
    async with pool().acquire() as conn:
        payment = await conn.fetchrow(
            "SELECT * FROM payments WHERE order_id=$1 AND kind='FINAL' ORDER BY created_at DESC LIMIT 1",
            order["id"],
        )
        if not payment:
            return "Record pelunasan tidak ditemukan."
        await conn.execute("UPDATE payments SET status='PAID',paid_at=now() WHERE id=$1", payment["id"])
        await conn.execute(
            """UPDATE service_orders SET final_payment_status='PAID',status='WAITING_CUSTOMER_CONFIRMATION',updated_at=now()
               WHERE id=$1""",
            order["id"],
        )
    await send_text(
        order["customer_wa"],
        f"Pelunasan {order_no} sebesar *{rupiah(payment['amount'])}* sudah terverifikasi.\n"
        f"Jika hasil service sudah baik, balas: *KONFIRMASI SELESAI {order_no}*\n"
        f"Jika ada masalah, balas: *MASALAH {order_no}*",
    )
    return f"Pelunasan {order_no} dikonfirmasi PAID."


async def owner_set_booking(order_no: str, amount: int) -> str:
    if amount < 0:
        return "Nominal tidak valid."
    order = await find_order(order_no)
    if not order:
        return "Nomor service tidak ditemukan."
    async with pool().acquire() as conn:
        await conn.execute(
            """UPDATE service_orders SET booking_fee=$2,status='WAITING_BOOKING_PAYMENT',booking_payment_status='UNPAID',updated_at=now()
               WHERE id=$1""",
            order["id"], amount,
        )
        await conn.execute("INSERT INTO payments(order_id,kind,amount,status) VALUES($1,'BOOKING',$2,'PENDING')", order["id"], amount)
    await send_payment_request(order["customer_wa"], order_no, amount, "BOOKING")
    return f"Booking {order_no} ditetapkan {rupiah(amount)} dan instruksi pembayaran sudah dikirim."


async def compute_final_bill(order_no: str) -> dict | None:
    order = await find_order(order_no)
    if not order:
        return None
    items = await order_items(order["id"])
    labour = 0
    parts = 0
    for item in items:
        if item["status"] == "COMPLETED":
            # Initial machines: diagnosis is absorbed into repair fee.
            # Technician-added machines may have an explicitly approved extra inspection fee.
            labour += int(item["repair_fee"] or 0)
            if item["declared_by"] == "TECHNICIAN":
                labour += int(item["inspection_fee"] or 0)
            parts += int(item["parts_fee"] or 0)
        elif item["status"] == "DECLINED":
            labour += int(item["inspection_fee"] or 0)
    return {"order": order, "items": items, **successful_bill(int(order["booking_fee"] or 0), labour, parts)}


async def prepare_final_payment(order_no: str) -> str:
    bill = await compute_final_bill(order_no)
    if not bill:
        return "Nomor service tidak ditemukan."
    order = bill["order"]
    due = int(bill["additional_due"])
    async with pool().acquire() as conn:
        await conn.execute("UPDATE service_orders SET final_amount_due=$2,updated_at=now() WHERE id=$1", order["id"], due)
        if due > 0:
            await conn.execute(
                """UPDATE service_orders SET status='WAITING_FINAL_PAYMENT',final_payment_status='UNPAID' WHERE id=$1""",
                order["id"],
            )
            await conn.execute("INSERT INTO payments(order_id,kind,amount,status) VALUES($1,'FINAL',$2,'PENDING')", order["id"], due)
        else:
            await conn.execute(
                """UPDATE service_orders SET status='WAITING_CUSTOMER_CONFIRMATION',final_payment_status='NOT_DUE' WHERE id=$1""",
                order["id"],
            )
    lines = [
        f"*RINCIAN AKHIR {order_no}*",
        f"Biaya jasa/pengecekan: {rupiah(bill['labour_and_inspection'])}",
        f"Spare part: {rupiah(bill['parts'])}",
        f"Booking sudah dibayar: -{rupiah(order['booking_fee'])}",
        f"Tambahan yang perlu dibayar: *{rupiah(due)}*",
    ]
    await send_text(order["customer_wa"], "\n".join(lines))
    if due > 0:
        await send_payment_request(order["customer_wa"], order_no, due, "FINAL")
        return f"Tagihan akhir {order_no}: {rupiah(due)}. Menunggu pembayaran customer."
    await send_text(
        order["customer_wa"],
        f"Tidak ada pembayaran tambahan. Jika hasil service sudah baik, balas *KONFIRMASI SELESAI {order_no}*. "
        f"Jika ada masalah, balas *MASALAH {order_no}*.",
    )
    return f"{order_no} tidak memiliki pembayaran tambahan; menunggu konfirmasi customer."


async def create_success_settlement(order_no: str) -> str:
    bill = await compute_final_bill(order_no)
    if not bill:
        return "Nomor service tidak ditemukan."
    order = bill["order"]
    data = success_settlement(int(order["booking_fee"]), bill["labour_and_inspection"], bill["parts"])
    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO settlements(order_id,outcome,gross_amount,customer_refund,technician_payout,platform_fee,status)
               VALUES($1,'SUCCESS',$2,0,$3,$4,'PENDING_OWNER')
               ON CONFLICT(order_id) DO UPDATE SET outcome='SUCCESS',gross_amount=EXCLUDED.gross_amount,
               customer_refund=0,technician_payout=EXCLUDED.technician_payout,platform_fee=EXCLUDED.platform_fee,
               status='PENDING_OWNER'""",
            order["id"], data["total"], data["technician_payout"], data["platform_fee"],
        )
        await conn.execute("UPDATE service_orders SET status='SETTLEMENT_PENDING_OWNER' WHERE id=$1", order["id"])
    await send_text(
        settings.owner_wa_number,
        f"*SETTLEMENT SUCCESS {order_no}*\n"
        f"Total customer: {rupiah(data['total'])}\n"
        f"Payout mekanik: {rupiah(data['technician_payout'])}\n"
        f"Fee Multitek: {rupiah(data['platform_fee'])}\n\n"
        f"Setujui: *SETUJUI SETTLEMENT {order_no}*",
    )
    return "Terima kasih. Hasil service sudah dikonfirmasi. Settlement menunggu finalisasi Multitek."


async def create_unrepairable_settlement(order_no: str) -> str:
    order = await find_order(order_no)
    if not order:
        return "Nomor service tidak ditemukan."
    data = unrepaired_settlement(int(order["booking_fee"] or 0))
    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO settlements(order_id,outcome,gross_amount,customer_refund,technician_payout,platform_fee,status)
               VALUES($1,'UNREPAIRABLE',$2,$3,$4,$5,'PENDING_OWNER')
               ON CONFLICT(order_id) DO UPDATE SET outcome='UNREPAIRABLE',gross_amount=EXCLUDED.gross_amount,
               customer_refund=EXCLUDED.customer_refund,technician_payout=EXCLUDED.technician_payout,
               platform_fee=EXCLUDED.platform_fee,status='PENDING_OWNER'""",
            order["id"], data["gross"], data["customer_refund"], data["technician_payout"], data["platform_fee"],
        )
        await conn.execute("UPDATE service_orders SET status='SETTLEMENT_PENDING_OWNER',close_reason='UNREPAIRABLE' WHERE id=$1", order["id"])
    await send_text(
        settings.owner_wa_number,
        f"*SETTLEMENT UNREPAIRABLE {order_no}*\n"
        f"Refund customer: {rupiah(data['customer_refund'])}\n"
        f"Kompensasi mekanik: {rupiah(data['technician_payout'])}\n"
        f"Fee Multitek: {rupiah(data['platform_fee'])}\n\n"
        f"Setujui: *SETUJUI SETTLEMENT {order_no}*",
    )
    return "Konfirmasi diterima. Settlement menunggu persetujuan owner Multitek."


async def owner_approve_settlement(order_no: str) -> str:
    order = await find_order(order_no)
    if not order:
        return "Nomor service tidak ditemukan."
    async with pool().acquire() as conn:
        settlement = await conn.fetchrow("SELECT * FROM settlements WHERE order_id=$1", order["id"])
        if not settlement:
            return "Settlement belum tersedia."
        await conn.execute("UPDATE settlements SET status='APPROVED',approved_at=now() WHERE id=$1", settlement["id"])
        await conn.execute("UPDATE service_orders SET status='SETTLED' WHERE id=$1", order["id"])
    if order["technician_wa"]:
        await send_text(order["technician_wa"], f"Settlement {order_no} disetujui. Payout manual: *{rupiah(settlement['technician_payout'])}*.")
    await send_text(order["customer_wa"], f"Settlement {order_no} sudah disetujui Multitek. Refund jika ada akan diproses manual sesuai rincian.")
    return (
        f"Settlement {order_no} APPROVED. Refund customer {rupiah(settlement['customer_refund'])}; "
        f"payout mekanik {rupiah(settlement['technician_payout'])}; fee Multitek {rupiah(settlement['platform_fee'])}."
    )


async def owner_mark_payout(order_no: str) -> str:
    order = await find_order(order_no)
    if not order:
        return "Nomor service tidak ditemukan."
    async with pool().acquire() as conn:
        settlement = await conn.fetchrow("SELECT * FROM settlements WHERE order_id=$1", order["id"])
        if not settlement or settlement["status"] != "APPROVED":
            return "Settlement belum disetujui."
        await conn.execute("UPDATE settlements SET status='PAID',paid_at=now() WHERE id=$1", settlement["id"])
        await conn.execute("UPDATE service_orders SET status='CLOSED' WHERE id=$1", order["id"])
        if order["assigned_technician_id"]:
            await conn.execute("UPDATE technicians SET jobs_completed=jobs_completed+1,updated_at=now() WHERE id=$1", order["assigned_technician_id"])
    return f"Payout {order_no} ditandai selesai. Order CLOSED."


async def owner_set_price(skill_code: str, field: str, amount: int) -> str:
    allowed = {"INSPEKSI": "inspection_fee", "RINGAN": "light_fee", "SEDANG": "medium_fee", "BERAT": "heavy_fee"}
    column = allowed.get(field.upper())
    if not column:
        return "Tipe tarif harus INSPEKSI/RINGAN/SEDANG/BERAT."
    if amount < 0:
        return "Nominal tidak valid."
    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM service_price_matrix WHERE skill_code=$1", skill_code)
        if not row:
            return "Kategori skill tidak ditemukan."
        await conn.execute(f"UPDATE service_price_matrix SET {column}=$2,updated_at=now() WHERE skill_code=$1", skill_code, amount)
    return f"Tarif {row['skill_name']} {field.upper()} = {rupiah(amount)}."


async def tariff_list() -> str:
    async with pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM service_price_matrix ORDER BY skill_name")
    lines = ["*TARIF SERVICE MATRIX*", "0 berarti belum ditetapkan / perlu quotation."]
    for r in rows:
        lines.append(
            f"{r['skill_name']}: cek {rupiah(r['inspection_fee'])}, ringan {rupiah(r['light_fee'])}, "
            f"sedang {rupiah(r['medium_fee'])}, berat {rupiah(r['heavy_fee'])}"
        )
    return "\n".join(lines)
