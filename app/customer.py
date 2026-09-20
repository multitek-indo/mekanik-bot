import re

from .ai import (
    classify_customer_message,
    conversational_customer_reply,
    quick_customer_signals,
    understand_customer_message,
)
from .config import settings
from .db import pool
from .location import location_label, haversine_km
from .matching import start_offer_batch
from .media import is_real_media_file
from .orders import (
    active_order_for_customer,
    add_attachment,
    change_status,
    create_order,
    find_order,
    get_or_create_customer,
    order_items,
)
from .pricing import booking_fee_for_distance, booking_tier_text, rupiah
from .skills import detect_skill_code
from .state import clear_state, get_state, set_state
from .types import IncomingMessage
from .wa import send_text


MAX_REFERENCE_MEDIA_PER_MACHINE = 6
MAX_REFERENCE_MEDIA_TOTAL = 20


def parse_bulk_machine_list(text: str) -> list[dict]:
    text = (text or "").strip()
    if ";" not in text and "|" not in text:
        return []

    chunks = [x.strip() for x in text.split(";") if x.strip()]
    result = []

    for chunk in chunks:
        if "|" in chunk:
            machine, problem = [x.strip() for x in chunk.split("|", 1)]
        else:
            machine, problem = chunk, ""

        if machine:
            result.append(
                {
                    "machine": machine[:300],
                    "problem": problem[:1500],
                }
            )

    return result


def _machines_from_ai(result: dict) -> list[dict]:
    machines = []

    for item in result.get("machines") or []:
        if not isinstance(item, dict):
            continue

        machine = str(item.get("machine") or "").strip()
        problem = str(item.get("problem") or "").strip()

        if machine or problem:
            machines.append(
                {
                    "machine": machine[:300],
                    "problem": problem[:1500],
                }
            )

    if machines:
        return machines[: settings.max_machines_per_order]

    fields = result.get("fields") or {}
    machine = str(fields.get("machine_description") or "").strip()
    problem = str(fields.get("problem") or "").strip()

    if machine or problem:
        return [
            {
                "machine": machine[:300],
                "problem": problem[:1500],
            }
        ]

    return []


def _context_items_from_payload(payload: dict) -> list[dict]:
    items = list(payload.get("items") or [])
    if items:
        return items

    return list(payload.get("prefill_machines") or [])


def _context_text(items: list[dict] | None) -> str:
    parts = []

    for item in list(items or []):
        if not isinstance(item, dict):
            continue

        machine = str(
            item.get("machine")
            or item.get("machine_text")
            or ""
        ).strip()
        problem = str(
            item.get("problem")
            or item.get("complaint")
            or ""
        ).strip()

        value = " ".join(x for x in (machine, problem) if x)
        if value:
            parts.append(value)

    return " ; ".join(parts)


def _context_label(items: list[dict] | None) -> str:
    values = []

    for item in list(items or []):
        if not isinstance(item, dict):
            continue

        machine = str(
            item.get("machine")
            or item.get("machine_text")
            or ""
        ).strip()
        problem = str(
            item.get("problem")
            or item.get("complaint")
            or ""
        ).strip()

        if machine and problem:
            values.append(f"{machine} dengan keluhan {problem}")
        elif machine:
            values.append(machine)
        elif problem:
            values.append(f"mesin dengan keluhan {problem}")

    if not values:
        return ""

    if len(values) == 1:
        return values[0]

    return f"{len(values)} mesin yang sudah Anda jelaskan"


def _looks_like_price_question(text: str) -> bool:
    low = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not low:
        return False

    markers = (
        "berapa biaya",
        "biaya berapa",
        "biayanya",
        "berapa harga",
        "harga berapa",
        "harganya",
        "berapa ongkos",
        "ongkosnya",
        "berapa tarif",
        "tarifnya",
        "biaya servis",
        "biaya service",
        "harga servis",
        "harga service",
    )
    return any(marker in low for marker in markers)


async def price_answer(
    text: str,
    context_items: list[dict] | None = None,
) -> str:
    context_items = list(context_items or [])
    context = _context_text(context_items)
    label = _context_label(context_items)
    lookup_text = " ".join(x for x in (text, context) if x)
    code = detect_skill_code(lookup_text)

    subject = f"Untuk *{label}*, " if label else "Untuk service mesin, "

    base = (
        subject
        + "biaya kunjungan mengikuti jarak lokasi. "
        + f"Tarif booking saat ini: {booking_tier_text()}\n\n"
        + "Biaya jasa perbaikan final ditentukan dari jenis mesin dan tingkat "
        + "kesulitan setelah mekanik melakukan diagnosis. "
        + "Booking yang sudah dibayar menjadi kredit/pengurang jasa jika "
        + "perbaikan berhasil; spare part dihitung terpisah dan dikonfirmasi terlebih dahulu."
    )

    if not code:
        if context_items:
            return (
                base
                + "\n\nUntuk data mesin yang sudah Anda sampaikan, "
                + "tarif jasa detail akan mengikuti hasil diagnosis mekanik."
            )

        return (
            base
            + "\n\nKalau Anda sebutkan jenis mesin dan keluhannya, "
            + "saya bisa cek apakah matrix tarifnya sudah tersedia."
        )

    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM service_price_matrix WHERE skill_code=$1",
            code,
        )

    if not row:
        return (
            base
            + "\n\nTarif jasa detail untuk kategori ini belum tersedia di matrix "
            + "dan akan dikonfirmasi setelah diagnosis mekanik."
        )

    inspection = int(row["inspection_fee"] or 0)
    light = int(row["light_fee"] or 0)
    medium = int(row["medium_fee"] or 0)
    heavy = int(row["heavy_fee"] or 0)

    if not any((inspection, light, medium, heavy)):
        return (
            base
            + f"\n\nUntuk *{row['skill_name']}*, tarif jasa detail belum dikunci "
            + "di matrix dan akan dikonfirmasi setelah diagnosis."
        )

    return (
        base
        + f"\n\n*Matrix {row['skill_name']}*\n"
        + f"Pengecekan: {rupiah(inspection) if inspection else 'belum ditetapkan'}\n"
        + f"Ringan: {rupiah(light) if light else 'quotation'}\n"
        + f"Sedang: {rupiah(medium) if medium else 'quotation'}\n"
        + f"Berat: {rupiah(heavy) if heavy else 'quotation'}"
    )


async def _remember_price_service_context(
    msg: IncomingMessage,
    classified: dict,
) -> None:
    machines = _machines_from_ai(classified)

    if not machines:
        return

    customer = await get_or_create_customer(
        msg.phone,
        msg.sender_name or None,
    )

    payload = {
        "customer_id": str(customer["id"]),
        "items": [],
        "prefill_machines": machines,
    }

    await set_state(
        msg.phone,
        "cust_price_context",
        payload,
    )

    async with pool().acquire() as conn:
        await conn.execute(
            """
            UPDATE conversation_states
            SET expires_at = now() + interval '6 hours'
            WHERE wa_number = $1
            """,
            msg.phone,
        )


def _media_machine_label(payload: dict, item_no: int) -> str:
    items = list(payload.get("items") or [])

    if 1 <= item_no <= len(items):
        machine = str(items[item_no - 1].get("machine") or "").strip()
        if machine:
            return machine

    return f"mesin ke-{item_no}"


async def _begin_customer_media(phone: str, payload: dict) -> str:
    items = list(payload.get("items") or [])

    if not items:
        await set_state(phone, "cust_landmark", payload)
        return (
            "Ada nama tempat atau patokan agar mekanik mudah menemukan lokasi? "
            "Kalau tidak ada, cukup jawab *tidak ada*."
        )

    payload.setdefault("customer_media", [])
    payload["media_item_no"] = 1
    await set_state(phone, "cust_media", payload)

    machine = _media_machine_label(payload, 1)

    return (
        "Baik, lokasinya sudah benar.\n\n"
        f"Sebelum saya carikan mekanik, kirim *foto atau video* kondisi *{machine}* "
        "sebagai referensi. Kalau kendalanya berupa suara atau gerakan yang tidak normal, "
        "video pendek akan lebih membantu mekanik.\n\n"
        "Boleh kirim beberapa foto/video. Kalau sudah cukup ketik *SELESAI*. "
        "Kalau tidak bisa mengirim sekarang, ketik *LEWATI*."
    )


async def _advance_customer_media(phone: str, payload: dict) -> str:
    items = list(payload.get("items") or [])

    try:
        current = int(payload.get("media_item_no") or 1)
    except (TypeError, ValueError):
        current = 1

    if current < len(items):
        current += 1
        payload["media_item_no"] = current
        await set_state(phone, "cust_media", payload)

        machine = _media_machine_label(payload, current)
        return (
            f"Selanjutnya untuk mesin ke-{current}, *{machine}*. "
            "Silakan kirim foto atau video kondisinya. "
            "Kalau sudah cukup ketik *SELESAI*. "
            "Kalau tidak ada dokumentasi ketik *LEWATI*."
        )

    payload.pop("media_item_no", None)
    await set_state(phone, "cust_landmark", payload)

    return (
        "Baik, referensi mesin sudah selesai. "
        "Ada nama tempat atau patokan agar mekanik mudah menemukan lokasi? "
        "Kalau tidak ada, cukup jawab *tidak ada*."
    )


async def _persist_customer_media(
    order_id,
    phone: str,
    payload: dict,
) -> int:
    entries = list(payload.get("customer_media") or [])
    if not entries:
        return 0

    rows = await order_items(order_id)
    item_ids = {int(row["item_no"]): row["id"] for row in rows}
    saved = 0

    for entry in entries:
        try:
            item_no = int(entry.get("item_no") or 1)
        except (TypeError, ValueError):
            item_no = 1

        item_id = item_ids.get(item_no)
        if item_id is None:
            continue

        media_type = str(entry.get("media_type") or "").lower()
        path = str(entry.get("media_path") or "").strip()
        message_id = str(entry.get("message_id") or "").strip()

        if not path:
            continue

        if media_type == "image":
            purpose = "CUSTOMER_MACHINE_PHOTO"
        elif media_type in {"video", "video_note"}:
            purpose = "CUSTOMER_MACHINE_VIDEO"
        else:
            continue

        await add_attachment(
            order_id,
            item_id,
            "CUSTOMER",
            phone,
            purpose,
            media_type,
            path,
            message_id,
        )
        saved += 1

    return saved


async def _order_context_items(order_id) -> list[dict]:
    rows = await order_items(order_id)
    return [
        {
            "machine": str(row["machine_text"] or "").strip(),
            "problem": str(row["complaint"] or "").strip(),
        }
        for row in rows
    ]


async def customer_status_summary(order_no: str) -> str:
    order = await find_order(order_no)
    if not order:
        return "Nomor service tidak ditemukan."

    items = await order_items(order["id"])
    machine_names = [
        str(item["machine_text"] or "").strip()
        for item in items
        if str(item["machine_text"] or "").strip()
    ]

    machine_text = ""
    if machine_names:
        if len(machine_names) == 1:
            machine_text = f" untuk *{machine_names[0]}*"
        else:
            machine_text = f" untuk *{len(machine_names)} mesin*"

    status = str(order["status"] or "").upper()
    technician = str(order["technician_name"] or "").strip()

    if status == "NO_TECHNICIAN":
        body = (
            f"Saat ini belum ada mekanik yang tersedia dan sesuai{machine_text} "
            "di sekitar lokasi Anda. Karena belum ada mekanik yang menerima pekerjaan, "
            "saya belum bisa memastikan waktu kedatangannya. Permintaan Anda tetap tercatat "
            "dan akan ditindaklanjuti ketika ada mekanik yang sesuai."
        )
    elif status in {"READY_FOR_MATCHING", "OFFERING"}:
        body = (
            f"Permintaan{machine_text} sedang dicocokkan dan ditawarkan ke mekanik "
            "yang sesuai berdasarkan skill, radius, dan jarak. "
            "Saya belum bisa memastikan waktu kedatangan sampai ada mekanik yang menerima."
        )
    elif status == "WAITING_CUSTOMER_TECH_SELECTION":
        body = (
            "Sudah ada mekanik yang berminat. "
            "Silakan lanjutkan proses pemilihan mekanik pada pesan yang tersedia."
        )
    elif status in {
        "WAITING_BOOKING_FEE_OWNER",
        "WAITING_BOOKING_PAYMENT",
        "BOOKING_PROOF_SUBMITTED",
    }:
        body = "Mekanik sudah diproses dan tahap booking/pembayaran awal sedang diselesaikan."
    elif status == "BOOKING_PAID":
        body = "Booking sudah terverifikasi. Proses berikutnya adalah konfirmasi lokasi final."
    elif status in {"WAITING_FINAL_LOCATION_CONFIRMATION", "READY_TO_DEPART"}:
        body = "Mekanik sudah dipilih dan sedang menunggu konfirmasi keberangkatan/lokasi final."
    elif status == "EN_ROUTE":
        body = "Mekanik sedang menuju lokasi Anda."
    elif status == "ARRIVED":
        body = "Mekanik sudah tiba di lokasi."
    elif status == "DIAGNOSING":
        body = "Mekanik sedang melakukan pengecekan/diagnosis mesin."
    elif status == "WAITING_CUSTOMER_APPROVAL":
        body = "Hasil diagnosis sudah diproses dan sedang menunggu persetujuan pekerjaan."
    elif status == "REPAIRING":
        body = "Mekanik sedang melakukan perbaikan mesin."
    elif status in {"WAITING_FINAL_PAYMENT", "FINAL_PROOF_SUBMITTED"}:
        body = "Pekerjaan sudah masuk tahap penyelesaian pembayaran akhir."
    elif status == "WAITING_CUSTOMER_CONFIRMATION":
        body = "Pekerjaan sudah selesai dan sedang menunggu konfirmasi akhir customer."
    elif status == "UNREPAIRABLE_REVIEW":
        body = "Mesin sedang dalam proses review karena belum dapat diselesaikan oleh mekanik."
    elif status == "DISPUTE":
        body = "Service sedang ditinjau oleh Multitek."
    elif status in {"SETTLEMENT_PENDING_OWNER", "SETTLED"}:
        body = "Service sudah selesai dan sedang dalam proses administrasi akhir."
    elif status == "CLOSED":
        body = "Service ini sudah selesai dan ditutup."
    elif status == "CANCELLED":
        body = "Service ini sudah dibatalkan."
    else:
        body = "Permintaan service Anda sedang diproses."

    lines = [f"*STATUS {order['order_no']}*", body]
    if technician:
        lines.append(f"Mekanik: *{technician}*")

    return "\n\n".join(lines)


async def _apply_machine_count(
    phone: str,
    payload: dict,
    count: int,
    machines: list[dict] | None = None,
) -> str:
    if not (1 <= count <= settings.max_machines_per_order):
        return f"Jumlah mesin harus 1 sampai {settings.max_machines_per_order}."

    source = list(machines or payload.pop("prefill_machines", []) or [])
    payload.pop("pending_machine_count", None)
    payload["machine_count"] = count
    payload["items"] = []

    complete: list[dict] = []
    partial_machine = None

    for item in source[:count]:
        if not isinstance(item, dict):
            continue

        machine = str(item.get("machine") or "").strip()
        problem = str(item.get("problem") or "").strip()

        if machine and problem:
            complete.append(
                {
                    "machine": machine[:300],
                    "problem": problem[:1500],
                }
            )
            continue

        if machine and not problem and partial_machine is None:
            partial_machine = machine[:300]
            break

        break

    payload["items"] = complete

    if len(complete) >= count:
        payload.pop("machine_index", None)
        payload.pop("current_machine", None)
        await set_state(phone, "cust_location", payload)
        return (
            f"Baik, saya sudah menangkap data {count} mesin beserta keluhannya. "
            "Sekarang kirim *Share Location* lokasi mesin yang akan diservis."
        )

    idx = len(complete) + 1
    payload["machine_index"] = idx

    if partial_machine:
        payload["current_machine"] = partial_machine
        await set_state(phone, "cust_machine_problem", payload)
        return (
            f"Baik, saya catat mesin ke-{idx}: *{partial_machine}*. "
            "Keluhannya bagaimana?"
        )

    payload.pop("current_machine", None)
    await set_state(phone, "cust_machine_desc", payload)
    return (
        f"Baik, saya pahami ada {count} mesin. "
        f"Mesin ke-{idx} jenis/merk/modelnya apa? Sebutkan yang Anda tahu saja."
    )


async def _finish_machine_item(
    phone: str,
    payload: dict,
    machine: str,
    problem: str,
) -> str:
    items = list(payload.get("items") or [])
    items.append(
        {
            "machine": machine[:300],
            "problem": problem[:1500],
        }
    )
    payload["items"] = items
    payload.pop("current_machine", None)

    count = int(payload.get("machine_count") or len(items))
    if len(items) < count:
        idx = len(items) + 1
        payload["machine_index"] = idx
        await set_state(phone, "cust_machine_desc", payload)
        return (
            "Baik, mesin sebelumnya sudah saya catat. "
            f"Sekarang mesin ke-{idx} jenis/merk/modelnya apa?"
        )

    await set_state(phone, "cust_location", payload)
    return (
        f"Baik, data {len(items)} mesin sudah saya catat. "
        "Sekarang kirim *Share Location* lokasi mesin. "
        "Titik ini digunakan untuk mencari mekanik terdekat."
    )


async def _start_intake(msg: IncomingMessage, classified: dict) -> str:
    customer = await get_or_create_customer(msg.phone, msg.sender_name or None)
    machines = list(classified.get("machines") or [])[: settings.max_machines_per_order]
    machine_count = classified.get("machine_count")

    payload = {
        "customer_id": str(customer["id"]),
        "items": [],
    }

    if machines:
        payload["prefill_machines"] = machines

    if machine_count is not None:
        try:
            machine_count = int(machine_count)
        except (TypeError, ValueError):
            machine_count = None

    if machine_count:
        payload["pending_machine_count"] = machine_count

    if not customer["name"]:
        await set_state(msg.phone, "cust_name", payload)
        return (
            "Bisa saya bantu carikan mekanik. "
            "Sebelum lanjut, boleh tahu nama Anda atau nama perusahaan?"
        )

    if machine_count:
        return await _apply_machine_count(
            msg.phone,
            payload,
            machine_count,
            machines,
        )

    await set_state(msg.phone, "cust_machine_count", payload)

    if machines and machines[0].get("machine"):
        machine_label = machines[0]["machine"]
        return (
            f"Baik, saya menangkap mesin *{machine_label}*. "
            "Ada berapa unit mesin yang ingin dicek? "
            "Boleh jawab biasa seperti *satu*, *2 unit*, atau *mung siji*."
        )

    return (
        "Bisa saya bantu. Ada berapa mesin yang ingin dicek? "
        "Boleh jawab dengan bahasa biasa, misalnya *satu*, *2 unit*, "
        "*loro mesin*, atau kirim daftar `Mesin | Keluhan; Mesin | Keluhan`."
    )


async def handle_customer_state(msg: IncomingMessage) -> str | None:
    row = await get_state(msg.phone)
    if not row:
        return None

    st = row["state"]
    if not st.startswith("cust_"):
        return None

    payload = dict(row["payload"] or {})
    text = (msg.text or "").strip()
    quick = quick_customer_signals(text, st) if text else {
        "control": "NONE",
        "machine_count": None,
    }

    if text.upper() == "BATAL" or quick.get("control") == "CANCEL":
        await clear_state(msg.phone)
        return (
            "Baik, proses service saya batalkan. "
            "Kalau nanti membutuhkan mekanik lagi, langsung chat saja."
        )

    ai_cache = None

    async def understand():
        nonlocal ai_cache
        if ai_cache is None:
            ai_cache = await understand_customer_message(
                text,
                state=st,
                context=payload,
            )
        return ai_cache

    if st == "cust_price_context":
        analysis = await understand()
        low = re.sub(r"\s+", " ", text.lower()).strip()

        continue_markers = (
            "kirim mekanik",
            "kirim teknisi",
            "panggil mekanik",
            "panggil teknisi",
            "carikan mekanik",
            "carikan teknisi",
            "butuh mekanik",
            "butuh teknisi",
            "mekanik ke tempat",
            "teknisi ke tempat",
            "ke tempatku",
            "ke lokasi saya",
            "ke lokasiku",
            "lanjut",
            "gas",
        )

        wants_service = (
            analysis.get("intent") == "SERVICE_REQUEST"
            or any(marker in low for marker in continue_markers)
        )

        if wants_service:
            remembered = list(payload.get("prefill_machines") or [])
            current = _machines_from_ai(analysis)
            classified = dict(analysis)

            if current:
                classified["machines"] = current
            elif remembered:
                classified["machines"] = remembered

            await clear_state(msg.phone)
            return await _start_intake(msg, classified)

        if analysis.get("intent") == "PRICE_QUESTION":
            machines = _machines_from_ai(analysis)
            if machines:
                payload["prefill_machines"] = machines
                await set_state(msg.phone, "cust_price_context", payload)

            return await price_answer(
                text,
                _context_items_from_payload(payload),
            )

        if analysis.get("control") == "GREETING":
            return (
                "Ya. Data mesin yang tadi masih saya ingat. "
                "Kalau ingin saya carikan mekanik, tinggal bilang lanjut."
            )

        return await conversational_customer_reply(text)

    if st == "cust_name":
        if quick.get("control") == "GREETING":
            return (
                "Halo. Sebelum melanjutkan pencarian mekanik, "
                "boleh tahu nama Anda atau nama perusahaan?"
            )

        if len(text) < 2:
            return "Boleh sebutkan nama Anda atau nama perusahaan?"

        analysis = await understand()
        name = (analysis.get("fields") or {}).get("name")

        if not name:
            name = re.sub(
                r"(?i)^\s*(?:nama\s+(?:saya|aku)\s*[:=-]?\s*|"
                r"saya\s+|aku\s+|jenengku\s*[:=-]?\s*|"
                r"asma\s+kula\s*[:=-]?\s*)",
                "",
                text,
            ).strip()

        if not name or len(name) < 2:
            return "Saya belum menangkap namanya. Boleh sebutkan nama Anda atau perusahaan?"

        async with pool().acquire() as conn:
            await conn.execute(
                "UPDATE customers SET name=$2,updated_at=now() WHERE id=$1",
                payload["customer_id"],
                name[:150],
            )

        pending = payload.pop("pending_machine_count", None)
        if pending:
            return await _apply_machine_count(
                msg.phone,
                payload,
                int(pending),
                payload.get("prefill_machines"),
            )

        await set_state(msg.phone, "cust_machine_count", payload)
        return (
            f"Terima kasih, {name}. Ada berapa mesin yang ingin dicek? "
            "Boleh jawab *satu*, *2 unit*, *loro mesin*, dan sebagainya."
        )

    if st == "cust_machine_count":
        bulk = parse_bulk_machine_list(text)
        if bulk:
            if len(bulk) > settings.max_machines_per_order:
                return f"Maksimal {settings.max_machines_per_order} mesin per order."
            return await _apply_machine_count(
                msg.phone,
                payload,
                len(bulk),
                bulk,
            )

        count = quick.get("machine_count")
        analysis = None

        if count is None:
            analysis = await understand()

            if analysis.get("intent") == "PRICE_QUESTION":
                answer = await price_answer(
                    text,
                    _context_items_from_payload(payload),
                )
                return (
                    answer
                    + "\n\nUntuk melanjutkan pencarian mekanik, ada berapa mesin yang ingin dicek?"
                )

            if analysis.get("control") == "GREETING":
                return (
                    "Halo. Saya masih membantu proses service Anda. "
                    "Saya perlu tahu jumlah mesinnya; misalnya *satu*, "
                    "*2 unit*, atau *loro mesin*."
                )

            count = analysis.get("machine_count")

        if count is None:
            return (
                "Saya paham Anda sedang membutuhkan service. "
                "Ada berapa mesin yang akan dicek? Tidak harus pakai angka; "
                "boleh jawab *cuma satu*, *mung siji*, *kalih unit*, dan sebagainya."
            )

        extra_machines = []
        if analysis:
            extra_machines = list(analysis.get("machines") or [])

        prefill = list(payload.get("prefill_machines") or [])
        if extra_machines:
            prefill = extra_machines or prefill

        return await _apply_machine_count(
            msg.phone,
            payload,
            int(count),
            prefill,
        )

    if st == "cust_machine_desc":
        if not text:
            return "Sebutkan yang Anda tahu tentang mesinnya, misalnya merek, jenis, atau model."

        analysis = await understand()

        if analysis.get("intent") == "PRICE_QUESTION":
            answer = await price_answer(
                text,
                _context_items_from_payload(payload),
            )
            return (
                answer
                + "\n\nUntuk melanjutkan, mesin yang dimaksud jenis/merk/modelnya apa?"
            )

        if analysis.get("control") == "GREETING":
            return "Halo. Kita lanjut ya. Mesin yang bermasalah jenis/merk/modelnya apa?"

        fields = analysis.get("fields") or {}
        machines = analysis.get("machines") or []
        machine = fields.get("machine_description")
        problem = fields.get("problem")

        if machines:
            machine = machine or machines[0].get("machine")
            problem = problem or machines[0].get("problem")

        if not machine:
            normalized = (analysis.get("normalized_text") or "").lower()
            if any(x in normalized for x in ("tidak tahu", "tidak mengetahui")):
                return (
                    "Tidak masalah kalau tidak tahu modelnya. "
                    "Sebutkan yang diketahui saja, misalnya *Juki*, *obras*, "
                    "*jarum 1*, atau mereknya saja."
                )
            if analysis.get("requires_clarification"):
                return "Saya belum yakin jenis mesinnya. Boleh sebutkan merek/jenis yang Anda tahu?"
            machine = text[:300]

        if problem:
            return await _finish_machine_item(
                msg.phone,
                payload,
                machine,
                problem,
            )

        payload["current_machine"] = machine[:300]
        await set_state(msg.phone, "cust_machine_problem", payload)
        return (
            f"Baik, saya catat *{machine}*. "
            "Keluhannya bagaimana? Ceritakan saja dengan bahasa sehari-hari."
        )

    if st == "cust_machine_problem":
        if not text:
            return (
                "Ceritakan gejalanya, misalnya tidak jalan, suara kasar, "
                "benang putus, error, atau lainnya."
            )

        analysis = await understand()

        if analysis.get("intent") == "PRICE_QUESTION":
            items = _context_items_from_payload(payload)
            current_machine = str(payload.get("current_machine") or "").strip()
            if current_machine:
                items = list(items) + [{"machine": current_machine, "problem": ""}]

            answer = await price_answer(text, items)
            return (
                answer
                + "\n\nUntuk membantu diagnosis awal, "
                f"apa keluhan pada *{payload.get('current_machine', 'mesin tersebut')}*?"
            )

        if analysis.get("control") == "GREETING":
            return (
                "Halo. Kita lanjut ya. "
                f"Apa keluhan pada *{payload.get('current_machine', 'mesin tersebut')}*?"
            )

        fields = analysis.get("fields") or {}
        machines = analysis.get("machines") or []
        problem = fields.get("problem")

        if not problem and machines:
            problem = machines[0].get("problem")

        if not problem:
            normalized = (analysis.get("normalized_text") or "").lower()
            if "tidak tahu" in normalized:
                return (
                    "Tidak masalah kalau belum tahu penyebabnya. "
                    "Ceritakan gejala yang terlihat atau terdengar saja."
                )
            if analysis.get("requires_clarification"):
                return (
                    "Saya belum yakin menangkap keluhannya. "
                    "Boleh ceritakan lagi gejalanya dengan singkat?"
                )
            problem = text[:1500]

        return await _finish_machine_item(
            msg.phone,
            payload,
            payload["current_machine"],
            problem,
        )

    if st == "cust_location":
        if not msg.location:
            if text and _looks_like_price_question(text):
                answer = await price_answer(
                    text,
                    _context_items_from_payload(payload),
                )
                return (
                    answer
                    + "\n\nUntuk melanjutkan pencarian mekanik, silakan kirim *Share Location* lokasi mesin."
                )

            if text:
                return (
                    f"Saya menerima keterangan lokasi *{text[:120]}*, "
                    "tetapi untuk menghitung jarak dan mencari mekanik terdekat "
                    "saya tetap membutuhkan *Share Location* dari WhatsApp."
                )
            return "Mohon kirim lokasi mesin menggunakan fitur *Share Location* WhatsApp."

        payload["location"] = msg.location
        await set_state(msg.phone, "cust_location_confirm", payload)
        return (
            f"Lokasi yang saya terima: *{location_label(msg.location)}*\n"
            "Apakah ini benar lokasi mesin yang akan diservis? "
            "Boleh jawab *iya*, *bener*, *nggih*, atau kirim Share Location ulang jika salah."
        )

    if st == "cust_location_confirm":
        if msg.location:
            payload["location"] = msg.location
            await set_state(msg.phone, "cust_location_confirm", payload)
            return (
                f"Lokasi diperbarui menjadi *{location_label(msg.location)}*. "
                "Apakah titik ini sudah benar?"
            )

        if text and _looks_like_price_question(text):
            answer = await price_answer(
                text,
                _context_items_from_payload(payload),
            )
            return (
                answer
                + "\n\nKalau titik lokasi tadi sudah sesuai, jawab *iya*, *bener*, *nggih*, atau *betul*."
            )

        control = quick.get("control")
        if control not in {"YES", "NO"} and text:
            analysis = await understand()
            control = analysis.get("control")

        if control == "YES":
            return await _begin_customer_media(msg.phone, payload)

        if control == "NO":
            return "Baik, berarti titik tadi belum benar. Silakan kirim *Share Location* yang benar."

        return (
            "Saya perlu memastikan titiknya benar. "
            "Kalau sudah sesuai, jawab *iya*, *bener*, *nggih*, atau *betul*. "
            "Kalau salah, kirim Share Location ulang."
        )

    if st == "cust_media":
        items = list(payload.get("items") or [])

        if not items:
            await set_state(msg.phone, "cust_landmark", payload)
            return (
                "Ada nama tempat atau patokan agar mekanik mudah menemukan lokasi? "
                "Kalau tidak ada, cukup jawab *tidak ada*."
            )

        try:
            item_no = int(payload.get("media_item_no") or 1)
        except (TypeError, ValueError):
            item_no = 1

        item_no = max(1, min(item_no, len(items)))
        machine = _media_machine_label(payload, item_no)

        if msg.media_type in {"image", "video", "video_note"}:
            if not msg.media_path or not is_real_media_file(msg.media_path):
                return (
                    "Foto/video terdeteksi tetapi belum berhasil disimpan. "
                    "Mohon kirim ulang sekali lagi."
                )

            entries = list(payload.get("customer_media") or [])
            per_machine = [
                entry
                for entry in entries
                if int(entry.get("item_no") or 1) == item_no
            ]

            if len(per_machine) >= MAX_REFERENCE_MEDIA_PER_MACHINE:
                return (
                    f"Referensi untuk *{machine}* sudah cukup. "
                    "Ketik *SELESAI* untuk lanjut."
                )

            if len(entries) >= MAX_REFERENCE_MEDIA_TOTAL:
                return (
                    "Jumlah dokumentasi untuk service ini sudah cukup. "
                    "Ketik *SELESAI* untuk melanjutkan."
                )

            media_type = "video" if msg.media_type == "video_note" else msg.media_type
            entries.append(
                {
                    "item_no": item_no,
                    "media_type": media_type,
                    "media_path": msg.media_path,
                    "message_id": msg.message_id,
                }
            )
            payload["customer_media"] = entries
            await set_state(msg.phone, "cust_media", payload)

            label = "Foto" if media_type == "image" else "Video"
            return (
                f"{label} untuk *{machine}* sudah saya terima. "
                "Kalau ada tambahan silakan kirim lagi. "
                "Kalau sudah cukup ketik *SELESAI*."
            )

        if msg.media_type:
            return (
                "Untuk referensi mesin, kirim *foto atau video* ya. "
                "Kalau tidak ada, ketik *LEWATI*."
            )

        low = re.sub(r"\s+", " ", text.lower()).strip()
        finished = {
            "selesai",
            "sudah",
            "sudah cukup",
            "cukup",
            "udah",
            "wis",
            "wes",
            "lewati",
            "skip",
            "tidak ada",
            "ga ada",
            "gak ada",
            "nggak ada",
            "ngga ada",
            "ora ono",
            "ora ana",
            "mboten wonten",
            "ga bisa",
            "gak bisa",
            "nggak bisa",
            "belum ada",
        }

        if low in finished:
            return await _advance_customer_media(msg.phone, payload)

        # Pertanyaan sampingan boleh dijawab tanpa menghilangkan state media.
        if _looks_like_price_question(text):
            answer = await price_answer(text, items)
            return (
                answer
                + f"\n\nKalau ada, silakan lanjut kirim foto/video *{machine}*. "
                "Kalau tidak ada, ketik *LEWATI*."
            )

        analysis = await understand() if text else {}
        if analysis.get("intent") == "PRICE_QUESTION":
            answer = await price_answer(text, items)
            return (
                answer
                + f"\n\nKalau ada, silakan lanjut kirim foto/video *{machine}*. "
                "Kalau tidak ada, ketik *LEWATI*."
            )

        return (
            f"Sekarang saya masih menunggu foto atau video kondisi *{machine}*. "
            "Kalau sudah cukup ketik *SELESAI*. Kalau tidak ada, ketik *LEWATI*."
        )

    if st == "cust_landmark":
        if text and _looks_like_price_question(text):
            answer = await price_answer(
                text,
                _context_items_from_payload(payload),
            )
            return (
                answer
                + "\n\nKalau tidak ada patokan tambahan, cukup jawab *tidak ada* atau *cukup*."
            )

        control = quick.get("control")
        low_landmark = re.sub(r"\s+", " ", text.lower()).strip()

        no_landmark_words = (
            "tidak ada",
            "ga ada",
            "gak ada",
            "nggak ada",
            "ngga ada",
            "ora ono",
            "ora ana",
            "mboten wonten",
            "lewati",
            "skip",
            "cukup",
            "sudah cukup",
            "udah cukup",
            "wis cukup",
            "wes cukup",
        )

        no_landmark = (
            control in {"SKIP", "NO"}
            or low_landmark in no_landmark_words
            or any(word in low_landmark for word in (
                "tidak ada patokan",
                "gak ada patokan",
                "ga ada patokan",
                "nggak ada patokan",
                "ora ono patokan",
                "mboten wonten patokan",
            ))
        )

        landmark = "" if no_landmark else text[:500]

        customer = await get_or_create_customer(msg.phone)
        items = payload.get("items") or []
        location = payload.get("location")

        if not items or not location:
            await clear_state(msg.phone)
            return (
                "Data service belum lengkap. "
                "Mari mulai lagi dengan menjelaskan mesin yang membutuhkan service."
            )

        order = await create_order(customer["id"], location, landmark, items)
        await _persist_customer_media(order["id"], msg.phone, payload)
        await clear_state(msg.phone)

        offered = await start_offer_batch(order["id"])

        if offered:
            return (
                f"Data sudah lengkap. Nomor service Anda *{order['order_no']}*.\n"
                "Permintaan sedang saya tawarkan ke mekanik yang sesuai berdasarkan "
                "skill, radius, dan jarak. Saya akan melanjutkan proses setelah ada "
                "mekanik yang merespons."
            )

        # start_offer_batch sudah mengirim informasi NO_TECHNICIAN ke customer.
        # Balasan ini sengaja netral agar tidak muncul pesan yang bertentangan.
        return (
            f"Data service sudah lengkap dan tercatat dengan nomor *{order['order_no']}*. "
            "Nomor ini dapat digunakan untuk mengecek perkembangan service Anda."
        )

    if st == "cust_update_location":
        order_no = payload.get("order_no")
        if not msg.location:
            return "Silakan kirim *Share Location* baru untuk lokasi mesin."

        order = await find_order(order_no)
        if not order or order["customer_wa"] != msg.phone:
            await clear_state(msg.phone)
            return "Nomor service tidak ditemukan."

        async with pool().acquire() as conn:
            tech = None
            if order["assigned_technician_id"]:
                tech = await conn.fetchrow(
                    "SELECT * FROM technicians WHERE id=$1",
                    order["assigned_technician_id"],
                )

        if tech:
            lat = tech["current_lat"] if tech["current_lat"] is not None else tech["base_lat"]
            lon = tech["current_lon"] if tech["current_lon"] is not None else tech["base_lon"]
            new_distance = haversine_km(
                msg.location["lat"],
                msg.location["lon"],
                float(lat),
                float(lon),
            )

            if new_distance > min(
                float(tech["service_radius_km"]),
                settings.max_match_distance_km,
            ):
                await clear_state(msg.phone)
                await send_text(
                    settings.owner_wa_number,
                    f"⚠️ {order_no}: customer mengubah lokasi di luar radius mekanik. "
                    "Perlu penanganan manual/rematching.",
                )
                return (
                    "Lokasi baru berada di luar radius mekanik yang dipilih. "
                    "Multitek akan meninjau ulang sebelum mekanik berangkat."
                )

            old_fee = int(order["booking_fee"] or 0)
            new_fee = booking_fee_for_distance(new_distance)
            if new_fee is None or (old_fee and new_fee != old_fee):
                await clear_state(msg.phone)
                await send_text(
                    settings.owner_wa_number,
                    f"⚠️ {order_no}: perubahan lokasi mengubah tier biaya/jarak "
                    f"menjadi ±{new_distance:.1f} km. Mohon review manual.",
                )
                return (
                    "Lokasi baru mengubah jarak/biaya kunjungan. "
                    "Multitek akan memeriksa perubahan ini secara manual "
                    "sebelum mekanik berangkat."
                )

        async with pool().acquire() as conn:
            await conn.execute(
                """UPDATE service_orders
                   SET location_lat=$2,location_lon=$3,location_name=$4,
                       location_address=$5,location_source=$6,
                       location_confirmed=true,updated_at=now()
                   WHERE id=$1""",
                order["id"],
                msg.location["lat"],
                msg.location["lon"],
                msg.location.get("name") or "",
                msg.location.get("address") or "",
                msg.location.get("source") or "WHATSAPP_SHARE_LOCATION",
            )

        await clear_state(msg.phone)
        return (
            f"Lokasi {order_no} sudah diperbarui. "
            f"Balas *LOKASI BENAR {order_no}* untuk mengizinkan mekanik berangkat."
        )

    return None


def _simple_greeting_reply(text: str) -> str | None:
    up = re.sub(r"\s+", " ", (text or "").upper()).strip()

    exact = {
        "HALO",
        "HALLO",
        "HAI",
        "HI",
        "HELLO",
        "MAS",
        "MIN",
        "ADMIN",
        "PERMISI",
        "ASSALAMUALAIKUM",
        "ASSALAMU'ALAIKUM",
        "ASSALAMU ALAIKUM",
    }

    if up in exact:
        return "Ya. Ada yang bisa saya bantu terkait mesin atau kebutuhan teknisi?"

    time_greetings = {
        "PAGI": "Pagi juga.",
        "SELAMAT PAGI": "Selamat pagi.",
        "PAGI MAS": "Pagi juga.",
        "SIANG": "Siang juga.",
        "SELAMAT SIANG": "Selamat siang.",
        "SIANG MAS": "Siang juga.",
        "SORE": "Sore juga.",
        "SELAMAT SORE": "Selamat sore.",
        "SORE MAS": "Sore juga.",
        "MALAM": "Malam juga.",
        "SELAMAT MALAM": "Selamat malam.",
        "MALAM MAS": "Malam juga.",
        "HALO MAS": "Halo.",
        "HAI MAS": "Hai.",
    }

    if up in time_greetings:
        return (
            time_greetings[up]
            + " Ada yang bisa saya bantu terkait mesin atau kebutuhan teknisi?"
        )

    return None


async def handle_customer_message(msg: IncomingMessage) -> str:
    state_reply = await handle_customer_state(msg)
    if state_reply is not None:
        return state_reply

    text = (msg.text or "").strip()
    up = text.upper()

    greeting = _simple_greeting_reply(text)
    if greeting:
        return greeting

    if up in {"SERVIS", "SERVICE", "PANGGIL TEKNISI", "CARI MEKANIK"}:
        return await _start_intake(
            msg,
            {"machines": [], "machine_count": None},
        )

    active = await active_order_for_customer(msg.phone)

    if up == "STATUS" and active:
        return await customer_status_summary(active["order_no"])

    m = re.search(r"\b(MTK-[A-Z0-9-]+)\b", up)
    if "STATUS" in up and m:
        return await customer_status_summary(m.group(1))

    classified = await classify_customer_message(text)

    if classified["intent"] == "PRICE_QUESTION":
        await _remember_price_service_context(msg, classified)

        context_items = _machines_from_ai(classified)
        if not context_items and active:
            context_items = await _order_context_items(active["id"])

        return await price_answer(text, context_items)

    if classified["intent"] == "STATUS_QUESTION":
        if active:
            return await customer_status_summary(active["order_no"])
        return (
            "Saya belum menemukan service aktif pada nomor ini. "
            "Jika Anda punya nomor MTK, kirim misalnya: *STATUS MTK-260919-0003*."
        )

    if classified["intent"] == "SERVICE_REQUEST":
        return await _start_intake(msg, classified)

    return await conversational_customer_reply(text)


async def confirm_final_location(phone: str, order_no: str) -> str:
    order = await find_order(order_no)
    if not order or order["customer_wa"] != phone:
        return "Nomor service tidak ditemukan atau bukan milik nomor ini."

    if order["booking_payment_status"] != "PAID":
        return "Booking belum terverifikasi."

    await change_status(
        order["id"],
        "READY_TO_DEPART",
        "CUSTOMER",
        phone,
        "Lokasi final dikonfirmasi",
    )

    if order["technician_wa"]:
        location_text = (
            order["location_address"]
            or order["location_name"]
            or f"{order['location_lat']},{order['location_lon']}"
        )
        await send_text(
            order["technician_wa"],
            f"✅ {order_no} siap diberangkatkan.\n"
            f"Customer: {order['customer_name'] or '-'}\n"
            f"Lokasi: {location_text}\n"
            f"Patokan: {order['location_landmark'] or '-'}\n\n"
            f"Jika mulai berangkat, balas: *BERANGKAT {order_no}*",
        )

    return f"Lokasi {order_no} sudah dikonfirmasi. Mekanik sudah diberi izin untuk berangkat."


async def request_location_change(phone: str, order_no: str) -> str:
    order = await find_order(order_no)
    if not order or order["customer_wa"] != phone:
        return "Nomor service tidak ditemukan atau bukan milik nomor ini."

    if order["status"] in {"EN_ROUTE", "ARRIVED", "DIAGNOSING", "REPAIRING"}:
        return (
            "Mekanik sudah bergerak/berada di lokasi. "
            "Perubahan lokasi harus ditangani manual oleh Multitek."
        )

    await set_state(
        phone,
        "cust_update_location",
        {"order_no": order_no},
    )

    return (
        "Silakan kirim *Share Location baru* untuk lokasi mesin. "
        "Mekanik belum akan diberangkatkan sampai perubahan selesai dicek."
    )
