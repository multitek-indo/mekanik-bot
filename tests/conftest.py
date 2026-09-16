import os
import sys
import types
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')
os.environ.setdefault('OWNER_WA_NUMBER', '62' + '0' * 11)
os.environ.setdefault('OWNER_API_TOKEN', 'test-owner-token')
os.environ.setdefault('GOWA_BASIC_AUTH_USER', 'test')
os.environ.setdefault('GOWA_BASIC_AUTH_PASSWORD', 'test')
os.environ.setdefault('GOWA_WEBHOOK_SECRET', 'test-secret')
os.environ.setdefault('PAYMENT_BANK_ACCOUNT', '1234567890')

# The execution environment used to validate this source snapshot may not have
# asyncpg installed. Unit tests below do not open a database connection, so a
# tiny import-only stub is enough for collection. Production Docker installs
# the real asyncpg package from requirements.txt.
if importlib.util.find_spec('asyncpg') is None:
    asyncpg = types.ModuleType('asyncpg')
    class Pool:  # pragma: no cover - import compatibility only
        pass
    async def create_pool(*args, **kwargs):  # pragma: no cover
        raise RuntimeError('asyncpg test stub: database access is not available')
    asyncpg.Pool = Pool
    asyncpg.create_pool = create_pool
    sys.modules['asyncpg'] = asyncpg
