"""Database connection pool management using asyncpg."""

import json
from typing import Optional
import asyncpg
from .config import settings

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Per-connection setup applied to every pooled connection.

    Registers a JSON codec for ``jsonb``. Without this asyncpg hands back the
    raw JSON *string*, so code that treats ``installed_software`` as a list
    silently iterates it character by character instead of package by package.
    """
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def create_pool() -> asyncpg.Pool:
    """Create and initialize the asyncpg connection pool."""
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        init=_init_connection,
    )
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
