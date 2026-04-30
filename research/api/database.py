import aiosqlite
from contextlib import asynccontextmanager
from api.config import settings


async def get_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA busy_timeout = 5000")
    return conn


async def get_db():
    """FastAPI dependency: read-write connection to research.db."""
    conn = await get_connection()
    try:
        yield conn
    finally:
        await conn.close()


@asynccontextmanager
async def get_library_db():
    """
    Read-only connection to library.sqlite. Used as an async context manager.
    Never used as a FastAPI dependency — callers manage scope explicitly.

    Usage:
        async with get_library_db() as lib:
            row = await lib.execute_fetchone(...)

    Raises RuntimeError if library_db_path is not configured.
    """
    if not settings.library_db_path:
        raise RuntimeError("library_db_path is not configured")
    conn = await aiosqlite.connect(
        f"file:{settings.library_db_path}?mode=ro", uri=True
    )
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()
