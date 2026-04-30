from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db
from api.models.trade import (
    TradeCreate,
    TradeClose,
    TradeEntryCreate,
    TradeExitCreate,
    OptionsMetaCreate,
    OptionLegCreate,
    OptionLegUpdate,
)

router = APIRouter()

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


# ─── TRADE CRUD ────────────────────────────────────────────────────────────────


@router.get("/new")
async def trade_new_form(request: Request, db=Depends(get_db)):
    canvases = await db.execute_fetchall(
        "SELECT id, name FROM canvas ORDER BY last_reviewed DESC"
    )
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse("trade/new.html", {
        "request": request,
        "canvases": [dict(r) for r in canvases],
        "now_date": now.strftime("%Y-%m-%d"),
    })


@router.post("")
async def create_trade(payload: TradeCreate, db=Depends(get_db)):
    thesis_rows = await db.execute_fetchall(
        "SELECT id, narrative FROM thesis WHERE id = ?", (payload.thesis_id,)
    )
    if not thesis_rows:
        raise HTTPException(404, "Thesis not found")

    thesis_snapshot = dict(thesis_rows[0])["narrative"]
    trade_id = str(ULID())

    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO trade (id, thesis_id, instrument_type,
                  entry_rules_stated, exit_rules_stated, thesis_snapshot)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (trade_id, payload.thesis_id, payload.instrument_type,
             payload.entry_rules_stated, payload.exit_rules_stated,
             thesis_snapshot),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": trade_id}


@router.get("/{trade_id}")
async def get_trade(trade_id: str, request: Request, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT * FROM trade WHERE id = ?", (trade_id,)
    )
    if not rows:
        raise HTTPException(404, "Trade not found")
    trade = dict(rows[0])

    entries = await db.execute_fetchall(
        "SELECT * FROM trade_entries WHERE trade_id = ? ORDER BY created_at ASC",
        (trade_id,),
    )

    exits = await db.execute_fetchall(
        "SELECT * FROM trade_exits WHERE trade_id = ? ORDER BY created_at ASC",
        (trade_id,),
    )

    options_meta = await db.execute_fetchall(
        "SELECT * FROM trade_options_meta WHERE trade_id = ?", (trade_id,),
    )

    option_legs = await db.execute_fetchall(
        "SELECT * FROM trade_option_legs WHERE trade_id = ? ORDER BY created_at ASC",
        (trade_id,),
    )

    review = None
    if trade.get("review_id"):
        review_rows = await db.execute_fetchall(
            "SELECT * FROM review WHERE id = ?", (trade["review_id"],)
        )
        if review_rows:
            review = dict(review_rows[0])

    accept = request.headers.get("accept", "")
    wants_html = "text/html" in accept and not request.headers.get("hx-request")

    if not wants_html:
        return {
            **trade,
            "entries": [dict(r) for r in entries],
            "exits": [dict(r) for r in exits],
            "options_meta": dict(options_meta[0]) if options_meta else None,
            "option_legs": [dict(r) for r in option_legs],
            "review": review,
        }

    # Fetch linked thesis for HTML view
    thesis = None
    if trade.get("thesis_id"):
        thesis_rows = await db.execute_fetchall(
            "SELECT id, instrument, status FROM thesis WHERE id = ?", (trade["thesis_id"],)
        )
        if thesis_rows:
            thesis = dict(thesis_rows[0])

    now = datetime.now(timezone.utc)

    from api.protocols.protocol4 import check_protocol4
    protocol4_flags = await check_protocol4(db, trade_id=trade_id)

    return templates.TemplateResponse("trade/detail.html", {
        "request": request,
        "trade": trade,
        "thesis": thesis,
        "entries": [dict(r) for r in entries],
        "exits": [dict(r) for r in exits],
        "options_meta": dict(options_meta[0]) if options_meta else None,
        "option_legs": [dict(r) for r in option_legs],
        "review": review,
        "now_date": now.strftime("%Y-%m-%d"),
        "protocol4_flags": protocol4_flags,
    })


@router.patch("/{trade_id}/close")
async def close_trade(
    trade_id: str, payload: TradeClose, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id, status FROM trade WHERE id = ?", (trade_id,)
    )
    if not rows:
        raise HTTPException(404, "Trade not found")

    from datetime import datetime
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    await db.execute("BEGIN")
    try:
        if payload.review_id:
            await db.execute(
                """UPDATE trade SET status = 'closed', closed_at = ?, review_id = ?
                   WHERE id = ?""",
                (now, payload.review_id, trade_id),
            )
        else:
            await db.execute(
                "UPDATE trade SET status = 'closed', closed_at = ? WHERE id = ?",
                (now, trade_id),
            )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": trade_id, "status": "closed", "closed_at": now}


# ─── TRADE ENTRIES (append-only) ──────────────────────────────────────────────


@router.post("/{trade_id}/entries")
async def add_trade_entry(
    trade_id: str, payload: TradeEntryCreate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM trade WHERE id = ?", (trade_id,)
    )
    if not rows:
        raise HTTPException(404, "Trade not found")

    entry_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO trade_entries (id, trade_id, date, price, size, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entry_id, trade_id, payload.date, payload.price,
             payload.size, payload.note),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": entry_id}


# ─── TRADE EXITS (append-only) ────────────────────────────────────────────────


@router.post("/{trade_id}/exits")
async def add_trade_exit(
    trade_id: str, payload: TradeExitCreate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM trade WHERE id = ?", (trade_id,)
    )
    if not rows:
        raise HTTPException(404, "Trade not found")

    exit_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO trade_exits (id, trade_id, date, price, size, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (exit_id, trade_id, payload.date, payload.price,
             payload.size, payload.note),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": exit_id}


# ─── OPTIONS METADATA ─────────────────────────────────────────────────────────


@router.post("/{trade_id}/options-meta")
async def set_options_meta(
    trade_id: str, payload: OptionsMetaCreate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM trade WHERE id = ?", (trade_id,)
    )
    if not rows:
        raise HTTPException(404, "Trade not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO trade_options_meta (
                   trade_id, strategy_type,
                   delta_at_entry, gamma_at_entry, theta_daily_at_entry,
                   vega_at_entry, iv_at_entry, iv_rank_at_entry,
                   delta_at_exit, gamma_at_exit, theta_daily_at_exit,
                   vega_at_exit, iv_at_exit,
                   max_loss_defined, max_loss_dollar, theta_decay_relevant
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(trade_id) DO UPDATE SET
                   strategy_type = excluded.strategy_type,
                   delta_at_entry = excluded.delta_at_entry,
                   gamma_at_entry = excluded.gamma_at_entry,
                   theta_daily_at_entry = excluded.theta_daily_at_entry,
                   vega_at_entry = excluded.vega_at_entry,
                   iv_at_entry = excluded.iv_at_entry,
                   iv_rank_at_entry = excluded.iv_rank_at_entry,
                   delta_at_exit = excluded.delta_at_exit,
                   gamma_at_exit = excluded.gamma_at_exit,
                   theta_daily_at_exit = excluded.theta_daily_at_exit,
                   vega_at_exit = excluded.vega_at_exit,
                   iv_at_exit = excluded.iv_at_exit,
                   max_loss_defined = excluded.max_loss_defined,
                   max_loss_dollar = excluded.max_loss_dollar,
                   theta_decay_relevant = excluded.theta_decay_relevant""",
            (trade_id, payload.strategy_type,
             payload.delta_at_entry, payload.gamma_at_entry,
             payload.theta_daily_at_entry, payload.vega_at_entry,
             payload.iv_at_entry, payload.iv_rank_at_entry,
             payload.delta_at_exit, payload.gamma_at_exit,
             payload.theta_daily_at_exit, payload.vega_at_exit,
             payload.iv_at_exit,
             payload.max_loss_defined, payload.max_loss_dollar,
             payload.theta_decay_relevant),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"trade_id": trade_id}


# ─── OPTION LEGS ───────────────────────────────────────────────────────────────


@router.post("/{trade_id}/option-legs")
async def add_option_leg(
    trade_id: str, payload: OptionLegCreate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM trade WHERE id = ?", (trade_id,)
    )
    if not rows:
        raise HTTPException(404, "Trade not found")

    leg_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO trade_option_legs
                   (id, trade_id, direction, type, strike, expiry,
                    contracts, entry_premium, date_opened)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (leg_id, trade_id, payload.direction, payload.type,
             payload.strike, payload.expiry, payload.contracts,
             payload.entry_premium, payload.date_opened),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": leg_id}


@router.patch("/{trade_id}/option-legs/{leg_id}")
async def update_option_leg(
    trade_id: str, leg_id: str, payload: OptionLegUpdate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM trade_option_legs WHERE id = ? AND trade_id = ?",
        (leg_id, trade_id),
    )
    if not rows:
        raise HTTPException(404, "Option leg not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "UPDATE trade_option_legs SET exit_premium = ?, date_closed = ? WHERE id = ?",
            (payload.exit_premium, payload.date_closed, leg_id),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": leg_id}
