"""Protocol 3: Decision point triggers on active theses.

Triggered when an active thesis has unfired decision points (trigger met but
not yet executed). Surfaces banners on thesis detail pages.

No dismiss — clears when decision executed or deviation logged."""


async def check_protocol3(db, thesis_id: str = None):
    """Return theses with unfired decision points.

    Args:
        db: aiosqlite connection
        thesis_id: if provided, check only this thesis

    Returns:
        list of dicts with thesis_id, instrument, trigger, decision
    """
    if thesis_id:
        rows = await db.execute_fetchall(
            """SELECT t.id AS thesis_id, t.instrument,
                      dp.id AS dp_id, dp.trigger, dp.decision
               FROM thesis t
               JOIN thesis_decision_points dp ON dp.thesis_id = t.id AND dp.fired_at IS NULL
               WHERE t.id = ? AND t.status = 'active'""",
            (thesis_id,),
        )
    else:
        rows = await db.execute_fetchall(
            """SELECT t.id AS thesis_id, t.instrument,
                      dp.id AS dp_id, dp.trigger, dp.decision
               FROM thesis t
               JOIN thesis_decision_points dp ON dp.thesis_id = t.id AND dp.fired_at IS NULL
               WHERE t.status = 'active'""",
        )

    return [dict(r) for r in rows]
