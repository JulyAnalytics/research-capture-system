from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db
from api.models.setup import SetupCreate

router = APIRouter()
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


@router.get("/new")
async def setup_new(request: Request, db=Depends(get_db)):
    """
    Render the setup creation form.
    Passes thesis and canvas lists for optional linking at creation time.
    """
    theses = await db.execute_fetchall(
        "SELECT id, instrument, status FROM thesis "
        "WHERE status IN ('building','ready','active') ORDER BY instrument ASC"
    )
    canvases = await db.execute_fetchall(
        "SELECT id, name FROM canvas ORDER BY last_reviewed DESC LIMIT 20"
    )
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse("setup/new.html", {
        "request": request,
        "theses": [dict(r) for r in theses],
        "canvases": [dict(r) for r in canvases],
        "now_date": now.strftime("%Y-%m-%d"),
        "prefill_name": request.query_params.get("title", ""),
    })


@router.post("")
async def create_setup(payload: SetupCreate, db=Depends(get_db)):
    """
    Create a setup (append-only after creation — no update routes exist).

    Args:
        payload: SetupCreate
        db:      aiosqlite connection

    Returns: {id: str}

    Side effects: inserts setup row; trigger logs to entity_events.
    """
    setup_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO setup (id, name, instrument, type, timeframe, setup_note, date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (setup_id, payload.name, payload.instrument, payload.type,
             payload.timeframe, payload.setup_note, payload.date),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": setup_id}


@router.get("/{setup_id}")
async def get_setup(setup_id: str, request: Request, db=Depends(get_db)):
    """
    Fetch setup with linked theses, linked canvases, and images.
    Returns JSON unless Accept: text/html.
    """
    rows = await db.execute_fetchall(
        "SELECT * FROM setup WHERE id = ?", (setup_id,)
    )
    if not rows:
        raise HTTPException(404, "Setup not found")
    setup = dict(rows[0])

    linked_theses = await db.execute_fetchall(
        """SELECT stl.thesis_id, t.instrument, t.status, stl.created_at
           FROM setup_thesis_links stl
           JOIN thesis t ON t.id = stl.thesis_id
           WHERE stl.setup_id = ?
           ORDER BY stl.created_at ASC""",
        (setup_id,),
    )

    linked_canvases = await db.execute_fetchall(
        """SELECT slc.canvas_id, c.name, c.status, slc.created_at
           FROM setup_linked_canvases slc
           JOIN canvas c ON c.id = slc.canvas_id
           WHERE slc.setup_id = ?
           ORDER BY slc.created_at ASC""",
        (setup_id,),
    )

    images = await db.execute_fetchall(
        "SELECT * FROM setup_images WHERE setup_id = ? ORDER BY created_at ASC",
        (setup_id,),
    )

    wants_html = (
        "text/html" in request.headers.get("accept", "")
        and not request.headers.get("hx-request")
    )

    data = {
        **setup,
        "linked_theses": [dict(r) for r in linked_theses],
        "linked_canvases": [dict(r) for r in linked_canvases],
        "images": [dict(r) for r in images],
    }

    if not wants_html:
        return data

    return templates.TemplateResponse("setup/detail.html", {
        "request": request,
        "setup": setup,
        "linked_theses": [dict(r) for r in linked_theses],
        "linked_canvases": [dict(r) for r in linked_canvases],
        "images": [dict(r) for r in images],
    })


@router.post("/{setup_id}/link-thesis/{thesis_id}")
async def link_thesis_to_setup(
    setup_id: str, thesis_id: str, db=Depends(get_db)
):
    """Link a setup to a thesis via setup_thesis_links (many-to-many)."""
    if not await db.execute_fetchall(
        "SELECT id FROM setup WHERE id = ?", (setup_id,)
    ):
        raise HTTPException(404, "Setup not found")
    if not await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    ):
        raise HTTPException(404, "Thesis not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?, ?)",
            (setup_id, thesis_id),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Thesis already linked to this setup")
    except Exception:
        await db.rollback()
        raise
    return {"setup_id": setup_id, "thesis_id": thesis_id}


@router.post("/{setup_id}/link-canvas/{canvas_id}")
async def link_canvas_to_setup(
    setup_id: str, canvas_id: str, db=Depends(get_db)
):
    """Link a setup to a canvas via setup_linked_canvases."""
    if not await db.execute_fetchall(
        "SELECT id FROM setup WHERE id = ?", (setup_id,)
    ):
        raise HTTPException(404, "Setup not found")
    if not await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (canvas_id,)
    ):
        raise HTTPException(404, "Canvas not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "INSERT INTO setup_linked_canvases (setup_id, canvas_id) VALUES (?, ?)",
            (setup_id, canvas_id),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Canvas already linked to this setup")
    except Exception:
        await db.rollback()
        raise
    return {"setup_id": setup_id, "canvas_id": canvas_id}
