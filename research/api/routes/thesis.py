from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlite3 import IntegrityError
from ulid import ULID
from api.database import get_db
from api.models.thesis import (
    ThesisCreate,
    ThesisUpdate,
    ThesisStatusTransition,
    MacroKillConditionCreate,
    TechnicalKillConditionCreate,
    DecisionPointCreate,
    DecisionPointFire,
    ThesisVersionHistoryCreate,
)

router = APIRouter()

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and not request.headers.get("hx-request")


# ─── THESIS CRUD ──────────────────────────────────────────────────────────────


@router.get("/search")
async def search_theses(q: str = "", canvas_id: str = "", db=Depends(get_db)):
    if canvas_id:
        rows = await db.execute_fetchall(
            """SELECT t.id, t.instrument, t.status
               FROM thesis t
               JOIN thesis_linked_canvases tlc ON t.id = tlc.thesis_id
               WHERE tlc.canvas_id = ? AND t.instrument LIKE ?
               LIMIT 10""",
            (canvas_id, f"%{q}%"),
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT id, instrument, status FROM thesis WHERE instrument LIKE ? LIMIT 10",
            (f"%{q}%",),
        )
    return [{"id": r["id"], "instrument": r["instrument"], "status": r["status"]} for r in rows]


@router.post("")
async def create_thesis(payload: ThesisCreate, db=Depends(get_db)):
    thesis_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO thesis (id, instrument, narrative, win_condition)
               VALUES (?, ?, ?, ?)""",
            (thesis_id, payload.instrument, payload.narrative, payload.win_condition),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": thesis_id}


@router.get("/{thesis_id}")
async def get_thesis(thesis_id: str, request: Request, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT * FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not rows:
        raise HTTPException(404, "Thesis not found")
    thesis = dict(rows[0])

    macro_kills = await db.execute_fetchall(
        """SELECT tkcm.*, c.name AS canvas_name
           FROM thesis_kill_conditions_macro tkcm
           LEFT JOIN canvas c ON c.id = tkcm.linked_canvas_id
           WHERE tkcm.thesis_id = ?
           ORDER BY tkcm.created_at ASC""",
        (thesis_id,),
    )

    technical_kills = await db.execute_fetchall(
        """SELECT tkct.*, s.instrument AS setup_instrument
           FROM thesis_kill_conditions_technical tkct
           LEFT JOIN setup s ON s.id = tkct.linked_setup_id
           WHERE tkct.thesis_id = ?
           ORDER BY tkct.created_at ASC""",
        (thesis_id,),
    )

    decision_points = await db.execute_fetchall(
        "SELECT * FROM thesis_decision_points WHERE thesis_id = ? ORDER BY created_at ASC",
        (thesis_id,),
    )

    linked_canvases = await db.execute_fetchall(
        """SELECT tlc.canvas_id, c.name, c.status, tlc.created_at
           FROM thesis_linked_canvases tlc
           JOIN canvas c ON c.id = tlc.canvas_id
           WHERE tlc.thesis_id = ?
           ORDER BY tlc.created_at ASC""",
        (thesis_id,),
    )

    linked_setups = await db.execute_fetchall(
        """SELECT stl.setup_id, s.instrument, s.setup_type, s.status, stl.created_at
           FROM setup_thesis_links stl
           JOIN setup s ON s.id = stl.setup_id
           WHERE stl.thesis_id = ?
           ORDER BY stl.created_at ASC""",
        (thesis_id,),
    )

    version_history = await db.execute_fetchall(
        """SELECT id, timestamp, diff_summary
           FROM thesis_version_history
           WHERE thesis_id = ?
           ORDER BY timestamp DESC""",
        (thesis_id,),
    )

    if not _wants_html(request):
        return {
            **thesis,
            "kill_conditions": {
                "macro": [dict(r) for r in macro_kills],
                "technical": [dict(r) for r in technical_kills],
            },
            "decision_points": [dict(r) for r in decision_points],
            "linked_canvases": [dict(r) for r in linked_canvases],
            "linked_setups": [dict(r) for r in linked_setups],
            "version_history": [dict(r) for r in version_history],
        }

    # Compute gate status for the ready button tooltip
    gate_status = {
        "has_kill_conditions": len(macro_kills) > 0,
        "has_decision_points": len(decision_points) > 0,
        "has_worst_case": thesis.get("worst_case_dollar") is not None and thesis["worst_case_dollar"] > 0,
        "has_linked_canvases": len(linked_canvases) > 0,
        "all_met": (
            len(macro_kills) > 0
            and len(decision_points) > 0
            and thesis.get("worst_case_dollar") is not None
            and thesis["worst_case_dollar"] > 0
            and len(linked_canvases) > 0
        ),
    }

    # Protocol checks for banners
    protocol2_flags = []
    protocol3_flags = []
    if thesis.get("status") == "active":
        from api.protocols.protocol2 import check_protocol2
        from api.protocols.protocol3 import check_protocol3
        protocol2_flags = await check_protocol2(db, thesis_id=thesis_id)
        protocol3_flags = await check_protocol3(db, thesis_id=thesis_id)

    return templates.TemplateResponse("thesis/detail.html", {
        "request": request,
        "thesis": thesis,
        "kill_conditions": {
            "macro": [dict(r) for r in macro_kills],
            "technical": [dict(r) for r in technical_kills],
        },
        "decision_points": [dict(r) for r in decision_points],
        "linked_canvases": [dict(r) for r in linked_canvases],
        "linked_setups": [dict(r) for r in linked_setups],
        "version_history": [dict(r) for r in version_history],
        "gate_status": gate_status,
        "protocol2_flags": protocol2_flags,
        "protocol3_flags": protocol3_flags,
    })


@router.patch("/{thesis_id}")
async def update_thesis(
    thesis_id: str, payload: ThesisUpdate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not rows:
        raise HTTPException(404, "Thesis not found")

    updates = []
    params = []
    if payload.narrative is not None:
        updates.append("narrative = ?")
        params.append(payload.narrative)
    if payload.win_condition is not None:
        updates.append("win_condition = ?")
        params.append(payload.win_condition)
    if payload.worst_case_dollar is not None:
        updates.append("worst_case_dollar = ?")
        params.append(payload.worst_case_dollar)
    if not updates:
        raise HTTPException(400, "No fields to update")

    params.append(thesis_id)
    await db.execute("BEGIN")
    try:
        await db.execute(
            f"UPDATE thesis SET {', '.join(updates)} WHERE id = ?", params
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"thesis_id": thesis_id, "updated": True}


# ─── THESIS STATE TRANSITIONS ─────────────────────────────────────────────────


@router.patch("/{thesis_id}/status")
async def transition_thesis_status(
    thesis_id: str, payload: ThesisStatusTransition, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id, status FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not rows:
        raise HTTPException(404, "Thesis not found")

    await db.execute("BEGIN")
    try:
        if payload.status == "active" and payload.linked_trade_id:
            await db.execute(
                """UPDATE thesis SET status = ?, linked_trade_id = ?
                   WHERE id = ?""",
                (payload.status, payload.linked_trade_id, thesis_id),
            )
        else:
            await db.execute(
                "UPDATE thesis SET status = ? WHERE id = ?",
                (payload.status, thesis_id),
            )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, detail=str(e))
    except Exception:
        await db.rollback()
        raise

    updated = await db.execute_fetchall(
        "SELECT status FROM thesis WHERE id = ?", (thesis_id,)
    )
    return {"thesis_id": thesis_id, "status": dict(updated[0])["status"]}


# ─── KILL CONDITIONS ──────────────────────────────────────────────────────────


@router.post("/{thesis_id}/kill-conditions/macro")
async def add_macro_kill_condition(
    thesis_id: str, payload: MacroKillConditionCreate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not rows:
        raise HTTPException(404, "Thesis not found")

    kc_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO thesis_kill_conditions_macro
                   (id, thesis_id, condition, linked_canvas_id)
               VALUES (?, ?, ?, ?)""",
            (kc_id, thesis_id, payload.condition, payload.linked_canvas_id),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": kc_id}


@router.post("/{thesis_id}/kill-conditions/technical")
async def add_technical_kill_condition(
    thesis_id: str, payload: TechnicalKillConditionCreate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not rows:
        raise HTTPException(404, "Thesis not found")

    kc_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO thesis_kill_conditions_technical
                   (id, thesis_id, condition, linked_setup_id)
               VALUES (?, ?, ?, ?)""",
            (kc_id, thesis_id, payload.condition, payload.linked_setup_id),
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except Exception:
        await db.rollback()
        raise
    return {"id": kc_id}


@router.patch("/{thesis_id}/kill-conditions/{kc_id}/fire")
async def fire_kill_condition(
    thesis_id: str, kc_id: str, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        """SELECT id FROM thesis_kill_conditions_macro
           WHERE id = ? AND thesis_id = ?
           UNION ALL
           SELECT id FROM thesis_kill_conditions_technical
           WHERE id = ? AND thesis_id = ?""",
        (kc_id, thesis_id, kc_id, thesis_id),
    )
    if not rows:
        raise HTTPException(404, "Kill condition not found")

    now = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.execute("BEGIN")
    try:
        await db.execute(
            "UPDATE thesis_kill_conditions_macro SET fired_at = ? WHERE id = ?",
            (now, kc_id),
        )
        await db.execute(
            "UPDATE thesis_kill_conditions_technical SET fired_at = ? WHERE id = ?",
            (now, kc_id),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": kc_id, "fired_at": now}


# ─── DECISION POINTS ──────────────────────────────────────────────────────────


@router.post("/{thesis_id}/decision-points")
async def add_decision_point(
    thesis_id: str, payload: DecisionPointCreate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not rows:
        raise HTTPException(404, "Thesis not found")

    dp_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO thesis_decision_points
                   (id, thesis_id, trigger, decision, instrument, size_pct)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (dp_id, thesis_id, payload.trigger, payload.decision,
             payload.instrument, payload.size_pct),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": dp_id}


@router.patch("/{thesis_id}/decision-points/{dp_id}/fire")
async def fire_decision_point(
    thesis_id: str,
    dp_id: str,
    payload: DecisionPointFire,
    db=Depends(get_db),
):
    rows = await db.execute_fetchall(
        "SELECT id FROM thesis_decision_points WHERE id = ? AND thesis_id = ?",
        (dp_id, thesis_id),
    )
    if not rows:
        raise HTTPException(404, "Decision point not found")

    now = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.execute("BEGIN")
    try:
        await db.execute(
            """UPDATE thesis_decision_points
               SET fired_at = ?, deviation_note = ?
               WHERE id = ?""",
            (now, payload.deviation_note, dp_id),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": dp_id, "fired_at": now}


# ─── THESIS ↔ CANVAS LINKS ───────────────────────────────────────────────────


@router.post("/{thesis_id}/link-canvas/{canvas_id}")
async def link_canvas_to_thesis(
    thesis_id: str, canvas_id: str, db=Depends(get_db)
):
    thesis_rows = await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not thesis_rows:
        raise HTTPException(404, "Thesis not found")
    canvas_rows = await db.execute_fetchall(
        "SELECT id FROM canvas WHERE id = ?", (canvas_id,)
    )
    if not canvas_rows:
        raise HTTPException(404, "Canvas not found")

    await db.execute("BEGIN")
    try:
        await db.execute(
            "INSERT INTO thesis_linked_canvases (thesis_id, canvas_id) VALUES (?, ?)",
            (thesis_id, canvas_id),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Canvas already linked to this thesis")
    except Exception:
        await db.rollback()
        raise
    return {"thesis_id": thesis_id, "canvas_id": canvas_id}


# ─── VERSION HISTORY ──────────────────────────────────────────────────────────


@router.post("/{thesis_id}/version-history")
async def add_version_history(
    thesis_id: str, payload: ThesisVersionHistoryCreate, db=Depends(get_db)
):
    rows = await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not rows:
        raise HTTPException(404, "Thesis not found")

    vh_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute(
            """INSERT INTO thesis_version_history (id, thesis_id, diff_summary)
               VALUES (?, ?, ?)""",
            (vh_id, thesis_id, payload.diff_summary),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": vh_id}


# ─── THESIS PANEL (HTMX partial) ─────────────────────────────────────────────


@router.get("/{thesis_id}/panel")
async def thesis_panel(thesis_id: str, request: Request, db=Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT id FROM thesis WHERE id = ?", (thesis_id,)
    )
    if not rows:
        raise HTTPException(404, "Thesis not found")

    linked_canvases = await db.execute_fetchall(
        """SELECT tlc.canvas_id, c.name, c.status
           FROM thesis_linked_canvases tlc
           JOIN canvas c ON c.id = tlc.canvas_id
           WHERE tlc.thesis_id = ?
           ORDER BY tlc.created_at ASC""",
        (thesis_id,),
    )

    linked_setups = await db.execute_fetchall(
        """SELECT stl.setup_id, s.instrument, s.setup_type, s.status
           FROM setup_thesis_links stl
           JOIN setup s ON s.id = stl.setup_id
           WHERE stl.thesis_id = ?
           ORDER BY stl.created_at ASC""",
        (thesis_id,),
    )

    version_history = await db.execute_fetchall(
        """SELECT id, timestamp, diff_summary
           FROM thesis_version_history
           WHERE thesis_id = ?
           ORDER BY timestamp DESC""",
        (thesis_id,),
    )

    # Protocol flags: check for active theses with observable kill conditions
    protocol_flags = []
    thesis = await db.execute_fetchall(
        "SELECT status FROM thesis WHERE id = ?", (thesis_id,)
    )
    if thesis and dict(thesis[0])["status"] == "active":
        fired_macro = await db.execute_fetchall(
            """SELECT COUNT(*) as cnt FROM thesis_kill_conditions_macro
               WHERE thesis_id = ? AND fired_at IS NOT NULL""",
            (thesis_id,),
        )
        if fired_macro and dict(fired_macro[0])["cnt"] > 0:
            protocol_flags.append("Protocol 2 — Kill condition fired. Write hold-vs-redeploy logic before acting.")

    return templates.TemplateResponse("thesis/panel.html", {
        "request": request,
        "linked_canvases": [dict(r) for r in linked_canvases],
        "linked_setups": [dict(r) for r in linked_setups],
        "version_history": [dict(r) for r in version_history],
        "protocol_flags": protocol_flags,
    })
