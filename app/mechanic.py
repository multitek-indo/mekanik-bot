from .config import settings
from .db import pool
from .finance import prepare_final_payment, create_unrepairable_settlement
from .orders import find_order, order_item, order_items, change_status, add_attachment
from .pricing import rupiah
from .skills import detect_skill_code, SKILL_BY_CODE
from .state import get_state, set_state, clear_state
from .types import IncomingMessage
from .wa import send_text, send_image, send_file

DIFFICULTY_MAP = {
    "1": "RINGAN", "RINGAN": "RINGAN",
    "2": "SEDANG", "SEDANG": "SEDANG",
    "3": "BERAT", "BERAT": "BERAT",
    "4": "KHUSUS", "KHUSUS": "KHUSUS", "SPECIAL": "KHUSUS",
}


async def mechanic_by_phone(phone: str):
    async with pool().acquire() as conn:
        return await conn.fetchrow("SELECT * FROM technicians WHERE wa_number=$1 AND is_active=true", phone)


async def set_online_wait_location(phone: str) -> str:
    await set_state(phone, "tech_online_location", {})
    return "Kirim *Share Location posisi Anda saat ini*. Posisi ini dipakai untuk matching job terdekat selama maksimal beberapa jam."


async def set_offline(phone: str) -> str:
    async with pool().acquire() as conn:
        await conn.execute("UPDATE technicians SET is_available=false,updated_at=now() WHERE wa_number=$1", phone)
    await clear_state(phone)
    return "Status Anda sekarang *OFFLINE*. Anda tidak akan menerima penawaran job sampai ONLINE kembali."


async def tech_depart(phone: str, order_no: str) -> str:
    order = await find_order(order_no)
    if not order or order["technician_wa"] != phone:
        return "Job tidak ditemukan atau bukan milik Anda."
    if order["status"] != "READY_TO_DEPART":
        return "Job belum diizinkan berangkat. Pastikan pembayaran dan lokasi final sudah dikonfirmasi customer."
    await change_status(order["id"], "EN_ROUTE", "TECHNICIAN", phone, "Mekanik berangkat")
    await send_text(order["customer_wa"], f"Mekanik *{order['technician_name']}* sedang menuju lokasi untuk {order_no}.")
    return f"Status {order_no}: *EN_ROUTE*."


async def tech_arrive(phone: str, order_no: str) -> str:
    order = await find_order(order_no)
    if not order or order["technician_wa"] != phone:
        return "Job tidak ditemukan atau bukan milik Anda."
    if order["status"] not in {"EN_ROUTE", "READY_TO_DEPART"}:
        return f"Status {order_no} saat ini {order['status']}; tidak dapat ditandai SAMPAI."
    await change_status(order["id"], "ARRIVED", "TECHNICIAN", phone, "Mekanik tiba")
    await send_text(order["customer_wa"], f"Mekanik sudah tiba untuk {order_no}. Pemeriksaan dapat dimulai.")
    items = await order_items(order["id"])
    lines = [f"{i['item_no']}. {i['machine_text']} — {i['complaint']}" for i in items]
    return (
        f"Status {order_no}: *ARRIVED*.\n\nMesin:\n" + "\n".join(lines)
        + f"\n\nMulai diagnosis dengan: *DIAGNOSIS {order_no} <nomor mesin>*\n"
        + f"Jika ada mesin tambahan: *TAMBAH MESIN {order_no} jenis/model | keluhan | biaya_cek*"
    )


async def start_diagnosis(phone: str, order_no: str, item_no: int) -> str:
    order = await find_order(order_no)
    if not order or order["technician_wa"] != phone:
        return "Job tidak ditemukan atau bukan milik Anda."
    if order["status"] not in {"ARRIVED", "DIAGNOSING", "WAITING_CUSTOMER_APPROVAL", "REPAIRING"}:
        return f"Diagnosis belum dapat dimulai pada status {order['status']}."
    item = await order_item(order["id"], item_no)
    if not item:
        return "Nomor mesin/item tidak ditemukan."
    if item["status"] in {"COMPLETED", "UNREPAIRABLE_CONFIRMED"}:
        return "Item tersebut sudah ditutup."
    await change_status(order["id"], "DIAGNOSING", "TECHNICIAN", phone, f"Diagnosis item {item_no}")
    async with pool().acquire() as conn:
        await conn.execute("UPDATE service_order_items SET status='DIAGNOSING',updated_at=now() WHERE id=$1", item["id"])
    await set_state(phone, "tech_diag_text", {"order_no": order_no, "item_no": item_no})
    return f"Diagnosis *{order_no} item {item_no} — {item['machine_text']}*. Jelaskan hasil pemeriksaan/diagnosis Anda."


async def start_unrepairable(phone: str, order_no: str, item_no: int) -> str:
    order = await find_order(order_no)
    if not order or order["technician_wa"] != phone:
        return "Job tidak ditemukan atau bukan milik Anda."
    item = await order_item(order["id"], item_no)
    if not item:
        return "Nomor mesin/item tidak ditemukan."
    await set_state(phone, "tech_unrepair_text", {"order_no": order_no, "item_no": item_no})
    async with pool().acquire() as conn:
        await conn.execute("UPDATE service_order_items SET status='UNREPAIRABLE_PENDING_EVIDENCE',updated_at=now() WHERE id=$1", item["id"])
    return (
        f"Untuk menyatakan item {item_no} tidak dapat diperbaiki, bukti wajib lengkap.\n"
        "Pertama, jelaskan *hasil diagnosis dan alasan teknis* mengapa perbaikan tidak dapat diselesaikan."
    )


async def add_extra_machine(phone: str, order_no: str, spec: str) -> str:
    order = await find_order(order_no)
    if not order or order["technician_wa"] != phone:
        return "Job tidak ditemukan atau bukan milik Anda."
    parts = [x.strip() for x in spec.split("|")]
    if len(parts) != 3:
        return f"Format: *TAMBAH MESIN {order_no} jenis/model | keluhan | biaya_cek*"
    machine, complaint, fee_text = parts
    try:
        fee = int("".join(ch for ch in fee_text if ch.isdigit()))
    except ValueError:
        fee = -1
    if not machine or not complaint or fee < 0:
        return "Data mesin/keluhan/biaya cek tidak valid."
    code = detect_skill_code(f"{machine} {complaint}")
    name = SKILL_BY_CODE[code]["name"] if code else None
    async with pool().acquire() as conn:
        next_no = await conn.fetchval("SELECT COALESCE(max(item_no),0)+1 FROM service_order_items WHERE order_id=$1", order["id"])
        item = await conn.fetchrow(
            """INSERT INTO service_order_items(
                   order_id,item_no,machine_category_code,machine_category_name,machine_text,complaint,declared_by,status,inspection_fee)
               VALUES($1,$2,$3,$4,$5,$6,'TECHNICIAN','EXTRA_PENDING_CUSTOMER',$7) RETURNING *""",
            order["id"], next_no, code, name, machine[:300], complaint[:1500], fee,
        )
    await send_text(
        order["customer_wa"],
        f"Mekanik mengajukan pemeriksaan mesin tambahan untuk {order_no}:\n"
        f"Item {item['item_no']}: *{machine}*\nKeluhan: {complaint}\n"
        f"Tambahan biaya pengecekan: *{rupiah(fee)}*\n\n"
        f"Setuju: *SETUJU TAMBAHAN {order_no} {item['item_no']}*\n"
        f"Tolak: *TOLAK TAMBAHAN {order_no} {item['item_no']}*",
    )
    return f"Mesin tambahan item {item['item_no']} diajukan ke customer. Tunggu persetujuan sebelum memeriksa."


async def customer_extra_response(phone: str, order_no: str, item_no: int, approve: bool) -> str:
    order = await find_order(order_no)
    if not order or order["customer_wa"] != phone:
        return "Nomor service tidak ditemukan atau bukan milik nomor ini."
    item = await order_item(order["id"], item_no)
    if not item or item["status"] != "EXTRA_PENDING_CUSTOMER":
        return "Permintaan mesin tambahan tidak ditemukan atau sudah diproses."
    new_status = "DECLARED" if approve else "DECLINED"
    async with pool().acquire() as conn:
        await conn.execute("UPDATE service_order_items SET status=$2,customer_approved=$3,updated_at=now() WHERE id=$1", item["id"], new_status, approve)
    if order["technician_wa"]:
        await send_text(order["technician_wa"], f"Customer {'MENYETUJUI' if approve else 'MENOLAK'} pemeriksaan item tambahan {item_no} pada {order_no}.")
    return f"Mesin tambahan item {item_no} {'disetujui' if approve else 'ditolak'}."


async def customer_quote_response(phone: str, order_no: str, item_no: int, approve: bool) -> str:
    order = await find_order(order_no)
    if not order or order["customer_wa"] != phone:
        return "Nomor service tidak ditemukan atau bukan milik nomor ini."
    item = await order_item(order["id"], item_no)
    if not item or item["status"] != "WAITING_CUSTOMER_APPROVAL":
        return "Quotation item tidak ditemukan atau sudah diproses."
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE service_order_items SET status=$2,customer_approved=$3,updated_at=now() WHERE id=$1",
            item["id"], "APPROVED" if approve else "DECLINED", approve,
        )
    if approve:
        await change_status(order["id"], "REPAIRING", "CUSTOMER", phone, f"Approve repair item {item_no}")
        if order["technician_wa"]:
            await send_text(order["technician_wa"], f"✅ Customer menyetujui repair {order_no} item {item_no}. Silakan kerjakan. Setelah selesai: *SELESAI ITEM {order_no} {item_no}*")
        return f"Perbaikan item {item_no} disetujui. Mekanik sudah diberi konfirmasi."
    if order["technician_wa"]:
        await send_text(order["technician_wa"], f"Customer menolak repair {order_no} item {item_no}. Jangan lakukan perbaikan pada item tersebut.")
    return f"Perbaikan item {item_no} tidak dilanjutkan. Biaya pengecekan yang telah disetujui/matrix tetap dapat diperhitungkan pada tagihan akhir."


async def complete_item(phone: str, order_no: str, item_no: int) -> str:
    order = await find_order(order_no)
    if not order or order["technician_wa"] != phone:
        return "Job tidak ditemukan atau bukan milik Anda."
    item = await order_item(order["id"], item_no)
    if not item:
        return "Item tidak ditemukan."
    if item["status"] not in {"APPROVED", "REPAIRING"}:
        return f"Item belum disetujui customer atau statusnya {item['status']}."
    async with pool().acquire() as conn:
        await conn.execute("UPDATE service_order_items SET status='COMPLETED',completed_at=now(),updated_at=now() WHERE id=$1", item["id"])
    await send_text(order["customer_wa"], f"Mekanik menandai {order_no} item {item_no} — *{item['machine_text']}* selesai diperbaiki.")
    return f"Item {item_no} ditandai COMPLETED. Jika seluruh pekerjaan selesai, kirim *SELESAI {order_no}*."


async def complete_order(phone: str, order_no: str) -> str:
    order = await find_order(order_no)
    if not order or order["technician_wa"] != phone:
        return "Job tidak ditemukan atau bukan milik Anda."
    items = await order_items(order["id"])
    blocked = [i for i in items if i["status"] in {"DECLARED", "DIAGNOSING", "WAITING_CUSTOMER_APPROVAL", "APPROVED", "REPAIRING", "EXTRA_PENDING_CUSTOMER", "UNREPAIRABLE_PENDING_EVIDENCE", "UNREPAIRABLE_PENDING_CUSTOMER"}]
    if blocked:
        return "Masih ada item yang belum ditutup: " + ", ".join(str(i["item_no"]) for i in blocked)
    if not any(i["status"] == "COMPLETED" for i in items):
        return "Belum ada item yang berhasil diselesaikan. Untuk kasus seluruh mesin tidak dapat diperbaiki, selesaikan flow TIDAK BISA + bukti."
    await send_text(order["customer_wa"], f"Mekanik menyatakan seluruh pekerjaan yang disetujui pada {order_no} selesai. Sistem sedang menghitung tagihan akhir.")
    return await prepare_final_payment(order_no)


async def customer_unrepairable_response(phone: str, order_no: str, item_no: int, approve: bool) -> str:
    order = await find_order(order_no)
    if not order or order["customer_wa"] != phone:
        return "Nomor service tidak ditemukan atau bukan milik nomor ini."
    item = await order_item(order["id"], item_no)
    if not item or item["status"] != "UNREPAIRABLE_PENDING_CUSTOMER":
        return "Konfirmasi tidak dapat diperbaiki untuk item tersebut tidak ditemukan."
    if not approve:
        await change_status(order["id"], "DISPUTE", "CUSTOMER", phone, f"Dispute unrepairable item {item_no}")
        await send_text(settings.owner_wa_number, f"⚠️ DISPUTE {order_no} item {item_no}. Customer tidak menyetujui kesimpulan mekanik.")
        return "Masalah sudah diteruskan ke owner Multitek. Settlement ditahan sampai review selesai."
    async with pool().acquire() as conn:
        await conn.execute("UPDATE service_order_items SET status='UNREPAIRABLE_CONFIRMED',customer_approved=true,updated_at=now() WHERE id=$1", item["id"])
    items = await order_items(order["id"])
    if all(i["status"] == "UNREPAIRABLE_CONFIRMED" for i in items):
        return await create_unrepairable_settlement(order_no)
    return f"Kesimpulan item {item_no} diterima. Item lain pada order tetap diproses sesuai statusnya."


async def handle_mechanic_state(msg: IncomingMessage) -> str | None:
    row = await get_state(msg.phone)
    if not row:
        return None
    st = row["state"]
    if not st.startswith("tech_"):
        return None
    payload = dict(row["payload"] or {})
    text = (msg.text or "").strip()

    if text.upper() == "BATAL":
        await clear_state(msg.phone)
        return "Proses dibatalkan."

    if st == "tech_online_location":
        if not msg.location:
            return "Mohon kirim Share Location posisi Anda saat ini."
        async with pool().acquire() as conn:
            await conn.execute(
                """UPDATE technicians SET current_lat=$2,current_lon=$3,current_location_at=now(),is_available=true,updated_at=now()
                   WHERE wa_number=$1""",
                msg.phone, msg.location["lat"], msg.location["lon"],
            )
        await clear_state(msg.phone)
        return "Status Anda *ONLINE*. Lokasi saat ini sudah disimpan dan Anda dapat menerima penawaran job."

    order_no = payload.get("order_no")
    item_no = int(payload.get("item_no", 0) or 0)
    order = await find_order(order_no) if order_no else None
    item = await order_item(order["id"], item_no) if order and item_no else None
    if order and order["technician_wa"] != msg.phone:
        await clear_state(msg.phone)
        return "Job bukan milik Anda."

    if st == "tech_diag_text":
        if len(text) < 5:
            return "Jelaskan hasil diagnosis sedikit lebih lengkap."
        payload["diagnosis"] = text[:2500]
        await set_state(msg.phone, "tech_diag_difficulty", payload)
        return "Tingkat kesulitan? Balas *1 RINGAN*, *2 SEDANG*, *3 BERAT*, atau *4 KHUSUS/quotation*."

    if st == "tech_diag_difficulty":
        key = text.upper().split()[0] if text else ""
        difficulty = DIFFICULTY_MAP.get(key) or DIFFICULTY_MAP.get(text.upper())
        if not difficulty:
            return "Balas 1/RINGAN, 2/SEDANG, 3/BERAT, atau 4/KHUSUS."
        payload["difficulty"] = difficulty
        code = item["machine_category_code"] if item else None
        fee = 0
        inspection_fee = 0
        if code:
            async with pool().acquire() as conn:
                matrix = await conn.fetchrow("SELECT * FROM service_price_matrix WHERE skill_code=$1", code)
            if matrix:
                inspection_fee = int(matrix["inspection_fee"] or 0)
                fee_field = {"RINGAN": "light_fee", "SEDANG": "medium_fee", "BERAT": "heavy_fee"}.get(difficulty)
                fee = int(matrix[fee_field] or 0) if fee_field else 0
        payload["inspection_fee"] = inspection_fee
        payload["repair_fee"] = fee
        if fee <= 0:
            await set_state(msg.phone, "tech_diag_fee", payload)
            return "Tarif matrix untuk kategori/tingkat ini belum ditetapkan. Masukkan *usulan jasa* dalam rupiah, contoh: *150000*."
        await set_state(msg.phone, "tech_diag_parts", payload)
        return f"Tarif jasa dari matrix: *{rupiah(fee)}*. Ada biaya spare part? Balas nominal, atau *0* jika tidak ada."

    if st == "tech_diag_fee":
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return "Masukkan usulan jasa dalam angka rupiah, contoh *150000*."
        payload["repair_fee"] = int(digits)
        await set_state(msg.phone, "tech_diag_parts", payload)
        return "Ada biaya spare part? Balas nominal rupiah, atau *0* jika tidak ada."

    if st == "tech_diag_parts":
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits and text != "0":
            return "Masukkan biaya spare part dalam angka, atau *0*."
        parts_fee = int(digits or 0)
        diagnosis = payload.get("diagnosis", "")
        difficulty = payload.get("difficulty", "")
        repair_fee = int(payload.get("repair_fee", 0))
        inspection_fee = int(payload.get("inspection_fee", 0))
        async with pool().acquire() as conn:
            await conn.execute(
                """UPDATE service_order_items SET diagnosis=$2,difficulty=$3,repair_fee=$4,parts_fee=$5,
                   inspection_fee=CASE WHEN declared_by='TECHNICIAN' THEN inspection_fee ELSE $6 END,
                   status='WAITING_CUSTOMER_APPROVAL',updated_at=now() WHERE id=$1""",
                item["id"], diagnosis, difficulty, repair_fee, parts_fee, inspection_fee,
            )
        await clear_state(msg.phone)
        await change_status(order["id"], "WAITING_CUSTOMER_APPROVAL", "TECHNICIAN", msg.phone, f"Quote item {item_no}")
        updated = await order_item(order["id"], item_no)
        extra_check = int(updated["inspection_fee"] or 0) if updated["declared_by"] == "TECHNICIAN" else 0
        total = repair_fee + parts_fee + extra_check
        await send_text(
            order["customer_wa"],
            f"*HASIL PEMERIKSAAN {order_no} — item {item_no}*\n"
            f"Mesin: {updated['machine_text']}\n"
            f"Diagnosis: {diagnosis}\n"
            f"Tingkat: {difficulty}\n"
            f"Jasa repair: {rupiah(repair_fee)}\n"
            + (f"Biaya cek tambahan: {rupiah(extra_check)}\n" if extra_check else "")
            + f"Spare part: {rupiah(parts_fee)}\n"
            f"Subtotal item: *{rupiah(total)}*\n\n"
            "Booking yang sudah dibayar akan diperhitungkan sekali sebagai kredit terhadap total jasa akhir.\n\n"
            f"Setuju: *SETUJU {order_no} {item_no}*\n"
            f"Tidak lanjut: *TOLAK {order_no} {item_no}*",
        )
        return f"Quotation item {item_no} sudah dikirim ke customer. Tunggu persetujuan."

    if st == "tech_unrepair_text":
        if len(text) < 10:
            return "Jelaskan diagnosis dan alasan teknis lebih lengkap (minimal beberapa kata)."
        payload["diagnosis"] = text[:2500]
        await set_state(msg.phone, "tech_unrepair_photo", payload)
        return "Sekarang kirim *foto kondisi/komponen/titik kerusakan* sebagai bukti analisa."

    if st == "tech_unrepair_photo":
        if msg.media_type != "image" or not msg.media_path:
            return "Foto wajib. Mohon kirim sebagai foto/image WhatsApp."
        payload["photo_path"] = msg.media_path
        await add_attachment(order["id"], item["id"], "TECHNICIAN", msg.phone, "UNREPAIRABLE_PHOTO", "image", msg.media_path, msg.message_id)
        await set_state(msg.phone, "tech_unrepair_video", payload)
        return "Foto diterima. Sekarang kirim *video analisa/pengujian* yang memperlihatkan alasan teknis mesin tidak dapat diperbaiki."

    if st == "tech_unrepair_video":
        if msg.media_type not in {"video", "video_note"} or not msg.media_path:
            return "Video analisa wajib. Mohon kirim video melalui WhatsApp."
        await add_attachment(order["id"], item["id"], "TECHNICIAN", msg.phone, "UNREPAIRABLE_VIDEO", msg.media_type, msg.media_path, msg.message_id)
        diagnosis = payload.get("diagnosis", "")
        photo_path = payload.get("photo_path")
        async with pool().acquire() as conn:
            await conn.execute(
                """UPDATE service_order_items SET diagnosis=$2,status='UNREPAIRABLE_PENDING_CUSTOMER',repair_fee=0,parts_fee=0,updated_at=now()
                   WHERE id=$1""",
                item["id"], diagnosis,
            )
        await clear_state(msg.phone)
        await change_status(order["id"], "UNREPAIRABLE_REVIEW", "TECHNICIAN", msg.phone, f"Unrepairable item {item_no} with photo+video evidence")
        await send_text(
            order["customer_wa"],
            f"*HASIL ANALISA {order_no} — item {item_no}*\n"
            f"Mesin: {item['machine_text']}\n"
            f"Mekanik menyatakan item ini belum/tidak dapat diperbaiki.\n"
            f"Alasan teknis: {diagnosis}\n\n"
            "Foto dan video analisa dilampirkan.\n"
            f"Jika menerima hasilnya: *SETUJU TIDAK BISA {order_no} {item_no}*\n"
            f"Jika keberatan: *MASALAH {order_no}*",
        )
        try:
            if photo_path:
                await send_image(order["customer_wa"], photo_path, f"Bukti foto analisa {order_no} item {item_no}")
            await send_file(order["customer_wa"], msg.media_path, f"Video analisa {order_no} item {item_no}")
        except Exception:
            pass
        return "Bukti foto+video lengkap dan hasil analisa sudah dikirim ke customer."

    return None
