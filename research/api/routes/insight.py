from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db
from api.models.insight import InsightCreate

router = APIRouter()

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))

# DECISION: linked_entity_type is validated against this set at the route layer.
# The DB has no FK enforcement on the polymorphic link — see insight migration
# header for full rationale.
# Map entity type to its table name for existence checks.
# DECISION: VALID_ENTITY_TYPES is derived from this dict's keys — single
# authoritative list. Adding a new linkable entity type requires only
# updating _ENTITY_TABLE here. Do not define VALID_ENTITY_TYPES separately.
_ENTITY_TABLE: dict[str, str] = {
    'canvas':      'canvas',
    'thesis':      'thesis',
    'observation': 'observation',
    'setup':       'setup',
    'trade':       'trade',
    'review':      'review',
}

VALID_ENTITY_TYPES = set(_ENTITY_TABLE.keys())


@router.get("/new")
async def insight_new(request: Request, db=Depends(get_db)):
    """
    Render the insight creation form.

    Passes lists for optional entity linking at creation time.
    All list fetches are lightweight (instrument/name + id only).

    Args:
        request: FastAPI Request.
        db:      aiosqlite connection.

    Returns: TemplateResponse for insight/new.html.

    Side effects: none — read-only route.
    """
    canvases = await db.execute_fetchall(
        "SELECT id, name FROM canvas WHERE status = 'active' ORDER BY last_reviewed DESC LIMIT 20"
    )
    theses = await db.execute_fetchall(
        "SELECT id, instrument, status FROM thesis "
        "WHERE status IN ('building','ready','active') ORDER BY instrument ASC"
    )
    trades = await db.execute_fetchall(
        "SELECT id, name, instrument_type, status FROM trade "
        "WHERE status IN ('idea','active') ORDER BY created_at DESC LIMIT 20"
    )
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse("insight/new.html", {
        "request": request,
        "canvases": [dict(r) for r in canvases],
        "theses": [dict(r) for r in theses],
        "trades": [dict(r) for r in trades],
        "now_date": now.strftime("%Y-%m-%d"),
        "prefill_name": request.query_params.get("title", ""),
        "valid_entity_types": sorted(VALID_ENTITY_TYPES),
    })


@router.post("")
async def create_insight(payload: InsightCreate, db=Depends(get_db)):
    """
    Create an insight.

    If linked_entity_type and linked_entity_id are provided, verifies the
    target entity exists before writing the link. Returns 400 if the entity
    type is not in VALID_ENTITY_TYPES. Returns 404 if the entity does not
    exist. The DB does not enforce this — this is the sole enforcement point.

    Args:
        payload: InsightCreate
        db:      aiosqlite connection

    Returns: {id: str}

    Side effects: inserts insight row; event_insight_created trigger logs
                  to entity_events.
    """
    if payload.linked_entity_type is not None:
        if payload.linked_entity_type not in VALID_ENTITY_TYPES:
            raise HTTPException(
                400,
                f"linked_entity_type must be one of: "
                f"{', '.join(sorted(VALID_ENTITY_TYPES))}"
            )
        table = _ENTITY_TABLE[payload.linked_entity_type]
        rows = await db.execute_fetchall(
            f"SELECT id FROM {table} WHERE id = ?",
            (payload.linked_entity_id,)
        )
        if not rows:
            raise HTTPException(
                404,
                f"{payload.linked_entity_type} '{payload.linked_entity_id}' not found"
            )

    insight_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO insight
                   (id, name, note, linked_entity_type, linked_entity_id, context_tag)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (insight_id, payload.name, payload.note,
             payload.linked_entity_type, payload.linked_entity_id,
             payload.context_tag),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": insight_id}


@router.get("/{insight_id}")
async def get_insight(insight_id: str, request: Request, db=Depends(get_db)):
    """
    Fetch a single insight. Returns JSON unless Accept: text/html.

    Args:
        insight_id: ULID of the insight.
        request:    FastAPI Request.
        db:         aiosqlite connection.

    Returns: insight dict or TemplateResponse.

    Side effects: none — read-only.
    """
    rows = await db.execute_fetchall(
        "SELECT * FROM insight WHERE id = ?", (insight_id,)
    )
    if not rows:
        raise HTTPException(404, "Insight not found")
    insight = dict(rows[0])

    # Resolve linked entity display name if link exists
    linked_entity = None
    if insight.get("linked_entity_type") and insight.get("linked_entity_id"):
        table = _ENTITY_TABLE.get(insight["linked_entity_type"])
        if table:
            name_col = "instrument" if insight["linked_entity_type"] in \
                       ("thesis", "trade") else "name"
            entity_rows = await db.execute_fetchall(
                f"SELECT id, {name_col} AS display_name FROM {table} WHERE id = ?",
                (insight["linked_entity_id"],)
            )
            if entity_rows:
                linked_entity = dict(entity_rows[0])

    wants_html = (
        "text/html" in request.headers.get("accept", "")
        and not request.headers.get("hx-request")
    )

    data = {**insight, "linked_entity": linked_entity}

    if not wants_html:
        return data

    return templates.TemplateResponse("insight/detail.html", {
        "request": request,
        "insight": insight,
        "linked_entity": linked_entity,
    })
