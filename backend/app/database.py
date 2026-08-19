"""Database connection pool management using asyncpg."""

from typing import Optional
import asyncpg
from .config import settings

_pool: Optional[asyncpg.Pool] = None


async def create_pool() -> asyncpg.Pool:
    """Create and initialize the asyncpg connection pool."""
    global _pool
    _pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL, min_size=2, max_size=10)
    return _pool


def get_pool() -> asyncpg.Pool:
    """Retrieve the initialized asyncpg connection pool.

    Raises:
        RuntimeError: If the pool has not been initialized yet.
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call create_pool() first.")
    return _pool


async def close_pool() -> None:
    """Close the asyncpg connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
