"""Protocol 2: Observable kill conditions on active theses.

Triggered when a linked canvas is recently updated and the active thesis has
unfired macro kill conditions. Surfaces banners on thesis detail pages.

No dismiss — only clears when hold-vs-redeploy paragraph is filed."""


async def check_protocol2(db, thesis_id: str = None):
    """Return theses with observable kill conditions.

    Checks active theses with unfired macro kill conditions where the linked
    canvas has been updated in the last 7 days.

    Args:
        db: aiosqlite connection
        thesis_id: if provided, check only this thesis

    Returns:
        list of dicts with thesis_id, instrument, condition, canvas_name
    """
    if thesis_id:
        rows = await db.execute_fetchall(
            """SELECT t.id AS thesis_id, t.instrument,
                      kcm.id AS kc_id, kcm.condition,
                      c.name AS canvas_name
               FROM thesis t
               JOIN thesis_kill_conditions_macro kcm ON kcm.thesis_id = t.id AND kcm.fired_at IS NULL
               JOIN thesis_linked_canvases tlc ON tlc.thesis_id = t.id
               JOIN canvas c ON c.id = tlc.canvas_id
               WHERE t.id = ? AND t.status = 'active'
                 AND c.last_reviewed >= datetime('now', '-7 days')""",
            (thesis_id,),
        )
    else:
        rows = await db.execute_fetchall(
            """SELECT t.id AS thesis_id, t.instrument,
                      kcm.id AS kc_id, kcm.condition,
                      c.name AS canvas_name
               FROM thesis t
               JOIN thesis_kill_conditions_macro kcm ON kcm.thesis_id = t.id AND kcm.fired_at IS NULL
               JOIN thesis_linked_canvases tlc ON tlc.thesis_id = t.id
               JOIN canvas c ON c.id = tlc.canvas_id
               WHERE t.status = 'active'
                 AND c.last_reviewed >= datetime('now', '-7 days')""",
        )

    return [dict(r) for r in rows]
