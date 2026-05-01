from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from api.database import get_db

router = APIRouter(prefix="/api")

VALID_TYPES = {"canvas", "thesis", "observation", "setup", "trade", "review"}


async def _fetch_entities(type: Optional[str], db):
    if type is not None and type not in VALID_TYPES:
        return []

    results = []

    if type is None or type == "canvas":
        rows = await db.execute_fetchall(
            """SELECT c.id, c.name, c.status, c.last_reviewed,
                      (SELECT COUNT(*) FROM thesis_linked_canvases tlc WHERE tlc.canvas_id = c.id) AS thesis_count,
                      (SELECT COUNT(*) FROM setup_linked_canvases slc WHERE slc.canvas_id = c.id) AS setup_backlink_count
               FROM canvas c
               ORDER BY c.last_reviewed DESC"""
        )
        for r in rows:
            results.append({
                "entity_type": "canvas",
                "id": r["id"],
                "display_name": r["name"],
                "status": r["status"],
                "last_updated": r["last_reviewed"],
                "links": {
                    "thesis_count": r["thesis_count"],
                    "setup_backlink_count": r["setup_backlink_count"],
                },
            })

    if type is None or type == "thesis":
        rows = await db.execute_fetchall(
            """SELECT t.id, t.instrument, t.status, t.last_updated,
                      (SELECT GROUP_CONCAT(c.name, ', ')
                       FROM thesis_linked_canvases tlc
                       JOIN canvas c ON c.id = tlc.canvas_id
                       WHERE tlc.thesis_id = t.id) AS linked_canvas_names,
                      CASE WHEN t.linked_trade_id IS NOT NULL THEN 1 ELSE 0 END AS has_active_trade
               FROM thesis t
               ORDER BY t.last_updated DESC"""
        )
        for r in rows:
            results.append({
                "entity_type": "thesis",
                "id": r["id"],
                "display_name": r["instrument"],
                "status": r["status"],
                "last_updated": r["last_updated"],
                "links": {
                    "linked_canvas_names": (r["linked_canvas_names"] or ""),
                    "has_active_trade": bool(r["has_active_trade"]),
                },
            })

    if type is None or type == "observation":
        rows = await db.execute_fetchall(
            """SELECT o.id, o.name, o.instrument, o.status, o.created_at,
                      (SELECT GROUP_CONCAT(t.instrument, ', ')
                       FROM observation_thesis_links otl
                       JOIN thesis t ON t.id = otl.thesis_id
                       WHERE otl.observation_id = o.id) AS linked_thesis_name
               FROM observation o
               ORDER BY o.created_at DESC"""
        )
        for r in rows:
            results.append({
                "entity_type": "observation",
                "id": r["id"],
                "display_name": r["name"] or r["instrument"],
                "status": r["status"],
                "last_updated": r["created_at"],
                "links": {
                    "linked_thesis_name": (r["linked_thesis_name"] or ""),
                },
            })

    if type is None or type == "setup":
        rows = await db.execute_fetchall(
            """SELECT s.id, s.name, s.instrument, s.type, s.created_at,
                      (SELECT GROUP_CONCAT(t.instrument, ', ')
                       FROM setup_thesis_links stl
                       JOIN thesis t ON t.id = stl.thesis_id
                       WHERE stl.setup_id = s.id) AS linked_thesis_name
               FROM setup s
               ORDER BY s.created_at DESC"""
        )
        for r in rows:
            results.append({
                "entity_type": "setup",
                "id": r["id"],
                "display_name": r["name"] or r["instrument"],
                "status": r["type"],
                "last_updated": r["created_at"],
                "links": {
                    "linked_thesis_name": (r["linked_thesis_name"] or ""),
                },
            })

    if type is None or type == "trade":
        rows = await db.execute_fetchall(
            """SELECT t.id, t.instrument_type, t.status, t.created_at,
                      th.instrument AS thesis_instrument,
                      CASE WHEN t.review_id IS NOT NULL THEN 1 ELSE 0 END AS has_review
               FROM trade t
               JOIN thesis th ON t.thesis_id = th.id
               ORDER BY t.created_at DESC"""
        )
        for r in rows:
            results.append({
                "entity_type": "trade",
                "id": r["id"],
                "display_name": r["instrument_type"],
                "status": r["status"],
                "last_updated": r["created_at"],
                "links": {
                    "thesis_instrument": r["thesis_instrument"],
                    "has_review": bool(r["has_review"]),
                },
            })

    if type is None or type == "review":
        rows = await db.execute_fetchall(
            """SELECT r.id, r.trade_id, r.phase2_created_at, r.locked_at,
                      th.instrument AS trade_instrument,
                      CASE WHEN r.phase2_created_at IS NOT NULL THEN 'P1+P2' ELSE 'P1' END AS phase_indicator
               FROM review r
               JOIN trade tr ON r.trade_id = tr.id
               JOIN thesis th ON tr.thesis_id = th.id
               ORDER BY r.locked_at DESC"""
        )
        for r in rows:
            results.append({
                "entity_type": "review",
                "id": r["id"],
                "display_name": r["trade_instrument"],
                "status": r["phase_indicator"],
                "last_updated": r["locked_at"],
                "links": {
                    "trade_instrument": r["trade_instrument"],
                    "phase_indicator": r["phase_indicator"],
                },
            })

    results.sort(key=lambda e: e["last_updated"], reverse=True)
    return results


@router.get("/entities")
async def list_entities(
    type: Optional[str] = Query(default=None), db=Depends(get_db)
):
    return await _fetch_entities(type, db)


async def _delete_trade_cascade(db, trade_id: str):
    await db.execute("UPDATE trade SET review_id = NULL WHERE id = ?", (trade_id,))
    await db.execute("DELETE FROM review WHERE trade_id = ?", (trade_id,))
    await db.execute("DELETE FROM trade_entries WHERE trade_id = ?", (trade_id,))
    await db.execute("DELETE FROM trade_exits WHERE trade_id = ?", (trade_id,))
    await db.execute("DELETE FROM trade_option_legs WHERE trade_id = ?", (trade_id,))
    await db.execute("DELETE FROM trade_options_meta WHERE trade_id = ?", (trade_id,))
    await db.execute("DELETE FROM trade WHERE id = ?", (trade_id,))


@router.delete("/entities/{entity_type}/{entity_id}")
async def delete_entity(entity_type: str, entity_id: str, db=Depends(get_db)):
    if entity_type not in VALID_TYPES:
        raise HTTPException(400, f"Unknown entity type: {entity_type}")

    await db.execute("BEGIN")
    try:
        if entity_type == "canvas":
            await db.execute("DELETE FROM canvas_source_documents WHERE canvas_id = ?", (entity_id,))
            await db.execute("DELETE FROM canvas_cross_currents WHERE source_canvas_id = ? OR target_canvas_id = ?", (entity_id, entity_id))
            await db.execute("DELETE FROM canvas_invalidation_conditions WHERE canvas_id = ?", (entity_id,))
            await db.execute("DELETE FROM canvas_version_history WHERE canvas_id = ?", (entity_id,))
            await db.execute("DELETE FROM thesis_linked_canvases WHERE canvas_id = ?", (entity_id,))
            await db.execute("DELETE FROM setup_linked_canvases WHERE canvas_id = ?", (entity_id,))
            await db.execute("DELETE FROM canvas WHERE id = ?", (entity_id,))

        elif entity_type == "thesis":
            await db.execute("DELETE FROM thesis_kill_conditions_macro WHERE thesis_id = ?", (entity_id,))
            await db.execute("DELETE FROM thesis_kill_conditions_technical WHERE thesis_id = ?", (entity_id,))
            await db.execute("DELETE FROM thesis_decision_points WHERE thesis_id = ?", (entity_id,))
            await db.execute("DELETE FROM thesis_linked_canvases WHERE thesis_id = ?", (entity_id,))
            await db.execute("DELETE FROM thesis_version_history WHERE thesis_id = ?", (entity_id,))
            await db.execute("DELETE FROM setup_thesis_links WHERE thesis_id = ?", (entity_id,))
            trade_rows = await db.execute_fetchall(
                "SELECT id FROM trade WHERE thesis_id = ?", (entity_id,)
            )
            for row in trade_rows:
                await _delete_trade_cascade(db, row["id"])
            await db.execute("DELETE FROM thesis WHERE id = ?", (entity_id,))

        elif entity_type == "setup":
            await db.execute("DELETE FROM setup_images WHERE setup_id = ?", (entity_id,))
            await db.execute("DELETE FROM setup_thesis_links WHERE setup_id = ?", (entity_id,))
            await db.execute("DELETE FROM observation_setup_links WHERE setup_id = ?", (entity_id,))
            await db.execute("DELETE FROM setup_linked_canvases WHERE setup_id = ?", (entity_id,))
            await db.execute("UPDATE action SET linked_setup_id = NULL WHERE linked_setup_id = ?", (entity_id,))
            await db.execute("UPDATE inbox SET routed_to_setup_id = NULL WHERE routed_to_setup_id = ?", (entity_id,))
            await db.execute("DELETE FROM setup WHERE id = ?", (entity_id,))

        elif entity_type == "trade":
            await _delete_trade_cascade(db, entity_id)

        elif entity_type == "observation":
            await db.execute("DELETE FROM observation_thesis_links WHERE observation_id = ?", (entity_id,))
            await db.execute("DELETE FROM observation_setup_links WHERE observation_id = ?", (entity_id,))
            await db.execute("DELETE FROM observation WHERE id = ?", (entity_id,))

        elif entity_type == "review":
            await db.execute("UPDATE trade SET review_id = NULL WHERE review_id = ?", (entity_id,))
            await db.execute("DELETE FROM review WHERE id = ?", (entity_id,))

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"deleted": True}
