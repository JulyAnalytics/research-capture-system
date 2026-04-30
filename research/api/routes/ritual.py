from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from api.database import get_db

router = APIRouter(prefix="/ritual")

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and not request.headers.get("hx-request")


@router.get("/morning")
async def morning_ritual(request: Request, db=Depends(get_db)):
    stale_canvases = [
        dict(r) for r in await db.execute_fetchall("SELECT * FROM stale_canvases")
    ]
    stale_theses = [
        dict(r) for r in await db.execute_fetchall("SELECT * FROM stale_theses")
    ]
    stale_conditions = [
        dict(r)
        for r in await db.execute_fetchall("SELECT * FROM stale_invalidation_conditions")
    ]

    active_theses_raw = await db.execute_fetchall(
        """SELECT t.id, t.instrument, t.status, t.last_updated,
                  (SELECT COUNT(*) FROM thesis_kill_conditions_macro kcm WHERE kcm.thesis_id = t.id AND kcm.fired_at IS NULL) AS unfired_macro_kills,
                  (SELECT COUNT(*) FROM thesis_kill_conditions_technical kct WHERE kct.thesis_id = t.id AND kct.fired_at IS NULL) AS unfired_technical_kills
           FROM thesis t
           WHERE t.status = 'active'
           ORDER BY t.last_updated DESC"""
    )
    active_theses = []
    for t in active_theses_raw:
        t = dict(t)
        t["unfired_macro"] = t.get("unfired_macro_kills", 0)
        t["unfired_technical"] = t.get("unfired_technical_kills", 0)
        t["total_kills"] = t["unfired_macro"] + t["unfired_technical"]
        t["fired_kills"] = False
        active_theses.append(t)

    overdue = [
        dict(r) for r in await db.execute_fetchall("SELECT * FROM overdue_actions")
    ]

    if not _wants_html(request):
        return {
            "stale_canvases": stale_canvases,
            "stale_theses": stale_theses,
            "stale_invalidation_conditions": stale_conditions,
            "active_theses": active_theses,
            "overdue_actions": overdue,
        }

    # Build combined stale items list for template
    stale_items = []
    for r in stale_canvases:
        stale_items.append({
            "entity_type": "canvas",
            "id": r["id"],
            "name": r.get("name", r["id"]),
            "days_stale": r.get("days_stale", 0),
        })
    for r in stale_theses:
        stale_items.append({
            "entity_type": "thesis",
            "id": r["id"],
            "name": r.get("instrument", r["id"]),
            "days_stale": r.get("days_stale", 0),
        })
    for r in stale_conditions:
        stale_items.append({
            "entity_type": "invalidation_condition",
            "id": r["id"],
            "name": r.get("condition", r["id"][:8]),
            "days_stale": r.get("days_stale", 0),
        })
    stale_items.sort(key=lambda x: x["days_stale"], reverse=True)

    return templates.TemplateResponse("ritual/morning.html", {
        "request": request,
        "today": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "stale_items": stale_items,
        "active_theses": active_theses,
        "overdue_actions": overdue,
    })


@router.post("/morning/staleness/{entity_type}/{entity_id}")
async def confirm_staleness(entity_type: str, entity_id: str, db=Depends(get_db)):
    now = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"

    if entity_type == "canvas":
        await db.execute(f"UPDATE canvas SET last_reviewed = {now} WHERE id = ?", (entity_id,))
    elif entity_type == "thesis":
        await db.execute(f"UPDATE thesis SET last_updated = {now} WHERE id = ?", (entity_id,))
    elif entity_type == "invalidation_condition":
        await db.execute(
            f"UPDATE canvas_invalidation_conditions SET last_assessed = {now} WHERE id = ?",
            (entity_id,),
        )
    else:
        return {"error": f"Unknown entity type: {entity_type}"}

    await db.commit()
    return {"status": "confirmed"}


@router.post("/morning/position/{thesis_id}/clear")
async def clear_position(thesis_id: str, db=Depends(get_db)):
    now = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
    await db.execute(f"UPDATE thesis SET last_updated = {now} WHERE id = ?", (thesis_id,))
    await db.commit()
    return {"status": "cleared"}


# ─── EVENING ROUTING ──────────────────────────────────────────────────────────


@router.get("/evening")
async def evening_routing(request: Request, direct: int = 0, text: str = "", db=Depends(get_db)):
    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if direct:
        if not _wants_html(request):
            return {"item": None, "total_count": 0, "direct_mode": True, "prefill_text": text}
        return templates.TemplateResponse("ritual/evening.html", {
            "request": request,
            "item": None,
            "total_count": 0,
            "now_date": now_date,
            "direct_mode": True,
            "prefill_text": text,
        })

    count_rows = await db.execute_fetchall(
        "SELECT COUNT(*) AS cnt FROM inbox WHERE routed_at IS NULL"
    )
    total_count = count_rows[0]["cnt"] if count_rows else 0

    item_rows = await db.execute_fetchall(
        "SELECT * FROM inbox WHERE routed_at IS NULL ORDER BY created_at ASC LIMIT 1"
    )
    item = dict(item_rows[0]) if item_rows else None

    if not _wants_html(request):
        return {"item": item, "total_count": total_count, "direct_mode": False, "prefill_text": ""}

    return templates.TemplateResponse("ritual/evening.html", {
        "request": request,
        "item": item,
        "total_count": total_count,
        "now_date": now_date,
        "direct_mode": False,
        "prefill_text": "",
    })
