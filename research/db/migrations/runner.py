from pathlib import Path
import aiosqlite

MIGRATIONS_DIR = Path(__file__).parent


async def run_pending(conn: aiosqlite.Connection):
    """
    Run numbered migration files in order. Simple DDL only — no compound statements.
    Trigger and view changes go in db/triggers.sql and db/views.sql, not here.

    Comment stripping is done on the raw file text before splitting on semicolons,
    avoiding incorrect splits when comment text contains semicolons.
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """)
    await conn.commit()

    cursor = await conn.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    current = row[0] or 0

    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(f.stem.split("_")[0])
        if version <= current:
            continue

        # Strip single-line comments before splitting on semicolons.
        raw = f.read_text()
        lines = [line.split('--')[0] for line in raw.splitlines()]
        text = '\n'.join(lines)
        statements = [s.strip() for s in text.split(';') if s.strip()]

        await conn.execute("BEGIN")
        try:
            for stmt in statements:
                await conn.execute(stmt)
            await conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (version,)
            )
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            raise RuntimeError(f"Migration {f.name} failed: {e}") from e
