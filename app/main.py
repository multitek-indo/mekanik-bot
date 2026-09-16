import os
import logging
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from .config import settings
from .db import init_pool, close_pool, pool
from .security import verify_gowa_signature
from .router import process_event
from .wa import normalize_phone
from .skills import SKILL_BY_CODE
from .version import APP_VERSION

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
log = logging.getLogger("multitek-service")

app = FastAPI(title="Multitek Service Marketplace MVP", version=APP_VERSION)


@app.on_event("startup")
async def startup():
    await init_pool()


@app.on_event("shutdown")
async def shutdown():
    await close_pool()


@app.get("/health")
async def health():
    async with pool().acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {
        "status": "ok",
        "version": APP_VERSION,
        "commit": os.getenv("APP_GIT_COMMIT", "unknown")[:12],
        "env": settings.app_env,
    }


def require_owner(auth: str | None):
    if auth != f"Bearer {settings.owner_api_token}":
        raise HTTPException(status_code=401, detail="unauthorized")


class TechnicianIn(BaseModel):
    name: str
    wa_number: str
    domicile: str = ""
    base_lat: float
    base_lon: float
    base_address: str = ""
    service_radius_km: float = 25
    years_experience: int = 0
    vehicle: str = ""
    profile_photo_path: str = ""
    skills: dict[str, int] = Field(default_factory=dict)


@app.post("/owner/technicians")
async def add_technician(data: TechnicianIn, authorization: str | None = Header(default=None)):
    require_owner(authorization)
    wa = normalize_phone(data.wa_number)
    async with pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """INSERT INTO technicians(
                       name,wa_number,domicile,base_lat,base_lon,base_address,service_radius_km,
                       years_experience,vehicle,profile_photo_path,is_active,is_available)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,true,true)
                   ON CONFLICT(wa_number) DO UPDATE SET
                       name=EXCLUDED.name,domicile=EXCLUDED.domicile,base_lat=EXCLUDED.base_lat,
                       base_lon=EXCLUDED.base_lon,base_address=EXCLUDED.base_address,
                       service_radius_km=EXCLUDED.service_radius_km,years_experience=EXCLUDED.years_experience,
                       vehicle=EXCLUDED.vehicle,profile_photo_path=EXCLUDED.profile_photo_path,
                       is_active=true,is_available=true,updated_at=now()
                   RETURNING *""",
                data.name, wa, data.domicile, data.base_lat, data.base_lon, data.base_address,
                data.service_radius_km, data.years_experience, data.vehicle, data.profile_photo_path or None,
            )
            for code, level in data.skills.items():
                code = code.upper()
                if code not in SKILL_BY_CODE or not (0 <= int(level) <= 5):
                    continue
                await conn.execute(
                    """INSERT INTO technician_skill_matrix(technician_id,skill_code,skill_name,level,verified)
                       VALUES($1,$2,$3,$4,true)
                       ON CONFLICT(technician_id,skill_code) DO UPDATE SET level=EXCLUDED.level,verified=true,updated_at=now()""",
                    row["id"], code, SKILL_BY_CODE[code]["name"], int(level),
                )
    return {"ok": True, "technician_id": str(row["id"]), "wa_number": row["wa_number"]}


@app.get("/owner/orders")
async def orders(authorization: str | None = Header(default=None)):
    require_owner(authorization)
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT o.order_no,o.status,o.booking_fee,o.booking_payment_status,o.final_amount_due,
                      o.final_payment_status,o.created_at,c.name customer_name,t.name technician_name
               FROM service_orders o JOIN customers c ON c.id=o.customer_id
               LEFT JOIN technicians t ON t.id=o.assigned_technician_id
               ORDER BY o.created_at DESC LIMIT 100"""
        )
    return [dict(r) for r in rows]


@app.post("/webhooks/gowa")
async def gowa_webhook(request: Request, background_tasks: BackgroundTasks):
    raw = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_gowa_signature(raw, signature):
        raise HTTPException(status_code=401, detail="invalid signature")
    data = await request.json()
    if data.get("event") != "message":
        return {"ok": True, "ignored": "event"}
    payload = data.get("payload") or {}
    message_id = str(payload.get("id") or "")
    sender = normalize_phone(str(payload.get("from") or payload.get("chat_id") or ""))
    if message_id:
        async with pool().acquire() as conn:
            inserted = await conn.fetchval(
                """INSERT INTO processed_messages(message_id,sender) VALUES($1,$2)
                   ON CONFLICT(message_id) DO NOTHING RETURNING message_id""",
                message_id, sender,
            )
        if not inserted:
            return {"ok": True, "ignored": "duplicate"}
    # GOWA expects webhook handlers to return quickly; work continues after the response.
    background_tasks.add_task(process_event, data)
    return {"ok": True, "queued": True}
