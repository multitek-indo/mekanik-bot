import json
from datetime import datetime, timedelta, timezone

from .db import pool
from .wa import normalize_phone


def _decode_payload(value) -> dict:
    """
    Normalize PostgreSQL JSON/JSONB payload menjadi Python dict.

    asyncpg secara default dapat mengembalikan JSON/JSONB sebagai string.
    Seluruh conversation state di aplikasi mengharapkan payload berupa dict.
    """
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}

        if isinstance(decoded, dict):
            return decoded

        return {}

    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


async def set_state(
    phone: str,
    state: str,
    payload: dict,
    ttl_minutes: int = 180,
):
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO conversation_states(
                wa_number,
                state,
                payload,
                expires_at,
                updated_at
            )
            VALUES($1,$2,$3::jsonb,$4,now())

            ON CONFLICT(wa_number)
            DO UPDATE SET
                state = EXCLUDED.state,
                payload = EXCLUDED.payload,
                expires_at = EXCLUDED.expires_at,
                updated_at = now()
            """,
            normalize_phone(phone),
            state,
            json.dumps(payload),
            expires,
        )


async def get_state(phone: str):
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM conversation_states
            WHERE wa_number=$1
              AND (expires_at IS NULL OR expires_at > now())
            """,
            normalize_phone(phone),
        )

    if row is None:
        return None

    # asyncpg.Record -> dict agar payload dapat dinormalisasi.
    result = dict(row)
    result["payload"] = _decode_payload(result.get("payload"))

    return result


async def clear_state(phone: str):
    async with pool().acquire() as conn:
        await conn.execute(
            "DELETE FROM conversation_states WHERE wa_number=$1",
            normalize_phone(phone),
        )
