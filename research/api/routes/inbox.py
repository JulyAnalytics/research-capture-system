from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db

router = APIRouter()


class InboxCapture(BaseModel):
    raw_text: str


class InboxRoute(BaseModel):
    route_type: str  # observation, action, setup, thesis-update
    # observation fields
    date: Optional[str] = None
    instrument: Optional[str] = None
    timeframe: Optional[str] = None
    type: Optional[str] = None
    observation: Optional[str] = None
    linked_canvas_id: Optional[str] = None
    linked_thesis_id: Optional[str] = None
    # action fields
    action: Optional[str] = None
    due_date: Optional[str] = None
    linked_setup_id: Optional[str] = None
    # setup fields
    setup_type: Optional[str] = None
    note: Optional[str] = None
    # thesis-update fields
    thesis_id: Optional[str] = None
    diff_summary: Optional[str] = None
    narrative: Optional[str] = None


@router.post("")
async def capture(payload: InboxCapture, db=Depends(get_db)):
    item_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            "INSERT INTO inbox (id, raw_text) VALUES (?, ?)",
            (item_id, payload.raw_text),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": item_id}


@router.get("")
async def list_inbox(db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT * FROM inbox WHERE routed_at IS NULL ORDER BY created_at ASC"
    )
    return {"items": [dict(r) for r in rows]}


@router.get("/{item_id}")
async def get_inbox_item(item_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall("SELECT * FROM inbox WHERE id = ?", (item_id,))
    if not rows:
        raise HTTPException(404, "Inbox item not found")
    return dict(rows[0])


@router.post("/{item_id}/route")
async def route_item(item_id: str, payload: InboxRoute, db=Depends(get_db)):
    rows = await db.execute_fetchall("SELECT * FROM inbox WHERE id = ?", (item_id,))
    if not rows:
        raise HTTPException(404, "Inbox item not found")

    routed_col = None
    created_id = None

    await db.execute("BEGIN")
    try:
        if payload.route_type == "observation":
            created_id = str(ULID())
            await db.execute(
                """INSERT INTO observation
                       (id, date, instrument, timeframe, type, observation, linked_thesis_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (created_id, payload.date, payload.instrument, payload.timeframe,
                 payload.type, payload.observation, payload.linked_thesis_id),
            )
            if payload.linked_canvas_id:
                await db.execute(
                    """INSERT OR IGNORE INTO observation_linked_canvases
                           (observation_id, canvas_id)
                       VALUES (?, ?)""",
                    (created_id, payload.linked_canvas_id),
                )
            routed_col = "routed_to_observation_id"

        elif payload.route_type == "action":
            created_id = str(ULID())
            await db.execute(
                """INSERT INTO action
                       (id, instrument, action, due_date, linked_thesis_id, linked_setup_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (created_id, payload.instrument, payload.action, payload.due_date,
                 payload.linked_thesis_id, payload.linked_setup_id),
            )
            routed_col = "routed_to_action_id"

        elif payload.route_type == "setup":
            created_id = str(ULID())
            await db.execute(
                """INSERT INTO setup (id, instrument, setup_type, note, date)
                   VALUES (?, ?, ?, ?, ?)""",
                (created_id, payload.instrument, payload.setup_type, payload.note, payload.date),
            )
            if payload.linked_thesis_id:
                await db.execute(
                    """INSERT OR IGNORE INTO setup_thesis_links (setup_id, thesis_id)
                       VALUES (?, ?)""",
                    (created_id, payload.linked_thesis_id),
                )
            routed_col = "routed_to_setup_id"

        elif payload.route_type == "thesis-update":
            if not payload.thesis_id:
                raise HTTPException(400, "thesis_id required for thesis-update")
            thesis_rows = await db.execute_fetchall(
                "SELECT id FROM thesis WHERE id = ?", (payload.thesis_id,)
            )
            if not thesis_rows:
                raise HTTPException(404, "Thesis not found")
            created_id = payload.thesis_id
            routed_col = "routed_to_thesis_id"

        else:
            raise HTTPException(400, f"Unknown route_type: {payload.route_type}")

        await db.execute(
            f"UPDATE inbox SET {routed_col} = ?, routed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            (created_id, item_id),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    return {"routed_to": created_id, "route_type": payload.route_type}
