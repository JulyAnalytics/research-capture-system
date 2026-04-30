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


def _setup(conn, **kw):
    sid = kw.get("id", _uid())
    _exec(
        conn,
        "INSERT INTO setup (id, instrument, setup_type, status, note, date) "
        "VALUES (?,?,?,'watching',?,?)",
        (sid, kw.get("instrument", "SPY"), kw.get("setup_type", "breakout"),
         kw.get("note", "n"), kw.get("date", "2026-01-15")),
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
        "INSERT INTO trade (id, thesis_id, instrument_type, entry_rules_stated, exit_rules_stated, "
        "thesis_snapshot, status) VALUES (?,?,'equity',?,?,?,'open')",
        (trid, thesis_id, kw.get("entry_rules", "er"), kw.get("exit_rules", "xr"),
         kw.get("snapshot", "snap")),
    )
    return trid


def _observation(conn, **kw):
    oid = kw.get("id", _uid())
    _exec(
        conn,
        "INSERT INTO observation (id, date, instrument, timeframe, type, observation) "
        "VALUES (?,?,?,?,?,?)",
        (oid, kw.get("date", "2026-01-15"), kw.get("instrument", "SPY"),
         kw.get("timeframe", "4H"), kw.get("type", "technical"), kw.get("observation", "obs")),
    )
    return oid


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
        "canvas_version_history", "setup", "setup_images", "thesis",
        "thesis_kill_conditions_macro", "thesis_kill_conditions_technical",
        "thesis_decision_points", "thesis_linked_canvases", "thesis_version_history",
        "trade", "trade_entries", "trade_exits", "trade_options_meta",
        "trade_option_legs", "observation", "observation_linked_canvases",
        "observation_images", "setup_thesis_links", "setup_observation_links",
        "action", "review", "inbox", "entity_events", "canvas_source_documents",
        "export_watermarks", "failed_exports", "schema_version",
    }
    missing = required_tables - tables
    assert not missing, f"Missing tables: {missing}"

    views = set(r[0] for r in _all(conn, "SELECT name FROM sqlite_master WHERE type='view'"))
    required_views = {
        "stale_canvases", "stale_theses", "stale_invalidation_conditions",
        "overdue_actions", "active_surveillance", "canvas_observation_backlinks",
        "passed_setup_analysis", "passed_setup_detail", "review_mistake_distribution",
        "decision_point_deviations", "options_iv_comparison",
        "invalidation_post_mortem", "thesis_lifespan", "review_lag",
    }
    missing_v = required_views - views
    assert not missing_v, f"Missing views: {missing_v}"

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


# -- 4. Setup State Machine ---------------------------------------------------

def test_setup_state_watching_to_taken(conn):
    sid = _setup(conn)
    tid = _thesis(conn)
    _exec(conn, "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?,?)", (sid, tid))
    _exec(conn, "UPDATE setup SET status = 'taken' WHERE id = ?", (sid,))
    assert _val(conn, "SELECT status FROM setup WHERE id = ?", (sid,)) == "taken"
    _ok("setup_state_watching_to_taken")


def test_setup_state_watching_to_passed(conn):
    sid = _setup(conn)
    _exec(conn, "UPDATE setup SET status = 'passed', passed_reason = 'no conv', "
                "passed_reason_type = 'analytical' WHERE id = ?", (sid,))
    assert _val(conn, "SELECT status FROM setup WHERE id = ?", (sid,)) == "passed"
    _ok("setup_state_watching_to_passed")


def test_setup_state_taken_is_terminal(conn):
    sid = _setup(conn)
    tid = _thesis(conn)
    _exec(conn, "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?,?)", (sid, tid))
    _exec(conn, "UPDATE setup SET status = 'taken' WHERE id = ?", (sid,))
    try:
        _exec(conn, "UPDATE setup SET status = 'watching' WHERE id = ?", (sid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("setup_state_taken_is_terminal")


def test_setup_state_passed_is_terminal(conn):
    sid = _setup(conn)
    _exec(conn, "UPDATE setup SET status = 'passed', passed_reason = 'r', "
                "passed_reason_type = 'psychological' WHERE id = ?", (sid,))
    try:
        _exec(conn, "UPDATE setup SET status = 'watching' WHERE id = ?", (sid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("setup_state_passed_is_terminal")


def test_setup_taken_gate_no_thesis_link(conn):
    sid = _setup(conn)
    try:
        _exec(conn, "UPDATE setup SET status = 'taken' WHERE id = ?", (sid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("setup_taken_gate_no_thesis_link")


def test_setup_passed_gate_no_reason(conn):
    sid = _setup(conn)
    try:
        _exec(conn, "UPDATE setup SET status = 'passed', passed_reason_type = 'analytical' WHERE id = ?", (sid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("setup_passed_gate_no_reason")


def test_setup_passed_gate_no_reason_type(conn):
    sid = _setup(conn)
    try:
        _exec(conn, "UPDATE setup SET status = 'passed', passed_reason = 'reason' WHERE id = ?", (sid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("setup_passed_gate_no_reason_type")


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


def test_observation_append_only(conn):
    oid = _observation(conn)
    try:
        _exec(conn, "UPDATE observation SET observation = 'modified' WHERE id = ?", (oid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    try:
        _exec(conn, "DELETE FROM observation WHERE id = ?", (oid,))
        raise Abort("should have raised")
    except sqlite3.IntegrityError:
        pass
    _ok("observation_append_only")


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
    assert row[0] == "trade" and row[1] == "created" and row[2] == "open"
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
    assert row[0] == "trade" and row[2] == "open" and row[3] == "closed"
    _ok("event_trade_closed")


def test_event_observation_created(conn):
    oid = _observation(conn)
    row = _row(conn, "SELECT entity_type, event_type FROM entity_events WHERE entity_id = ?", (oid,))
    assert row is not None, "no event logged for observation"
    assert row[0] == "observation" and row[1] == "created"
    _ok("event_observation_created")


def test_event_setup_created(conn):
    sid = _setup(conn)
    row = _row(conn, "SELECT entity_type, event_type, new_status FROM entity_events WHERE entity_id = ?", (sid,))
    assert row is not None
    assert row[0] == "setup" and row[1] == "created" and row[2] == "watching"
    _ok("event_setup_created")


def test_event_setup_status_changed(conn):
    sid = _setup(conn)
    tid = _thesis(conn)
    _exec(conn, "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?,?)", (sid, tid))
    _exec(conn, "UPDATE setup SET status = 'taken' WHERE id = ?", (sid,))
    row = _row(conn, "SELECT event_type, old_status, new_status FROM entity_events "
                      "WHERE entity_id = ? AND event_type = 'status_changed'", (sid,))
    assert row is not None
    assert row[1] == "watching" and row[2] == "taken"
    _ok("event_setup_status_changed")


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
    sid = _setup(conn)
    tid = _thesis(conn)
    oid = _observation(conn)
    _exec(conn, "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?,?)", (sid, tid))
    _exec(conn, "INSERT INTO setup_observation_links (setup_id, observation_id) VALUES (?,?)", (sid, oid))
    rows = _all(conn, "SELECT id, thesis_link_count, observation_link_count FROM active_surveillance")
    assert len(rows) == 1
    assert rows[0][0] == sid
    assert rows[0][1] == 1  # thesis_link_count
    assert rows[0][2] == 1  # observation_link_count
    _ok("active_surveillance_view")


def test_active_surveillance_excludes_taken(conn):
    sid = _setup(conn)
    tid = _thesis(conn)
    _exec(conn, "INSERT INTO setup_thesis_links (setup_id, thesis_id) VALUES (?,?)", (sid, tid))
    _exec(conn, "UPDATE setup SET status = 'taken' WHERE id = ?", (sid,))
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


def test_passed_setup_analysis_view(conn):
    sid1 = _setup(conn)
    _exec(conn, "UPDATE setup SET status = 'passed', passed_reason = 'r', passed_reason_type = 'analytical' "
                "WHERE id = ?", (sid1,))
    sid2 = _setup(conn)
    _exec(conn, "UPDATE setup SET status = 'passed', passed_reason = 'r', passed_reason_type = 'psychological' "
                "WHERE id = ?", (sid2,))
    rows = _all(conn, "SELECT passed_reason_type, count FROM passed_setup_analysis ORDER BY passed_reason_type")
    types = {r[0]: r[1] for r in rows}
    assert types.get("analytical") == 1
    assert types.get("psychological") == 1
    _ok("passed_setup_analysis_view")


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
    # 4. Setup state machine
    test_setup_state_watching_to_taken,
    test_setup_state_watching_to_passed,
    test_setup_state_taken_is_terminal,
    test_setup_state_passed_is_terminal,
    # Setup gates
    test_setup_taken_gate_no_thesis_link,
    test_setup_passed_gate_no_reason,
    test_setup_passed_gate_no_reason_type,
    # 5. Frozen fields
    test_trade_frozen_entry_rules,
    test_trade_frozen_exit_rules,
    test_trade_frozen_thesis_snapshot,
    test_option_legs_partial_update_ok,
    test_option_legs_partial_update_frozen,
    # 6. Append-only tables
    test_trade_entries_append_only,
    test_trade_exits_append_only,
    test_observation_append_only,
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
    test_event_setup_created,
    test_event_setup_status_changed,
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
    test_passed_setup_analysis_view,
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
