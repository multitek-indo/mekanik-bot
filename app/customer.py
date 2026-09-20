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


def _normalize_customer_text(text: str) -> str:
    """Normalize noisy Indonesian/Javanese only for intent detection.

    The raw customer sentence is still preserved for database values.  This
    helper makes common WhatsApp abbreviations, typos, ngoko/krama words, and
    mixed Indonesian-Javanese easier for deterministic guards to recognize.
    """
    low = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not low:
        return ""

    phrase_rules = (
        (r"\bdi\s*mana\b", "mana"),
        (r"\bneng\s+endi\b", "mana"),
        (r"\bning\s+endi\b", "mana"),
        (r"\bsaking\s+pundi\b", "dari mana"),
        (r"\bkados\s+pundi\b", "bagaimana"),
        (r"\bpunyamesin\b", "punya mesin"),
        (r"\bmesinjahit\b", "mesin jahit"),
        (r"\bgakjalan\b", "gak jalan"),
        (r"\bgajalan\b", "ga jalan"),
        (r"\n", " "),
    )
    for pattern, replacement in phrase_rules:
        low = re.sub(pattern, replacement, low, flags=re.I)

    word_rules = {
        # WhatsApp shorthand / common typos
        "brp": "berapa",
        "brapa": "berapa",
        "biya": "biaya",
        "byaya": "biaya",
        "hrga": "harga",
        "mkanik": "mekanik",
        "meknik": "mekanik",
        "teknsi": "teknisi",
        "tehnisi": "teknisi",
        "msin": "mesin",
        "mesn": "mesin",
        "jhkit": "jahit",
        "jhit": "jahit",
        "jait": "jahit",
        "srng": "sering",
        "lonct": "loncat",
        "eror": "error",
        "srvis": "servis",
        "service": "servis",
        "dateng": "datang",
        "dtg": "datang",
        "bs": "bisa",
        "gmn": "bagaimana",
        "gmna": "bagaimana",
        "gimana": "bagaimana",
        "knp": "kenapa",
        "kpn": "kapan",
        "dmn": "mana",
        # Javanese ngoko / krama frequently seen in WA
        "sampean": "anda",
        "sampeyan": "anda",
        "panjenengan": "anda",
        "piro": "berapa",
        "pinten": "berapa",
        "piye": "bagaimana",
        "pripun": "bagaimana",
        "opo": "apa",
        "nopo": "apa",
        "menopo": "apa",
        "ngopo": "kenapa",
        "ngendi": "mana",
        "endi": "mana",
        "pundi": "mana",
        "sopo": "siapa",
        "sinten": "siapa",
        "iso": "bisa",
        "saged": "bisa",
        "teko": "datang",
        "teka": "datang",
        "sesuk": "besok",
        "saiki": "sekarang",
        "ora": "tidak",
        "mboten": "tidak",
        "ono": "ada",
        "wonten": "ada",
        "omah": "rumah",
        "omahe": "rumah",
        "omahmu": "rumah",
        "cedak": "dekat",
        "kene": "sini",
        "mriki": "sini",
        "kantore": "kantor",
        "garansine": "garansi",
        "regane": "harga",
        "biayane": "biaya",
        "mekanike": "mekanik",
        "teknisine": "teknisi",
        "mesine": "mesin",
    }

    tokens = re.split(r"(\W+)", low)
    tokens = [word_rules.get(token, token) for token in tokens]
    low = "".join(tokens)
    return re.sub(r"\s+", " ", low).strip()


def _looks_like_question(text: str) -> bool:
    low = _normalize_customer_text(text)
    if not low:
        return False

    if "?" in (text or ""):
        return True

    question_markers = (
        "apa ",
        "apakah ",
        "bisa ",
        "boleh ",
        "kapan ",
        "mana ",
        "dari mana",
        "bagaimana",
        "kenapa",
        "mengapa",
        "kok ",
        "siapa",
        "berapa",
        "termasuk",
        "sudah termasuk",
        "ada garansi",
        "ada mekanik",
        "ada teknisi",
        "ada tidak",
        "ada nggak",
        "ada gak",
        "ada ga",
        "jadi bagaimana",
        "terus bagaimana",
    )
    return any(marker in low for marker in question_markers)

def _looks_like_problem_statement(text: str) -> bool:
    """Conservative fallback for short symptom statements.

    AI extraction remains primary. This only prevents ordinary symptom phrases
    such as "sering loncat mas" from being mistaken for general chat.
    """
    low = _normalize_customer_text(text)
    if not low:
        return False

    symptom_markers = (
        "error",
        "rusak",
        "macet",
        "mati",
        "loncat",
        "loncatan",
        "lompat",
        "skip",
        "putus",
        "patah",
        "bocor",
        "panas",
        "berisik",
        "bunyi",
        "suara",
        "kasar",
        "tidak jalan",
        "tidak mau jalan",
        "ga jalan",
        "gak jalan",
        "nggak jalan",
        "ngga jalan",
        "ora mlaku",
        "ra mlaku",
        "ra gelem mlaku",
        "tidak mlaku",
        "tidak bisa mlaku",
        "tidak gelem mlaku",
        "ora gelem mlaku",
        "ora muter",
        "tidak muter",
        "pedot",
        "seret",
        "getar",
        "geter",
        "ngebul",
        "nggerung",
        "setik",
        "jahitane",
        "tidak njahit",
        "ora njahit",
        "tidak respon",
        "tidak merespon",
        "ga respon",
        "gak respon",
        "nggak respon",
        "ngga respon",
        "jahitan",
        "benang",
        "jarum",
        "pedal",
        "dinamo",
        "motor",
        "servo",
        "kode",
        "ngadat",
        "miring",
        "tidak normal",
        "kendala",
        "masalah",
        "trouble",
    )
    return any(marker in low for marker in symptom_markers)


def _analysis_problem(analysis: dict | None) -> str:
    analysis = analysis or {}
    fields = analysis.get("fields") or {}
    problem = str(fields.get("problem") or "").strip()
    if problem:
        return problem[:1500]

    for item in list(analysis.get("machines") or []):
        if not isinstance(item, dict):
            continue
        problem = str(item.get("problem") or "").strip()
        if problem:
            return problem[:1500]

    return ""


def _clean_problem_fragment(text: str) -> str:
    low = _normalize_customer_text(text)
    if not low:
        return ""

    count_prefix = re.compile(
        r"^(?:(?:cuma|hanya|mung)\s+)?"
        r"(?:1|satu|sebuah|siji|setunggal|2|dua|loro|kalih|3|tiga|telu|telung|"
        r"4|empat|papat|5|lima|limo)"
        r"(?:\s*(?:unit|mesin|buah))?\b[\s,.;:-]*",
        flags=re.I,
    )
    cleaned = count_prefix.sub("", low, count=1).strip()

    for _ in range(4):
        new_value = re.sub(
            r"^(?:mas|min|pak|bu|mbak|mba|gan|ya|iya|nggih|nih|ini)\b[\s,.;:-]*",
            "",
            cleaned,
            count=1,
            flags=re.I,
        ).strip()
        if new_value == cleaned:
            break
        cleaned = new_value

    cleaned = re.sub(
        r"^(?:mesinnya|mesin saya|mesinku|mesin)\b[\s,.;:-]*",
        "",
        cleaned,
        count=1,
        flags=re.I,
    ).strip()
    cleaned = re.sub(
        r"[\s,.;:-]*(?:mas|min|pak|bu|mbak|mba|gan|nggih)$",
        "",
        cleaned,
        count=1,
        flags=re.I,
    ).strip()

    return cleaned


def _problem_from_count_reply(text: str, analysis: dict | None = None) -> str:
    """Extract a symptom even when count + symptom + another question share one message."""
    extracted = _analysis_problem(analysis)
    if extracted:
        return extracted

    raw = (text or "").strip()
    if not raw:
        return ""

    # Split natural multi-intent WhatsApp messages.  Example:
    # "siji mas, mesine sering loncat. mekanike iso teko sore?"
    fragments = [
        part.strip()
        for part in re.split(
            r"[\n.!?;,]+|\b(?:terus|trus|btw|ngomong\s*ngomong|tapi)\b",
            raw,
            flags=re.I,
        )
        if part.strip()
    ]

    candidates = fragments or [raw]
    for fragment in candidates:
        cleaned = _clean_problem_fragment(fragment)
        if len(cleaned) < 3:
            continue
        if _looks_like_price_question(cleaned):
            continue
        if _side_question_topic(cleaned) in {
            "schedule",
            "mechanic_origin",
            "company_identity",
            "warranty",
            "payment",
            "duration",
            "coverage",
            "process",
            "human",
        }:
            continue
        if _looks_like_problem_statement(cleaned):
            return cleaned[:1500]

    return ""

def _looks_like_name_answer(text: str) -> bool:
    raw = (text or "").strip()
    low = _normalize_customer_text(raw)
    if len(raw) < 2 or not low:
        return False
    if _looks_like_question(raw):
        return False
    if _looks_like_problem_statement(raw):
        return False

    banned = (
        "servis", "service", "mesin", "rusak", "error", "harga", "biaya",
        "mekanik", "teknisi", "datang", "lokasi", "garansi", "booking",
        "share location", "berapa", "bisa", "tolong carikan",
        "sedang", "lagi", "mau", "punya", "butuh", "perlu",
        "saya di", "aku di", "di rumah", "di pabrik", "di kantor",
    )
    if any(token in low for token in banned):
        return False

    cleaned = re.sub(
        r"(?i)^\s*(?:nama\s+(?:saya|aku)\s*[:=-]?\s*|saya\s+|aku\s+|"
        r"jenengku\s*[:=-]?\s*|asma\s+kula\s*[:=-]?\s*)",
        "",
        raw,
    ).strip()
    if not (2 <= len(cleaned) <= 100):
        return False
    words = cleaned.split()
    if not (1 <= len(words) <= 8):
        return False
    return bool(re.search(r"[A-Za-zÀ-ÿ]", cleaned))


def _merge_prefill_from_analysis(payload: dict, analysis: dict | None) -> bool:
    """Remember useful machine/count facts even if the customer answered another slot."""
    analysis = analysis or {}
    changed = False

    incoming = _machines_from_ai(analysis)
    if incoming:
        remembered = [
            dict(item)
            for item in list(payload.get("prefill_machines") or [])
            if isinstance(item, dict)
        ]
        if not remembered:
            remembered = [dict(item) for item in incoming]
            changed = True
        else:
            for new_item in incoming:
                new_machine = str(new_item.get("machine") or "").strip()
                new_problem = str(new_item.get("problem") or "").strip()
                matched = False
                for old_item in remembered:
                    old_machine = str(old_item.get("machine") or "").strip()
                    if new_machine and old_machine.lower() == new_machine.lower():
                        if new_problem and not str(old_item.get("problem") or "").strip():
                            old_item["problem"] = new_problem[:1500]
                            changed = True
                        matched = True
                        break
                if not matched and (new_machine or new_problem):
                    remembered.append(dict(new_item))
                    changed = True
        payload["prefill_machines"] = remembered[: settings.max_machines_per_order]

    count = analysis.get("machine_count")
    try:
        count = int(count) if count is not None else None
    except (TypeError, ValueError):
        count = None
    if count and 1 <= count <= settings.max_machines_per_order:
        if payload.get("pending_machine_count") != count:
            payload["pending_machine_count"] = count
            changed = True

    return changed


def _landmark_from_text_fallback(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""

    location_cues = (
        "depan", "belakang", "samping", "sebelah", "dekat", "gang", "gg ",
        "jalan ", "jl ", "rt ", "rw ", "masjid", "mushola", "musala",
        "alfamart", "indomaret", "pasar", "sekolah", "toko",
        "pertigaan", "perempatan", "jembatan", "lapangan",
        "rumah warna", "pagar", "gerbang",
    )
    parts = [
        part.strip()
        for part in re.split(r"[\n.!?;,]+", raw)
        if part.strip()
    ]
    for part in parts or [raw]:
        low = _normalize_customer_text(part)
        if any(cue in low for cue in location_cues):
            return part[:500]
    return ""


def _media_finish_requested(text: str) -> bool:
    low = _normalize_customer_text(text)
    if not low:
        return False
    done_phrases = (
        "selesai", "sudah cukup", "sudah", "cukup", "udah", "wis", "wes",
        "lewati", "skip", "tidak ada", "ga ada", "gak ada", "nggak ada",
        "ngga ada", "ora ono", "ora ana", "belum ada", "ga bisa",
        "gak bisa", "nggak bisa",
    )
    first = re.split(r"[,.;!?]|\b(?:tapi|terus|trus)\b", low, maxsplit=1)[0].strip()
    return first in done_phrases


def _price_question_kind(text: str) -> str | None:
    low = _normalize_customer_text(text)
    if not low:
        return None

    if "booking" in low and any(
        marker in low
        for marker in (
            "berapa",
            "biaya",
            "harga",
            "tarif",
            "termasuk",
            "masuk jasa",
            "pengurang",
            "potong",
            "dipotong",
            "kembali",
            "refund",
        )
    ):
        return "booking"

    if any(x in low for x in ("spare part", "sparepart", "suku cadang")) and (
        _looks_like_question(text)
        or any(x in low for x in ("harga", "biaya", "tarif", "termasuk", "ganti"))
    ):
        return "sparepart"

    if any(
        marker in low
        for marker in (
            "tidak jadi diperbaiki",
            "gak jadi diperbaiki",
            "ga jadi diperbaiki",
            "nggak jadi diperbaiki",
            "tidak lanjut perbaikan",
            "gak lanjut perbaikan",
            "ga lanjut perbaikan",
        )
    ):
        return "not_repaired"

    tier_markers = {
        "inspection": ("pengecekan", "cek saja", "biaya cek", "harga cek"),
        "light": ("ringan",),
        "medium": ("sedang",),
        "heavy": ("berat",),
    }
    for kind, markers in tier_markers.items():
        if any(marker in low for marker in markers) and (
            _looks_like_question(text)
            or any(x in low for x in ("harga", "biaya", "tarif", "ongkos"))
        ):
            return kind

    generic_markers = (
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
        "estimasi biaya",
        "perkiraan biaya",
    )
    if any(marker in low for marker in generic_markers):
        return "overview"

    return None


def _looks_like_price_question(text: str) -> bool:
    return _price_question_kind(text) is not None


async def price_answer(
    text: str,
    context_items: list[dict] | None = None,
) -> str:
    context_items = list(context_items or [])
    context = _context_text(context_items)
    label = _context_label(context_items)
    lookup_text = " ".join(x for x in (text, context) if x)
    code = detect_skill_code(lookup_text)
    kind = _price_question_kind(text) or "overview"

    subject = f"Untuk *{label}*, " if label else "Untuk service mesin, "

    if kind == "booking":
        return (
            subject
            + "booking dihitung dari jarak lokasi, bukan dari tingkat kerusakan. "
            + f"Tarif booking saat ini: {booking_tier_text()}\n\n"
            + "Booking yang sudah dibayar menjadi kredit/pengurang jasa jika "
            + "perbaikan berhasil. Spare part tetap dihitung terpisah."
        )

    if kind == "sparepart":
        return (
            subject
            + "spare part belum termasuk dalam booking atau nominal jasa yang saya tampilkan. "
            + "Kalau setelah diagnosis ada komponen yang perlu diganti, kebutuhan dan nilainya "
            + "harus dikonfirmasi terlebih dahulu sebelum pekerjaan dilanjutkan."
        )

    if kind == "not_repaired":
        return (
            subject
            + "kalau setelah pengecekan pekerjaan tidak dilanjutkan ke perbaikan, "
            + "biaya akhirnya harus mengikuti hasil diagnosis dan status transaksi pada order. "
            + "Saya tidak akan menebak nominal potongan atau pengembalian sebelum hasilnya tercatat."
        )

    row = None
    if code:
        async with pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM service_price_matrix WHERE skill_code=$1",
                code,
            )

    if kind in {"inspection", "light", "medium", "heavy"}:
        labels = {
            "inspection": ("pengecekan", "inspection_fee"),
            "light": ("ringan", "light_fee"),
            "medium": ("sedang", "medium_fee"),
            "heavy": ("berat", "heavy_fee"),
        }
        tier_name, column = labels[kind]

        if not code:
            return (
                f"Untuk kategori *{tier_name}*, saya perlu tahu jenis mesinnya dulu "
                "supaya tidak mengambil matrix tarif yang salah."
            )

        if not row:
            return (
                f"Untuk kategori *{tier_name}* pada {label or 'mesin tersebut'}, "
                "nominal detailnya belum tersedia di matrix. "
                "Kategori dan biaya final tetap dikonfirmasi setelah diagnosis mekanik."
            )

        amount = int(row[column] or 0)
        if not amount:
            return (
                f"Untuk *{row['skill_name']}* kategori *{tier_name}*, "
                "nominalnya belum dikunci di matrix dan masih memerlukan quotation setelah diagnosis."
            )

        return (
            f"Untuk *{row['skill_name']}* kategori *{tier_name}*, "
            f"acuan matrix saat ini *{rupiah(amount)}*. "
            "Kategori ringan/sedang/berat baru dipastikan setelah mekanik melakukan diagnosis. "
            "Spare part, bila diperlukan, dihitung terpisah."
        )

    base = (
        subject
        + "biaya awal yang bisa dipastikan adalah booking berdasarkan jarak lokasi. "
        + f"Tarif booking saat ini: {booking_tier_text()}\n\n"
        + "Untuk jasa perbaikan, nilainya mengikuti jenis mesin dan tingkat kesulitan "
        + "setelah diagnosis. Booking yang sudah dibayar menjadi pengurang jasa jika "
        + "perbaikan berhasil; spare part dihitung terpisah."
    )

    if not code:
        if context_items:
            return (
                base
                + "\n\nUntuk mesin yang sudah Anda jelaskan, saya belum menemukan matrix "
                + "yang cukup spesifik untuk memberi nominal jasa tanpa diagnosis."
            )

        return (
            base
            + "\n\nSebutkan jenis mesin dan keluhannya kalau Anda ingin saya cek "
            + "apakah matrix tarif detailnya sudah tersedia."
        )

    if not row:
        return (
            base
            + "\n\nTarif jasa detail untuk kategori mesin ini belum tersedia di matrix "
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



def _interruption_context_items(payload: dict) -> list[dict]:
    items = list(_context_items_from_payload(payload))
    current_machine = str(payload.get("current_machine") or "").strip()

    if current_machine:
        existing = {
            str(
                item.get("machine")
                or item.get("machine_text")
                or ""
            ).strip().lower()
            for item in items
            if isinstance(item, dict)
        }
        if current_machine.lower() not in existing:
            items.append({"machine": current_machine, "problem": ""})

    return items


def _state_resume_prompt(state: str, payload: dict) -> str:
    if state == "cust_name":
        return "Kalau sudah jelas, boleh sebutkan nama Anda atau nama perusahaan?"

    if state == "cust_machine_count":
        return "Kalau lanjut, ada berapa unit mesin yang mau dicek?"

    if state == "cust_machine_desc":
        idx = int(payload.get("machine_index") or 1)
        return f"Untuk lanjut, mesin ke-{idx} jenis/merk/modelnya apa?"

    if state == "cust_machine_problem":
        machine = str(payload.get("current_machine") or "mesin tersebut").strip()
        return f"Kalau lanjut, apa keluhan pada *{machine}*? Ceritakan gejalanya saja—misalnya loncat, bunyi kasar, error, atau tidak jalan."

    if state == "cust_location":
        return "Kalau lanjut, kirim *Share Location* lokasi mesinnya ya supaya saya bisa mencari mekanik terdekat."

    if state == "cust_location_confirm":
        return "Kalau titik lokasi tadi sudah benar, jawab *iya* atau *betul*. Kalau salah, kirim Share Location ulang."

    if state == "cust_media":
        try:
            item_no = int(payload.get("media_item_no") or 1)
        except (TypeError, ValueError):
            item_no = 1
        machine = _media_machine_label(payload, item_no)
        return (
            f"Kalau ada, silakan lanjut kirim foto/video *{machine}*. "
            "Kalau tidak ada, ketik *LEWATI*."
        )

    if state == "cust_landmark":
        return "Kalau ada, sebutkan patokan lokasinya. Kalau tidak ada, cukup jawab *cukup* atau *tidak ada*."

    if state == "cust_price_context":
        return "Kalau ingin dilanjutkan menjadi permintaan service, tinggal bilang *lanjut* atau *carikan mekanik*."

    if state == "cust_update_location":
        return "Untuk melanjutkan perubahan lokasi, kirim *Share Location* yang baru."

    return ""


def _side_question_topic(text: str) -> str | None:
    low = _normalize_customer_text(text)
    if not low:
        return None

    if _looks_like_price_question(text):
        return "price"

    if any(x in low for x in ("garansi", "warranty")):
        return "warranty"

    if any(
        marker in low
        for marker in (
            "cara bayar",
            "cara pembayaran",
            "bayarnya bagaimana",
            "bayar bagaimana",
            "transfer kemana",
            "transfer ke mana",
            "transfer mana",
            "bisa cash",
            "bisa tunai",
            "bisa qris",
            "pembayaran bagaimana",
            "bayare bagaimana",
        )
    ):
        return "payment"

    # Questions directed at the bot/company itself, e.g. "sampean rumahnya mana?"
    if any(
        marker in low
        for marker in (
            "anda rumah",
            "anda mana",
            "kamu mana",
            "admin mana",
            "anda siapa",
            "kamu siapa",
            "ini bot",
            "bot atau admin",
            "rumah anda",
            "rumahnya mana",
            "alamatnya mana",
            "alamat anda",
            "anda alamat",
            "kantor mana",
            "alamat kantor",
            "lokasi kantor",
            "multitek mana",
            "multitek dari mana",
            "anda dari mana",
            "kamu dari mana",
            "admin dari mana",
        )
    ):
        return "company_identity"

    if re.search(r"\b(?:anda|kamu|admin)\b.*\b(?:rumah|alamat|kantor|mana|siapa)\b", low):
        return "company_identity"

    if re.search(r"\b(?:mekanik|teknisi)\b.*\b(?:mana|asal|daerah)\b", low):
        return "mechanic_origin"

    if any(
        marker in low
        for marker in (
            "mekanik dari mana",
            "teknisi dari mana",
            "mekanik mana",
            "teknisi mana",
            "lokasi mekanik",
            "lokasi teknisi",
            "mekanik rumah",
            "teknisi rumah",
            "mekanik daerah mana",
            "teknisi daerah mana",
        )
    ):
        return "mechanic_origin"

    if any(
        marker in low
        for marker in (
            "bisa datang",
            "bisa hari",
            "datang kapan",
            "kapan datang",
            "kapan mekanik",
            "kapan teknisi",
            "jadwal mekanik",
            "jadwal teknisi",
            "jam berapa datang",
            "datang jam berapa",
            "datang sore",
            "datang pagi",
            "datang malam",
            "datang siang",
            "hari minggu",
            "hari sabtu",
            "besok bisa",
            "hari ini bisa",
            "maunya sore",
            "maunya pagi",
            "maunya malam",
            "sekarang bisa",
        )
    ):
        return "schedule"

    if any(
        marker in low
        for marker in (
            "berapa lama",
            "lama perbaikan",
            "lama servis",
            "selesai berapa lama",
            "pengerjaan berapa lama",
        )
    ):
        return "duration"

    if any(
        marker in low
        for marker in (
            "daerah saya ada mekanik",
            "daerah saya ada teknisi",
            "ada mekanik dekat",
            "ada teknisi dekat",
            "mekanik dekat sini",
            "teknisi dekat sini",
            "bisa ke daerah",
            "bisa sampai",
            "sampai daerah",
            "bisa melayani",
            "bisa ke lokasi saya",
            "jangkau daerah",
            "jangkau lokasi",
            "melayani daerah",
            "melayani sampai",
        )
    ):
        return "coverage"

    if any(
        marker in low
        for marker in (
            "alur servis",
            "alur service",
            "prosesnya bagaimana",
            "cara panggil mekanik",
            "cara pesan mekanik",
            "cara order",
            "selanjutnya bagaimana",
        )
    ):
        return "process"

    if any(
        marker in low
        for marker in (
            "admin manusia",
            "bicara sama admin",
            "bicara dengan admin",
            "hubungi admin",
            "orang asli",
            "customer service manusia",
            "cs manusia",
        )
    ):
        return "human"

    if any(
        marker in low
        for marker in (
            "bisa diservis",
            "bisa diperbaiki",
            "melayani mesin",
            "bisa service",
            "bisa servis",
        )
    ):
        return "service_capability"

    # A question about a symptom is not an unrelated interruption.  It can be
    # recorded as the complaint while we answer cautiously about diagnosis.
    if _looks_like_problem_statement(low) and any(
        marker in low for marker in ("kenapa", "kok ", "penyebab", "akibat apa")
    ):
        return "diagnosis"

    if _looks_like_question(text):
        return "general"

    return None


def _append_resume(answer: str, resume: str) -> str:
    answer = (answer or "").strip()
    resume = (resume or "").strip()

    if not resume:
        return answer
    if not answer:
        return resume
    return answer + "\n\n" + resume


async def _common_question_answer(
    msg: IncomingMessage,
    topic: str | None,
    text: str,
    context_items: list[dict] | None = None,
    analysis: dict | None = None,
) -> str | None:
    analysis = analysis or {}
    context_items = list(context_items or [])

    if topic == "price" or analysis.get("intent") == "PRICE_QUESTION":
        return await price_answer(text, context_items)

    if analysis.get("intent") == "STATUS_QUESTION":
        active = await active_order_for_customer(msg.phone)
        if active:
            return await customer_status_summary(active["order_no"])
        return (
            "Untuk proses yang sedang kita isi ini belum ada nomor service, "
            "jadi status pencarian mekanik memang belum terbentuk."
        )

    if topic == "company_identity":
        return (
            "Saya admin virtual Multitek Service, jadi saya bukan mekanik yang datang langsung "
            "dan tidak punya alamat rumah pribadi. Untuk kunjungan service, saya akan mencarikan "
            "mekanik yang skill-nya sesuai dan paling masuk radius dari lokasi mesin Anda."
        )

    if topic == "schedule":
        return (
            "Bisa saya bantu carikan jadwal, tetapi waktunya belum bisa saya janjikan "
            "sebelum ada mekanik yang menerima pekerjaan. Setelah ada kandidat yang cocok, "
            "jadwal kedatangannya bisa dikonfirmasi sesuai ketersediaan mekanik."
        )

    if topic == "mechanic_origin":
        return (
            "Mekanik tidak berasal dari satu tempat tertentu. Sistem mencari mekanik aktif "
            "yang skill-nya sesuai dan masih masuk radius dari lokasi mesin. Nama dan jaraknya "
            "baru bisa diketahui setelah ada kandidat yang merespons."
        )

    if topic == "warranty":
        return (
            "Garansi mengikuti pekerjaan yang benar-benar dilakukan. Setelah diagnosis dan "
            "jenis perbaikannya jelas, ketentuan garansi jasa atau spare part bisa dikonfirmasi "
            "sebelum pekerjaan disetujui."
        )

    if topic == "payment":
        return (
            "Pembayaran mengikuti tahapan order. Jangan transfer sebelum ada instruksi resmi "
            "di percakapan service. Booking dihitung dari jarak dan menjadi pengurang jasa "
            "jika perbaikan berhasil."
        )

    if topic == "duration":
        return (
            "Lama pengerjaan tergantung jenis kerusakan dan kebutuhan spare part. Sebelum "
            "diagnosis saya belum bisa memberi waktu pasti; setelah dicek, estimasinya bisa "
            "dijelaskan sebelum pekerjaan dilanjutkan."
        )

    if topic == "coverage":
        return (
            "Bisa dicek. Ketersediaan mekanik ditentukan dari *Share Location* lokasi mesin, "
            "lalu sistem mencocokkan skill, radius layanan, dan jarak mekanik."
        )

    if topic == "process":
        return (
            "Alurnya sederhana: saya catat mesin dan keluhannya, minta lokasi serta foto/video "
            "jika ada, lalu sistem mencari mekanik yang sesuai. Setelah ada mekanik yang "
            "merespons, proses booking dan kedatangan dilanjutkan dari order yang sama."
        )

    if topic == "human":
        return (
            "Saya admin virtual yang membantu intake dan alur service. Bagian yang membutuhkan "
            "keputusan manual tetap dapat ditinjau oleh pengelola Multitek melalui order yang tercatat."
        )

    if topic == "service_capability":
        return (
            "Bisa saya cek dan carikan mekanik yang sesuai. Jenis kerusakan tetap perlu dicatat "
            "supaya pencarian skill mekaniknya tidak salah."
        )

    if topic == "diagnosis":
        return (
            "Gejala seperti itu bisa punya beberapa penyebab, jadi saya tidak akan menebak "
            "kerusakan final sebelum mesin dicek. Keluhannya tetap saya catat supaya mekanik "
            "punya gambaran awal."
        )

    if topic == "general":
        return await conversational_customer_reply(text)

    return None


async def _answer_side_question(
    msg: IncomingMessage,
    state: str,
    payload: dict,
    analysis: dict | None = None,
    context_items: list[dict] | None = None,
) -> str | None:
    text = (msg.text or "").strip()
    if not text:
        return None

    analysis = analysis or {}
    resume = _state_resume_prompt(state, payload)
    context_items = list(context_items or _interruption_context_items(payload))

    if analysis.get("control") == "GREETING":
        return _append_resume("Halo, silakan.", resume)

    topic = _side_question_topic(text)
    if topic is None and analysis.get("intent") == "PRICE_QUESTION":
        topic = "price"
    if topic is None and analysis.get("intent") == "STATUS_QUESTION":
        topic = "general"

    answer = await _common_question_answer(
        msg,
        topic,
        text,
        context_items=context_items,
        analysis=analysis,
    )
    if answer is None:
        return None
    return _append_resume(answer, resume)


async def _apply_machine_count(
    phone: str,
    payload: dict,
    count: int,
    machines: list[dict] | None = None,
) -> str:
    if not (1 <= count <= settings.max_machines_per_order):
        return f"Jumlah mesin harus 1 sampai {settings.max_machines_per_order}."

    remembered = list(payload.pop("prefill_machines", []) or [])
    source = list(machines or remembered)
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
    payload.pop("pending_problem", None)

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
        machine_label = str(machines[0]["machine"]).strip()
        if machine_label.lower().startswith("mesin "):
            machine_phrase = f"*{machine_label}*"
        else:
            machine_phrase = f"mesin *{machine_label}*"
        return (
            f"Baik, saya menangkap {machine_phrase}. "
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
        low = _normalize_customer_text(text)

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

        if (
            _looks_like_price_question(text)
            or analysis.get("intent") == "PRICE_QUESTION"
        ):
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

        side = await _answer_side_question(
            msg,
            st,
            payload,
            analysis,
        )
        if side is not None:
            return side

        return await conversational_customer_reply(text)

    if st == "cust_name":
        analysis = await understand() if text else {}

        if quick.get("control") == "GREETING" or analysis.get("control") == "GREETING":
            return (
                "Halo. Sebelum melanjutkan pencarian mekanik, "
                "boleh tahu nama Anda atau nama perusahaan?"
            )

        if len(text) < 2:
            return "Boleh sebutkan nama Anda atau nama perusahaan?"

        fields = analysis.get("fields") or {}
        name = str(fields.get("name") or "").strip()

        remembered_extra = _merge_prefill_from_analysis(payload, analysis)
        if remembered_extra:
            await set_state(msg.phone, "cust_name", payload)

        if not name:
            side = await _answer_side_question(
                msg,
                st,
                payload,
                analysis,
            )
            if side is not None:
                return side

            if _looks_like_name_answer(text):
                name = re.sub(
                    r"(?i)^\s*(?:nama\s+(?:saya|aku)\s*[:=-]?\s*|"
                    r"saya\s+|aku\s+|jenengku\s*[:=-]?\s*|"
                    r"asma\s+kula\s*[:=-]?\s*)",
                    "",
                    text,
                ).strip()

        if not name or len(name) < 2:
            prefix = "Info mesinnya sudah saya catat dulu. " if remembered_extra else ""
            return prefix + "Saya belum menangkap namanya. Boleh sebutkan nama Anda atau perusahaan?"

        async with pool().acquire() as conn:
            await conn.execute(
                "UPDATE customers SET name=$2,updated_at=now() WHERE id=$1",
                payload["customer_id"],
                name[:150],
            )

        pending = payload.pop("pending_machine_count", None)
        if pending:
            next_prompt = await _apply_machine_count(
                msg.phone,
                payload,
                int(pending),
                payload.get("prefill_machines"),
            )
        else:
            await set_state(msg.phone, "cust_machine_count", payload)
            next_prompt = (
                f"Terima kasih, {name}. Ada berapa mesin yang ingin dicek? "
                "Boleh jawab *satu*, *2 unit*, *loro mesin*, dan sebagainya."
            )

        if (
            _looks_like_price_question(text)
            or analysis.get("intent") == "PRICE_QUESTION"
        ):
            answer = await price_answer(
                text,
                _interruption_context_items(payload),
            )
            return _append_resume(answer, next_prompt)

        return next_prompt

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
        analysis = await understand() if text else {}
        if count is None:
            count = analysis.get("machine_count")

        problem_hint = _problem_from_count_reply(text, analysis)
        extra_machines = list(analysis.get("machines") or [])
        original_prefill = [
            dict(item)
            for item in list(payload.get("prefill_machines") or [])
            if isinstance(item, dict)
        ]
        original_pending_problem = str(payload.get("pending_problem") or "").strip()
        prefill = [dict(item) for item in original_prefill]
        if extra_machines:
            prefill = [
                dict(item)
                for item in extra_machines
                if isinstance(item, dict)
            ]

        # A customer may answer the count and the symptom in one natural sentence,
        # e.g. "Satu mas mesinnya sering loncatan". Merge that symptom into
        # the already-known machine instead of asking for it again.
        if problem_hint:
            merged = False
            for item in prefill:
                machine = str(item.get("machine") or "").strip()
                existing_problem = str(item.get("problem") or "").strip()
                if machine and not existing_problem:
                    item["problem"] = problem_hint
                    merged = True
                    break

            if not merged:
                fields = analysis.get("fields") or {}
                machine = str(fields.get("machine_description") or "").strip()
                if not machine and extra_machines:
                    machine = str(extra_machines[0].get("machine") or "").strip()

                if machine:
                    prefill.insert(
                        0,
                        {"machine": machine[:300], "problem": problem_hint},
                    )
                else:
                    # Keep the symptom until the machine description is supplied.
                    payload["pending_problem"] = problem_hint

        # Keep useful machine/problem details even if the customer still has not
        # answered the quantity question. This avoids asking them to repeat data.
        # Only write conversation state when this message actually changed the
        # remembered machine/problem data. A pure side question such as
        # "Sampean rumahnya mana?" must not trigger an unnecessary DB write.
        new_prefill = prefill[: settings.max_machines_per_order]
        if new_prefill:
            payload["prefill_machines"] = new_prefill

        state_payload_changed = (
            new_prefill != original_prefill
            or str(payload.get("pending_problem") or "").strip()
            != original_pending_problem
        )
        if count is None and state_payload_changed:
            await set_state(msg.phone, "cust_machine_count", payload)

        if (
            _looks_like_price_question(text)
            or analysis.get("intent") == "PRICE_QUESTION"
        ):
            answer = await price_answer(
                text,
                _context_items_from_payload(payload),
            )

            if count is not None:
                next_prompt = await _apply_machine_count(
                    msg.phone,
                    payload,
                    int(count),
                    prefill,
                )
                return _append_resume(answer, next_prompt)

            return _append_resume(
                answer,
                "Untuk melanjutkan pencarian mekanik, ada berapa mesin yang ingin dicek?",
            )

        if count is not None:
            next_prompt = await _apply_machine_count(
                msg.phone,
                payload,
                int(count),
                prefill,
            )

            # A single WhatsApp message can contain count + symptom + another
            # question. Record the usable data first, then answer the side question
            # without losing the newly advanced state.
            if len(payload.get("items") or []) >= int(count):
                next_state = "cust_location"
            elif payload.get("current_machine"):
                next_state = "cust_machine_problem"
            else:
                next_state = "cust_machine_desc"

            side_topic = _side_question_topic(text)
            if side_topic in {
                "schedule", "mechanic_origin", "company_identity", "warranty",
                "payment", "duration", "coverage", "process", "human",
                "service_capability", "diagnosis", "price", "general",
            }:
                side = await _answer_side_question(
                    msg,
                    next_state,
                    payload,
                    analysis,
                )
                if side is not None:
                    return side

            return next_prompt

        side = await _answer_side_question(
            msg,
            st,
            payload,
            analysis,
        )
        if side is not None:
            return side

        return (
            "Saya masih perlu jumlah mesinnya. Tidak harus pakai angka; "
            "boleh jawab *cuma satu*, *mung siji*, *kalih unit*, dan sebagainya."
        )

    if st == "cust_machine_desc":
        if not text:
            return "Sebutkan yang Anda tahu tentang mesinnya, misalnya merek, jenis, atau model."

        analysis = await understand()
        fields = analysis.get("fields") or {}
        machines = analysis.get("machines") or []
        machine = str(fields.get("machine_description") or "").strip()
        problem = str(fields.get("problem") or "").strip()

        if machines:
            machine = machine or str(machines[0].get("machine") or "").strip()
            problem = problem or str(machines[0].get("problem") or "").strip()

        pending_problem = str(payload.get("pending_problem") or "").strip()
        if machine and not problem and pending_problem:
            problem = pending_problem

        if (
            _looks_like_price_question(text)
            or analysis.get("intent") == "PRICE_QUESTION"
        ):
            price_context = _interruption_context_items(payload)
            if machine or problem:
                price_context.append({"machine": machine, "problem": problem})

            answer = await price_answer(text, price_context)

            if machine and problem:
                next_prompt = await _finish_machine_item(
                    msg.phone,
                    payload,
                    machine,
                    problem,
                )
                return _append_resume(answer, next_prompt)

            if machine:
                payload["current_machine"] = machine[:300]
                await set_state(msg.phone, "cust_machine_problem", payload)
                next_prompt = f"Saya juga catat mesinnya *{machine}*. Keluhannya bagaimana?"
                return _append_resume(answer, next_prompt)

            return _append_resume(
                answer,
                _state_resume_prompt(st, payload),
            )

        if analysis.get("control") == "GREETING":
            return "Halo. Kita lanjut ya. Mesin yang bermasalah jenis/merk/modelnya apa?"

        side_topic = _side_question_topic(text)

        if machine:
            if problem:
                next_prompt = await _finish_machine_item(
                    msg.phone,
                    payload,
                    machine,
                    problem,
                )
                count = int(payload.get("machine_count") or len(payload.get("items") or []))
                next_state = (
                    "cust_location"
                    if len(payload.get("items") or []) >= count
                    else "cust_machine_desc"
                )
            else:
                payload["current_machine"] = machine[:300]
                await set_state(msg.phone, "cust_machine_problem", payload)
                next_state = "cust_machine_problem"
                next_prompt = (
                    f"Baik, saya catat *{machine}*. "
                    "Ceritakan gejalanya ya—misalnya loncat, bunyi kasar, error, atau tidak jalan."
                )

            if side_topic in {
                "schedule", "mechanic_origin", "company_identity", "warranty",
                "payment", "duration", "coverage", "process", "human",
                "service_capability", "diagnosis", "general",
            }:
                side = await _answer_side_question(
                    msg,
                    next_state,
                    payload,
                    analysis,
                )
                if side is not None:
                    return side

            return next_prompt

        # If the customer gives the symptom before naming the machine, keep it.
        # We can ask only for the missing machine instead of forcing repetition.
        if not machine and problem and side_topic not in {
            "schedule", "mechanic_origin", "company_identity", "warranty",
            "payment", "duration", "coverage", "process", "human", "price",
        }:
            payload["pending_problem"] = problem[:1500]
            await set_state(msg.phone, "cust_machine_desc", payload)
            return (
                "Keluhannya sudah saya catat. Tinggal sebutkan mesin yang dimaksud—"
                "merek, jenis, atau model yang Anda tahu saja."
            )

        if (
            not machine
            and not problem
            and _looks_like_problem_statement(text)
            and not _looks_like_question(text)
        ):
            payload["pending_problem"] = text[:1500]
            await set_state(msg.phone, "cust_machine_desc", payload)
            return (
                "Keluhannya sudah saya catat. Tinggal sebutkan mesin yang dimaksud—"
                "merek, jenis, atau model yang Anda tahu saja."
            )

        side = await _answer_side_question(
            msg,
            st,
            payload,
            analysis,
        )
        if side is not None:
            return side

        normalized = str(analysis.get("normalized_text") or "").lower()
        if any(x in normalized for x in ("tidak tahu", "tidak mengetahui")):
            return (
                "Tidak masalah kalau tidak tahu modelnya. "
                "Sebutkan yang diketahui saja, misalnya *Juki*, *obras*, "
                "*jarum 1*, atau mereknya saja."
            )

        if analysis.get("requires_clarification"):
            return "Saya belum yakin jenis mesinnya. Boleh sebutkan merek/jenis yang Anda tahu?"

        return (
            "Saya belum menangkap jenis mesinnya. "
            "Sebutkan yang Anda tahu saja, misalnya merek, jenis, atau model."
        )

    if st == "cust_machine_problem":
        if not text:
            return (
                "Ceritakan gejalanya, misalnya tidak jalan, suara kasar, "
                "benang putus, error, atau lainnya."
            )

        analysis = await understand()
        fields = analysis.get("fields") or {}
        machines = analysis.get("machines") or []
        problem = str(fields.get("problem") or "").strip()

        if not problem and machines:
            problem = str(machines[0].get("problem") or "").strip()

        current_machine = str(payload.get("current_machine") or "").strip()

        if (
            _looks_like_price_question(text)
            or analysis.get("intent") == "PRICE_QUESTION"
        ):
            price_context = _interruption_context_items(payload)
            if current_machine and problem:
                price_context = [
                    item
                    for item in price_context
                    if str(item.get("machine") or "").strip().lower()
                    != current_machine.lower()
                ]
                price_context.append({"machine": current_machine, "problem": problem})

            answer = await price_answer(text, price_context)

            if problem:
                next_prompt = await _finish_machine_item(
                    msg.phone,
                    payload,
                    current_machine,
                    problem,
                )
                return _append_resume(answer, next_prompt)

            return _append_resume(
                answer,
                _state_resume_prompt(st, payload),
            )

        if analysis.get("control") == "GREETING":
            return (
                "Halo. Kita lanjut ya. "
                f"Apa keluhan pada *{current_machine or 'mesin tersebut'}*?"
            )

        side_topic = _side_question_topic(text)

        if not problem and _looks_like_problem_statement(text):
            # Preserve the customer's wording if NLU did not extract a clean problem.
            # This also works for mixed messages such as
            # "sering loncat mas, mekanike iso teko sore?".
            fragments = [
                p.strip()
                for p in re.split(r"[\n.!?;,]+", text)
                if p.strip()
            ]
            for fragment in fragments or [text]:
                if _looks_like_problem_statement(fragment) and _side_question_topic(fragment) not in {
                    "schedule", "mechanic_origin", "company_identity", "warranty",
                    "payment", "duration", "coverage", "process", "human",
                }:
                    problem = fragment[:1500]
                    break

        if problem:
            next_prompt = await _finish_machine_item(
                msg.phone,
                payload,
                current_machine,
                problem,
            )
            count = int(payload.get("machine_count") or len(payload.get("items") or []))
            next_state = (
                "cust_location"
                if len(payload.get("items") or []) >= count
                else "cust_machine_desc"
            )

            if side_topic in {
                "schedule", "mechanic_origin", "company_identity", "warranty",
                "payment", "duration", "coverage", "process", "human",
                "service_capability", "diagnosis", "general",
            }:
                side = await _answer_side_question(
                    msg,
                    next_state,
                    payload,
                    analysis,
                )
                if side is not None:
                    return side

            return next_prompt

        side = await _answer_side_question(
            msg,
            st,
            payload,
            analysis,
        )
        if side is not None:
            return side

        normalized = str(analysis.get("normalized_text") or "").lower()
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

        return (
            "Saya belum menangkap gejala kerusakannya. "
            f"Boleh ceritakan apa yang terjadi pada *{current_machine or 'mesin tersebut'}*?"
        )

    if st == "cust_location":
        if not msg.location:
            analysis = await understand() if text else {}
            side = await _answer_side_question(
                msg,
                st,
                payload,
                analysis,
            )
            if side is not None:
                return side

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

        control = quick.get("control")
        analysis = None
        if control not in {"YES", "NO"} and text:
            analysis = await understand()
            control = analysis.get("control")

        if control == "YES":
            next_prompt = await _begin_customer_media(msg.phone, payload)
            topic = _side_question_topic(text)
            if topic not in {None, "general"}:
                answer = await _common_question_answer(
                    msg,
                    topic,
                    text,
                    context_items=_interruption_context_items(payload),
                    analysis=analysis or {},
                )
                if answer:
                    return _append_resume(answer, next_prompt)
            return next_prompt

        if control == "NO":
            next_prompt = "Baik, berarti titik tadi belum benar. Silakan kirim *Share Location* yang benar."
            topic = _side_question_topic(text)
            if topic not in {None, "general"}:
                answer = await _common_question_answer(
                    msg,
                    topic,
                    text,
                    context_items=_interruption_context_items(payload),
                    analysis=analysis or {},
                )
                if answer:
                    return _append_resume(answer, next_prompt)
            return next_prompt

        if text:
            if analysis is None:
                analysis = await understand()
            side = await _answer_side_question(
                msg,
                st,
                payload,
                analysis,
            )
            if side is not None:
                return side

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

        low = _normalize_customer_text(text)
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

        if low in finished or _media_finish_requested(text):
            next_prompt = await _advance_customer_media(msg.phone, payload)
            analysis = await understand() if text else {}
            topic = _side_question_topic(text)
            if topic not in {None, "general"}:
                answer = await _common_question_answer(
                    msg,
                    topic,
                    text,
                    context_items=items,
                    analysis=analysis,
                )
                if answer:
                    return _append_resume(answer, next_prompt)
            return next_prompt

        analysis = await understand() if text else {}
        side = await _answer_side_question(
            msg,
            st,
            payload,
            analysis,
            context_items=items,
        )
        if side is not None:
            return side

        return (
            f"Sekarang saya masih menunggu foto atau video kondisi *{machine}*. "
            "Kalau sudah cukup ketik *SELESAI*. Kalau tidak ada, ketik *LEWATI*."
        )

    if st == "cust_landmark":
        control = quick.get("control")
        low_landmark = _normalize_customer_text(text)

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

        first_clause = re.split(r"[,.;!?]", low_landmark, maxsplit=1)[0].strip()
        no_landmark = (
            control in {"SKIP", "NO"}
            or low_landmark in no_landmark_words
            or first_clause in no_landmark_words
            or any(word in low_landmark for word in (
                "tidak ada patokan",
                "gak ada patokan",
                "ga ada patokan",
                "nggak ada patokan",
                "ora ono patokan",
                "mboten wonten patokan",
            ))
        )

        analysis = await understand() if text else {}
        landmark_from_ai = str((analysis.get("fields") or {}).get("landmark") or "").strip()
        landmark_fallback = _landmark_from_text_fallback(text)
        strong_topic = _side_question_topic(text)

        # If the message is only an interruption, answer it and keep the
        # landmark state unchanged. If it also contains a real landmark (or a
        # clear "tidak ada/cukup"), finish the order in this same turn.
        if (
            not no_landmark
            and not landmark_from_ai
            and not landmark_fallback
            and (
                strong_topic in {
                    "price", "schedule", "mechanic_origin", "company_identity",
                    "warranty", "payment", "duration", "coverage", "process",
                    "human", "service_capability", "diagnosis", "general",
                }
                or analysis.get("intent") == "STATUS_QUESTION"
            )
        ):
            side = await _answer_side_question(
                msg,
                st,
                payload,
                analysis,
            )
            if side is not None:
                return side

        if no_landmark:
            landmark = ""
        elif landmark_from_ai:
            landmark = landmark_from_ai[:500]
        elif landmark_fallback:
            landmark = landmark_fallback[:500]
        else:
            return (
                "Saya belum menangkap patokannya. Contohnya *depan masjid*, "
                "*sebelah Indomaret*, atau *rumah pagar hitam*. Kalau tidak ada, "
                "cukup jawab *tidak ada*."
            )

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

        offered = await start_offer_batch(
            order["id"],
            notify_customer=False,
        )

        if offered:
            final_reply = (
                f"Data sudah lengkap. Nomor service Anda *{order['order_no']}*.\n\n"
                "Permintaan sedang saya tawarkan ke mekanik yang sesuai berdasarkan "
                "skill, radius, dan jarak. Saya akan memberi kabar setelah ada mekanik "
                "yang merespons."
            )
        else:
            final_reply = (
                f"Data sudah lengkap. Nomor service Anda *{order['order_no']}*.\n\n"
                "Saat ini belum ada mekanik yang tersedia dan sesuai di sekitar lokasi Anda. "
                "Permintaan tetap tercatat dan akan ditindaklanjuti ketika ada mekanik "
                "yang sesuai."
            )

        if strong_topic not in {None, "general"}:
            side_answer = await _common_question_answer(
                msg,
                strong_topic,
                text,
                context_items=list(items),
                analysis=analysis,
            )
            if side_answer:
                return _append_resume(side_answer, final_reply)

        return final_reply


    if st == "cust_update_location":
        order_no = payload.get("order_no")
        if not msg.location:
            analysis = await understand() if text else {}
            side = await _answer_side_question(
                msg,
                st,
                payload,
                analysis,
            )
            if side is not None:
                return side
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
        "SUGENG ENJING": "Sugeng enjing.",
        "SUGENG SIANG": "Sugeng siang.",
        "SUGENG SONTEN": "Sugeng sonten.",
        "SUGENG DALU": "Sugeng dalu.",
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

    # Use the richer NLU here as well. It is better at typo-heavy Indonesian,
    # Javanese ngoko/krama, and mixed sentences than the lightweight classifier.
    try:
        classified = await understand_customer_message(
            text,
            state="",
            context={},
        )
    except Exception:
        classified = await classify_customer_message(text)

    if (
        _looks_like_price_question(text)
        or classified.get("intent") == "PRICE_QUESTION"
    ):
        await _remember_price_service_context(msg, classified)

        context_items = _machines_from_ai(classified)
        if not context_items and active:
            context_items = await _order_context_items(active["id"])

        return await price_answer(text, context_items)

    if classified.get("intent") == "STATUS_QUESTION":
        if active:
            return await customer_status_summary(active["order_no"])
        return (
            "Saya belum menemukan service aktif pada nomor ini. "
            "Jika Anda punya nomor MTK, kirim misalnya: *STATUS MTK-260919-0003*."
        )

    if classified.get("intent") == "SERVICE_REQUEST":
        return await _start_intake(msg, classified)

    # Answer common off-flow questions directly even when no intake state exists.
    topic = _side_question_topic(text)
    common = await _common_question_answer(
        msg,
        topic,
        text,
        context_items=(await _order_context_items(active["id"]) if active else []),
        analysis=classified,
    )
    if common is not None:
        return common

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
