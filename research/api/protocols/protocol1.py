async def check_protocol1(db, canvas_id: str) -> dict:
    """
    Protocol 1: surface active and ready theses linked to a canvas at the
    mutation site. Called after a canvas narrative update.

    Args:
        db:        aiosqlite connection (from get_db dependency).
        canvas_id: ULID string of the canvas that was just updated.
                   Must refer to an existing canvas row — caller is
                   responsible for the 404 check.

    Returns:
        dict with keys:
          affected_theses (list[dict]): zero or more rows of
            {id: str, instrument: str, status: str} for theses in
            'ready' or 'active' status linked to this canvas.
            Empty list means no active theses are affected — not an error.
          action_required (str): fixed instruction string for the UI banner.

    Side effects: none. Read-only query.
    """
    affected = await db.execute_fetchall(
        """SELECT t.id, t.instrument, t.status
           FROM thesis t
           JOIN thesis_linked_canvases tlc ON t.id = tlc.thesis_id
           WHERE tlc.canvas_id = ? AND t.status IN ('ready', 'active')""",
        (canvas_id,),
    )
    return {
        "affected_theses": [dict(r) for r in affected],
        "action_required": "Review kill conditions on each listed thesis against this canvas update.",
    }
