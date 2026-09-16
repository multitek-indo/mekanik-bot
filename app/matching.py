from datetime import datetime, timedelta, timezone
from .config import settings
from .db import pool
from .location import haversine_km
from .orders import find_order, order_items, change_status
from .pricing import booking_fee_for_distance, rupiah
from .skills import SKILL_BY_CODE
from .wa import send_text, send_image, send_file
from .media import is_real_media_file


def _tech_coords(tech):
    now = datetime.now(timezone.utc)
    current_at = tech["current_location_at"]
    if (
        tech["current_lat"] is not None
        and tech["current_lon"] is not None
        and current_at is not None
        and current_at >= now - timedelta(hours=settings.technician_current_location_max_age_hours)
    ):
        return float(tech["current_lat"]), float(tech["current_lon"]), "current"
    return float(tech["base_lat"]), float(tech["base_lon"]), "base"


async def _required_skill_codes(order_id):
    items = await order_items(order_id)
    return sorted({i["machine_category_code"] for i in items if i["machine_category_code"]})


async def candidate_list(order, include_already_offered: bool = False):
    required = await _required_skill_codes(order["id"])
    async with pool().acquire() as conn:
        techs = await conn.fetch("SELECT * FROM technicians WHERE is_active=true AND is_available=true")
        matrix_rows = await conn.fetch(
            "SELECT technician_id,skill_code,level FROM technician_skill_matrix WHERE technician_id=ANY($1::uuid[])",
            [t["id"] for t in techs] if techs else [],
        )
        offered = set()
        if not include_already_offered:
            offered = {
                r["technician_id"]
                for r in await conn.fetch("SELECT technician_id FROM job_offers WHERE order_id=$1", order["id"])
            }
    levels: dict = {}
    for r in matrix_rows:
        levels.setdefault(r["technician_id"], {})[r["skill_code"]] = int(r["level"])

    result = []
    for tech in techs:
        if tech["id"] in offered:
            continue
        lat, lon, location_source = _tech_coords(tech)
        distance = haversine_km(float(order["location_lat"]), float(order["location_lon"]), lat, lon)
        max_distance = min(float(tech["service_radius_km"]), float(settings.max_match_distance_km))
        if distance > max_distance:
            continue

        tech_levels = levels.get(tech["id"], {})
        if required:
            matched = [tech_levels.get(code, 0) for code in required]
            qualified_count = sum(1 for x in matched if x >= settings.technician_min_skill_level)
            coverage = qualified_count / len(required)
            average_skill = sum(matched) / len(matched)
            if coverage <= 0:
                continue
        else:
            coverage = 0.5
            average_skill = 0

        result.append(
            {
                "tech": tech,
                "distance": distance,
                "coverage": coverage,
                "average_skill": average_skill,
                "levels": tech_levels,
                "required": required,
                "location_source": location_source,
            }
        )

    result.sort(
        key=lambda c: (
            -c["coverage"],
            -c["average_skill"],
            c["distance"],
            -float(c["tech"]["rating"]),
            -int(c["tech"]["jobs_completed"]),
        )
    )
    return result



# =====================================================================
# CUSTOMER REFERENCE MEDIA TO MECHANIC V1
# =====================================================================

async def _customer_reference_media(order_id):
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                a.id,
                a.media_type,
                a.local_path,
                a.purpose,
                soi.item_no,
                soi.machine_text,
                soi.complaint
            FROM attachments a
            LEFT JOIN service_order_items soi
              ON soi.id = a.item_id
            WHERE a.order_id = $1
              AND a.actor_type = 'CUSTOMER'
              AND a.purpose IN (
                  'CUSTOMER_MACHINE_PHOTO',
                  'CUSTOMER_MACHINE_VIDEO'
              )
              AND a.local_path IS NOT NULL
            ORDER BY
                soi.item_no,
                a.created_at
            LIMIT 20
            """,
            order_id,
        )

    result = []

    for row in rows:
        path = str(
            row["local_path"] or ""
        ).strip()

        if not path:
            continue

        if not is_real_media_file(path):
            continue

        result.append(row)

    return result


async def start_offer_batch(order_id) -> bool:
    async with pool().acquire() as conn:
        order = await conn.fetchrow("SELECT * FROM service_orders WHERE id=$1", order_id)
    if not order or order["assigned_technician_id"]:
        return False

    candidates = await candidate_list(order)
    batch = candidates[: settings.technician_offer_batch_size]
    if not batch:
        await change_status(order_id, "NO_TECHNICIAN", "SYSTEM", "matcher", "Tidak ada kandidat lain")
        full = await find_order(order["order_no"])
        await send_text(
            full["customer_wa"],
            f"Belum ada mekanik yang tersedia untuk *{order['order_no']}*. Multitek akan menindaklanjuti secara manual.",
        )
        await send_text(settings.owner_wa_number, f"⚠️ {order['order_no']} belum mendapatkan mekanik.")
        return False

    items = await order_items(order_id)

    customer_refs = await _customer_reference_media(
        order_id
    )

    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.technician_offer_timeout_seconds)
    async with pool().acquire() as conn:
        for c in batch:
            await conn.execute(
                """INSERT INTO job_offers(order_id,technician_id,status,distance_km,coverage,average_skill,expires_at)
                   VALUES($1,$2,'PENDING',$3,$4,$5,$6)
                   ON CONFLICT(order_id,technician_id) DO NOTHING""",
                order_id, c["tech"]["id"], c["distance"], c["coverage"], c["average_skill"], expires,
            )
    await change_status(order_id, "OFFERING", "SYSTEM", "matcher", f"Batch {len(batch)} mekanik")

    item_lines = "\n".join(
        f"{i['item_no']}. {i['machine_text']} — {i['complaint']}" for i in items
    )
    for c in batch:
        tech = c["tech"]
        skill_lines = []
        for code in c["required"]:
            skill_lines.append(f"- {SKILL_BY_CODE[code]['name']}: {c['levels'].get(code,0)}/5")
        await send_text(
            tech["wa_number"],
            f"🔧 *PENAWARAN JOB {order['order_no']}*\n\n"
            f"Mesin:\n{item_lines}\n\n"
            f"Jarak dari titik Anda: ±{c['distance']:.1f} km\n"
            f"Kecocokan skill: {int(c['coverage']*100)}%\n"
            + (("\n".join(skill_lines) + "\n") if skill_lines else "")
            + f"\nJika bersedia masuk daftar pilihan customer, balas:\n*BERMINAT {order['order_no']}*\n\n"
            f"Jika tidak, balas:\n*TOLAK {order['order_no']}*\n\n"
            f"Waktu respon: {settings.technician_offer_timeout_seconds // 60} menit.",
        )

        # ----------------------------------------------------
        # Referensi foto/video customer
        # ----------------------------------------------------
        for ref in customer_refs:
            media_type = str(
                ref["media_type"] or ""
            ).lower()

            path = str(
                ref["local_path"] or ""
            ).strip()

            item_no = (
                ref["item_no"]
                if ref["item_no"] is not None
                else "-"
            )

            machine = str(
                ref["machine_text"] or "Mesin"
            ).strip()

            caption = (
                f"Referensi customer — "
                f"Mesin {item_no}: {machine}"
            )

            try:
                if media_type == "image":
                    await send_image(
                        tech["wa_number"],
                        path,
                        caption,
                    )

                elif media_type in {
                    "video",
                    "video_note",
                }:
                    await send_file(
                        tech["wa_number"],
                        path,
                        caption,
                    )

            except Exception:
                # Media tidak boleh menggagalkan
                # penawaran job utama.
                continue

    return True


async def mechanic_offer_response(phone: str, order_no: str, interested: bool) -> str:
    async with pool().acquire() as conn:
        tech = await conn.fetchrow("SELECT * FROM technicians WHERE wa_number=$1 AND is_active=true", phone)
        order = await conn.fetchrow("SELECT * FROM service_orders WHERE upper(order_no)=upper($1)", order_no)
        if not tech or not order:
            return "Mekanik atau nomor service tidak ditemukan."
        offer = await conn.fetchrow(
            """SELECT * FROM job_offers WHERE order_id=$1 AND technician_id=$2 AND status='PENDING'
               ORDER BY offered_at DESC LIMIT 1""",
            order["id"], tech["id"],
        )
        if not offer:
            return "Penawaran ini sudah berakhir atau tidak ditemukan."
        if offer["expires_at"] <= datetime.now(timezone.utc):
            await conn.execute("UPDATE job_offers SET status='EXPIRED',responded_at=now() WHERE id=$1", offer["id"])
            return "Waktu penawaran sudah berakhir."
        await conn.execute(
            "UPDATE job_offers SET status=$2,responded_at=now() WHERE id=$1",
            offer["id"], "INTERESTED" if interested else "DECLINED",
        )
        pending = await conn.fetchval("SELECT count(*) FROM job_offers WHERE order_id=$1 AND status='PENDING'", order["id"])
    if pending == 0:
        await finalize_offer_window(order["id"])
    return (
        f"Minat Anda untuk {order_no} sudah dicatat. Customer akan memilih dari mekanik yang tersedia."
        if interested else f"Penawaran {order_no} ditolak. Terima kasih."
    )


async def finalize_offer_window(order_id) -> bool:
    async with pool().acquire() as conn:
        order = await conn.fetchrow("SELECT * FROM service_orders WHERE id=$1", order_id)
        if not order or order["assigned_technician_id"]:
            return False
        await conn.execute(
            "UPDATE job_offers SET status='EXPIRED',responded_at=COALESCE(responded_at,now()) WHERE order_id=$1 AND status='PENDING'",
            order_id,
        )
        interested = await conn.fetch(
            """SELECT jo.*,t.name,t.wa_number,t.domicile,t.years_experience,t.vehicle,t.profile_photo_path,
                      t.rating,t.jobs_completed,t.id technician_id
               FROM job_offers jo JOIN technicians t ON t.id=jo.technician_id
               WHERE jo.order_id=$1 AND jo.status='INTERESTED'
               ORDER BY jo.coverage DESC,jo.average_skill DESC,jo.distance_km,t.rating DESC""",
            order_id,
        )
    if not interested:
        return await start_offer_batch(order_id)

    async with pool().acquire() as conn:
        for idx, row in enumerate(interested, start=1):
            await conn.execute("UPDATE job_offers SET customer_rank=$2 WHERE id=$1", row["id"], idx)
    await change_status(order_id, "WAITING_CUSTOMER_TECH_SELECTION", "SYSTEM", "matcher", "Mekanik berminat tersedia")
    full = await find_order(order["order_no"])
    customer = full["customer_wa"]
    await send_text(customer, f"Saya menemukan *{len(interested)} mekanik* yang bersedia menangani {order['order_no']}. Silakan pilih berdasarkan profil berikut.")

    required = await _required_skill_codes(order_id)
    async with pool().acquire() as conn:
        matrices = await conn.fetch(
            """SELECT technician_id,skill_code,skill_name,level
               FROM technician_skill_matrix WHERE technician_id=ANY($1::uuid[]) AND level>0""",
            [x["technician_id"] for x in interested],
        )
    by_tech = {}
    for row in matrices:
        by_tech.setdefault(row["technician_id"], []).append(row)

    for idx, row in enumerate(interested, start=1):
        matrix = by_tech.get(row["technician_id"], [])
        relevant = [m for m in matrix if m["skill_code"] in required]
        relevant.sort(key=lambda m: -m["level"])
        other = [m for m in matrix if m["skill_code"] not in required and m["level"] >= 3]
        other.sort(key=lambda m: -m["level"])
        skill_text = "\n".join(f"- {m['skill_name']}: {m['level']}/5" for m in relevant[:6]) or "- Belum ada kategori spesifik terdeteksi"
        other_text = "\n".join(f"- {m['skill_name']}: {m['level']}/5" for m in other[:4])
        profile = (
            f"*PILIHAN {idx} — {row['name']}*\n"
            f"Domisili: {row['domicile'] or '-'}\n"
            f"Jarak: ±{float(row['distance_km']):.1f} km\n"
            f"Pengalaman: {row['years_experience']} tahun\n"
            f"Pekerjaan selesai: {row['jobs_completed']}\n"
            f"Rating: {float(row['rating']):.1f}/5\n\n"
            f"*Skill relevan*\n{skill_text}"
        )
        if other_text:
            profile += f"\n\n*Skill lain*\n{other_text}"
        profile += f"\n\nPilih dengan: *PILIH {order['order_no']} {idx}*"
        if row["profile_photo_path"]:
            try:
                await send_image(customer, row["profile_photo_path"], f"Foto mekanik — {row['name']}")
            except Exception:
                pass
        await send_text(customer, profile)
    await send_text(customer, "Nomor kontak mekanik tidak ditampilkan pada tahap pemilihan. Semua komunikasi tetap melalui Multitek.")
    return True


async def select_candidate(customer_phone: str, order_no: str, rank: int) -> str:
    order = await find_order(order_no)
    if not order or order["customer_wa"] != customer_phone:
        return "Nomor service tidak ditemukan atau bukan milik nomor ini."
    if order["status"] != "WAITING_CUSTOMER_TECH_SELECTION":
        return "Saat ini tidak ada pilihan mekanik yang menunggu dipilih."
    async with pool().acquire() as conn:
        offer = await conn.fetchrow(
            """SELECT jo.*,t.* FROM job_offers jo JOIN technicians t ON t.id=jo.technician_id
               WHERE jo.order_id=$1 AND jo.status='INTERESTED' AND jo.customer_rank=$2""",
            order["id"], rank,
        )
        if not offer:
            return "Pilihan mekanik tidak valid. Silakan pilih nomor yang ditampilkan."
        await conn.execute(
            "UPDATE service_orders SET assigned_technician_id=$2,selected_distance_km=$3,updated_at=now() WHERE id=$1",
            order["id"], offer["technician_id"], offer["distance_km"],
        )
        await conn.execute(
            "UPDATE job_offers SET status=CASE WHEN technician_id=$2 THEN 'SELECTED' ELSE 'NOT_SELECTED' END WHERE order_id=$1 AND status='INTERESTED'",
            order["id"], offer["technician_id"],
        )
    fee = booking_fee_for_distance(float(offer["distance_km"]))
    async with pool().acquire() as conn:
        if fee is None:
            await conn.execute("UPDATE service_orders SET status='WAITING_BOOKING_FEE_OWNER' WHERE id=$1", order["id"])
            await send_text(settings.owner_wa_number, f"{order_no}: jarak mekanik ±{float(offer['distance_km']):.1f} km. Tentukan booking dengan: SET BOOKING {order_no} <nominal>")
            return f"Anda memilih *{offer['name']}*. Karena jaraknya di atas {int(settings.booking_manual_over_km)} km, biaya kunjungan akan dikonfirmasi Multitek terlebih dahulu."
        await conn.execute(
            "UPDATE service_orders SET booking_fee=$2,status='WAITING_BOOKING_PAYMENT',booking_payment_status='UNPAID',updated_at=now() WHERE id=$1",
            order["id"], fee,
        )
        await conn.execute(
            "INSERT INTO payments(order_id,kind,amount,status) VALUES($1,'BOOKING',$2,'PENDING')",
            order["id"], fee,
        )
    await send_text(offer["wa_number"], f"Customer memilih Anda untuk *{order_no}*. Tunggu pembayaran dan konfirmasi lokasi sebelum berangkat.")
    from .finance import send_payment_request
    await send_payment_request(customer_phone, order_no, fee, "BOOKING")
    return f"Anda memilih *{offer['name']}*. Biaya kunjungan awal: *{rupiah(fee)}*. Instruksi pembayaran sudah dikirim."
