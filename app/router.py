import logging
import re
from .config import settings
from .db import pool
from .location import normalize_location_payload
from .media import extract_media, persist_incoming_media
from .types import IncomingMessage
from .wa import normalize_phone, send_text, send_image
from .state import get_state
from .orders import active_order_for_customer, find_order, change_status, status_summary
from .onboarding import (
    start_registration,
    handle_registration,
    owner_application_list,
    owner_application_detail,
    owner_approve_application,
    owner_reject_application,
)
from .owner import ticket_list, order_detail, owner_help, skill_code_from_number
from .matching import mechanic_offer_response, select_candidate
from .customer import handle_customer_message, confirm_final_location, request_location_change
from .mechanic import (
    mechanic_by_phone,
    handle_mechanic_state,
    set_online_wait_location,
    set_offline,
    tech_depart,
    tech_arrive,
    start_diagnosis,
    start_unrepairable,
    add_extra_machine,
    customer_extra_response,
    customer_quote_response,
    complete_item,
    complete_order,
    customer_unrepairable_response,
)
from .finance import (
    submit_payment_proof,
    owner_confirm_booking,
    owner_confirm_final,
    owner_set_booking,
    create_success_settlement,
    owner_approve_settlement,
    owner_mark_payout,
    owner_set_price,
    tariff_list,
)

log = logging.getLogger("multitek-router")

ORDER_RE = r"(MTK-[A-Z0-9-]+)"
APP_RE = r"(MKN-[A-Z0-9-]+)"


def _is_truthy(value) -> bool:
    """
    GoWA/provider payload tidak selalu konsisten tipe datanya.
    Terima boolean, integer, maupun string sebagai flag true.
    """
    if value is True:
        return True

    if isinstance(value, int):
        return value == 1

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "y",
            "on",
        }

    return False


async def build_message(data: dict) -> IncomingMessage | None:
    if data.get("event") != "message":
        return None

    payload = data.get("payload") or {}

    # Jangan pernah memproses pesan yang dikirim bot/device sendiri.
    if _is_truthy(payload.get("is_from_me")):
        log.info(
            "Ignoring outgoing/from_me message id=%s",
            payload.get("id") or "-",
        )
        return None
    chat_id = str(payload.get("chat_id") or "")
    sender = str(payload.get("from") or chat_id)
    if chat_id.endswith("@g.us"):
        return None
    phone = normalize_phone(sender or chat_id)
    if not phone:
        return None
    text = str(payload.get("body") or payload.get("message") or payload.get("text") or "").strip()
    location = normalize_location_payload(payload)
    kind, ref = extract_media(payload)
    media_path = None
    if kind and ref:
        media_path = await persist_incoming_media(kind, ref, phone, "incoming")
    return IncomingMessage(
        message_id=str(payload.get("id") or ""),
        phone=phone,
        sender_name=str(payload.get("sender_display_name") or payload.get("from_name") or "").strip(),
        text=text,
        location=location,
        image=payload.get("image"),
        video=payload.get("video") or payload.get("video_note"),
        document=payload.get("document"),
        media_type=kind,
        media_path=media_path,
        raw_payload=payload,
    )


async def _send_owner_detail(app_no: str):
    text, photo = await owner_application_detail(app_no)
    if photo:
        try:
            await send_image(settings.owner_wa_number, photo, f"Foto calon mekanik {app_no}")
        except Exception:
            pass
    await send_text(settings.owner_wa_number, text)


async def try_owner_command(msg: IncomingMessage) -> bool:
    text = (msg.text or "").strip()
    up = text.upper()

    if up == "TIKET":
        await send_text(msg.phone, await ticket_list())
        return True
    m = re.fullmatch(rf"RINCI\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await order_detail(m.group(1)))
        return True
    if up == "CALON MEKANIK":
        await send_text(msg.phone, await owner_application_list())
        return True
    m = re.fullmatch(rf"DETAIL\s+MEKANIK\s+{APP_RE}", up)
    if m:
        await _send_owner_detail(m.group(1))
        return True
    m = re.fullmatch(rf"SETUJUI\s+MEKANIK\s+{APP_RE}", up)
    if m:
        reply, applicant_phone = await owner_approve_application(m.group(1))
        await send_text(msg.phone, reply)
        if applicant_phone:
            await send_text(applicant_phone, "Pendaftaran Anda sudah *DISETUJUI*. Anda sekarang aktif sebagai partner mekanik Multitek. Ketik *ONLINE* lalu kirim Share Location saat siap menerima job.")
        return True
    m = re.fullmatch(rf"TOLAK\s+MEKANIK\s+{APP_RE}\s+(.+)", text, flags=re.I)
    if m:
        reply, applicant_phone = await owner_reject_application(m.group(1), m.group(2))
        await send_text(msg.phone, reply)
        if applicant_phone:
            await send_text(applicant_phone, f"Pendaftaran mekanik Anda belum dapat disetujui. Alasan: {m.group(2)}")
        return True
    m = re.fullmatch(rf"KONFIRMASI\s+BAYAR\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await owner_confirm_booking(m.group(1)))
        return True
    m = re.fullmatch(rf"KONFIRMASI\s+PELUNASAN\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await owner_confirm_final(m.group(1)))
        return True
    m = re.fullmatch(rf"SET\s+BOOKING\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await owner_set_booking(m.group(1), int(m.group(2))))
        return True
    m = re.fullmatch(rf"SETUJUI\s+SETTLEMENT\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await owner_approve_settlement(m.group(1)))
        return True
    m = re.fullmatch(rf"PAYOUT\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await owner_mark_payout(m.group(1)))
        return True
    if up == "TARIF":
        await send_text(msg.phone, await tariff_list())
        return True
    m = re.fullmatch(r"SET\s+TARIF\s+(\d{1,2})\s+(INSPEKSI|RINGAN|SEDANG|BERAT)\s+(\d+)", up)
    if m:
        code = skill_code_from_number(int(m.group(1)))
        if not code:
            await send_text(msg.phone, "Nomor skill tidak valid (1-18).")
        else:
            await send_text(msg.phone, await owner_set_price(code, m.group(2), int(m.group(3))))
        return True
    if up in {"OWNER", "HELP OWNER", "BANTUAN OWNER"}:
        await send_text(msg.phone, owner_help())
        return True
    return False


async def try_mechanic_command(msg: IncomingMessage) -> bool:
    # State replies (diagnosis, evidence, ONLINE location) have priority.
    state_reply = await handle_mechanic_state(msg)
    if state_reply is not None:
        await send_text(msg.phone, state_reply)
        return True

    text = (msg.text or "").strip()
    up = text.upper()
    if up == "ONLINE":
        await send_text(msg.phone, await set_online_wait_location(msg.phone))
        return True
    if up == "OFFLINE":
        await send_text(msg.phone, await set_offline(msg.phone))
        return True
    m = re.fullmatch(rf"(BERMINAT|TERIMA|TOLAK)\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await mechanic_offer_response(msg.phone, m.group(2), m.group(1) != "TOLAK"))
        return True
    m = re.fullmatch(rf"BERANGKAT\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await tech_depart(msg.phone, m.group(1)))
        return True
    m = re.fullmatch(rf"SAMPAI\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await tech_arrive(msg.phone, m.group(1)))
        return True
    m = re.fullmatch(rf"DIAGNOSIS\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await start_diagnosis(msg.phone, m.group(1), int(m.group(2))))
        return True
    m = re.fullmatch(rf"TIDAK\s+BISA\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await start_unrepairable(msg.phone, m.group(1), int(m.group(2))))
        return True
    m = re.fullmatch(rf"TAMBAH\s+MESIN\s+{ORDER_RE}\s+(.+)", text, flags=re.I | re.S)
    if m:
        await send_text(msg.phone, await add_extra_machine(msg.phone, m.group(1).upper(), m.group(2)))
        return True
    m = re.fullmatch(rf"SELESAI\s+ITEM\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await complete_item(msg.phone, m.group(1), int(m.group(2))))
        return True
    m = re.fullmatch(rf"SELESAI\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await complete_order(msg.phone, m.group(1)))
        return True
    if up in {"BANTUAN", "HELP", "MENU"}:
        await send_text(
            msg.phone,
            "*PERINTAH MEKANIK*\nONLINE / OFFLINE\nBERMINAT MTK-... / TOLAK MTK-...\n"
            "BERANGKAT MTK-...\nSAMPAI MTK-...\nDIAGNOSIS MTK-... <item>\n"
            "TIDAK BISA MTK-... <item>\nTAMBAH MESIN MTK-... jenis | keluhan | biaya_cek\n"
            "SELESAI ITEM MTK-... <item>\nSELESAI MTK-...",
        )
        return True
    return False


async def try_customer_command(msg: IncomingMessage) -> bool:
    text = (msg.text or "").strip()
    up = text.upper()

    active = await active_order_for_customer(msg.phone)
    # A payment screenshot is routed by current payment state, not by AI image recognition.
    if msg.media_type == "image" and msg.media_path and active:
        if active["status"] in {"WAITING_BOOKING_PAYMENT", "BOOKING_PROOF_SUBMITTED"}:
            reply = await submit_payment_proof(msg.phone, active["order_no"], "BOOKING", msg.media_path, "image", msg.message_id)
            await send_text(msg.phone, reply)
            return True
        if active["status"] in {"WAITING_FINAL_PAYMENT", "FINAL_PROOF_SUBMITTED"}:
            reply = await submit_payment_proof(msg.phone, active["order_no"], "FINAL", msg.media_path, "image", msg.message_id)
            await send_text(msg.phone, reply)
            return True

    m = re.fullmatch(rf"PILIH\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await select_candidate(msg.phone, m.group(1), int(m.group(2))))
        return True
    m = re.fullmatch(rf"LOKASI\s+BENAR\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await confirm_final_location(msg.phone, m.group(1)))
        return True
    m = re.fullmatch(rf"UBAH\s+LOKASI\s+{ORDER_RE}", up)
    if m:
        await send_text(msg.phone, await request_location_change(msg.phone, m.group(1)))
        return True
    m = re.fullmatch(rf"SETUJU\s+TAMBAHAN\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await customer_extra_response(msg.phone, m.group(1), int(m.group(2)), True))
        return True
    m = re.fullmatch(rf"TOLAK\s+TAMBAHAN\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await customer_extra_response(msg.phone, m.group(1), int(m.group(2)), False))
        return True
    m = re.fullmatch(rf"SETUJU\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await customer_quote_response(msg.phone, m.group(1), int(m.group(2)), True))
        return True
    m = re.fullmatch(rf"TOLAK\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await customer_quote_response(msg.phone, m.group(1), int(m.group(2)), False))
        return True
    m = re.fullmatch(rf"SETUJU\s+TIDAK\s+BISA\s+{ORDER_RE}\s+(\d+)", up)
    if m:
        await send_text(msg.phone, await customer_unrepairable_response(msg.phone, m.group(1), int(m.group(2)), True))
        return True
    m = re.fullmatch(rf"KONFIRMASI\s+SELESAI\s+{ORDER_RE}", up)
    if m:
        order = await find_order(m.group(1))
        if not order or order["customer_wa"] != msg.phone:
            reply = "Nomor service tidak ditemukan atau bukan milik nomor ini."
        elif order["status"] != "WAITING_CUSTOMER_CONFIRMATION":
            reply = f"Order belum pada tahap konfirmasi selesai. Status saat ini: {order['status']}."
        elif order["final_payment_status"] not in {"PAID", "NOT_DUE"}:
            reply = "Pelunasan belum terverifikasi."
        else:
            reply = await create_success_settlement(m.group(1))
        await send_text(msg.phone, reply)
        return True
    m = re.fullmatch(rf"MASALAH\s+{ORDER_RE}", up)
    if m:
        order = await find_order(m.group(1))
        if not order or order["customer_wa"] != msg.phone:
            reply = "Nomor service tidak ditemukan atau bukan milik nomor ini."
        else:
            await change_status(order["id"], "DISPUTE", "CUSTOMER", msg.phone, "Customer melaporkan masalah")
            await send_text(settings.owner_wa_number, f"⚠️ DISPUTE {m.group(1)} dari customer {order['customer_name'] or order['customer_wa']}. Payout ditahan.")
            reply = "Masalah sudah diteruskan ke owner Multitek. Pembayaran/payout ditahan sampai review selesai."
        await send_text(msg.phone, reply)
        return True
    if up.startswith("SUDAH BAYAR"):
        await send_text(msg.phone, "Mohon kirim *foto/screenshot bukti pembayaran*. Status PAID hanya ditetapkan setelah owner mengecek rekening secara manual.")
        return True
    if up == "STATUS":
        if active:
            await send_text(msg.phone, await status_summary(active["order_no"]))
        else:
            await send_text(msg.phone, "Tidak ada service aktif pada nomor ini.")
        return True
    return False


async def process_event(data: dict):
    try:
        msg = await build_message(data)
        if not msg:
            return
        if not msg.text and not msg.location and not msg.media_type:
            return

        log.info(
            "INBOUND id=%s phone=%s text=%r location=%s media=%s",
            msg.message_id or "-",
            msg.phone,
            (msg.text or "")[:160],
            bool(msg.location),
            msg.media_type or "-",
        )

        # Registration can be started by any non-active user, including owner if desired.
        if (msg.text or "").strip().upper() == "DAFTAR MEKANIK":
            tech = await mechanic_by_phone(msg.phone)
            if tech:
                await send_text(msg.phone, "Nomor ini sudah aktif sebagai mekanik Multitek.")
            else:
                await send_text(msg.phone, await start_registration(msg.phone))
            return

        # Existing application state comes before normal role routing.
        reg_reply = await handle_registration(msg)
        if reg_reply is not None:
            await send_text(msg.phone, reg_reply)
            if "Nomor pendaftaran" in reg_reply:
                await send_text(settings.owner_wa_number, "Ada pendaftaran calon mekanik baru. Ketik *CALON MEKANIK* untuk melihat daftar.")
            return

        owner_number = normalize_phone(settings.owner_wa_number)
        is_owner = msg.phone == owner_number
        tech = await mechanic_by_phone(msg.phone)

        # Owner may also be a registered mechanic. Owner-specific commands get first priority;
        # unmatched commands can still flow to mechanic commands.
        if is_owner and await try_owner_command(msg):
            return
        if tech and await try_mechanic_command(msg):
            return
        if is_owner:
            await send_text(msg.phone, owner_help())
            return

        if await try_customer_command(msg):
            return
        await send_text(msg.phone, await handle_customer_message(msg))
    except Exception:
        log.exception("Failed processing inbound WhatsApp event")
        try:
            payload = data.get("payload") or {}
            phone = normalize_phone(str(payload.get("from") or payload.get("chat_id") or ""))
            if phone:
                await send_text(phone, "Terjadi gangguan saat memproses pesan. Data transaksi tidak diubah. Silakan ulangi pesan terakhir beberapa saat lagi.")
        except Exception:
            pass
