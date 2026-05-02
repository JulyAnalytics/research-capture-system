#!/usr/bin/env python3
"""
Task 003 — State Machine Verification with Seed Data

Comprehensive test script exercising every state machine transition, every gate,
every append-only constraint, and every event log trigger against a fresh
in-memory SQLite database loaded with schema.sql + triggers.sql + views.sql.

Run:
    python3 research/tests/test_state_machines.py

Must print "ALL TESTS PASSED" with 0 failures.
"""

import sqlite3
import sys
import time
import traceback
from pathlib import Path

from ulid import ULID

# -- paths -------------------------------------------------------------------

DB_DIR = Path(__file__).resolve().parent.parent / "db"

# -- helpers ------------------------------------------------------------------

_results: list = []  # (name, passed, detail|None)


def _uid():
    return str(ULID())


def _ok(name, detail=None):
    _results.append((name, True, detail))


def _fail(name, detail):
    _results.append((name, False, detail))


class Abort(Exception):
    """Raised to signal the enclosing test should catch and fail."""
    pass


# -- database fixture ---------------------------------------------------------

def _fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    for fn in ("schema.sql", "triggers.sql", "views.sql"):
        sql = (DB_DIR / fn).read_text()
        conn.executescript(sql)
    return conn


def _exec(conn, sql, params=None):
    conn.execute(sql, params or [])
    conn.commit()


def _val(conn, sql, params=None):
    cur = conn.execute(sql, params or [])
    row = cur.fetchone()
    return row[0] if row else None


def _row(conn, sql, params=None):
    cur = conn.execute(sql, params or [])
    return cur.fetchone()


def _all(conn, sql, params=None):
    cur = conn.execute(sql, params or [])
    return cur.fetchall()


# -- entity factories ---------------------------------------------------------

def _canvas(conn, **kw):
    cid = kw.get("id", _uid())
    _exec(
        conn,
        "INSERT INTO canvas (id, name, narrative, status, last_reviewed) VALUES (?,?,?,?,?)",
        (cid, kw.get("name", "Canvas"), kw.get("narrative", "n"),
         kw.get("status", "active"), kw.get("last_reviewed", "2026-01-01T00:00:00Z")),
    )
    return cid


def _observation(conn, **kw):
    """Creates a watching-state observation row (lightweight state-machine entity)."""
    oid = kw.get("id", _uid())
    _exec(
        conn,
        "INSERT INTO observation (id, name, instrument, note, date) VALUES (?,?,?,?,?)",
        (oid, kw.get("name", "obs label"), kw.get("instrument", "SPY"),
         kw.get("note", "n"), kw.get("date", "2026-01-15")),
    )
    return oid


def _setup(conn, **kw):
    """Creates an append-only setup row (structured analytical entity)."""
    sid = kw.get("id", _uid())
    _exec(
        conn,
        "INSERT INTO setup (id, name, instrument, type, timeframe, setup_note, date) "
        "VALUES (?,?,?,?,?,?,?)",
        (sid, kw.get("name", "setup label"), kw.get("instrument", "SPY"),
         kw.get("type", "technical"), kw.get("timeframe", "daily"),
         kw.get("setup_note", "n"), kw.get("date", "2026-01-15")),
    )
    return sid


def _thesis(conn, **kw):
    tid = kw.get("id", _uid())
    _exec(
        conn,
        "INSERT INTO thesis (id, instrument, status, narrative, win_condition, worst_case_dollar) "
        "VALUES (?,?,'building',?,?,?)",
        (tid, kw.get("instrument", "SPY"), kw.get("narrative", "n"),
         kw.get("win_condition", "wc"), kw.get("worst_case_dollar")),
    )
    return tid


def _full_thesis(conn, tid=None):
    """Thesis with all ready-gate requirements met (building -> ready)."""
    tid = tid or _thesis(conn, worst_case_dollar=500.0)
    cid = _canvas(conn)
    _exec(conn, "INSERT INTO thesis_kill_conditions_macro (id, thesis_id, condition) VALUES (?,?,?)",
          (_uid(), tid, "macro kill"))
    _exec(conn, "INSERT INTO thesis_decision_points (id, thesis_id, trigger, decision, instrument, size_pct) "
                "VALUES (?,?,?,?,?,?)",
          (_uid(), tid, "trigger", "decision", "SPY", "100%"))
    _exec(conn, "INSERT INTO thesis_linked_canvases (thesis_id, canvas_id) VALUES (?,?)", (tid, cid))
    return tid


def _trade(conn, thesis_id, **kw):
    trid = kw.get("id", _uid())
    _exec(
        conn,
        "INSERT INTO trade (id, name, thesis_id, instrument_type, "
        "entry_rules_stated, exit_rules_stated, thesis_snapshot, status) "
        "VALUES (?,?,?,'equity',?,?,?,'active')",
        (trid, kw.get("name", "Test trade"), thesis_id,
         kw.get("entry_rules", "er"),
         kw.get("exit_rules", "xr"),
         kw.get("snapshot", "snap")),
    )
    return trid


def _idea(conn, **kw):
    """
    Create a minimal idea trade (status='idea', no thesis_id).
    Used for testing idea→active transition via UPDATE — the only path
    that exercises trade_active_gate. Do not use _trade() for this
    purpose: _trade() inserts directly as 'active' and bypasses the gate.
    """
    tid = kw.get("id", _uid())
    _exec(
        conn,
        "INSERT INTO trade (id, name, instrument_type, status) "
        "VALUES (?,?,'equity','idea')",
        (tid, kw.get("name", "Test idea")),
    )
    return tid


# =============================================================================
#  TEST FUNCTIONS
# =============================================================================


# -- Pre-flight ---------------------------------------------------------------

def test_preflight(conn):
    """Pre-flight: schema loads, foreign keys enabled, all required tables/views present."""
    fk = _val(conn, "PRAGMA foreign_keys")
    assert fk == 1, f"foreign_keys should be 1, got {fk}"

    tables = set(r[0] for r in _all(conn, "SELECT name FROM sqlite_master WHERE type='table'"))
    required_tables = {
        "canvas", "canvas_cross_currents", "canvas_invalidation_conditions",
        "canvas_version_history", "setup", "setup_images", "setup_thesis_links",
        "setup_linked_canvases", "thesis",
        "thesis_kill_conditions_macro", "thesis_kill_conditions_technical",
        "thesis_decision_points", "thesis_linked_canvases", "thesis_version_history",
        "trade", "trade_entries", "trade_exits", "trade_options_meta",
        "trade_option_legs", "observation", "observation_thesis_links",
        "observation_setup_links",
        "action", "review", "entity_events", "canvas_source_documents",
        "export_watermarks", "failed_exports", "schema_version",
        "insight",
    }
    missing = required_tables - tables
    assert not missing, f"Missing tables: {missing}"

    absent_tables = {"setup_observation_links", "observation_linked_canvases", "observation_images"}
    present = absent_tables & tables
    assert not present, f"Tables that must not exist are present: {present}"

    views = set(r[0] for r in _all(conn, "SELECT name FROM sqlite_master WHERE type='view'"))
    required_views = {
        "stale_canvases", "stale_theses", "stale_invalidation_conditions",
        "overdue_actions", "active_surveillance", "canvas_setup_backlinks",
        "passed_observation_analysis", "passed_observation_detail",
        "review_mistake_distribution", "decision_point_deviations",
        "options_iv_comparison", "invalidation_post_mortem", "thesis_lifespan", "review_lag",
        "recent_insights",
    }
    missing_v = required_views - views
    assert not missing_v, f"Missing views: {missing_v}"

    absent_views = {"canvas_observation_backlinks", "passed_setup_analysis", "passed_setup_detail"}
    present_v = absent_views & views
    assert not present_v, f"Views that must not exist are present: {present_v}"

    _ok("preflight")


# -- 2. Thesis State Machine --------------------------------------------------

def test_thesis_state_building_to_ready(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    assert _val(conn, "SELECT status FROM thesis WHERE id = ?", (tid,)) == "ready"
    _ok("thesis_state_building_to_ready")


def test_thesis_state_building_invalid(conn):
    """building -> active is an invalid transition."""
    tid = _thesis(conn)
    try:
        _exec(conn, "UPDATE thesis SET status = 'active' WHERE id = ?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("thesis_state_building_invalid")


def test_thesis_state_ready_to_active(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    assert _val(conn, "SELECT status FROM thesis WHERE id = ?", (tid,)) == "active"
    _ok("thesis_state_ready_to_active")


def test_thesis_state_ready_back_to_building(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'building' WHERE id = ?", (tid,))
    assert _val(conn, "SELECT status FROM thesis WHERE id = ?", (tid,)) == "building"
    _ok("thesis_state_ready_back_to_building")


def test_thesis_state_active_to_invalidated(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'invalidated' WHERE id = ?", (tid,))
    assert _val(conn, "SELECT status FROM thesis WHERE id = ?", (tid,)) == "invalidated"
    _ok("thesis_state_active_to_invalidated")


def test_thesis_state_active_to_archived(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'archived' WHERE id = ?", (tid,))
    assert _val(conn, "SELECT status FROM thesis WHERE id = ?", (tid,)) == "archived"
    _ok("thesis_state_active_to_archived")


def test_thesis_state_invalidated_to_building(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'invalidated' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'building' WHERE id = ?", (tid,))
    assert _val(conn, "SELECT status FROM thesis WHERE id = ?", (tid,)) == "building"
    _ok("thesis_state_invalidated_to_building")


def test_thesis_state_archived_terminal(conn):
    """archived -> building is an invalid transition (terminal state)."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'archived' WHERE id = ?", (tid,))
    try:
        _exec(conn, "UPDATE thesis SET status = 'building' WHERE id = ?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("thesis_state_archived_terminal")


# -- 3. Thesis Gates ----------------------------------------------------------

def test_thesis_ready_gate_no_kill_conditions(conn):
    tid = _thesis(conn, worst_case_dollar=500.0)
    cid = _canvas(conn)
    _exec(conn, "INSERT INTO thesis_decision_points (id, thesis_id, trigger, decision, instrument, size_pct) "
                "VALUES (?,?,?,?,?,?)", (_uid(), tid, "t", "d", "SPY", "100%"))
    _exec(conn, "INSERT INTO thesis_linked_canvases (thesis_id, canvas_id) VALUES (?,?)", (tid, cid))
    try:
        _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("thesis_ready_gate_no_kill_conditions")


def test_thesis_ready_gate_no_decision_points(conn):
    tid = _thesis(conn, worst_case_dollar=500.0)
    cid = _canvas(conn)
    _exec(conn, "INSERT INTO thesis_kill_conditions_macro (id, thesis_id, condition) VALUES (?,?,?)",
          (_uid(), tid, "kc"))
    _exec(conn, "INSERT INTO thesis_linked_canvases (thesis_id, canvas_id) VALUES (?,?)", (tid, cid))
    try:
        _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("thesis_ready_gate_no_decision_points")


def test_thesis_ready_gate_no_worst_case(conn):
    tid = _thesis(conn)  # worst_case_dollar = None
    cid = _canvas(conn)
    _exec(conn, "INSERT INTO thesis_kill_conditions_macro (id, thesis_id, condition) VALUES (?,?,?)",
          (_uid(), tid, "kc"))
    _exec(conn, "INSERT INTO thesis_decision_points (id, thesis_id, trigger, decision, instrument, size_pct) "
                "VALUES (?,?,?,?,?,?)", (_uid(), tid, "t", "d", "SPY", "100%"))
    _exec(conn, "INSERT INTO thesis_linked_canvases (thesis_id, canvas_id) VALUES (?,?)", (tid, cid))
    try:
        _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("thesis_ready_gate_no_worst_case")


def test_thesis_ready_gate_no_canvas_link(conn):
    tid = _thesis(conn, worst_case_dollar=500.0)
    _exec(conn, "INSERT INTO thesis_kill_conditions_macro (id, thesis_id, condition) VALUES (?,?,?)",
          (_uid(), tid, "kc"))
    _exec(conn, "INSERT INTO thesis_decision_points (id, thesis_id, trigger, decision, instrument, size_pct) "
                "VALUES (?,?,?,?,?,?)", (_uid(), tid, "t", "d", "SPY", "100%"))
    try:
        _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("thesis_ready_gate_no_canvas_link")


def test_thesis_active_gate_no_trade_id(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    try:
        _exec(conn, "UPDATE thesis SET status = 'active' WHERE id = ?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("thesis_active_gate_no_trade_id")


# -- 4. Observation State Machine ---------------------------------------------

def test_observation_state_watching_to_taken(conn):
    oid = _observation(conn)
    tid = _thesis(conn)
    _exec(conn, "INSERT INTO observation_thesis_links (observation_id, thesis_id) VALUES (?,?)", (oid, tid))
    _exec(conn, "UPDATE observation SET status = 'taken' WHERE id = ?", (oid,))
    assert _val(conn, "SELECT status FROM observation WHERE id = ?", (oid,)) == "taken"
    _ok("observation_state_watching_to_taken")


def test_observation_state_watching_to_passed(conn):
    oid = _observation(conn)
    _exec(conn, "UPDATE observation SET status = 'passed', passed_reason = 'no conv', "
                "passed_reason_type = 'analytical' WHERE id = ?", (oid,))
    assert _val(conn, "SELECT status FROM observation WHERE id = ?", (oid,)) == "passed"
    _ok("observation_state_watching_to_passed")


def test_observation_state_taken_is_terminal(conn):
    oid = _observation(conn)
    tid = _thesis(conn)
    _exec(conn, "INSERT INTO observation_thesis_links (observation_id, thesis_id) VALUES (?,?)", (oid, tid))
    _exec(conn, "UPDATE observation SET status = 'taken' WHERE id = ?", (oid,))
    try:
        _exec(conn, "UPDATE observation SET status = 'watching' WHERE id = ?", (oid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("observation_state_taken_is_terminal")


def test_observation_state_passed_is_terminal(conn):
    oid = _observation(conn)
    _exec(conn, "UPDATE observation SET status = 'passed', passed_reason = 'r', "
                "passed_reason_type = 'psychological' WHERE id = ?", (oid,))
    try:
        _exec(conn, "UPDATE observation SET status = 'watching' WHERE id = ?", (oid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("observation_state_passed_is_terminal")


def test_observation_taken_gate_no_thesis_link(conn):
    oid = _observation(conn)
    try:
        _exec(conn, "UPDATE observation SET status = 'taken' WHERE id = ?", (oid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("observation_taken_gate_no_thesis_link")


def test_observation_passed_gate_no_reason(conn):
    oid = _observation(conn)
    try:
        _exec(conn, "UPDATE observation SET status = 'passed', passed_reason_type = 'analytical' WHERE id = ?", (oid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("observation_passed_gate_no_reason")


def test_observation_passed_gate_no_reason_type(conn):
    oid = _observation(conn)
    try:
        _exec(conn, "UPDATE observation SET status = 'passed', passed_reason = 'reason' WHERE id = ?", (oid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("observation_passed_gate_no_reason_type")


# -- 5. Frozen Fields ---------------------------------------------------------

def test_trade_frozen_entry_rules(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    try:
        _exec(conn, "UPDATE trade SET entry_rules_stated = 'modified' WHERE id = ?", (trid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("trade_frozen_entry_rules")


def test_trade_frozen_exit_rules(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    try:
        _exec(conn, "UPDATE trade SET exit_rules_stated = 'modified' WHERE id = ?", (trid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("trade_frozen_exit_rules")


def test_trade_frozen_thesis_snapshot(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    try:
        _exec(conn, "UPDATE trade SET thesis_snapshot = 'modified' WHERE id = ?", (trid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("trade_frozen_thesis_snapshot")


def test_option_legs_partial_update_ok(conn):
    """exit_premium and date_closed updates are allowed."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    lid = _uid()
    _exec(conn, "INSERT INTO trade_option_legs (id, trade_id, direction, type, strike, expiry, "
                "contracts, entry_premium, date_opened) VALUES (?,?,'long','call',450,'2026-03-21',1,5.00,'2026-01-15')",
          (lid, trid))
    _exec(conn, "UPDATE trade_option_legs SET exit_premium = 7.50, date_closed = '2026-02-01' WHERE id = ?", (lid,))
    assert _val(conn, "SELECT exit_premium FROM trade_option_legs WHERE id = ?", (lid,)) == 7.5
    _ok("option_legs_partial_update_ok")


def test_option_legs_partial_update_frozen(conn):
    """Updates to non-exit fields (e.g. strike) are rejected."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    lid = _uid()
    _exec(conn, "INSERT INTO trade_option_legs (id, trade_id, direction, type, strike, expiry, "
                "contracts, entry_premium, date_opened) VALUES (?,?,'long','call',450,'2026-03-21',1,5.00,'2026-01-15')",
          (lid, trid))
    try:
        _exec(conn, "UPDATE trade_option_legs SET strike = 500 WHERE id = ?", (lid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("option_legs_partial_update_frozen")


# -- 6. Append-Only Tables ----------------------------------------------------

def test_trade_entries_append_only(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    eid = _uid()
    _exec(conn, "INSERT INTO trade_entries (id, trade_id, date, price, size) VALUES (?,?,?,?,?)",
          (eid, trid, "2026-01-15", 100.0, 10))
    try:
        _exec(conn, "UPDATE trade_entries SET price = 200 WHERE id = ?", (eid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    try:
        _exec(conn, "DELETE FROM trade_entries WHERE id = ?", (eid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("trade_entries_append_only")


def test_trade_exits_append_only(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    eid = _uid()
    _exec(conn, "INSERT INTO trade_exits (id, trade_id, date, price, size) VALUES (?,?,?,?,?)",
          (eid, trid, "2026-01-20", 110.0, 10))
    try:
        _exec(conn, "UPDATE trade_exits SET price = 200 WHERE id = ?", (eid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    try:
        _exec(conn, "DELETE FROM trade_exits WHERE id = ?", (eid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("trade_exits_append_only")


def test_setup_append_only(conn):
    """setup is now append-only — UPDATE and DELETE are rejected."""
    sid = _setup(conn)
    try:
        _exec(conn, "UPDATE setup SET setup_note = 'modified' WHERE id = ?", (sid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    try:
        _exec(conn, "DELETE FROM setup WHERE id = ?", (sid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("setup_append_only")


def test_canvas_version_history_append_only(conn):
    cid = _canvas(conn)
    vid = _uid()
    _exec(conn, "INSERT INTO canvas_version_history (id, canvas_id, diff_summary) VALUES (?,?,?)",
          (vid, cid, "v1"))
    try:
        _exec(conn, "UPDATE canvas_version_history SET diff_summary = 'modified' WHERE id = ?", (vid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    try:
        _exec(conn, "DELETE FROM canvas_version_history WHERE id = ?", (vid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("canvas_version_history_append_only")


def test_thesis_version_history_append_only(conn):
    tid = _thesis(conn)
    vid = _uid()
    _exec(conn, "INSERT INTO thesis_version_history (id, thesis_id, diff_summary) VALUES (?,?,?)",
          (vid, tid, "v1"))
    try:
        _exec(conn, "UPDATE thesis_version_history SET diff_summary = 'modified' WHERE id = ?", (vid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    try:
        _exec(conn, "DELETE FROM thesis_version_history WHERE id = ?", (vid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("thesis_version_history_append_only")


def test_option_legs_append_only_delete(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    lid = _uid()
    _exec(conn, "INSERT INTO trade_option_legs (id, trade_id, direction, type, strike, expiry, "
                "contracts, entry_premium, date_opened) VALUES (?,?,'long','call',450,'2026-03-21',1,5.00,'2026-01-15')",
          (lid, trid))
    try:
        _exec(conn, "DELETE FROM trade_option_legs WHERE id = ?", (lid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("option_legs_append_only_delete")


# -- 7. Review Enforcement ----------------------------------------------------

def test_review_emotional_state_single_word_ok(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    rid = _uid()
    _exec(conn, "INSERT INTO review (id, trade_id, closed_at, entry_fill, exit_fill, "
                "thesis_at_entry, exit_rules_as_written, what_i_actually_did, emotional_state, rules_followed) "
                "VALUES (?,?,'2026-02-01','fill','fill','snap','rules','did stuff','calm','yes')",
          (rid, trid))
    assert _val(conn, "SELECT emotional_state FROM review WHERE id = ?", (rid,)) == "calm"
    _ok("review_emotional_state_single_word_ok")


def test_review_emotional_state_multi_word_insert(conn):
    """INSERT with multi-word emotional_state is rejected."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    try:
        _exec(conn, "INSERT INTO review (id, trade_id, closed_at, entry_fill, exit_fill, "
                      "thesis_at_entry, exit_rules_as_written, what_i_actually_did, emotional_state, rules_followed) "
                      "VALUES (?,?,'2026-02-01','fill','fill','snap','rules','did stuff','very calm','yes')",
              (_uid(), trid))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("review_emotional_state_multi_word_insert")


def test_review_emotional_state_multi_word_update(conn):
    """UPDATE with multi-word emotional_state is rejected."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    rid = _uid()
    _exec(conn, "INSERT INTO review (id, trade_id, closed_at, entry_fill, exit_fill, "
                "thesis_at_entry, exit_rules_as_written, what_i_actually_did, emotional_state, rules_followed) "
                "VALUES (?,?,'2026-02-01','fill','fill','snap','rules','did stuff','calm','yes')",
          (rid, trid))
    try:
        _exec(conn, "UPDATE review SET emotional_state = 'very calm' WHERE id = ?", (rid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("review_emotional_state_multi_word_update")


def test_review_zone3_timelock_block(conn):
    """Zone 3 clearance blocked within 24 hours of locked_at."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    rid = _uid()
    # locked_at defaults to now, so zone 3 should be blocked
    _exec(conn, "INSERT INTO review (id, trade_id, closed_at, entry_fill, exit_fill, "
                "thesis_at_entry, exit_rules_as_written, what_i_actually_did, emotional_state, rules_followed) "
                "VALUES (?,?,'2026-02-01','fill','fill','snap','rules','did stuff','calm','yes')",
          (rid, trid))
    try:
        _exec(conn, "UPDATE review SET zone_3_clear = 1 WHERE id = ?", (rid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("review_zone3_timelock_block")


def test_review_zone3_timelock_allow(conn):
    """Zone 3 clearance allowed when 24h have passed."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    rid = _uid()
    # Set locked_at far in the past so 24h has elapsed
    past = "2020-01-01T00:00:00Z"
    _exec(conn, "INSERT INTO review (id, trade_id, closed_at, entry_fill, exit_fill, "
                "thesis_at_entry, exit_rules_as_written, what_i_actually_did, emotional_state, rules_followed, "
                "locked_at) VALUES (?,?,'2026-02-01','fill','fill','snap','rules','did stuff','calm','yes',?)",
          (rid, trid, past))
    _exec(conn, "UPDATE review SET zone_3_clear = 1 WHERE id = ?", (rid,))
    assert _val(conn, "SELECT zone_3_clear FROM review WHERE id = ?", (rid,)) == 1
    _ok("review_zone3_timelock_allow")


def test_review_phase2_gate(conn):
    """Phase 2 blocked when zone_3_clear is not committed."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    rid = _uid()
    past = "2020-01-01T00:00:00Z"
    _exec(conn, "INSERT INTO review (id, trade_id, closed_at, entry_fill, exit_fill, "
                "thesis_at_entry, exit_rules_as_written, what_i_actually_did, emotional_state, rules_followed, "
                "locked_at) VALUES (?,?,'2026-02-01','fill','fill','snap','rules','did stuff','calm','yes',?)",
          (rid, trid, past))
    # Phase 2 without zone 3 clearance should fail
    try:
        _exec(conn, "UPDATE review SET phase2_created_at = '2026-02-05T00:00:00Z' WHERE id = ?", (rid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass

    # Clear zone 3, then phase 2 should succeed
    _exec(conn, "UPDATE review SET zone_3_clear = 1 WHERE id = ?", (rid,))
    _exec(conn, "UPDATE review SET phase2_created_at = '2026-02-05T00:00:00Z' WHERE id = ?", (rid,))
    assert _val(conn, "SELECT phase2_created_at FROM review WHERE id = ?", (rid,)) is not None
    _ok("review_phase2_gate")


# -- 8. trade_review_id_fk ----------------------------------------------------

def test_trade_review_id_soft_fk(conn):
    """Setting trade.review_id to nonexistent review is rejected by trigger."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    try:
        _exec(conn, "UPDATE trade SET review_id = 'NONEXISTENT' WHERE id = ?", (trid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("trade_review_id_soft_fk")


# -- 9. Entity Event Log ------------------------------------------------------

def test_event_canvas_created(conn):
    cid = _canvas(conn)
    row = _row(conn, "SELECT entity_type, entity_id, event_type, new_status FROM entity_events "
                      "WHERE entity_id = ?", (cid,))
    assert row is not None, "no event logged"
    assert row[0] == "canvas" and row[2] == "created" and row[3] == "active"
    _ok("event_canvas_created")


def test_event_canvas_updated(conn):
    cid = _canvas(conn)
    # Clear events from creation
    _exec(conn, "DELETE FROM entity_events")
    _exec(conn, "UPDATE canvas SET last_reviewed = '2026-02-01T00:00:00Z' WHERE id = ?", (cid,))
    row = _row(conn, "SELECT entity_type, entity_id, event_type FROM entity_events WHERE entity_id = ?", (cid,))
    assert row is not None, "no event logged"
    assert row[2] == "updated"
    _ok("event_canvas_updated")


def test_event_thesis_created(conn):
    tid = _thesis(conn)
    row = _row(conn, "SELECT entity_type, event_type, new_status FROM entity_events WHERE entity_id = ?", (tid,))
    assert row is not None
    assert row[0] == "thesis" and row[1] == "created" and row[2] == "building"
    _ok("event_thesis_created")


def test_event_thesis_status_changed(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    row = _row(conn, "SELECT event_type, old_status, new_status FROM entity_events "
                      "WHERE entity_id = ? AND event_type = 'status_changed'", (tid,))
    assert row is not None
    assert row[1] == "building" and row[2] == "ready"
    _ok("event_thesis_status_changed")


def test_event_trade_created(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    row = _row(conn, "SELECT entity_type, event_type, new_status FROM entity_events "
                      "WHERE entity_id = ?", (trid,))
    assert row is not None, "no event logged for trade created"
    assert row[0] == "trade" and row[1] == "created" and row[2] == "active"
    _ok("event_trade_created")


def test_event_trade_closed(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    _exec(conn, "UPDATE trade SET status = 'closed', closed_at = '2026-02-01T00:00:00Z' WHERE id = ?", (trid,))
    row = _row(conn, "SELECT entity_type, event_type, old_status, new_status FROM entity_events "
                      "WHERE entity_id = ? AND event_type = 'status_changed'", (trid,))
    assert row is not None, "no status_changed event for trade closed"
    assert row[0] == "trade" and row[2] == "active" and row[3] == "closed"
    _ok("event_trade_closed")


def test_event_observation_created(conn):
    oid = _observation(conn)
    row = _row(conn, "SELECT entity_type, event_type, new_status FROM entity_events WHERE entity_id = ?", (oid,))
    assert row is not None, "no event logged for observation"
    assert row[0] == "observation" and row[1] == "created" and row[2] == "watching"
    _ok("event_observation_created")


def test_event_observation_status_changed(conn):
    oid = _observation(conn)
    tid = _thesis(conn)
    _exec(conn, "INSERT INTO observation_thesis_links (observation_id, thesis_id) VALUES (?,?)", (oid, tid))
    _exec(conn, "UPDATE observation SET status = 'taken' WHERE id = ?", (oid,))
    row = _row(conn, "SELECT event_type, old_status, new_status FROM entity_events "
                      "WHERE entity_id = ? AND event_type = 'status_changed'", (oid,))
    assert row is not None
    assert row[1] == "watching" and row[2] == "taken"
    _ok("event_observation_status_changed")


def test_event_setup_created(conn):
    sid = _setup(conn)
    row = _row(conn, "SELECT entity_type, event_type FROM entity_events WHERE entity_id = ?", (sid,))
    assert row is not None
    assert row[0] == "setup" and row[1] == "created"
    _ok("event_setup_created")


def test_event_review_phase1_filed(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    rid = _uid()
    _exec(conn, "INSERT INTO review (id, trade_id, closed_at, entry_fill, exit_fill, "
                "thesis_at_entry, exit_rules_as_written, what_i_actually_did, emotional_state, rules_followed) "
                "VALUES (?,?,'2026-02-01','fill','fill','snap','rules','did','calm','yes')", (rid, trid))
    row = _row(conn, "SELECT entity_type, event_type FROM entity_events WHERE entity_id = ?", (rid,))
    assert row is not None
    assert row[0] == "review" and row[1] == "filed"
    _ok("event_review_phase1_filed")


def test_event_review_phase2_filed(conn):
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    trid = _trade(conn, tid)
    rid = _uid()
    past = "2020-01-01T00:00:00Z"
    _exec(conn, "INSERT INTO review (id, trade_id, closed_at, entry_fill, exit_fill, "
                "thesis_at_entry, exit_rules_as_written, what_i_actually_did, emotional_state, rules_followed, "
                "locked_at) VALUES (?,?,'2026-02-01','fill','fill','snap','rules','did','calm','yes',?)",
          (rid, trid, past))
    _exec(conn, "UPDATE review SET zone_3_clear = 1 WHERE id = ?", (rid,))
    _exec(conn, "UPDATE review SET phase2_created_at = '2026-02-05T00:00:00Z', "
                "mistake_type = 'type_1', analysis = 'analysis', single_update = 'update', "
                "what_not_changing = 'nothing' WHERE id = ?", (rid,))
    row = _row(conn, "SELECT event_type, new_status FROM entity_events "
                      "WHERE entity_id = ? AND new_status = 'phase2'", (rid,))
    assert row is not None
    assert row[0] == "filed"
    _ok("event_review_phase2_filed")


# -- 10. Views ----------------------------------------------------------------

def test_thesis_lifespan_view(conn):
    """Thesis lifespan view returns one row per terminal thesis with correct lifespan."""
    tid = _full_thesis(conn)
    # Transition to invalidated
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-001' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'invalidated' WHERE id = ?", (tid,))
    rows = _all(conn, "SELECT id, status, lifespan_days FROM thesis_lifespan WHERE id = ?", (tid,))
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    assert rows[0][1] == "invalidated"
    assert rows[0][2] >= 0, "lifespan_days should be non-negative"

    # Now rebuild: invalidated -> building -> ready -> active -> archived
    _exec(conn, "UPDATE thesis SET status = 'building' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'ready' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'active', linked_trade_id = 'TR-002' WHERE id = ?", (tid,))
    _exec(conn, "UPDATE thesis SET status = 'archived' WHERE id = ?", (tid,))
    rows2 = _all(conn, "SELECT id, status, lifespan_days FROM thesis_lifespan WHERE id = ?", (tid,))
    assert len(rows2) == 1, f"Expected 1 row after rebuild, got {len(rows2)}"
    assert rows2[0][1] == "archived"
    _ok("thesis_lifespan_view")


def test_stale_theses_view(conn):
    """Theses in ready/active with last_updated > 7 days ago appear in stale_theses."""
    # Insert thesis with old last_updated
    tid = _uid()
    conn2 = _fresh_db()
    _exec(conn2, "INSERT INTO thesis (id, instrument, status, narrative, win_condition, last_updated) "
                 "VALUES (?,?,'ready','n','wc','2020-01-01T00:00:00Z')", (tid, "SPY"))
    rows = _all(conn2, "SELECT id FROM stale_theses WHERE id = ?", (tid,))
    assert len(rows) == 1, f"Expected stale_theses row, got {len(rows)}"
    conn2.close()
    _ok("stale_theses_view")


def test_stale_canvases_view(conn):
    cid = _canvas(conn, last_reviewed="2020-01-01T00:00:00Z")
    rows = _all(conn, "SELECT id FROM stale_canvases WHERE id = ?", (cid,))
    assert len(rows) == 1
    _ok("stale_canvases_view")


def test_stale_invalidation_conditions_view(conn):
    cid = _canvas(conn)
    _exec(conn, "INSERT INTO canvas_invalidation_conditions "
                "(id, canvas_id, condition, type, probability, lead_time_days, last_assessed) "
                "VALUES (?,?,?,'necessary','low',5,'2020-01-01')", (_uid(), cid, "cond"))
    rows = _all(conn, "SELECT id FROM stale_invalidation_conditions WHERE canvas_id = ?", (cid,))
    assert len(rows) == 1
    _ok("stale_invalidation_conditions_view")


def test_active_surveillance_view(conn):
    """active_surveillance now queries observation (watching state) with observation_thesis_links and observation_setup_links."""
    oid = _observation(conn)
    tid = _thesis(conn)
    sid = _setup(conn)
    _exec(conn, "INSERT INTO observation_thesis_links (observation_id, thesis_id) VALUES (?,?)", (oid, tid))
    _exec(conn, "INSERT INTO observation_setup_links (observation_id, setup_id) VALUES (?,?)", (oid, sid))
    rows = _all(conn, "SELECT id, thesis_link_count, setup_link_count FROM active_surveillance")
    assert len(rows) == 1
    assert rows[0][0] == oid
    assert rows[0][1] == 1  # thesis_link_count
    assert rows[0][2] == 1  # setup_link_count
    _ok("active_surveillance_view")


def test_active_surveillance_excludes_taken(conn):
    oid = _observation(conn)
    tid = _thesis(conn)
    _exec(conn, "INSERT INTO observation_thesis_links (observation_id, thesis_id) VALUES (?,?)", (oid, tid))
    _exec(conn, "UPDATE observation SET status = 'taken' WHERE id = ?", (oid,))
    rows = _all(conn, "SELECT id FROM active_surveillance")
    assert len(rows) == 0
    _ok("active_surveillance_excludes_taken")


def test_overdue_actions_view(conn):
    aid = _uid()
    _exec(conn, "INSERT INTO action (id, action, due_date, status) VALUES (?,?,'2020-01-01','open')",
          (aid, "overdue action"))
    rows = _all(conn, "SELECT id FROM overdue_actions WHERE id = ?", (aid,))
    assert len(rows) == 1
    _ok("overdue_actions_view")


def test_passed_observation_analysis_view(conn):
    """passed_observation_analysis view queries observation (not setup)."""
    oid1 = _observation(conn)
    _exec(conn, "UPDATE observation SET status = 'passed', passed_reason = 'r', passed_reason_type = 'analytical' "
                "WHERE id = ?", (oid1,))
    oid2 = _observation(conn)
    _exec(conn, "UPDATE observation SET status = 'passed', passed_reason = 'r', passed_reason_type = 'psychological' "
                "WHERE id = ?", (oid2,))
    rows = _all(conn, "SELECT passed_reason_type, count FROM passed_observation_analysis ORDER BY passed_reason_type")
    types = {r[0]: r[1] for r in rows}
    assert types.get("analytical") == 1
    assert types.get("psychological") == 1
    _ok("passed_observation_analysis_view")


# -- 11. New tests added for swap ---------------------------------------------

def test_setup_thesis_links_junction(conn):
    """setup_thesis_links is a free many-to-many junction with no status gate.
    Under the new schema setup is the analytical entity: linking to thesis requires
    no prior status transition (contrast with the old observation_taken_gate which
    requires observation_thesis_links before status='taken').
    Also verifies FK integrity on both columns."""
    sid = _setup(conn)
    tid1 = _thesis(conn)
    tid2 = _thesis(conn)

    # Link setup to thesis with no status precondition — must succeed with no trigger fire
    _exec(conn, "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?,?)", (sid, tid1))
    _exec(conn, "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?,?)", (sid, tid2))
    count = _val(conn, "SELECT COUNT(*) FROM setup_thesis_links WHERE setup_id = ?", (sid,))
    assert count == 2, f"Expected 2 links, got {count}"

    # setup remains append-only regardless of thesis links — no status column exists
    try:
        _exec(conn, "UPDATE setup SET setup_note = 'modified' WHERE id = ?", (sid,))
        raise Abort("setup should still be append-only after thesis links inserted")
    except sqlite3.IntegrityError:
        pass

    # FK enforcement: nonexistent thesis_id must be rejected
    try:
        _exec(conn, "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?,?)", (sid, "NO-EXIST"))
        raise Abort("should have raised on bad thesis_id FK")
    except sqlite3.IntegrityError:
        pass

    # FK enforcement: nonexistent setup_id must be rejected
    try:
        _exec(conn, "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?,?)", ("NO-EXIST", tid1))
        raise Abort("should have raised on bad setup_id FK")
    except sqlite3.IntegrityError:
        pass

    _ok("setup_thesis_links_junction")


def test_observation_append_only_blocked(conn):
    """observation is NOT append-only — UPDATE succeeds (state machine allows note updates).
    setup IS append-only — UPDATE raises."""
    oid = _observation(conn)
    # observation note update must succeed (no append-only trigger on observation)
    _exec(conn, "UPDATE observation SET note = 'changed note' WHERE id = ?", (oid,))
    assert _val(conn, "SELECT note FROM observation WHERE id = ?", (oid,)) == "changed note"

    # setup update must raise
    sid = _setup(conn)
    try:
        _exec(conn, "UPDATE setup SET setup_note = 'changed' WHERE id = ?", (sid,))
        raise Abort("should have raised for setup update")
    except sqlite3.IntegrityError:
        pass
    _ok("observation_append_only_blocked")


# -- 12. Trade idea state machine tests ---------------------------------------

def test_trade_idea_creation(conn):
    """Idea trade inserts with no thesis_id — succeeds."""
    tid = _idea(conn)
    row = _row(conn, "SELECT status, thesis_id FROM trade WHERE id = ?", (tid,))
    assert row[0] == 'idea'
    assert row[1] is None
    _ok("test_trade_idea_creation")


def test_trade_idea_to_active_gate_no_thesis(conn):
    """idea→active blocked when thesis_id is NULL."""
    tid = _idea(conn)
    try:
        _exec(conn, "UPDATE trade SET status='active' WHERE id=?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError as e:
        assert "thesis_id required" in str(e), f"Wrong error: {e}"
    _ok("test_trade_idea_to_active_gate_no_thesis")


def test_trade_idea_to_active_gate_no_entry_rules(conn):
    """idea→active blocked when entry_rules_stated is NULL."""
    full_tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status='ready' WHERE id=?", (full_tid,))
    tid = _idea(conn)
    _exec(conn,
          "UPDATE trade SET thesis_id=?, exit_rules_stated='xr', "
          "thesis_snapshot='snap' WHERE id=?",
          (full_tid, tid))
    try:
        _exec(conn, "UPDATE trade SET status='active' WHERE id=?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError as e:
        assert "entry_rules_stated required" in str(e), f"Wrong error: {e}"
    _ok("test_trade_idea_to_active_gate_no_entry_rules")


def test_trade_idea_to_active_succeeds(conn):
    """idea→active succeeds when all gate fields are set via UPDATE."""
    full_tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status='ready' WHERE id=?", (full_tid,))
    tid = _idea(conn)
    _exec(conn,
          "UPDATE trade SET thesis_id=?, entry_rules_stated='er', "
          "exit_rules_stated='xr', thesis_snapshot='snap' WHERE id=?",
          (full_tid, tid))
    _exec(conn, "UPDATE trade SET status='active' WHERE id=?", (tid,))
    row = _row(conn, "SELECT status FROM trade WHERE id=?", (tid,))
    assert row[0] == 'active'
    _ok("test_trade_idea_to_active_succeeds")


def test_trade_idea_to_closed_blocked(conn):
    """idea→closed is blocked by trade_state_machine."""
    tid = _idea(conn)
    try:
        _exec(conn, "UPDATE trade SET status='closed' WHERE id=?", (tid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError as e:
        assert "idea may only transition" in str(e), f"Wrong error: {e}"
    _ok("test_trade_idea_to_closed_blocked")


def test_trade_idea_to_discarded(conn):
    """idea→discarded succeeds."""
    tid = _idea(conn)
    _exec(conn, "UPDATE trade SET status='discarded' WHERE id=?", (tid,))
    row = _row(conn, "SELECT status FROM trade WHERE id=?", (tid,))
    assert row[0] == 'discarded'
    _ok("test_trade_idea_to_discarded")


def test_trade_active_to_closed(conn):
    """active→closed succeeds (renamed from open→closed)."""
    full_tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status='ready' WHERE id=?", (full_tid,))
    _exec(conn, "UPDATE thesis SET status='active', linked_trade_id='TR-001' WHERE id=?", (full_tid,))
    trid = _trade(conn, full_tid)
    _exec(conn, "UPDATE trade SET status='closed', closed_at='2026-04-30T00:00:00Z' WHERE id=?", (trid,))
    row = _row(conn, "SELECT status FROM trade WHERE id=?", (trid,))
    assert row[0] == 'closed'
    _ok("test_trade_active_to_closed")


def test_trade_idea_fields_mutable(conn):
    """entry_rules_stated can be updated on an idea row — frozen only after active."""
    tid = _idea(conn)
    _exec(conn, "UPDATE trade SET entry_rules_stated='updated' WHERE id=?", (tid,))
    row = _row(conn, "SELECT entry_rules_stated FROM trade WHERE id=?", (tid,))
    assert row[0] == 'updated'
    _ok("test_trade_idea_fields_mutable")


def test_trade_active_frozen_fields(conn):
    """entry_rules_stated frozen once active — update raises."""
    full_tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status='ready' WHERE id=?", (full_tid,))
    _exec(conn, "UPDATE thesis SET status='active', linked_trade_id='TR-001' WHERE id=?", (full_tid,))
    trid = _trade(conn, full_tid)
    try:
        _exec(conn, "UPDATE trade SET entry_rules_stated='modified' WHERE id=?", (trid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError as e:
        assert "frozen" in str(e), f"Wrong error: {e}"
    _ok("test_trade_active_frozen_fields")


def test_thesis_active_gate_trade_not_active(conn):
    """thesis_active_gate blocks if linked_trade_id references an idea trade."""
    tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status='ready' WHERE id=?", (tid,))
    idea_id = _idea(conn)
    try:
        _exec(conn,
              "UPDATE thesis SET status='active', linked_trade_id=? WHERE id=?",
              (idea_id, tid))
        raise Abort("should have raised")
    except sqlite3.IntegrityError as e:
        assert "active gate" in str(e), f"Wrong error: {e}"
    _ok("test_thesis_active_gate_trade_not_active")


def test_event_trade_created_idea(conn):
    """Event log records new_status='idea' on idea INSERT."""
    tid = _idea(conn)
    row = _row(conn,
               "SELECT entity_type, event_type, new_status FROM entity_events "
               "WHERE entity_id=?", (tid,))
    assert row is not None
    assert row[0] == 'trade' and row[1] == 'created' and row[2] == 'idea'
    _ok("test_event_trade_created_idea")


def test_event_trade_activated(conn):
    """Event log records idea→active status_changed."""
    full_tid = _full_thesis(conn)
    _exec(conn, "UPDATE thesis SET status='ready' WHERE id=?", (full_tid,))
    tid = _idea(conn)
    _exec(conn,
          "UPDATE trade SET thesis_id=?, entry_rules_stated='er', "
          "exit_rules_stated='xr', thesis_snapshot='snap' WHERE id=?",
          (full_tid, tid))
    _exec(conn, "DELETE FROM entity_events")
    _exec(conn, "UPDATE trade SET status='active' WHERE id=?", (tid,))
    row = _row(conn,
               "SELECT event_type, old_status, new_status FROM entity_events "
               "WHERE entity_id=? AND event_type='status_changed'", (tid,))
    assert row is not None
    assert row[1] == 'idea' and row[2] == 'active'
    _ok("test_event_trade_activated")


# -- 13. Insight entity tests ----------------------------------------------------

def test_insight_creation(conn):
    """Insight row inserts with minimal fields (name optional, note required)."""
    _exec(conn,
          "INSERT INTO insight (id, note) VALUES ('INS1','first insight')")
    row = _row(conn, "SELECT note, linked_entity_type FROM insight WHERE id='INS1'")
    assert row[0] == 'first insight'
    assert row[1] is None  # no link
    _ok("test_insight_creation")


def test_insight_with_polymorphic_link(conn):
    """Insight links to canvas via polymorphic columns."""
    _exec(conn,
          "INSERT INTO canvas (id, name, narrative, last_reviewed) "
          "VALUES ('C1','Test canvas','n','2026-01-01')")
    _exec(conn,
          "INSERT INTO insight (id, note, linked_entity_type, linked_entity_id) "
          "VALUES ('INS2','canvas insight','canvas','C1')")
    row = _row(conn,
               "SELECT linked_entity_type, linked_entity_id "
               "FROM insight WHERE id='INS2'")
    assert row[0] == 'canvas'
    assert row[1] == 'C1'
    _ok("test_insight_with_polymorphic_link")


def test_insight_event_log(conn):
    """event_insight_created trigger fires on INSERT and logs to entity_events."""
    _exec(conn, "INSERT INTO insight (id, note) VALUES ('INS3','logged insight')")
    row = _row(conn,
               "SELECT entity_type, event_type FROM entity_events "
               "WHERE entity_id='INS3'")
    assert row is not None, "No entity_events row for insight"
    assert row[0] == 'insight'
    assert row[1] == 'created'
    _ok("test_insight_event_log")


def test_entity_events_accepts_insight(conn):
    """entity_events CHECK constraint now permits entity_type='insight'."""
    _exec(conn, "INSERT INTO insight (id, note) VALUES ('INS4','chk insight')")
    # Direct insert to entity_events with type='insight' must succeed
    _exec(conn,
          "INSERT INTO entity_events (id, entity_type, entity_id, event_type) "
          "VALUES ('EV1','insight','INS4','updated')")
    row = _row(conn,
               "SELECT entity_type FROM entity_events WHERE id='EV1'")
    assert row[0] == 'insight'
    _ok("test_entity_events_accepts_insight")


def test_insight_export_watermark_exists(conn):
    """export_watermarks has a row for insight (6th entry)."""
    row = _row(conn,
               "SELECT entity_type FROM export_watermarks "
               "WHERE entity_type='insight'")
    assert row is not None, "No export_watermark row for insight"
    wm_count = _val(conn, "SELECT COUNT(*) FROM export_watermarks")
    assert wm_count == 6, f"Expected 6 watermarks, got {wm_count}"
    _ok("test_insight_export_watermark_exists")


# -- 11. Summary --------------------------------------------------------------


# =============================================================================
#  TEST RUNNER
# =============================================================================

# All test functions in order
TESTS = [
    # Pre-flight
    test_preflight,
    # 2. Thesis state machine
    test_thesis_state_building_to_ready,
    test_thesis_state_building_invalid,
    test_thesis_state_ready_to_active,
    test_thesis_state_ready_back_to_building,
    test_thesis_state_active_to_invalidated,
    test_thesis_state_active_to_archived,
    test_thesis_state_invalidated_to_building,
    test_thesis_state_archived_terminal,
    # 3. Thesis ready gate
    test_thesis_ready_gate_no_kill_conditions,
    test_thesis_ready_gate_no_decision_points,
    test_thesis_ready_gate_no_worst_case,
    test_thesis_ready_gate_no_canvas_link,
    # Thesis active gate
    test_thesis_active_gate_no_trade_id,
    # 4. Observation state machine (was setup state machine)
    test_observation_state_watching_to_taken,
    test_observation_state_watching_to_passed,
    test_observation_state_taken_is_terminal,
    test_observation_state_passed_is_terminal,
    # Observation gates
    test_observation_taken_gate_no_thesis_link,
    test_observation_passed_gate_no_reason,
    test_observation_passed_gate_no_reason_type,
    # 5. Frozen fields
    test_trade_frozen_entry_rules,
    test_trade_frozen_exit_rules,
    test_trade_frozen_thesis_snapshot,
    test_option_legs_partial_update_ok,
    test_option_legs_partial_update_frozen,
    # 6. Append-only tables
    test_trade_entries_append_only,
    test_trade_exits_append_only,
    test_setup_append_only,
    test_canvas_version_history_append_only,
    test_thesis_version_history_append_only,
    test_option_legs_append_only_delete,
    # 7. Review enforcement
    test_review_emotional_state_single_word_ok,
    test_review_emotional_state_multi_word_insert,
    test_review_emotional_state_multi_word_update,
    test_review_zone3_timelock_block,
    test_review_zone3_timelock_allow,
    test_review_phase2_gate,
    # 8. trade_review_id_fk
    test_trade_review_id_soft_fk,
    # 9. Entity event log
    test_event_canvas_created,
    test_event_canvas_updated,
    test_event_thesis_created,
    test_event_thesis_status_changed,
    test_event_trade_created,
    test_event_trade_closed,
    test_event_observation_created,
    test_event_observation_status_changed,
    test_event_setup_created,
    test_event_review_phase1_filed,
    test_event_review_phase2_filed,
    # 10. Views
    test_thesis_lifespan_view,
    test_stale_theses_view,
    test_stale_canvases_view,
    test_stale_invalidation_conditions_view,
    test_active_surveillance_view,
    test_active_surveillance_excludes_taken,
    test_overdue_actions_view,
    test_passed_observation_analysis_view,
    # 11. New tests for schema swap
    test_setup_thesis_links_junction,
    test_observation_append_only_blocked,
    # 12. Trade idea state machine
    test_trade_idea_creation,
    test_trade_idea_to_active_gate_no_thesis,
    test_trade_idea_to_active_gate_no_entry_rules,
    test_trade_idea_to_active_succeeds,
    test_trade_idea_to_closed_blocked,
    test_trade_idea_to_discarded,
    test_trade_active_to_closed,
    test_trade_idea_fields_mutable,
    test_trade_active_frozen_fields,
    test_thesis_active_gate_trade_not_active,
    test_event_trade_created_idea,
    test_event_trade_activated,
    # 13. Insight entity
    test_insight_creation,
    test_insight_with_polymorphic_link,
    test_insight_event_log,
    test_entity_events_accepts_insight,
    test_insight_export_watermark_exists,
]


def run_tests():
    print(f"\n{'='*60}")
    print(f" Task 003 — State Machine Verification with Seed Data")
    print(f" {len(TESTS)} tests")
    print(f"{'='*60}\n")

    for test_fn in TESTS:
        name = test_fn.__name__
        conn = _fresh_db()
        try:
            test_fn(conn)
        except Abort as exc:
            _fail(name, str(exc))
        except AssertionError as exc:
            _fail(name, str(exc))
        except Exception as exc:
            _fail(name, f"unexpected {type(exc).__name__}: {exc}")
        finally:
            conn.close()

    # -- summary --
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = len(_results) - passed
    print()

    if failed:
        for name, ok, detail in _results:
            if not ok:
                print(f"  X  {name}: {detail}")
        print()

    for name, ok, detail in _results:
        if ok:
            print(f"  +  {name}")

    print(f"\n{'='*60}")
    print(f"  {passed}/{len(_results)} tests passed")
    if failed == 0:
        print(f"  ALL TESTS PASSED")
    print(f"{'='*60}\n")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
