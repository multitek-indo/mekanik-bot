import asyncio
import logging
from .config import settings
from .db import init_pool, close_pool, pool
from .matching import finalize_offer_window

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
log = logging.getLogger("multitek-worker")


async def expire_offer_windows():
    async with pool().acquire() as conn:
        order_ids = await conn.fetch(
            """SELECT DISTINCT order_id FROM job_offers
               WHERE status='PENDING' AND expires_at<=now()"""
        )
    for row in order_ids:
        try:
            await finalize_offer_window(row["order_id"])
        except Exception:
            log.exception("Failed finalizing offer window for %s", row["order_id"])


async def run():
    await init_pool()
    try:
        while True:
            try:
                await expire_offer_windows()
            except Exception:
                log.exception("Worker cycle failed")
            await asyncio.sleep(5)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
