from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db
from api.models.observation import ObservationCreate

router = APIRouter()

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


# ─── OBSERVATION CREATE ────────────────────────────────────────────────────────


@router.post("")
async def create_observation(payload: ObservationCreate, db=Depends(get_db)):
    obs_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO observation
                   (id, date, instrument, timeframe, type, observation, linked_thesis_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (obs_id, payload.date, payload.instrument, payload.timeframe,
             payload.type, payload.observation, payload.linked_thesis_id),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": obs_id}


# ─── OBSERVATION READ ──────────────────────────────────────────────────────────


@router.get("/new")
async def observation_form(request: Request):
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse("observation/form.html", {
        "request": request,
        "now_date": now.strftime("%Y-%m-%d"),
    })


@router.get("/{observation_id}")
async def get_observation(observation_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT * FROM observation WHERE id = ?", (observation_id,)
    )
    if not rows:
        raise HTTPException(404, "Observation not found")
    observation = dict(rows[0])

    linked_canvases = await db.execute_fetchall(
        """SELECT olc.canvas_id, c.name, c.status, olc.created_at
           FROM observation_linked_canvases olc
           JOIN canvas c ON c.id = olc.canvas_id
           WHERE olc.observation_id = ?
           ORDER BY olc.created_at ASC""",
        (observation_id,),
    )

    images = await db.execute_fetchall(
        "SELECT * FROM observation_images WHERE observation_id = ? ORDER BY created_at ASC",
        (observation_id,),
    )

    return {
        **observation,
        "linked_canvases": [dict(r) for r in linked_canvases],
        "images": [dict(r) for r in images],
    }


# ─── OBSERVATION ↔ CANVAS LINKS ───────────────────────────────────────────────


@router.post("/{observation_id}/link-canvas/{canvas_id}")
async def link_canvas_to_observation(
    observation_id: str, canvas_id: str, db=Depends(get_db)
):
    obs_rows = await db.execute_fetchall(
        "SELECT id FROM observation WHERE id = ?", (observation_id,)
    )
    if not obs_rows:
        raise HTTPException(404, "Observation not found")
    canvas_rows = await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not canvas_rows:
        raise HTTPException(404, "Canvas not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "INSERT INTO observation_linked_canvases (observation_id, canvas_id) VALUES (?, ?)",
            (observation_id, canvas_id),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Canvas already linked to this observation")
    except Exception:
        await db.rollback()
        raise
    return {"observation_id": observation_id, "canvas_id": canvas_id}
