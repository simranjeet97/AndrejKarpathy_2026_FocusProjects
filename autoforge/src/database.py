from typing import AsyncGenerator
import asyncpg
from src.config import settings

_pool = None

async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url.get_secret_value(),
            min_size=1,
            max_size=10
        )
    return _pool

async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

async def get_db_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn
