from pathlib import Path
import asyncpg
from .config import settings

_pool: asyncpg.Pool | None = None


async def init_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=10,
            command_timeout=30,
        )
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        async with _pool.acquire() as conn:
            await conn.execute(schema)


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool belum diinisialisasi")
    return _pool
