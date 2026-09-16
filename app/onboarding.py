from datetime import datetime, timezone
from .db import pool
from .state import get_state, set_state, clear_state
from .skills import SKILLS, SKILL_BY_NUMBER, SKILL_BY_CODE, skills_menu, level_menu, parse_top_skill_numbers
from .pricing import rupiah
from .wa import normalize_phone
from .types import IncomingMessage


def _skill_prompt(index: int) -> str:
    item = SKILL_BY_NUMBER[index]
    return (
        f"Skill {index}/{len(SKILLS)} — *{item['name']}*\n"
        "Nilai kemampuan Anda 0-5:\n"
        + level_menu()
    )


def _verification_prompt(code: str) -> str:
    item = SKILL_BY_CODE[code]
    return f"Verifikasi singkat *{item['name']}*:\n{item['questions'][0]}"


async def _new_application(phone: str):
    phone = normalize_phone(phone)
    async with pool().acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM technician_applications WHERE wa_number=$1 ORDER BY created_at DESC LIMIT 1",
            phone,
        )
        if existing:
            if existing["status"] in {"DRAFT", "SUBMITTED", "APPROVED"}:
                return existing
            if existing["status"] == "REJECTED":
                async with conn.transaction():
                    await conn.execute("DELETE FROM technician_skill_answers WHERE application_id=$1", existing["id"])
                    await conn.execute("DELETE FROM technician_application_skills WHERE application_id=$1", existing["id"])
                    existing = await conn.fetchrow(
                        """UPDATE technician_applications SET name=NULL,domicile=NULL,base_lat=NULL,base_lon=NULL,base_address=NULL,
                           service_radius_km=25,years_experience=NULL,vehicle=NULL,profile_photo_path=NULL,top_skills='{}',
                           status='DRAFT',submitted_at=NULL,reviewed_at=NULL,review_note=NULL,updated_at=now()
                           WHERE id=$1 RETURNING *""", existing["id"]
                    )
                return existing
        seq = await conn.fetchval("SELECT nextval('mechanic_application_number_seq')")
        now = datetime.now(timezone.utc)
        app_no = f"MKN-{now:%y%m%d}-{seq:04d}"
        return await conn.fetchrow(
            """INSERT INTO technician_applications(application_no,wa_number,status)
               VALUES($1,$2,'DRAFT') RETURNING *""",
            app_no,
            phone,
        )


async def _app_by_id(app_id):
    async with pool().acquire() as conn:
        return await conn.fetchrow("SELECT * FROM technician_applications WHERE id=$1", app_id)


async def _app_by_no(app_no: str):
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM technician_applications WHERE upper(application_no)=upper($1)", app_no.strip()
        )


async def _save_skill(app_id, skill_index: int, level: int):
    item = SKILL_BY_NUMBER[skill_index]
    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO technician_application_skills(application_id,skill_code,skill_name,self_level)
               VALUES($1,$2,$3,$4)
               ON CONFLICT(application_id,skill_code) DO UPDATE
               SET skill_name=EXCLUDED.skill_name,self_level=EXCLUDED.self_level""",
            app_id, item["code"], item["name"], level,
        )


async def _eligible_top_skills(app_id):
    async with pool().acquire() as conn:
        return await conn.fetch(
            """SELECT skill_code,skill_name,self_level
               FROM technician_application_skills
               WHERE application_id=$1 AND self_level>=3
               ORDER BY self_level DESC,skill_name""",
            app_id,
        )


async def _finish(phone: str, app_id, app_no: str) -> str:
    async with pool().acquire() as conn:
        await conn.execute(
            """UPDATE technician_applications
               SET status='SUBMITTED',submitted_at=now(),updated_at=now()
               WHERE id=$1""",
            app_id,
        )
    await clear_state(phone)
    return (
        f"Pendaftaran Anda sudah lengkap. Nomor pendaftaran: *{app_no}*.\n"
        "Data akan diperiksa owner Multitek. Anda akan menerima pemberitahuan setelah disetujui atau ditolak."
    )


async def start_registration(phone: str) -> str:
    app = await _new_application(phone)
    if app["status"] == "APPROVED":
        return f"Nomor ini sudah terdaftar sebagai mekanik Multitek ({app['application_no']})."
    await set_state(phone, "mech_name", {"application_id": str(app["id"]), "application_no": app["application_no"]})
    return (
        "Baik, saya bantu pendaftaran calon mekanik Multitek. Prosesnya singkat: data diri, lokasi basis, "
        "foto diri, lalu skill matrix.\n\nSiapa nama lengkap Anda?"
    )


async def handle_registration(msg: IncomingMessage) -> str | None:
    state = await get_state(msg.phone)
    if not state:
        return None
    st = state["state"]
    if not st.startswith("mech_"):
        return None
    payload = dict(state["payload"] or {})
    app_id = payload.get("application_id")
    app_no = payload.get("application_no")
    raw = (msg.text or "").strip()

    if raw.upper() == "BATAL":
        await clear_state(msg.phone)
        return "Pendaftaran dibatalkan. Ketik *DAFTAR MEKANIK* kapan saja untuk memulai lagi."

    if st == "mech_name":
        if len(raw) < 3:
            return "Nama terlalu singkat. Mohon kirim nama lengkap Anda."
        async with pool().acquire() as conn:
            await conn.execute("UPDATE technician_applications SET name=$2,updated_at=now() WHERE id=$1", app_id, raw[:150])
        await set_state(msg.phone, "mech_domicile", payload)
        return "Domisili Anda di kota/kabupaten mana?"

    if st == "mech_domicile":
        if len(raw) < 2:
            return "Mohon kirim nama kota/kabupaten domisili Anda."
        async with pool().acquire() as conn:
            await conn.execute("UPDATE technician_applications SET domicile=$2,updated_at=now() WHERE id=$1", app_id, raw[:150])
        await set_state(msg.phone, "mech_location", payload)
        return (
            "Sekarang kirim *Share Location* lokasi basis Anda (rumah/workshop/titik keberangkatan utama).\n"
            "Gunakan WhatsApp → Lampiran → Lokasi → Kirim lokasi Anda saat ini."
        )

    if st == "mech_location":
        if not msg.location:
            return "Saya belum menerima titik lokasi. Mohon kirim menggunakan fitur *Share Location* WhatsApp."
        loc = msg.location
        address = loc.get("address") or loc.get("name") or ""
        async with pool().acquire() as conn:
            await conn.execute(
                """UPDATE technician_applications SET base_lat=$2,base_lon=$3,base_address=$4,updated_at=now()
                   WHERE id=$1""",
                app_id, loc["lat"], loc["lon"], address[:500],
            )
        await set_state(msg.phone, "mech_radius", payload)
        return "Berapa radius maksimal pelayanan Anda dalam kilometer? Contoh: *10*, *25*, atau *50*."

    if st == "mech_radius":
        try:
            radius = float(raw.replace(",", "."))
        except ValueError:
            return "Balas angka kilometer saja. Contoh: *25*."
        if not (1 <= radius <= 200):
            return "Radius harus antara 1 sampai 200 km."
        async with pool().acquire() as conn:
            await conn.execute("UPDATE technician_applications SET service_radius_km=$2,updated_at=now() WHERE id=$1", app_id, radius)
        await set_state(msg.phone, "mech_experience", payload)
        return "Berapa tahun pengalaman Anda sebagai mekanik? Balas angka tahun, contoh: *8*."

    if st == "mech_experience":
        if not raw.isdigit() or not (0 <= int(raw) <= 60):
            return "Balas angka pengalaman dalam tahun. Contoh: *8*."
        async with pool().acquire() as conn:
            await conn.execute("UPDATE technician_applications SET years_experience=$2,updated_at=now() WHERE id=$1", app_id, int(raw))
        await set_state(msg.phone, "mech_vehicle", payload)
        return "Kendaraan yang biasa digunakan untuk menuju customer? Contoh: *Motor* atau *Mobil*."

    if st == "mech_vehicle":
        if len(raw) < 2:
            return "Mohon tulis kendaraan yang Anda gunakan."
        async with pool().acquire() as conn:
            await conn.execute("UPDATE technician_applications SET vehicle=$2,updated_at=now() WHERE id=$1", app_id, raw[:100])
        await set_state(msg.phone, "mech_selfie", payload)
        return (
            "Kirim *1 foto diri/selfie terbaru* yang jelas, menghadap kamera, tanpa masker/helm. "
            "Foto ini akan ditampilkan kepada customer saat memilih mekanik."
        )

    if st == "mech_selfie":
        if msg.media_type != "image" or not msg.media_path:
            return "Foto diri belum terbaca. Mohon kirim sebagai *foto/image* WhatsApp, bukan dokumen."
        async with pool().acquire() as conn:
            await conn.execute("UPDATE technician_applications SET profile_photo_path=$2,updated_at=now() WHERE id=$1", app_id, msg.media_path)
        payload["skill_index"] = 1
        await set_state(msg.phone, "mech_skill", payload)
        return (
            "Selanjutnya skill matrix. Nilai diri Anda secara jujur; data ini dipakai untuk matching job.\n\n"
            + _skill_prompt(1)
        )

    if st == "mech_skill":
        index = int(payload.get("skill_index", 1))
        if raw not in {"0", "1", "2", "3", "4", "5"}:
            return _skill_prompt(index)
        await _save_skill(app_id, index, int(raw))
        if index < len(SKILLS):
            payload["skill_index"] = index + 1
            await set_state(msg.phone, "mech_skill", payload)
            return _skill_prompt(index + 1)

        eligible = await _eligible_top_skills(app_id)
        if not eligible:
            async with pool().acquire() as conn:
                await conn.execute("UPDATE technician_applications SET top_skills='{}' WHERE id=$1", app_id)
            return await _finish(msg.phone, app_id, app_no)

        eligible_codes = [r["skill_code"] for r in eligible]
        payload["eligible_codes"] = eligible_codes
        await set_state(msg.phone, "mech_top3", payload)
        line_map = {item["code"]: (n, item["name"]) for n, item in SKILL_BY_NUMBER.items()}
        lines = []
        for r in eligible:
            n, name = line_map[r["skill_code"]]
            lines.append(f"{n}. {name} (level {r['self_level']})")
        return (
            "Pilih maksimal *3 skill utama* untuk verifikasi singkat. Balas nomor dipisahkan koma, contoh: *1,3,14*.\n\n"
            + "\n".join(lines)
        )

    if st == "mech_top3":
        numbers = parse_top_skill_numbers(raw)
        if not numbers or len(numbers) > 3:
            return "Pilih 1 sampai 3 nomor skill, contoh: *1,3,14*."
        codes = [SKILL_BY_NUMBER[n]["code"] for n in numbers]
        eligible = set(payload.get("eligible_codes") or [])
        if any(code not in eligible for code in codes):
            return "Top skill hanya boleh dipilih dari skill yang Anda beri level 3-5."
        async with pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute("UPDATE technician_applications SET top_skills=$2,updated_at=now() WHERE id=$1", app_id, codes)
                await conn.execute("UPDATE technician_application_skills SET is_top_skill=false WHERE application_id=$1", app_id)
                await conn.execute(
                    "UPDATE technician_application_skills SET is_top_skill=true WHERE application_id=$1 AND skill_code=ANY($2::text[])",
                    app_id, codes,
                )
        payload["top_codes"] = codes
        payload["verify_pos"] = 0
        await set_state(msg.phone, "mech_verify", payload)
        return _verification_prompt(codes[0])

    if st == "mech_verify":
        codes = payload.get("top_codes") or []
        pos = int(payload.get("verify_pos", 0))
        if not codes or pos >= len(codes):
            return await _finish(msg.phone, app_id, app_no)
        if len(raw) < 8:
            return "Jawaban terlalu singkat. Jelaskan langkah atau pengalaman Anda secara singkat tetapi jelas."
        code = codes[pos]
        question = SKILL_BY_CODE[code]["questions"][0]
        async with pool().acquire() as conn:
            await conn.execute(
                """INSERT INTO technician_skill_answers(application_id,skill_code,question_no,question_text,answer_text)
                   VALUES($1,$2,1,$3,$4)
                   ON CONFLICT(application_id,skill_code,question_no) DO UPDATE
                   SET question_text=EXCLUDED.question_text,answer_text=EXCLUDED.answer_text""",
                app_id, code, question, raw[:2000],
            )
        pos += 1
        payload["verify_pos"] = pos
        if pos >= len(codes):
            return await _finish(msg.phone, app_id, app_no)
        await set_state(msg.phone, "mech_verify", payload)
        return _verification_prompt(codes[pos])

    return None


async def owner_application_list() -> str:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT application_no,name,domicile,years_experience,status,submitted_at
               FROM technician_applications ORDER BY created_at DESC LIMIT 20"""
        )
    if not rows:
        return "Belum ada pendaftaran calon mekanik."
    lines = ["*CALON MEKANIK*"]
    for r in rows:
        lines.append(
            f"{r['application_no']} | {r['status']} | {r['name'] or '-'} | {r['domicile'] or '-'} | "
            f"{r['years_experience'] if r['years_experience'] is not None else '-'} th"
        )
    return "\n".join(lines)


async def owner_application_detail(application_no: str) -> tuple[str, str | None]:
    app = await _app_by_no(application_no)
    if not app:
        return "Pendaftaran calon mekanik tidak ditemukan.", None
    async with pool().acquire() as conn:
        skills = await conn.fetch(
            """SELECT skill_code,skill_name,self_level,is_top_skill
               FROM technician_application_skills WHERE application_id=$1""",
            app["id"],
        )
        answers = await conn.fetch(
            """SELECT skill_code,question_text,answer_text
               FROM technician_skill_answers WHERE application_id=$1 ORDER BY id""",
            app["id"],
        )
    order = {item["code"]: n for n, item in SKILL_BY_NUMBER.items()}
    skills = sorted(skills, key=lambda r: order.get(r["skill_code"], 999))
    location_text = app["base_address"] or f"{app['base_lat']},{app['base_lon']}"
    lines = [
        f"*DETAIL {app['application_no']}*",
        f"Status: {app['status']}",
        f"Nama: {app['name'] or '-'}",
        f"WA: {app['wa_number']}",
        f"Domisili: {app['domicile'] or '-'}",
        f"Lokasi basis: {location_text}",
        f"Radius: {app['service_radius_km']} km",
        f"Pengalaman: {app['years_experience'] or 0} tahun",
        f"Kendaraan: {app['vehicle'] or '-'}",
        "",
        "*SKILL MATRIX*",
    ]
    for s in skills:
        marker = " ⭐" if s["is_top_skill"] else ""
        lines.append(f"{order.get(s['skill_code'],'?')}. {s['skill_name']}: {s['self_level']}/5{marker}")
    if answers:
        lines.append("")
        lines.append("*JAWABAN VERIFIKASI*")
        for a in answers:
            name = SKILL_BY_CODE.get(a["skill_code"], {}).get("name", a["skill_code"])
            lines.append(f"[{name}] {a['question_text']}\nJawab: {(a['answer_text'] or '')[:700]}")
    lines.extend([
        "",
        f"Setujui: *SETUJUI MEKANIK {app['application_no']}*",
        f"Tolak: *TOLAK MEKANIK {app['application_no']} alasan*",
    ])
    return "\n".join(lines), app["profile_photo_path"]


async def owner_approve_application(application_no: str) -> tuple[str, str | None]:
    app = await _app_by_no(application_no)
    if not app:
        return "Pendaftaran tidak ditemukan.", None
    if app["status"] == "APPROVED":
        return "Mekanik ini sudah disetujui.", app["wa_number"]
    required = [app["name"], app["base_lat"], app["base_lon"], app["profile_photo_path"]]
    if any(v is None or v == "" for v in required):
        return "Data pendaftaran belum lengkap; belum dapat disetujui.", None

    async with pool().acquire() as conn:
        async with conn.transaction():
            tech = await conn.fetchrow(
                """INSERT INTO technicians(
                       name,wa_number,domicile,base_lat,base_lon,base_address,service_radius_km,
                       years_experience,vehicle,profile_photo_path,is_active,is_available,source_application_id)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,true,true,$11)
                   ON CONFLICT(wa_number) DO UPDATE SET
                       name=EXCLUDED.name,domicile=EXCLUDED.domicile,base_lat=EXCLUDED.base_lat,
                       base_lon=EXCLUDED.base_lon,base_address=EXCLUDED.base_address,
                       service_radius_km=EXCLUDED.service_radius_km,years_experience=EXCLUDED.years_experience,
                       vehicle=EXCLUDED.vehicle,profile_photo_path=EXCLUDED.profile_photo_path,
                       is_active=true,is_available=true,source_application_id=EXCLUDED.source_application_id,
                       updated_at=now()
                   RETURNING *""",
                app["name"], app["wa_number"], app["domicile"], app["base_lat"], app["base_lon"],
                app["base_address"], app["service_radius_km"], app["years_experience"] or 0,
                app["vehicle"], app["profile_photo_path"], app["id"],
            )
            skills = await conn.fetch(
                "SELECT skill_code,skill_name,self_level FROM technician_application_skills WHERE application_id=$1",
                app["id"],
            )
            for s in skills:
                await conn.execute(
                    """INSERT INTO technician_skill_matrix(technician_id,skill_code,skill_name,level,verified,source_application_id)
                       VALUES($1,$2,$3,$4,false,$5)
                       ON CONFLICT(technician_id,skill_code) DO UPDATE SET
                       skill_name=EXCLUDED.skill_name,level=EXCLUDED.level,source_application_id=EXCLUDED.source_application_id,
                       updated_at=now()""",
                    tech["id"], s["skill_code"], s["skill_name"], s["self_level"], app["id"],
                )
            await conn.execute(
                "UPDATE technician_applications SET status='APPROVED',reviewed_at=now(),updated_at=now() WHERE id=$1",
                app["id"],
            )
    return f"{application_no} disetujui. {app['name']} sekarang aktif sebagai mekanik Multitek.", app["wa_number"]


async def owner_reject_application(application_no: str, reason: str) -> tuple[str, str | None]:
    app = await _app_by_no(application_no)
    if not app:
        return "Pendaftaran tidak ditemukan.", None
    async with pool().acquire() as conn:
        await conn.execute(
            """UPDATE technician_applications SET status='REJECTED',review_note=$2,reviewed_at=now(),updated_at=now()
               WHERE id=$1""",
            app["id"], reason[:500],
        )
    return f"{application_no} ditolak. Alasan: {reason}", app["wa_number"]
