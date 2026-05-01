from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from ulid import ULID
from api.config import settings
from api.database import get_db, get_library_db
from api.models.canvas import (
    CanvasCreate,
    CanvasUpdate,
    CrossCurrentPayload,
    InvalidationConditionCreate,
    InvalidationConditionPatch,
)
from api.protocols.protocol1 import check_protocol1
from api.protocols.protocol2 import check_protocol2

router = APIRouter()

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and not request.headers.get("hx-request")


# ─── CANVAS CRUD ──────────────────────────────────────────────────────────────


@router.post("")
async def create_canvas(payload: CanvasCreate, db=Depends(get_db)):
    canvas_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO canvas (id, name, narrative, last_reviewed)
               VALUES (?, ?, ?, ?)""",
            (canvas_id, payload.name, payload.narrative, payload.last_reviewed),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": canvas_id}


@router.get("/search")
async def search_canvases(q: str = "", db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT id, name FROM canvas WHERE name LIKE ? LIMIT 10",
        (f"%{q}%",),
    )
    return [{"id": r["id"], "name": r["name"]} for r in rows]


@router.get("/{canvas_id}")
async def get_canvas(canvas_id: str, request: Request, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT * FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not rows:
        raise HTTPException(404, "Canvas not found")
    canvas = dict(rows[0])

    cross_currents = await db.execute_fetchall(
        """SELECT cc.id, cc.target_canvas_id, c.name AS target_name,
                  cc.relationship_description, cc.created_at
           FROM canvas_cross_currents cc
           JOIN canvas c ON c.id = cc.target_canvas_id
           WHERE cc.source_canvas_id = ?
           ORDER BY cc.created_at ASC""",
        (canvas_id,),
    )
    cross_currents = [dict(r) for r in cross_currents]

    invalidation_conditions = await db.execute_fetchall(
        "SELECT * FROM canvas_invalidation_conditions WHERE canvas_id = ?",
        (canvas_id,),
    )
    invalidation_conditions = [dict(r) for r in invalidation_conditions]

    version_history = await db.execute_fetchall(
        """SELECT id, timestamp, diff_summary
           FROM canvas_version_history
           WHERE canvas_id = ?
           ORDER BY timestamp DESC""",
        (canvas_id,),
    )
    version_history = [dict(r) for r in version_history]

    if not _wants_html(request):
        return {
            **canvas,
            "cross_currents": cross_currents,
            "invalidation_conditions": invalidation_conditions,
            "version_history": version_history,
        }

    # Compute staleness
    now = datetime.now(timezone.utc)
    try:
        last_reviewed = datetime.fromisoformat(canvas["last_reviewed"].replace("Z", "+00:00"))
        days_since_reviewed = (now - last_reviewed).days
    except (ValueError, TypeError, KeyError):
        days_since_reviewed = 0

    # Add days_since_assessed to invalidation conditions
    for ic in invalidation_conditions:
        try:
            last_assessed = datetime.fromisoformat(ic["last_assessed"].replace("Z", "+00:00"))
            ic["days_since_assessed"] = (now - last_assessed).days
        except (ValueError, TypeError, KeyError):
            ic["days_since_assessed"] = 0

    from api.config import settings
    return templates.TemplateResponse("canvas/detail.html", {
        "request": request,
        "canvas": canvas,
        "cross_currents": cross_currents,
        "invalidation_conditions": invalidation_conditions,
        "version_history": version_history,
        "days_since_reviewed": days_since_reviewed,
        "now_iso": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "library_configured": bool(settings.library_db_path),
    })


# ─── CANVAS PANEL (HTMX partial) ─────────────────────────────────────────────


@router.get("/{canvas_id}/panel")
async def canvas_panel(canvas_id: str, request: Request, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not rows:
        raise HTTPException(404, "Canvas not found")

    linked_theses = await db.execute_fetchall(
        """SELECT t.id, t.instrument, t.status
           FROM thesis t
           JOIN thesis_linked_canvases tlc ON t.id = tlc.thesis_id
           WHERE tlc.canvas_id = ?
           ORDER BY t.last_updated DESC""",
        (canvas_id,),
    )

    observation_backlinks = await db.execute_fetchall(
        """SELECT o.id, o.instrument, o.type, o.created_at
           FROM observation o
           JOIN observation_linked_canvases olc ON o.id = olc.observation_id
           WHERE olc.canvas_id = ?
           ORDER BY o.created_at DESC""",
        (canvas_id,),
    )

    cross_currents = await db.execute_fetchall(
        """SELECT cc.id, cc.target_canvas_id, c.name AS target_name,
                  cc.relationship_description
           FROM canvas_cross_currents cc
           JOIN canvas c ON c.id = cc.target_canvas_id
           WHERE cc.source_canvas_id = ?
           ORDER BY cc.created_at ASC""",
        (canvas_id,),
    )

    version_history = await db.execute_fetchall(
        """SELECT id, timestamp, diff_summary
           FROM canvas_version_history
           WHERE canvas_id = ?
           ORDER BY timestamp DESC""",
        (canvas_id,),
    )

    return templates.TemplateResponse("canvas/panel.html", {
        "request": request,
        "linked_theses": [dict(r) for r in linked_theses],
        "observation_backlinks": [dict(r) for r in observation_backlinks],
        "cross_currents": [dict(r) for r in cross_currents],
        "version_history": [dict(r) for r in version_history],
    })


# ─── CANVAS CONFIRM REVIEWED ─────────────────────────────────────────────────


@router.patch("/{canvas_id}/reviewed")
async def confirm_reviewed(canvas_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not rows:
        raise HTTPException(404, "Canvas not found")
    now = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
    await db.execute(f"UPDATE canvas SET last_reviewed = {now} WHERE id = ?", (canvas_id,))
    await db.commit()
    return {"status": "reviewed"}


# ─── CANVAS UPDATE (Protocol 1) ──────────────────────────────────────────────


@router.patch("/{canvas_id}")
async def update_canvas(
    canvas_id: str, payload: CanvasUpdate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not rows:
        raise HTTPException(404, "Canvas not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            """UPDATE canvas SET
                   narrative = ?,
                   last_reviewed = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
               WHERE id = ?""",
            (payload.narrative, canvas_id),
        )
        await db.execute(
            """INSERT INTO canvas_version_history (id, canvas_id, diff_summary)
               VALUES (?, ?, ?)""",
            (str(ULID()), canvas_id, payload.diff_summary),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    protocol_1 = await check_protocol1(db, canvas_id)
    protocol_2 = await check_protocol2(db)
    return {
        "canvas_id": canvas_id,
        "protocol_1": protocol_1,
        "protocol_2": protocol_2,
    }


# ─── CANVAS ARCHIVE ───────────────────────────────────────────────────────────


@router.patch("/{canvas_id}/archive")
async def archive_canvas(canvas_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT id, status FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not rows:
        raise HTTPException(404, "Canvas not found")
    canvas = rows[0]
    if canvas["status"] == "archived":
        raise HTTPException(400, "Canvas already archived")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "UPDATE canvas SET status = 'archived' WHERE id = ?", (canvas_id,)
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"canvas_id": canvas_id, "status": "archived"}


# ─── CROSS-CURRENTS ──────────────────────────────────────────────────────────


@router.post("/{canvas_id}/cross-currents")
async def add_cross_current(
    canvas_id: str, payload: CrossCurrentPayload, db=Depends(get_db)
):
    if canvas_id == payload.target_canvas_id:
        raise HTTPException(400, "Cannot link a canvas to itself")
    src = await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not src:
        raise HTTPException(404, "Source canvas not found")
    tgt = await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (payload.target_canvas_id,)
    )
    if not tgt:
        raise HTTPException(404, "Target canvas not found")

    cc_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO canvas_cross_currents
                   (id, source_canvas_id, target_canvas_id, relationship_description)
               VALUES (?, ?, ?, ?)""",
            (cc_id, canvas_id, payload.target_canvas_id, payload.relationship_description),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": cc_id}


@router.delete("/{canvas_id}/cross-currents/{target_canvas_id}")
async def remove_cross_current(
    canvas_id: str, target_canvas_id: str, db=Depends(get_db)
):
    await db.execute(
        """DELETE FROM canvas_cross_currents
           WHERE source_canvas_id = ? AND target_canvas_id = ?""",
        (canvas_id, target_canvas_id),
    )
    await db.commit()
    return {"deleted": True}


@router.get("/{canvas_id}/cross-currents")
async def list_cross_currents(canvas_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        """SELECT cc.id, cc.target_canvas_id, c.name AS target_name,
                  cc.relationship_description, cc.created_at
           FROM canvas_cross_currents cc
           JOIN canvas c ON c.id = cc.target_canvas_id
           WHERE cc.source_canvas_id = ?
           ORDER BY cc.created_at ASC""",
        (canvas_id,),
    )
    return {"cross_currents": [dict(r) for r in rows]}


# ─── INVALIDATION CONDITIONS ─────────────────────────────────────────────────


@router.post("/{canvas_id}/invalidation-conditions")
async def add_invalidation_condition(
    canvas_id: str, payload: InvalidationConditionCreate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not rows:
        raise HTTPException(404, "Canvas not found")

    cond_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO canvas_invalidation_conditions
                   (id, canvas_id, condition, type, probability,
                    lead_time_days, last_assessed)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                cond_id,
                canvas_id,
                payload.condition,
                payload.type,
                payload.probability,
                payload.lead_time_days,
                payload.last_assessed,
            ),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": cond_id}


@router.get("/{canvas_id}/invalidation-conditions")
async def list_invalidation_conditions(canvas_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        """SELECT * FROM canvas_invalidation_conditions
           WHERE canvas_id = ?
           ORDER BY created_at ASC""",
        (canvas_id,),
    )
    return {"invalidation_conditions": [dict(r) for r in rows]}


@router.patch("/{canvas_id}/invalidation-conditions/{condition_id}")
async def update_invalidation_condition(
    canvas_id: str,
    condition_id: str,
    payload: InvalidationConditionPatch,
    db=Depends(get_db),
):
    rows = await db.execute_fetchall(
        "SELECT id FROM canvas_invalidation_conditions WHERE id = ? AND canvas_id = ?",
        (condition_id, canvas_id),
    )
    if not rows:
        raise HTTPException(404, "Invalidation condition not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            """UPDATE canvas_invalidation_conditions
               SET last_assessed = ?
               WHERE id = ?""",
            (payload.last_assessed, condition_id),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": condition_id, "last_assessed": payload.last_assessed}


# ─── SOURCE DOCUMENT ROUTES ───────────────────────────────────────────────────


@router.post("/{canvas_id}/sources")
async def link_source(canvas_id: str, request: Request, db=Depends(get_db)):
    if not settings.library_db_path:
        raise HTTPException(503, "Library integration is not configured")

    body = await request.json()
    library_document_id = body.get("library_document_id")
    note = body.get("note", "")

    if not library_document_id:
        raise HTTPException(400, "library_document_id is required")

    # Validate canvas exists
    canvas_rows = await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not canvas_rows:
        raise HTTPException(404, "Canvas not found")

    # Validate document exists in library
    try:
        async with get_library_db() as lib:
            doc_rows = await lib.execute_fetchall(
                "SELECT id FROM documents WHERE id = ?",
                (library_document_id,),
            )
            if not doc_rows:
                raise HTTPException(404, "Document not found in library")
    except RuntimeError:
        raise HTTPException(503, "Library integration is not configured")

    from datetime import datetime, timezone
    linked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT OR IGNORE INTO canvas_source_documents
                   (canvas_id, library_document_id, note, linked_at)
               VALUES (?, ?, ?, ?)""",
            (canvas_id, library_document_id, note, linked_at),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"canvas_id": canvas_id, "library_document_id": library_document_id}


@router.delete("/{canvas_id}/sources/{library_document_id}")
async def unlink_source(canvas_id: str, library_document_id: str, db=Depends(get_db)):
    await db.execute("BEGIN")
    try:
        await db.execute(
            """DELETE FROM canvas_source_documents
               WHERE canvas_id = ? AND library_document_id = ?""",
            (canvas_id, library_document_id),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"status": "unlinked"}


@router.get("/{canvas_id}/sources")
async def list_sources(canvas_id: str, db=Depends(get_db)):
    if not settings.library_db_path:
        raise HTTPException(503, "Library integration is not configured")

    links = await db.execute_fetchall(
        """SELECT csd.library_document_id, csd.note, csd.linked_at
           FROM canvas_source_documents csd
           WHERE csd.canvas_id = ?
           ORDER BY csd.linked_at DESC""",
        (canvas_id,),
    )

    result = []
    try:
        async with get_library_db() as lib:
            for link in links:
                doc = dict(link)
                doc_rows = await lib.execute_fetchall(
                    "SELECT title, authors, year FROM documents WHERE id = ?",
                    (link["library_document_id"],),
                )
                if doc_rows:
                    meta = dict(doc_rows[0])
                    doc["title"] = meta.get("title", "")
                    doc["authors"] = meta.get("authors", "")
                    doc["year"] = meta.get("year", "")
                result.append(doc)
    except RuntimeError:
        raise HTTPException(503, "Library integration is not configured")

    return {"sources": result}


@router.get("/library-search")
async def library_search(q: str = ""):
    if not settings.library_db_path:
        raise HTTPException(503, "Library integration is not configured")

    q = q.strip()
    if len(q) < 2:
        raise HTTPException(400, "Query must be at least 2 characters")

    try:
        async with get_library_db() as lib:
            rows = await lib.execute_fetchall(
                """SELECT id, title, authors, year
                   FROM documents
                   WHERE title LIKE ? OR authors LIKE ?
                   LIMIT 20""",
                (f"%{q}%", f"%{q}%"),
            )
    except RuntimeError:
        raise HTTPException(503, "Library integration is not configured")

    return [{"id": r["id"], "title": r["title"], "authors": r.get("authors", ""), "year": r.get("year", "")} for r in rows]
