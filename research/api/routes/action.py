from fastapi import APIRouter, Depends, HTTPException
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db
from api.models.action import ActionCreate, ActionCancel

router = APIRouter()


# ─── ACTION CRUD ───────────────────────────────────────────────────────────────


@router.post("")
async def create_action(payload: ActionCreate, db=Depends(get_db)):
    action_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO action
                   (id, instrument, action, due_date, linked_thesis_id, linked_setup_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (action_id, payload.instrument, payload.action, payload.due_date,
             payload.linked_thesis_id, payload.linked_setup_id),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": action_id}


@router.get("/{action_id}")
async def get_action(action_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT * FROM action WHERE id = ?", (action_id,)
    )
    if not rows:
        raise HTTPException(404, "Action not found")
    return dict(rows[0])


@router.patch("/{action_id}/done")
async def mark_done(action_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT id, status FROM action WHERE id = ?", (action_id,)
    )
    if not rows:
        raise HTTPException(404, "Action not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "UPDATE action SET status = 'done' WHERE id = ?", (action_id,)
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": action_id, "status": "done"}


@router.patch("/{action_id}/cancel")
async def cancel_action(
    action_id: str, payload: ActionCancel, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id, status FROM action WHERE id = ?", (action_id,)
    )
    if not rows:
        raise HTTPException(404, "Action not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            """UPDATE action SET status = 'cancelled', cancellation_note = ?
               WHERE id = ?""",
            (payload.cancellation_note, action_id),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": action_id, "status": "cancelled"}
