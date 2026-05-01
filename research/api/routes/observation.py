from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db
from api.models.observation import ObservationCreate, ObservationStatusTransition

router = APIRouter()
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


@router.get("/new")
async def observation_new(request: Request, db=Depends(get_db)):
    """
    Render the observation creation form.
    Passes thesis list for optional thesis linking at creation time.
    """
    theses = await db.execute_fetchall(
        "SELECT id, instrument, status FROM thesis WHERE status IN ('building','ready','active') "
        "ORDER BY instrument ASC"
    )
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse("observation/new.html", {
        "request": request,
        "theses": [dict(r) for r in theses],
        "now_date": now.strftime("%Y-%m-%d"),
        "prefill_name": request.query_params.get("title", ""),
    })


@router.post("")
async def create_observation(payload: ObservationCreate, db=Depends(get_db)):
    """
    Create an observation in 'watching' status.

    Args:
        payload: ObservationCreate
        db:      aiosqlite connection

    Returns: {id: str}

    Side effects: inserts observation row; trigger logs to entity_events.
    """
    obs_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO observation (id, name, instrument, note, date)
               VALUES (?, ?, ?, ?, ?)""",
            (obs_id, payload.name, payload.instrument, payload.note, payload.date),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": obs_id}


@router.get("/{observation_id}")
async def get_observation(observation_id: str, request: Request, db=Depends(get_db)):
    """
    Fetch observation with linked theses and linked setups.
    Returns JSON unless Accept: text/html, in which case renders detail template.
    """
    rows = await db.execute_fetchall(
        "SELECT * FROM observation WHERE id = ?", (observation_id,)
    )
    if not rows:
        raise HTTPException(404, "Observation not found")
    observation = dict(rows[0])

    linked_theses = await db.execute_fetchall(
        """SELECT otl.thesis_id, t.instrument, t.status, otl.created_at
           FROM observation_thesis_links otl
           JOIN thesis t ON t.id = otl.thesis_id
           WHERE otl.observation_id = ?
           ORDER BY otl.created_at ASC""",
        (observation_id,),
    )

    linked_setups = await db.execute_fetchall(
        """SELECT osl.setup_id, s.name, s.instrument, s.type, osl.created_at
           FROM observation_setup_links osl
           JOIN setup s ON s.id = osl.setup_id
           WHERE osl.observation_id = ?
           ORDER BY osl.created_at ASC""",
        (observation_id,),
    )

    wants_html = (
        "text/html" in request.headers.get("accept", "")
        and not request.headers.get("hx-request")
    )

    data = {
        **observation,
        "linked_theses": [dict(r) for r in linked_theses],
        "linked_setups": [dict(r) for r in linked_setups],
    }

    if not wants_html:
        return data

    all_theses = await db.execute_fetchall(
        "SELECT id, instrument, status FROM thesis "
        "WHERE status IN ('building','ready','active') ORDER BY instrument ASC"
    )
    all_setups = await db.execute_fetchall(
        "SELECT id, name, instrument FROM setup ORDER BY date DESC LIMIT 50"
    )

    return templates.TemplateResponse("observation/detail.html", {
        "request": request,
        "observation": observation,
        "linked_theses": [dict(r) for r in linked_theses],
        "linked_setups": [dict(r) for r in linked_setups],
        "all_theses": [dict(r) for r in all_theses],
        "all_setups": [dict(r) for r in all_setups],
    })


@router.patch("/{observation_id}/status")
async def transition_observation_status(
    observation_id: str,
    payload: ObservationStatusTransition,
    db=Depends(get_db),
):
    """
    Transition observation: watching → taken or passed.
    DB triggers enforce the gate conditions. IntegrityError → 400.

    Args:
        observation_id: ULID of the observation.
        payload:        ObservationStatusTransition
        db:             aiosqlite connection

    Returns: {observation_id: str, status: str}
    """
    rows = await db.execute_fetchall(
        "SELECT id, status FROM observation WHERE id = ?", (observation_id,)
    )
    if not rows:
        raise HTTPException(404, "Observation not found")

    await db.execute("BEGIN")
    try:
        if payload.status == "passed":
            await db.execute(
                """UPDATE observation
                   SET status = ?, passed_reason = ?, passed_reason_type = ?
                   WHERE id = ?""",
                (payload.status, payload.passed_reason,
                 payload.passed_reason_type, observation_id),
            )
        else:
            await db.execute(
                "UPDATE observation SET status = ? WHERE id = ?",
                (payload.status, observation_id),
            )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise

    updated = await db.execute_fetchall(
        "SELECT status FROM observation WHERE id = ?", (observation_id,)
    )
    return {"observation_id": observation_id, "status": dict(updated[0])["status"]}


@router.post("/{observation_id}/link-thesis/{thesis_id}")
async def link_thesis_to_observation(
    observation_id: str, thesis_id: str, db=Depends(get_db)
):
    """
    Link an observation to a thesis via observation_thesis_links.
    observation_taken_gate requires at least one linked thesis before
    the observation can be taken.
    """
    if not await db.execute_fetchall(
        "SELECT id FROM observation WHERE id = ?", (observation_id,)
    ):
        raise HTTPException(404, "Observation not found")
    if not await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    ):
        raise HTTPException(404, "Thesis not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "INSERT INTO observation_thesis_links (observation_id, thesis_id) VALUES (?, ?)",
            (observation_id, thesis_id),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Thesis already linked to this observation")
    except Exception:
        await db.rollback()
        raise
    return {"observation_id": observation_id, "thesis_id": thesis_id}


@router.post("/{observation_id}/link-setup/{setup_id}")
async def link_setup_to_observation(
    observation_id: str, setup_id: str, db=Depends(get_db)
):
    """
    Link an observation to a setup via observation_setup_links.
    Direction: observation led to this setup (observation → setup).
    """
    if not await db.execute_fetchall(
        "SELECT id FROM observation WHERE id = ?", (observation_id,)
    ):
        raise HTTPException(404, "Observation not found")
    if not await db.execute_fetchall(
        "SELECT id FROM setup WHERE id = ?", (setup_id,)
    ):
        raise HTTPException(404, "Setup not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "INSERT INTO observation_setup_links (observation_id, setup_id) VALUES (?, ?)",
            (observation_id, setup_id),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Setup already linked to this observation")
    except Exception:
        await db.rollback()
        raise
    return {"observation_id": observation_id, "setup_id": setup_id}
