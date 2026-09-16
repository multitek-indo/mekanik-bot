from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from .db import pool
from .skills import detect_skill_code, SKILL_BY_CODE
from .wa import normalize_phone

ORDER_STATUSES = {
    "COLLECTING_INFORMATION",
    "READY_FOR_MATCHING",
    "OFFERING",
    "WAITING_CUSTOMER_TECH_SELECTION",
    "WAITING_BOOKING_FEE_OWNER",
    "WAITING_BOOKING_PAYMENT",
    "BOOKING_PROOF_SUBMITTED",
    "BOOKING_PAID",
    "WAITING_FINAL_LOCATION_CONFIRMATION",
    "READY_TO_DEPART",
    "EN_ROUTE",
    "ARRIVED",
    "DIAGNOSING",
    "WAITING_CUSTOMER_APPROVAL",
    "REPAIRING",
    "WAITING_FINAL_PAYMENT",
    "FINAL_PROOF_SUBMITTED",
    "WAITING_CUSTOMER_CONFIRMATION",
    "UNREPAIRABLE_REVIEW",
    "DISPUTE",
    "SETTLEMENT_PENDING_OWNER",
    "SETTLED",
    "CLOSED",
    "NO_TECHNICIAN",
    "CANCELLED",
}


async def get_or_create_customer(phone: str, name: str | None = None):
    phone = normalize_phone(phone)
    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM customers WHERE wa_number=$1", phone)
        if row:
            if name and not row["name"]:
                row = await conn.fetchrow(
                    "UPDATE customers SET name=$2,updated_at=now() WHERE id=$1 RETURNING *",
                    row["id"], name[:150],
                )
            return row
        return await conn.fetchrow(
            "INSERT INTO customers(wa_number,name) VALUES($1,$2) RETURNING *",
            phone, name[:150] if name else None,
        )


async def customer_by_phone(phone: str):
    async with pool().acquire() as conn:
        return await conn.fetchrow("SELECT * FROM customers WHERE wa_number=$1", normalize_phone(phone))


async def next_order_no(conn) -> str:
    seq = await conn.fetchval("SELECT nextval('service_order_number_seq')")
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    return f"MTK-{now:%y%m%d}-{seq:04d}"


async def create_order(customer_id, location: dict, landmark: str, items: list[dict]):
    async with pool().acquire() as conn:
        async with conn.transaction():
            order_no = await next_order_no(conn)
            order = await conn.fetchrow(
                """INSERT INTO service_orders(
                       order_no,customer_id,status,location_lat,location_lon,location_name,location_address,
                       location_landmark,location_source,location_confirmed)
                   VALUES($1,$2,'READY_FOR_MATCHING',$3,$4,$5,$6,$7,$8,true)
                   RETURNING *""",
                order_no, customer_id, location["lat"], location["lon"], location.get("name") or "",
                location.get("address") or "", landmark[:500], location.get("source") or "UNKNOWN",
            )
            for idx, item in enumerate(items, start=1):
                machine = str(item.get("machine") or "").strip()[:300]
                complaint = str(item.get("problem") or "").strip()[:1500]
                code = detect_skill_code(f"{machine} {complaint}")
                name = SKILL_BY_CODE[code]["name"] if code else None
                await conn.execute(
                    """INSERT INTO service_order_items(
                           order_id,item_no,machine_category_code,machine_category_name,machine_text,complaint,declared_by,status)
                       VALUES($1,$2,$3,$4,$5,$6,'CUSTOMER','DECLARED')""",
                    order["id"], idx, code, name, machine, complaint,
                )
            await conn.execute(
                """INSERT INTO service_order_status_history(order_id,new_status,actor_type,actor_ref,note)
                   VALUES($1,'READY_FOR_MATCHING','CUSTOMER','whatsapp','Lokasi customer sudah dikonfirmasi')""",
                order["id"],
            )
            return order


async def find_order(order_no: str):
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            """SELECT o.*,c.wa_number customer_wa,c.name customer_name,
                      t.name technician_name,t.wa_number technician_wa,t.profile_photo_path technician_photo
               FROM service_orders o
               JOIN customers c ON c.id=o.customer_id
               LEFT JOIN technicians t ON t.id=o.assigned_technician_id
               WHERE upper(o.order_no)=upper($1)""",
            order_no.strip(),
        )


async def active_order_for_customer(phone: str):
    phone = normalize_phone(phone)
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            """SELECT o.* FROM service_orders o
               JOIN customers c ON c.id=o.customer_id
               WHERE c.wa_number=$1 AND o.status NOT IN ('CLOSED','CANCELLED')
               ORDER BY o.created_at DESC LIMIT 1""",
            phone,
        )


async def order_items(order_id):
    async with pool().acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM service_order_items WHERE order_id=$1 ORDER BY item_no",
            order_id,
        )


async def order_item(order_id, item_no: int):
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM service_order_items WHERE order_id=$1 AND item_no=$2",
            order_id, item_no,
        )


async def change_status(order_id, new_status: str, actor_type: str, actor_ref: str, note: str = ""):
    if new_status not in ORDER_STATUSES:
        raise ValueError(f"Status tidak valid: {new_status}")
    async with pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT status FROM service_orders WHERE id=$1 FOR UPDATE", order_id)
            if not row:
                raise ValueError("Service order tidak ditemukan")
            old = row["status"]
            if old == new_status:
                return
            await conn.execute("UPDATE service_orders SET status=$2,updated_at=now() WHERE id=$1", order_id, new_status)
            await conn.execute(
                """INSERT INTO service_order_status_history(order_id,old_status,new_status,actor_type,actor_ref,note)
                   VALUES($1,$2,$3,$4,$5,$6)""",
                order_id, old, new_status, actor_type, actor_ref, note[:1000],
            )


async def add_attachment(order_id, item_id, actor_type: str, actor_ref: str, purpose: str, media_type: str, path: str, message_id: str):
    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO attachments(order_id,item_id,actor_type,actor_ref,purpose,media_type,local_path,message_id)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
            order_id, item_id, actor_type, actor_ref, purpose, media_type, path, message_id,
        )


async def audit(actor_type: str, actor_ref: str, action: str, object_type: str = "", object_ref: str = "", payload: str = "{}"):
    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO audit_logs(actor_type,actor_ref,action,object_type,object_ref,payload)
               VALUES($1,$2,$3,$4,$5,$6::jsonb)""",
            actor_type, actor_ref, action, object_type, object_ref, payload,
        )


async def status_summary(order_no: str) -> str:
    order = await find_order(order_no)
    if not order:
        return "Nomor service tidak ditemukan."
    items = await order_items(order["id"])
    lines = [
        f"*STATUS {order['order_no']}*",
        f"Status utama: {order['status']}",
        f"Mekanik: {order['technician_name'] or 'belum dipilih'}",
        f"Booking: {order['booking_payment_status']}",
    ]
    for item in items:
        lines.append(f"{item['item_no']}. {item['machine_text']} — {item['status']}")
    return "\n".join(lines)
