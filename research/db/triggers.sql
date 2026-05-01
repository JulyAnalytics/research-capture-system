-- db/triggers.sql
-- Loaded via executescript() at startup.
-- Each trigger is preceded by DROP TRIGGER IF EXISTS so definition changes
-- take effect on the next startup without a migration.

-- ─────────────────────────────────────────
-- THESIS STATE MACHINE
-- ─────────────────────────────────────────

DROP TRIGGER IF EXISTS thesis_state_machine;
CREATE TRIGGER thesis_state_machine
BEFORE UPDATE OF status ON thesis
WHEN OLD.status != NEW.status
BEGIN
    SELECT CASE
        WHEN OLD.status = 'building'    AND NEW.status NOT IN ('ready')
            THEN RAISE(ABORT, 'invalid transition: building → ready only')
        WHEN OLD.status = 'ready'       AND NEW.status NOT IN ('building', 'active')
            THEN RAISE(ABORT, 'invalid transition: ready → building or active only')
        WHEN OLD.status = 'active'      AND NEW.status NOT IN ('invalidated', 'archived')
            THEN RAISE(ABORT, 'invalid transition: active → invalidated or archived only')
        WHEN OLD.status = 'invalidated' AND NEW.status NOT IN ('building')
            THEN RAISE(ABORT, 'invalid transition: invalidated → building only')
        WHEN OLD.status = 'archived'
            THEN RAISE(ABORT, 'invalid transition: archived is terminal')
    END;
END;

DROP TRIGGER IF EXISTS thesis_ready_gate;
CREATE TRIGGER thesis_ready_gate
BEFORE UPDATE OF status ON thesis
WHEN NEW.status = 'ready' AND OLD.status = 'building'
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM thesis_kill_conditions_macro WHERE thesis_id = NEW.id) = 0
            THEN RAISE(ABORT, 'ready gate: no macro kill conditions')
        WHEN (SELECT COUNT(*) FROM thesis_decision_points WHERE thesis_id = NEW.id) = 0
            THEN RAISE(ABORT, 'ready gate: no decision points')
        WHEN (NEW.worst_case_dollar IS NULL OR NEW.worst_case_dollar <= 0)
            THEN RAISE(ABORT, 'ready gate: worst_case_dollar must be positive')
        WHEN (SELECT COUNT(*) FROM thesis_linked_canvases WHERE thesis_id = NEW.id) = 0
            THEN RAISE(ABORT, 'ready gate: must link at least one canvas')
    END;
END;

DROP TRIGGER IF EXISTS thesis_active_gate;
CREATE TRIGGER thesis_active_gate
BEFORE UPDATE OF status ON thesis
WHEN NEW.status = 'active'
BEGIN
    SELECT CASE
        WHEN NEW.linked_trade_id IS NULL
            THEN RAISE(ABORT, 'active gate: linked_trade_id required')
        WHEN (SELECT status FROM trade WHERE id = NEW.linked_trade_id) != 'active'
            THEN RAISE(ABORT, 'active gate: linked trade must be in active status')
    END;
END;

DROP TRIGGER IF EXISTS thesis_touch_on_macro_kill;
CREATE TRIGGER thesis_touch_on_macro_kill
AFTER INSERT ON thesis_kill_conditions_macro
BEGIN
    UPDATE thesis SET last_updated = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = NEW.thesis_id;
END;

DROP TRIGGER IF EXISTS thesis_touch_on_technical_kill;
CREATE TRIGGER thesis_touch_on_technical_kill
AFTER INSERT ON thesis_kill_conditions_technical
BEGIN
    UPDATE thesis SET last_updated = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = NEW.thesis_id;
END;

DROP TRIGGER IF EXISTS thesis_touch_on_decision_point;
CREATE TRIGGER thesis_touch_on_decision_point
AFTER INSERT ON thesis_decision_points
BEGIN
    UPDATE thesis SET last_updated = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = NEW.thesis_id;
END;

DROP TRIGGER IF EXISTS thesis_touch_on_canvas_link;
CREATE TRIGGER thesis_touch_on_canvas_link
AFTER INSERT ON thesis_linked_canvases
BEGIN
    UPDATE thesis SET last_updated = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = NEW.thesis_id;
END;

DROP TRIGGER IF EXISTS thesis_touch_on_version_history;
CREATE TRIGGER thesis_touch_on_version_history
AFTER INSERT ON thesis_version_history
BEGIN
    UPDATE thesis SET last_updated = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    WHERE id = NEW.thesis_id;
END;

-- ─────────────────────────────────────────
-- OBSERVATION STATE MACHINE
-- (observation is now the watching/taken/passed entity)
-- ─────────────────────────────────────────

DROP TRIGGER IF EXISTS setup_state_machine;
DROP TRIGGER IF EXISTS observation_state_machine;
CREATE TRIGGER observation_state_machine
BEFORE UPDATE OF status ON observation
WHEN OLD.status != NEW.status
BEGIN
    SELECT CASE
        WHEN OLD.status IN ('taken', 'passed')
            THEN RAISE(ABORT, 'observation: taken and passed are terminal states')
        WHEN OLD.status = 'watching' AND NEW.status NOT IN ('taken', 'passed')
            THEN RAISE(ABORT, 'observation: invalid transition from watching — must be taken or passed')
    END;
END;

DROP TRIGGER IF EXISTS setup_taken_gate;
DROP TRIGGER IF EXISTS observation_taken_gate;
CREATE TRIGGER observation_taken_gate
BEFORE UPDATE OF status ON observation
WHEN NEW.status = 'taken'
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM observation_thesis_links
              WHERE observation_id = NEW.id) = 0
            THEN RAISE(ABORT, 'observation taken gate: must have at least one linked thesis')
    END;
END;

DROP TRIGGER IF EXISTS setup_passed_gate;
DROP TRIGGER IF EXISTS observation_passed_gate;
CREATE TRIGGER observation_passed_gate
BEFORE UPDATE OF status ON observation
WHEN NEW.status = 'passed'
BEGIN
    SELECT CASE
        WHEN NEW.passed_reason IS NULL OR trim(NEW.passed_reason) = ''
            THEN RAISE(ABORT, 'observation passed gate: passed_reason required')
        WHEN NEW.passed_reason_type IS NULL
            THEN RAISE(ABORT, 'observation passed gate: passed_reason_type required')
    END;
END;

-- ─────────────────────────────────────────
-- TRADE
-- ─────────────────────────────────────────

DROP TRIGGER IF EXISTS trade_state_machine;
CREATE TRIGGER trade_state_machine
BEFORE UPDATE OF status ON trade
WHEN OLD.status != NEW.status
BEGIN
    SELECT CASE
        WHEN OLD.status IN ('closed', 'discarded')
            THEN RAISE(ABORT, 'trade: closed and discarded are terminal states')
        WHEN OLD.status = 'idea' AND NEW.status NOT IN ('active', 'discarded')
            THEN RAISE(ABORT, 'trade: idea may only transition to active or discarded')
        WHEN OLD.status = 'active' AND NEW.status NOT IN ('closed')
            THEN RAISE(ABORT, 'trade: active may only transition to closed')
    END;
END;

DROP TRIGGER IF EXISTS trade_active_gate;
CREATE TRIGGER trade_active_gate
BEFORE UPDATE OF status ON trade
WHEN NEW.status = 'active'
BEGIN
    SELECT CASE
        WHEN NEW.thesis_id IS NULL
            THEN RAISE(ABORT, 'trade active gate: thesis_id required')
        WHEN NEW.entry_rules_stated IS NULL OR trim(NEW.entry_rules_stated) = ''
            THEN RAISE(ABORT, 'trade active gate: entry_rules_stated required')
        WHEN NEW.exit_rules_stated IS NULL OR trim(NEW.exit_rules_stated) = ''
            THEN RAISE(ABORT, 'trade active gate: exit_rules_stated required')
        WHEN NEW.thesis_snapshot IS NULL OR trim(NEW.thesis_snapshot) = ''
            THEN RAISE(ABORT, 'trade active gate: thesis_snapshot required')
    END;
END;

DROP TRIGGER IF EXISTS trade_review_id_fk;
CREATE TRIGGER trade_review_id_fk
BEFORE UPDATE OF review_id ON trade
WHEN NEW.review_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM review WHERE id = NEW.review_id) = 0
            THEN RAISE(ABORT, 'trade.review_id: referenced review does not exist')
    END;
END;

-- ─────────────────────────────────────────
-- ACTION
-- ─────────────────────────────────────────

DROP TRIGGER IF EXISTS action_cancel_note_required;
CREATE TRIGGER action_cancel_note_required
BEFORE UPDATE OF status ON action
WHEN NEW.status = 'cancelled'
BEGIN
    SELECT CASE
        WHEN (NEW.cancellation_note IS NULL OR trim(NEW.cancellation_note) = '')
            THEN RAISE(ABORT, 'cancel gate: cancellation_note required')
    END;
END;

-- ─────────────────────────────────────────
-- REVIEW ENFORCEMENT
-- ─────────────────────────────────────────

DROP TRIGGER IF EXISTS review_zone3_timelock;
CREATE TRIGGER review_zone3_timelock
BEFORE UPDATE OF zone_3_clear ON review
WHEN NEW.zone_3_clear = 1
BEGIN
    SELECT CASE
        WHEN datetime('now') < datetime(OLD.locked_at, '+24 hours')
            THEN RAISE(ABORT, 'time-lock: zone 3 clearance cannot be filed within 24 hours of Phase 1')
    END;
END;

DROP TRIGGER IF EXISTS review_phase2_zone3_gate;
CREATE TRIGGER review_phase2_zone3_gate
BEFORE UPDATE OF phase2_created_at ON review
WHEN NEW.phase2_created_at IS NOT NULL
BEGIN
    SELECT CASE
        WHEN (OLD.zone_3_clear IS NULL OR OLD.zone_3_clear = 0)
            THEN RAISE(ABORT, 'phase2 gate: zone_3_clear must be committed before filing analysis')
    END;
END;

-- Emotional state: single word — enforced on INSERT and UPDATE
DROP TRIGGER IF EXISTS review_emotional_state_one_word_ins;
CREATE TRIGGER review_emotional_state_one_word_ins
BEFORE INSERT ON review
WHEN instr(trim(NEW.emotional_state), ' ') > 0
BEGIN
    SELECT RAISE(ABORT, 'emotional_state must be a single word');
END;

DROP TRIGGER IF EXISTS review_emotional_state_one_word_upd;
CREATE TRIGGER review_emotional_state_one_word_upd
BEFORE UPDATE OF emotional_state ON review
WHEN instr(trim(NEW.emotional_state), ' ') > 0
BEGIN
    SELECT RAISE(ABORT, 'emotional_state must be a single word');
END;

-- ─────────────────────────────────────────
-- FROZEN FIELDS
-- ─────────────────────────────────────────

DROP TRIGGER IF EXISTS trade_rules_frozen;
DROP TRIGGER IF EXISTS trade_frozen_entry_rules;
CREATE TRIGGER trade_frozen_entry_rules
BEFORE UPDATE OF entry_rules_stated ON trade
WHEN OLD.status = 'active'
BEGIN
    SELECT RAISE(ABORT, 'trade: entry_rules_stated is frozen once active');
END;

DROP TRIGGER IF EXISTS trade_frozen_exit_rules;
CREATE TRIGGER trade_frozen_exit_rules
BEFORE UPDATE OF exit_rules_stated ON trade
WHEN OLD.status = 'active'
BEGIN
    SELECT RAISE(ABORT, 'trade: exit_rules_stated is frozen once active');
END;

DROP TRIGGER IF EXISTS trade_snapshot_frozen;
DROP TRIGGER IF EXISTS trade_frozen_thesis_snapshot;
CREATE TRIGGER trade_frozen_thesis_snapshot
BEFORE UPDATE OF thesis_snapshot ON trade
WHEN OLD.status = 'active'
BEGIN
    SELECT RAISE(ABORT, 'trade: thesis_snapshot is frozen once active');
END;

-- ─────────────────────────────────────────
-- APPEND-ONLY TABLES
-- ─────────────────────────────────────────

DROP TRIGGER IF EXISTS ao_trade_entries_upd;
CREATE TRIGGER ao_trade_entries_upd BEFORE UPDATE ON trade_entries
BEGIN SELECT RAISE(ABORT, 'trade_entries is append-only'); END;
DROP TRIGGER IF EXISTS ao_trade_entries_del;
CREATE TRIGGER ao_trade_entries_del BEFORE DELETE ON trade_entries
BEGIN SELECT RAISE(ABORT, 'trade_entries is append-only'); END;

DROP TRIGGER IF EXISTS ao_trade_exits_upd;
CREATE TRIGGER ao_trade_exits_upd BEFORE UPDATE ON trade_exits
BEGIN SELECT RAISE(ABORT, 'trade_exits is append-only'); END;
DROP TRIGGER IF EXISTS ao_trade_exits_del;
CREATE TRIGGER ao_trade_exits_del BEFORE DELETE ON trade_exits
BEGIN SELECT RAISE(ABORT, 'trade_exits is append-only'); END;

DROP TRIGGER IF EXISTS ao_observation_upd;
DROP TRIGGER IF EXISTS ao_observation_del;
DROP TRIGGER IF EXISTS setup_append_only_update;
DROP TRIGGER IF EXISTS setup_append_only_delete;
CREATE TRIGGER setup_append_only_update BEFORE UPDATE ON setup
BEGIN SELECT RAISE(ABORT, 'setup is append-only'); END;
CREATE TRIGGER setup_append_only_delete BEFORE DELETE ON setup
BEGIN SELECT RAISE(ABORT, 'setup is append-only'); END;

DROP TRIGGER IF EXISTS ao_canvas_vh_upd;
CREATE TRIGGER ao_canvas_vh_upd BEFORE UPDATE ON canvas_version_history
BEGIN SELECT RAISE(ABORT, 'canvas_version_history is append-only'); END;
DROP TRIGGER IF EXISTS ao_canvas_vh_del;
CREATE TRIGGER ao_canvas_vh_del BEFORE DELETE ON canvas_version_history
BEGIN SELECT RAISE(ABORT, 'canvas_version_history is append-only'); END;

DROP TRIGGER IF EXISTS ao_thesis_vh_upd;
CREATE TRIGGER ao_thesis_vh_upd BEFORE UPDATE ON thesis_version_history
BEGIN SELECT RAISE(ABORT, 'thesis_version_history is append-only'); END;
DROP TRIGGER IF EXISTS ao_thesis_vh_del;
CREATE TRIGGER ao_thesis_vh_del BEFORE DELETE ON thesis_version_history
BEGIN SELECT RAISE(ABORT, 'thesis_version_history is append-only'); END;

DROP TRIGGER IF EXISTS option_legs_partial_update;
CREATE TRIGGER option_legs_partial_update
BEFORE UPDATE ON trade_option_legs
WHEN (OLD.direction != NEW.direction OR OLD.type != NEW.type OR
      OLD.strike != NEW.strike OR OLD.expiry != NEW.expiry OR
      OLD.contracts != NEW.contracts OR OLD.entry_premium != NEW.entry_premium OR
      OLD.date_opened != NEW.date_opened)
BEGIN
    SELECT RAISE(ABORT, 'trade_option_legs: only exit_premium and date_closed may be updated');
END;

DROP TRIGGER IF EXISTS ao_option_legs_del;
CREATE TRIGGER ao_option_legs_del BEFORE DELETE ON trade_option_legs
BEGIN SELECT RAISE(ABORT, 'trade_option_legs is append-only'); END;

-- ─────────────────────────────────────────
-- ENTITY EVENT LOG TRIGGERS
-- One AFTER trigger per significant state transition.
-- Fire after state machine BEFORE triggers have validated the transition.
-- Purely observational — no logic changes to state machines.
-- Trade events are logged here but not consumed by the exporter (see Design Decision 12).
-- ─────────────────────────────────────────

DROP TRIGGER IF EXISTS event_canvas_created;
CREATE TRIGGER event_canvas_created
AFTER INSERT ON canvas
BEGIN
    INSERT INTO entity_events (id, entity_type, entity_id, event_type, new_status)
    VALUES (lower(hex(randomblob(16))), 'canvas', NEW.id, 'created', NEW.status);
END;

DROP TRIGGER IF EXISTS event_canvas_updated;
CREATE TRIGGER event_canvas_updated
AFTER UPDATE OF last_reviewed ON canvas
BEGIN
    INSERT INTO entity_events (id, entity_type, entity_id, event_type)
    VALUES (lower(hex(randomblob(16))), 'canvas', NEW.id, 'updated');
END;

DROP TRIGGER IF EXISTS event_thesis_created;
CREATE TRIGGER event_thesis_created
AFTER INSERT ON thesis
BEGIN
    INSERT INTO entity_events (id, entity_type, entity_id, event_type, new_status)
    VALUES (lower(hex(randomblob(16))), 'thesis', NEW.id, 'created', NEW.status);
END;

DROP TRIGGER IF EXISTS event_thesis_status_changed;
CREATE TRIGGER event_thesis_status_changed
AFTER UPDATE OF status ON thesis
WHEN OLD.status != NEW.status
BEGIN
    INSERT INTO entity_events (
        id, entity_type, entity_id, event_type, old_status, new_status
    ) VALUES (
        lower(hex(randomblob(16))), 'thesis', NEW.id,
        'status_changed', OLD.status, NEW.status
    );
END;

DROP TRIGGER IF EXISTS event_trade_created;
CREATE TRIGGER event_trade_created
AFTER INSERT ON trade
BEGIN
    INSERT INTO entity_events (id, entity_type, entity_id, event_type, new_status)
    VALUES (lower(hex(randomblob(16))), 'trade', NEW.id, 'created', NEW.status);
END;

DROP TRIGGER IF EXISTS event_trade_closed;
CREATE TRIGGER event_trade_closed
AFTER UPDATE OF status ON trade
WHEN NEW.status = 'closed'
BEGIN
    INSERT INTO entity_events (
        id, entity_type, entity_id, event_type, old_status, new_status
    ) VALUES (
        lower(hex(randomblob(16))), 'trade', NEW.id,
        'status_changed', OLD.status, NEW.status
    );
END;

DROP TRIGGER IF EXISTS event_trade_activated;
CREATE TRIGGER event_trade_activated
AFTER UPDATE OF status ON trade
WHEN NEW.status = 'active' AND OLD.status = 'idea'
BEGIN
    INSERT INTO entity_events (
        id, entity_type, entity_id, event_type, old_status, new_status
    ) VALUES (
        lower(hex(randomblob(16))), 'trade', NEW.id,
        'status_changed', 'idea', 'active'
    );
END;

DROP TRIGGER IF EXISTS event_trade_discarded;
CREATE TRIGGER event_trade_discarded
AFTER UPDATE OF status ON trade
WHEN NEW.status = 'discarded'
BEGIN
    INSERT INTO entity_events (
        id, entity_type, entity_id, event_type, old_status, new_status
    ) VALUES (
        lower(hex(randomblob(16))), 'trade', NEW.id,
        'status_changed', OLD.status, 'discarded'
    );
END;

DROP TRIGGER IF EXISTS event_observation_created;
CREATE TRIGGER event_observation_created
AFTER INSERT ON observation
BEGIN
    INSERT INTO entity_events (id, entity_type, entity_id, event_type, new_status)
    VALUES (lower(hex(randomblob(16))), 'observation', NEW.id, 'created', NEW.status);
END;

DROP TRIGGER IF EXISTS event_observation_status_changed;
CREATE TRIGGER event_observation_status_changed
AFTER UPDATE OF status ON observation
WHEN OLD.status != NEW.status
BEGIN
    INSERT INTO entity_events (
        id, entity_type, entity_id, event_type, old_status, new_status
    ) VALUES (
        lower(hex(randomblob(16))), 'observation', NEW.id,
        'status_changed', OLD.status, NEW.status
    );
END;

DROP TRIGGER IF EXISTS event_setup_created;
CREATE TRIGGER event_setup_created
AFTER INSERT ON setup
BEGIN
    INSERT INTO entity_events (id, entity_type, entity_id, event_type)
    VALUES (lower(hex(randomblob(16))), 'setup', NEW.id, 'created');
END;

DROP TRIGGER IF EXISTS event_setup_status_changed;

DROP TRIGGER IF EXISTS event_review_phase1_filed;
CREATE TRIGGER event_review_phase1_filed
AFTER INSERT ON review
BEGIN
    INSERT INTO entity_events (id, entity_type, entity_id, event_type)
    VALUES (lower(hex(randomblob(16))), 'review', NEW.id, 'filed');
END;

DROP TRIGGER IF EXISTS event_review_phase2_filed;
CREATE TRIGGER event_review_phase2_filed
AFTER UPDATE OF phase2_created_at ON review
WHEN NEW.phase2_created_at IS NOT NULL AND OLD.phase2_created_at IS NULL
BEGIN
    INSERT INTO entity_events (
        id, entity_type, entity_id, event_type, new_status
    ) VALUES (
        lower(hex(randomblob(16))), 'review', NEW.id, 'filed', 'phase2'
    );
END;
