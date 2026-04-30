from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db
from api.models.review import ReviewCreate, Phase2Payload

router = APIRouter()

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))

ZONE3_LOCK_HOURS = 24


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and not request.headers.get("hx-request")


# ─── REVIEW PHASE 1 ────────────────────────────────────────────────────────────


@router.post("")
async def create_review(payload: ReviewCreate, db=Depends(get_db)):
    trade_rows = await db.execute_fetchall(
        "SELECT id FROM trade WHERE id = ?", (payload.trade_id,)
    )
    if not trade_rows:
        raise HTTPException(404, "Trade not found")

    review_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO review (
                   id, trade_id, closed_at, entry_fill, exit_fill,
                   thesis_at_entry, exit_rules_as_written,
                   what_i_actually_did, emotional_state, rules_followed
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (review_id, payload.trade_id, payload.closed_at,
             payload.entry_fill, payload.exit_fill,
             payload.thesis_at_entry, payload.exit_rules_as_written,
             payload.what_i_actually_did, payload.emotional_state,
             payload.rules_followed),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise

    return {"id": review_id}


# ─── REVIEW NEW (Phase 1 form) ────────────────────────────────────────────────


@router.get("/new")
async def new_review(request: Request, trade_id: str = "", db=Depends(get_db)):
    if not trade_id:
        raise HTTPException(400, "trade_id is required")

    trade_rows = await db.execute_fetchall(
        """SELECT t.*, th.instrument AS thesis_instrument, th.narrative AS thesis_narrative
           FROM trade t
           LEFT JOIN thesis th ON th.id = t.thesis_id
           WHERE t.id = ?""",
        (trade_id,),
    )
    if not trade_rows:
        raise HTTPException(404, "Trade not found")

    trade = dict(trade_rows[0])
    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return templates.TemplateResponse("review/phase1_new.html", {
        "request": request,
        "trade": trade,
        "now_date": now_date,
    })


# ─── REVIEW READ ───────────────────────────────────────────────────────────────


@router.get("/{review_id}")
async def get_review(review_id: str, request: Request, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT * FROM review WHERE id = ?", (review_id,)
    )
    if not rows:
        raise HTTPException(404, "Review not found")

    review = dict(rows[0])

    if _wants_html(request):
        # Get trade info for breadcrumb
        trade_rows = await db.execute_fetchall(
            """SELECT t.id, t.instrument_type, t.status, t.thesis_id,
                      th.instrument AS thesis_instrument
               FROM trade t
               LEFT JOIN thesis th ON th.id = t.thesis_id
               WHERE t.id = ?""",
            (review["trade_id"],),
        )
        trade = dict(trade_rows[0]) if trade_rows else {}

        # Compute Zone 3 timing
        zone3_remaining_seconds = 0
        zone3_countdown = ""
        if review.get("zone_3_clear") != 1 and review.get("locked_at"):
            try:
                locked_at = datetime.fromisoformat(
                    review["locked_at"].replace("Z", "+00:00")
                ).replace(tzinfo=None)
                now = datetime.utcnow()
                elapsed = now - locked_at
                required = timedelta(hours=ZONE3_LOCK_HOURS)
                if elapsed < required:
                    remaining = required - elapsed
                    zone3_remaining_seconds = int(remaining.total_seconds())
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    zone3_countdown = f"{hours}h {minutes}m"
            except (ValueError, TypeError):
                pass

        trade_id_short = (review["trade_id"] or "")[:8]

        return templates.TemplateResponse("review/phase1.html", {
            "request": request,
            "review": review,
            "trade": trade,
            "trade_id_short": trade_id_short,
            "zone3_remaining_seconds": zone3_remaining_seconds,
            "zone3_countdown": zone3_countdown,
        })

    return review


# ─── ZONE 3 CLEARANCE ─────────────────────────────────────────────────────────


@router.patch("/{review_id}/zone3-clear")
async def zone3_clear(review_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT * FROM review WHERE id = ?", (review_id,)
    )
    if not rows:
        raise HTTPException(404, "Review not found")

    review = dict(rows[0])

    if review.get("zone_3_clear") == 1:
        return {"id": review_id, "zone_3_clear": True}

    locked_at = datetime.fromisoformat(
        review["locked_at"].replace("Z", "+00:00")
    ).replace(tzinfo=None)
    now = datetime.utcnow()
    elapsed = now - locked_at
    required = timedelta(hours=ZONE3_LOCK_HOURS)

    if elapsed < required:
        remaining = required - elapsed
        raise HTTPException(
            400,
            f"Zone 3 timelock active. {int(remaining.total_seconds())} seconds remaining.",
        )

    now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.execute("BEGIN")
    try:
        await db.execute(
            """UPDATE review SET zone_3_clear = 1, zone_3_cleared_at = ?
               WHERE id = ?""",
            (now_str, review_id),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": review_id, "zone_3_clear": True, "zone_3_cleared_at": now_str}


# ─── REVIEW PHASE 2 ───────────────────────────────────────────────────────────


@router.patch("/{review_id}/phase2")
async def file_phase2(
    review_id: str, payload: Phase2Payload, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT * FROM review WHERE id = ?", (review_id,)
    )
    if not rows:
        raise HTTPException(404, "Review not found")

    review = dict(rows[0])

    if review.get("zone_3_clear") != 1:
        raise HTTPException(400, "Zone 3 must be cleared before filing Phase 2")

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    await db.execute("BEGIN")
    try:
        await db.execute(
            """UPDATE review SET
                   phase2_created_at = ?,
                   mistake_type = ?,
                   analysis = ?,
                   single_update = ?,
                   what_not_changing = ?
               WHERE id = ?""",
            (now, payload.mistake_type, payload.analysis,
             payload.single_update, payload.what_not_changing, review_id),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": review_id, "phase2_created_at": now}
