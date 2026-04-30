from pathlib import Path
import aiosqlite

DB_DIR = Path(__file__).parent


async def init_schema(conn: aiosqlite.Connection):
    """
    Load schema, triggers, and views at application startup.

    executescript() issues an implicit COMMIT before running. Safe at startup
    (no open transaction). Do not call inside an open transaction.
    """
    for filename in ('schema.sql', 'triggers.sql', 'views.sql'):
        sql = (DB_DIR / filename).read_text()
        await conn.executescript(sql)
