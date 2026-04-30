from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db
from api.models.setup import SetupCreate, SetupStatusTransition

router = APIRouter()

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


# ─── SETUP CRUD ───────────────────────────────────────────────────────────────


@router.post("")
async def create_setup(payload: SetupCreate, db=Depends(get_db)):
    setup_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO setup (id, instrument, setup_type, note, date)
               VALUES (?, ?, ?, ?, ?)""",
            (setup_id, payload.instrument, payload.setup_type, payload.note, payload.date),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": setup_id}


@router.get("/{setup_id}")
async def get_setup(setup_id: str, request: Request, db=Depends(get_db)):
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

    linked_observations = await db.execute_fetchall(
        """SELECT sol.observation_id, o.instrument AS obs_instrument,
                  o.type AS obs_type, o.observation, sol.created_at
           FROM setup_observation_links sol
           JOIN observation o ON o.id = sol.observation_id
           WHERE sol.setup_id = ?
           ORDER BY sol.created_at ASC""",
        (setup_id,),
    )

    images = await db.execute_fetchall(
        "SELECT * FROM setup_images WHERE setup_id = ? ORDER BY created_at ASC",
        (setup_id,),
    )

    accept = request.headers.get("accept", "")
    wants_html = "text/html" in accept and not request.headers.get("hx-request")

    if not wants_html:
        return {
            **setup,
            "linked_theses": [dict(r) for r in linked_theses],
            "linked_observations": [dict(r) for r in linked_observations],
            "images": [dict(r) for r in images],
        }

    return templates.TemplateResponse("setup/detail.html", {
        "request": request,
        "setup": setup,
        "linked_theses": [dict(r) for r in linked_theses],
        "linked_observations": [dict(r) for r in linked_observations],
        "images": [dict(r) for r in images],
    })


# ─── SETUP STATE TRANSITIONS ─────────────────────────────────────────────────


@router.patch("/{setup_id}/status")
async def transition_setup_status(
    setup_id: str, payload: SetupStatusTransition, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id, status FROM setup WHERE id = ?", (setup_id,)
    )
    if not rows:
        raise HTTPException(404, "Setup not found")

    await db.execute("BEGIN")
    try:
        if payload.status == "passed":
            await db.execute(
                """UPDATE setup SET status = ?, passed_reason = ?, passed_reason_type = ?
                   WHERE id = ?""",
                (payload.status, payload.passed_reason, payload.passed_reason_type, setup_id),
            )
        else:
            await db.execute(
                "UPDATE setup SET status = ? WHERE id = ?",
                (payload.status, setup_id),
            )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, detail=str(e))
    except Exception:
        await db.rollback()
        raise

    updated = await db.execute_fetchall(
        "SELECT status FROM setup WHERE id = ?", (setup_id,)
    )
    return {"setup_id": setup_id, "status": dict(updated[0])["status"]}


# ─── SETUP ↔ THESIS LINKS ────────────────────────────────────────────────────


@router.post("/{setup_id}/link-thesis/{thesis_id}")
async def link_thesis_to_setup(
    setup_id: str, thesis_id: str, db=Depends(get_db)
):
    setup_rows = await db.execute_fetchall(
        "SELECT id FROM setup WHERE id = ?", (setup_id,)
    )
    if not setup_rows:
        raise HTTPException(404, "Setup not found")
    thesis_rows = await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not thesis_rows:
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


# ─── SETUP ↔ OBSERVATION LINKS ───────────────────────────────────────────────


@router.post("/{setup_id}/link-observation/{observation_id}")
async def link_observation_to_setup(
    setup_id: str, observation_id: str, db=Depends(get_db)
):
    setup_rows = await db.execute_fetchall(
        "SELECT id FROM setup WHERE id = ?", (setup_id,)
    )
    if not setup_rows:
        raise HTTPException(404, "Setup not found")
    obs_rows = await db.execute_fetchall(
        "SELECT id FROM observation WHERE id = ?", (observation_id,)
    )
    if not obs_rows:
        raise HTTPException(404, "Observation not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "INSERT INTO setup_observation_links (setup_id, observation_id) VALUES (?, ?)",
            (setup_id, observation_id),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Observation already linked to this setup")
    except Exception:
        await db.rollback()
        raise
    return {"setup_id": setup_id, "observation_id": observation_id}
