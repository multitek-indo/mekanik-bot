from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .ai import compose_customer_service_reply


TOPIC_MAP = {
    "PRICE": "price",
    "BOOKING": "price",
    "SPAREPART": "price",
    "SCHEDULE": "schedule",
    "MECHANIC_ORIGIN": "mechanic_origin",
    "WARRANTY": "warranty",
    "PAYMENT": "payment",
    "DURATION": "duration",
    "COVERAGE": "coverage",
    "PROCESS": "process",
    "COMPANY_IDENTITY": "company_identity",
    "SERVICE_CAPABILITY": "service_capability",
    "DIAGNOSIS": "diagnosis",
    "STATUS": "status",
    "OTHER": "general",
}


def normalize_chat_text(text: str) -> str:
    low = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not low:
        return ""

    phrase_rules = (
        (r"\bneng\s+endi\b", "mana"),
        (r"\bning\s+endi\b", "mana"),
        (r"\bsaking\s+pundi\b", "dari mana"),
        (r"\bpunya\s*mes[ni]+\b", "punya mesin"),
        (r"\bpunyames[ni]+\b", "punya mesin"),
        (r"\bmesinjahit\b", "mesin jahit"),
        (r"\bgakjalan\b", "gak jalan"),
        (r"\bgajalan\b", "ga jalan"),
    )
    for pattern, replacement in phrase_rules:
        low = re.sub(pattern, replacement, low, flags=re.I)

    words = {
        "brp": "berapa",
        "brapa": "berapa",
        "biya": "biaya",
        "byaya": "biaya",
        "hrga": "harga",
        "mkanik": "mekanik",
        "mkanike": "mekanik",
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
        "gmn": "bagaimana",
        "gmna": "bagaimana",
        "gimana": "bagaimana",
        "knp": "kenapa",
        "kpn": "kapan",
        "dmn": "mana",
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
        "kantore": "kantor",
        "garansine": "garansi",
        "regane": "harga",
        "biayane": "biaya",
        "mekanike": "mekanik",
        "teknisine": "teknisi",
        "mesine": "mesin",
        "tulung": "tolong",
        "arep": "mau",
        "pengen": "mau",
        "kepengin": "mau",
        "ndandani": "perbaiki",
        "dandani": "perbaiki",
        "didandani": "diperbaiki",
        "benerke": "perbaiki",
        "benakke": "perbaiki",
    }
    tokens = re.split(r"(\W+)", low)
    tokens = [words.get(token, token) for token in tokens]
    return re.sub(r"\s+", " ", "".join(tokens)).strip()


def split_clauses(text: str) -> list[str]:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return []
    pieces = re.split(
        r"(?:[\n.!?;]+|\s*,\s*|\s+\b(?:tapi|tp|terus|trus|lanjut|dan)\b\s+)",
        raw,
        flags=re.I,
    )
    return [piece.strip(" ,.-") for piece in pieces if piece.strip(" ,.-")]


def looks_like_question(text: str) -> bool:
    low = normalize_chat_text(text)
    if not low:
        return False
    if "?" in (text or ""):
        return True
    return any(
        marker in low
        for marker in (
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
            "ada garansi",
            "ada mekanik",
            "ada teknisi",
        )
    )


def wants_service(text: str, analysis: dict | None = None) -> bool:
    analysis = analysis or {}
    if analysis.get("service_requested") is True:
        return True

    low = normalize_chat_text(text)
    if not low:
        return False
    if any(
        marker in low
        for marker in (
            "tidak jadi",
            "ga jadi",
            "gak jadi",
            "nggak jadi",
            "ora dadi",
            "jangan dulu",
            "nanti dulu",
        )
    ):
        return False

    direct = (
        "lanjut",
        "lanjut servis",
        "lanjut perbaikan",
        "proses servis",
        "proses perbaikan",
        "carikan mekanik",
        "carikan teknisi",
        "panggil mekanik",
        "panggil teknisi",
        "kirim mekanik",
        "kirim teknisi",
        "butuh mekanik",
        "butuh teknisi",
        "mau servis",
        "mau perbaiki",
        "ingin servis",
        "ingin perbaiki",
        "tolong servis",
        "tolong perbaiki",
        "bisa bantu servis",
        "bisa bantu perbaiki",
        "bisa dibantu servis",
        "bisa dibantu perbaiki",
    )
    if any(marker in low for marker in direct):
        return True

    return bool(
        re.search(r"\b(?:tolong|mau|ingin)\b.*\b(?:servis|perbaiki|diperbaiki)\b", low)
        or re.search(r"\b(?:bisa|boleh)\b.*\bbantu\b.*\b(?:servis|perbaiki|diperbaiki)\b", low)
    )


def detect_side_topics(text: str, analysis: dict | None = None) -> list[str]:
    analysis = analysis or {}
    topics: list[str] = []

    for item in analysis.get("questions") or []:
        if not isinstance(item, dict):
            continue
        mapped = TOPIC_MAP.get(str(item.get("topic") or "").upper(), "general")
        if mapped not in topics:
            topics.append(mapped)

    low = normalize_chat_text(text)
    if not low:
        return topics

    def add(topic: str) -> None:
        if topic not in topics:
            topics.append(topic)

    price_words = ("harga", "biaya", "tarif", "ongkos", "booking", "spare part", "sparepart")
    price_tiers = ("ringan", "sedang", "berat", "pengecekan", "cek saja")
    if any(x in low for x in price_words) or ("berapa" in low and any(x in low for x in price_tiers)):
        if looks_like_question(text) or any(x in low for x in ("berapa", "termasuk", "masuk jasa")):
            add("price")

    if any(x in low for x in ("garansi", "warranty")):
        add("warranty")

    if any(
        x in low
        for x in (
            "cara bayar",
            "cara pembayaran",
            "bayarnya bagaimana",
            "transfer kemana",
            "transfer ke mana",
            "bisa cash",
            "bisa tunai",
            "bisa qris",
        )
    ):
        add("payment")

    if (
        re.search(r"\b(?:anda|kamu|admin)\b.*\b(?:rumah|alamat|kantor|mana|siapa)\b", low)
        or any(
            x in low
            for x in (
                "rumahnya mana",
                "alamatnya mana",
                "alamat kantor",
                "lokasi kantor",
                "multitek mana",
                "multitek dari mana",
            )
        )
    ):
        add("company_identity")

    if re.search(r"\b(?:mekanik|teknisi)\b.*\b(?:mana|asal|daerah)\b", low):
        add("mechanic_origin")

    if any(
        x in low
        for x in (
            "bisa datang",
            "datang kapan",
            "kapan datang",
            "kapan mekanik",
            "kapan teknisi",
            "jadwal mekanik",
            "jadwal teknisi",
            "jam berapa datang",
            "datang sore",
            "datang pagi",
            "datang malam",
            "hari minggu",
            "hari sabtu",
            "besok bisa",
            "hari ini bisa",
            "sekarang bisa",
        )
    ):
        add("schedule")

    if any(x in low for x in ("berapa lama", "lama perbaikan", "lama servis", "pengerjaan berapa lama")):
        add("duration")

    if any(
        x in low
        for x in (
            "ada mekanik dekat",
            "ada teknisi dekat",
            "mekanik dekat sini",
            "teknisi dekat sini",
            "bisa ke daerah",
            "bisa sampai",
            "bisa melayani",
            "jangkau daerah",
            "melayani daerah",
        )
    ):
        add("coverage")

    if any(
        x in low
        for x in (
            "alur servis",
            "alur service",
            "prosesnya bagaimana",
            "cara panggil mekanik",
            "cara pesan mekanik",
            "cara order",
            "selanjutnya bagaimana",
        )
    ):
        add("process")

    if any(
        x in low
        for x in (
            "bisa diservis",
            "bisa diperbaiki",
            "melayani mesin",
            "bisa service",
            "bisa servis",
        )
    ) and not wants_service(text, analysis):
        add("service_capability")

    if analysis.get("intent") == "STATUS_QUESTION":
        add("status")

    if looks_like_question(text) and not topics:
        add("general")

    return topics


def explicit_correction_signal(text: str, analysis: dict | None = None) -> bool:
    analysis = analysis or {}
    if "CORRECTION" in (analysis.get("speech_acts") or []):
        return True
    low = normalize_chat_text(text)
    return any(
        marker in low
        for marker in (
            "tadi salah",
            "yang tadi salah",
            "bukan itu",
            "bukan juki",
            "bukan ",
            "maksud saya",
            "maksudnya",
            "koreksi",
            "ternyata",
            "sebenarnya",
            "ralat",
        )
    )


def apply_corrections_to_payload(
    payload: dict,
    analysis: dict | None,
    text: str,
) -> tuple[dict, list[str]]:
    """Apply only explicit, bounded corrections to in-progress intake data."""
    analysis = analysis or {}
    if not explicit_correction_signal(text, analysis):
        return payload, []

    updated = deepcopy(payload)
    notes: list[str] = []
    corrections = [x for x in analysis.get("corrections") or [] if isinstance(x, dict)]
    fields = analysis.get("fields") or {}
    machines = [x for x in analysis.get("machines") or [] if isinstance(x, dict)]

    # AI may omit the corrections array while still extracting the replacement.
    if not corrections:
        if analysis.get("machine_count") is not None:
            corrections.append({"field": "machine_count", "value": str(analysis["machine_count"]), "target_index": None})
        machine_value = str(fields.get("machine_description") or "").strip()
        if not machine_value and machines:
            machine_value = str(machines[0].get("machine") or "").strip()
        if machine_value:
            corrections.append({"field": "machine", "value": machine_value, "target_index": 1})
        problem_value = str(fields.get("problem") or "").strip()
        if not problem_value and machines:
            problem_value = str(machines[0].get("problem") or "").strip()
        if problem_value:
            corrections.append({"field": "problem", "value": problem_value, "target_index": 1})

    for item in corrections:
        field = str(item.get("field") or "").lower()
        value = str(item.get("value") or "").strip()
        target = item.get("target_index")
        try:
            target = int(target) if target is not None else 1
        except (TypeError, ValueError):
            target = 1
        target = max(1, target)
        idx = target - 1

        if field == "machine_count":
            try:
                count = int(value or analysis.get("machine_count"))
            except (TypeError, ValueError):
                continue
            if count > 0:
                if "machine_count" in updated:
                    updated["machine_count"] = count
                else:
                    updated["pending_machine_count"] = count
                if isinstance(updated.get("items"), list) and len(updated["items"]) > count:
                    updated["items"] = list(updated["items"])[:count]
                if isinstance(updated.get("prefill_machines"), list) and len(updated["prefill_machines"]) > count:
                    updated["prefill_machines"] = list(updated["prefill_machines"])[:count]
                notes.append(f"jumlah mesin dikoreksi menjadi {count}")
            continue

        if field == "name" and value:
            updated["pending_name_correction"] = value[:150]
            notes.append("nama dikoreksi")
            continue

        if field == "landmark" and value:
            updated["pending_landmark_correction"] = value[:500]
            notes.append("patokan dikoreksi")
            continue

        drafts = [
            dict(x)
            for x in list(updated.get("prefill_machines") or updated.get("items") or [])
            if isinstance(x, dict)
        ]
        while len(drafts) <= idx:
            drafts.append({"machine": "", "problem": ""})

        if field == "machine" and value:
            drafts[idx]["machine"] = value[:300]
            notes.append(f"mesin ke-{target} dikoreksi")
        elif field == "problem" and value:
            drafts[idx]["problem"] = value[:1500]
            notes.append(f"keluhan mesin ke-{target} dikoreksi")
        else:
            continue

        updated["prefill_machines"] = drafts
        # If items already exist, keep them synchronized before order creation.
        if updated.get("items"):
            updated["items"] = [
                {"machine": str(x.get("machine") or "")[:300], "problem": str(x.get("problem") or "")[:1500]}
                for x in drafts
                if str(x.get("machine") or "").strip() and str(x.get("problem") or "").strip()
            ]
        if target == int(updated.get("machine_index") or target):
            if field == "machine":
                updated["current_machine"] = value[:300]
            elif field == "problem":
                updated["pending_problem"] = value[:1500]

    return updated, notes


def build_conversation_summary(payload: dict, state: str = "") -> str:
    parts: list[str] = []
    count = payload.get("machine_count") or payload.get("pending_machine_count")
    if count:
        parts.append(f"jumlah mesin {count}")

    machines: list[dict] = []
    for key in ("items", "prefill_machines"):
        for item in payload.get(key) or []:
            if isinstance(item, dict):
                machines.append(item)
        if machines:
            break

    current_machine = str(payload.get("current_machine") or "").strip()
    if current_machine:
        machines.append({"machine": current_machine, "problem": payload.get("pending_problem") or ""})

    seen = set()
    labels = []
    for item in machines[:8]:
        machine = str(item.get("machine") or "").strip()
        problem = str(item.get("problem") or "").strip()
        key = (machine.lower(), problem.lower())
        if key in seen:
            continue
        seen.add(key)
        if machine and problem:
            labels.append(f"{machine}: {problem}")
        elif machine:
            labels.append(machine)
        elif problem:
            labels.append(f"keluhan: {problem}")
    if labels:
        parts.append("; ".join(labels))

    if payload.get("location"):
        parts.append("lokasi sudah diterima")
    if state:
        parts.append(f"tahap sekarang {state}")
    return ". ".join(parts)[:2000]


def enrich_payload_memory(payload: dict, state: str, analysis: dict | None = None) -> dict:
    out = deepcopy(payload)
    out["conversation_summary"] = build_conversation_summary(out, state)
    out["last_bot_goal"] = state
    if analysis:
        questions = analysis.get("questions") or []
        if questions and isinstance(questions[0], dict):
            out["last_customer_topic"] = str(questions[0].get("topic") or "")[:80]
        elif analysis.get("intent"):
            out["last_customer_topic"] = str(analysis.get("intent"))[:80]
    return out


def friendly_resume_prompt(state: str, payload: dict, language_style: str = "INDONESIA") -> str:
    prefix = ""
    style = (language_style or "").upper()
    if style in {"JAWA_NGOKO", "JAWA_KRAMA", "MIXED"}:
        prefix = "Nggih, "

    if state == "cust_name":
        return prefix + "boleh sebutkan nama Anda atau nama perusahaan?"
    if state == "cust_machine_count":
        return prefix + "kalau servicenya dilanjutkan, ada berapa unit mesin yang mau dicek?"
    if state == "cust_machine_desc":
        idx = int(payload.get("machine_index") or 1)
        return prefix + f"tinggal mesin ke-{idx}: merek, jenis, atau modelnya apa?"
    if state == "cust_machine_problem":
        machine = str(payload.get("current_machine") or "mesin tersebut").strip()
        return prefix + f"kalau lanjut, apa keluhan pada *{machine}*? Ceritakan gejalanya seperti biasa saja."
    if state == "cust_location":
        return prefix + "kalau sudah siap, kirim *Share Location* lokasi mesinnya supaya saya bisa cek mekanik terdekat."
    if state == "cust_location_confirm":
        return prefix + "kalau titik tadi sudah tepat, cukup jawab *iya/betul*. Kalau salah, kirim ulang lokasinya."
    if state == "cust_media":
        try:
            item_no = int(payload.get("media_item_no") or 1)
        except (TypeError, ValueError):
            item_no = 1
        items = list(payload.get("items") or [])
        machine = "mesin tersebut"
        if 1 <= item_no <= len(items) and isinstance(items[item_no - 1], dict):
            machine = str(items[item_no - 1].get("machine") or machine).strip()
        return prefix + f"kalau ada, kirim foto/video *{machine}* (foto atau video biasa). Kalau tidak ada, boleh dilewati."
    if state == "cust_landmark":
        return prefix + "kalau ada patokan, sebutkan saja. Kalau tidak ada, bilang *tidak ada*."
    if state == "cust_price_context":
        return prefix + "kalau ingin saya lanjutkan servicenya, bilang saja mau dilanjutkan atau ceritakan detail kerusakannya."
    if state == "cust_update_location":
        return prefix + "silakan kirim *Share Location* yang baru."
    return ""


async def compose_approved_reply(
    customer_text: str,
    approved_answer: str,
    resume_prompt: str,
    analysis: dict | None,
    payload: dict,
) -> str:
    analysis = analysis or {}
    return await compose_customer_service_reply(
        customer_text,
        approved_answer,
        resume_prompt,
        language_style=str(analysis.get("language_style") or "INDONESIA"),
        known_context=enrich_payload_memory(payload, str(payload.get("last_bot_goal") or ""), analysis),
    )
