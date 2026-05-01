"""Protocol 4: Trade closed without review filed.

Triggered when a trade is closed but no review exists. Surfaces banners on
trade detail pages.

No dismiss — clears when Phase 1 is filed."""


async def check_protocol4(db, trade_id: str = None):
    """Return closed trades without reviews.

    Args:
        db: aiosqlite connection
        trade_id: if provided, check only this trade

    Returns:
        list of dicts with trade_id, thesis_instrument, closed_at
    """
    if trade_id:
        rows = await db.execute_fetchall(
            """SELECT t.id AS trade_id,
                      COALESCE(th.instrument, t.instrument, 'unknown') AS thesis_instrument,
                      t.closed_at
               FROM trade t
               LEFT JOIN thesis th ON th.id = t.thesis_id
               LEFT JOIN review r ON r.trade_id = t.id
               WHERE t.id = ? AND t.status = 'closed' AND r.id IS NULL""",
            (trade_id,),
        )
    else:
        rows = await db.execute_fetchall(
            """SELECT t.id AS trade_id,
                      COALESCE(th.instrument, t.instrument, 'unknown') AS thesis_instrument,
                      t.closed_at
               FROM trade t
               LEFT JOIN thesis th ON th.id = t.thesis_id
               LEFT JOIN review r ON r.trade_id = t.id
               WHERE t.status = 'closed' AND r.id IS NULL""",
        )

    return [dict(r) for r in rows]
