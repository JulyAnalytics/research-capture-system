-- db/views.sql
-- Loaded via executescript() at startup.
-- Each view is preceded by DROP VIEW IF EXISTS.

-- ─── STALENESS SWEEP ─────────────────────────────────────────────────────────

DROP VIEW IF EXISTS stale_canvases;
CREATE VIEW stale_canvases AS
SELECT id, name, last_reviewed,
       CAST(julianday('now') - julianday(last_reviewed) AS INTEGER) AS days_stale
FROM canvas
WHERE status = 'active'
  AND julianday('now') - julianday(last_reviewed) > 14
ORDER BY days_stale DESC;

DROP VIEW IF EXISTS stale_theses;
CREATE VIEW stale_theses AS
SELECT id, instrument, status, last_updated,
       CAST(julianday('now') - julianday(last_updated) AS INTEGER) AS days_stale
FROM thesis
WHERE status IN ('ready', 'active')
  AND julianday('now') - julianday(last_updated) > 7
ORDER BY days_stale DESC;

DROP VIEW IF EXISTS stale_invalidation_conditions;
CREATE VIEW stale_invalidation_conditions AS
SELECT cic.id, cic.canvas_id, c.name AS canvas_name,
       cic.condition, cic.type, cic.probability, cic.last_assessed,
       CAST(julianday('now') - julianday(cic.last_assessed) AS INTEGER) AS days_stale
FROM canvas_invalidation_conditions cic
JOIN canvas c ON cic.canvas_id = c.id
WHERE c.status = 'active'
  AND julianday('now') - julianday(cic.last_assessed) > 21
ORDER BY days_stale DESC;

DROP VIEW IF EXISTS overdue_actions;
CREATE VIEW overdue_actions AS
SELECT a.*, t.instrument AS thesis_instrument
FROM action a
LEFT JOIN thesis t ON a.linked_thesis_id = t.id
WHERE a.status = 'open'
  AND date(a.due_date) <= date('now')
ORDER BY a.due_date ASC;

-- active_surveillance: 1 row per observation in watching state.
-- Uses subqueries rather than LEFT JOINs to avoid N×M row explosion when an observation
-- has multiple linked theses or setups.
-- thesis_link_count and setup_link_count expose the full cardinality.
-- The primary linked_thesis_id / linked_setup_id return an arbitrary single
-- linked record for display purposes; full link lists are queried via junction tables.
DROP VIEW IF EXISTS active_surveillance;
CREATE VIEW active_surveillance AS
SELECT
    o.id,
    o.name,
    o.instrument,
    o.note,
    o.date,
    (
        SELECT otl.thesis_id FROM observation_thesis_links otl
        WHERE otl.observation_id = o.id LIMIT 1
    ) AS linked_thesis_id,
    (
        SELECT t.status FROM observation_thesis_links otl
        JOIN thesis t ON t.id = otl.thesis_id
        WHERE otl.observation_id = o.id LIMIT 1
    ) AS thesis_status,
    (
        SELECT osl.setup_id FROM observation_setup_links osl
        WHERE osl.observation_id = o.id LIMIT 1
    ) AS linked_setup_id,
    (SELECT COUNT(*) FROM observation_thesis_links otl
     WHERE otl.observation_id = o.id) AS thesis_link_count,
    (SELECT COUNT(*) FROM observation_setup_links osl
     WHERE osl.observation_id = o.id) AS setup_link_count
FROM observation o
WHERE o.status = 'watching'
ORDER BY o.date ASC;

-- ─── ANALYTICAL ──────────────────────────────────────────────────────────────

-- Protocol 1 is NOT a view — it fires from the canvas update route.

DROP VIEW IF EXISTS canvas_observation_backlinks;
DROP VIEW IF EXISTS canvas_setup_backlinks;
CREATE VIEW canvas_setup_backlinks AS
SELECT slc.canvas_id,
       s.id AS setup_id,
       s.date,
       s.instrument,
       s.type,
       s.setup_note,
       (SELECT COUNT(*) FROM setup_images si WHERE si.setup_id = s.id) AS image_count
FROM setup_linked_canvases slc
JOIN setup s ON slc.setup_id = s.id
ORDER BY s.date DESC;

-- ─── LEARNING ────────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS passed_setup_analysis;
DROP VIEW IF EXISTS passed_observation_analysis;
CREATE VIEW passed_observation_analysis AS
SELECT
    passed_reason_type,
    COUNT(*) AS count,
    ROUND(
        100.0 * COUNT(*) / NULLIF(
            (SELECT COUNT(*) FROM observation WHERE status = 'passed'), 0
        ), 1
    ) AS pct
FROM observation
WHERE status = 'passed'
GROUP BY passed_reason_type;

DROP VIEW IF EXISTS passed_setup_detail;
DROP VIEW IF EXISTS passed_observation_detail;
CREATE VIEW passed_observation_detail AS
SELECT id, name, instrument, passed_reason, passed_reason_type, date
FROM observation
WHERE status = 'passed'
ORDER BY date DESC;

DROP VIEW IF EXISTS review_mistake_distribution;
CREATE VIEW review_mistake_distribution AS
SELECT mistake_type, COUNT(*) AS count,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM review WHERE mistake_type IS NOT NULL), 1) AS pct
FROM review
WHERE mistake_type IS NOT NULL
GROUP BY mistake_type;

DROP VIEW IF EXISTS decision_point_deviations;
CREATE VIEW decision_point_deviations AS
SELECT dp.id, dp.thesis_id, t.instrument, dp.trigger, dp.decision,
       dp.deviation_note, dp.fired_at,
       (SELECT r.mistake_type FROM review r WHERE r.trade_id = t.linked_trade_id) AS review_type
FROM thesis_decision_points dp
JOIN thesis t ON dp.thesis_id = t.id
WHERE dp.deviation_note IS NOT NULL
ORDER BY dp.fired_at DESC;

DROP VIEW IF EXISTS options_iv_comparison;
CREATE VIEW options_iv_comparison AS
SELECT t.id AS trade_id, th.instrument,
       om.iv_at_entry, om.iv_rank_at_entry, om.iv_at_exit,
       ROUND(om.iv_at_exit - om.iv_at_entry, 4) AS iv_change,
       r.mistake_type
FROM trade t
JOIN thesis th ON t.thesis_id = th.id
JOIN trade_options_meta om ON t.id = om.trade_id
LEFT JOIN review r ON t.review_id = r.id
WHERE t.status = 'closed'
ORDER BY t.closed_at DESC;

DROP VIEW IF EXISTS invalidation_post_mortem;
CREATE VIEW invalidation_post_mortem AS
SELECT t.id AS thesis_id, t.instrument,
       kc.condition, kc.linked_canvas_id, c.name AS canvas_name,
       kc.fired_at, r.mistake_type
FROM thesis t
JOIN thesis_kill_conditions_macro kc ON t.id = kc.thesis_id
LEFT JOIN canvas c ON kc.linked_canvas_id = c.id
LEFT JOIN review r ON t.linked_trade_id = r.trade_id
WHERE t.status = 'invalidated' AND kc.fired_at IS NOT NULL
ORDER BY kc.fired_at DESC;

-- ─── TIME-AXIS ANALYTICS ─────────────────────────────────────────────────────

-- thesis_lifespan: correlated subquery returns most recent terminal event,
-- handling theses that cycle through invalidated → building → ... → invalidated.
DROP VIEW IF EXISTS thesis_lifespan;
CREATE VIEW thesis_lifespan AS
SELECT
    t.id,
    t.instrument,
    t.status,
    e_created.occurred_at AS created_at,
    (
        SELECT occurred_at FROM entity_events
        WHERE entity_id = t.id
          AND event_type = 'status_changed'
          AND new_status IN ('invalidated', 'archived')
        ORDER BY occurred_at DESC
        LIMIT 1
    ) AS terminal_at,
    CAST(
        julianday((
            SELECT occurred_at FROM entity_events
            WHERE entity_id = t.id
              AND event_type = 'status_changed'
              AND new_status IN ('invalidated', 'archived')
            ORDER BY occurred_at DESC
            LIMIT 1
        )) - julianday(e_created.occurred_at)
        AS INTEGER
    ) AS lifespan_days,
    r.mistake_type
FROM thesis t
JOIN entity_events e_created
    ON e_created.entity_id = t.id AND e_created.event_type = 'created'
LEFT JOIN review r ON r.trade_id = t.linked_trade_id
WHERE t.status IN ('invalidated', 'archived');

DROP VIEW IF EXISTS review_lag;
CREATE VIEW review_lag AS
SELECT
    r.id AS review_id,
    th.instrument,
    e_close.occurred_at AS trade_closed_at,
    e_p2.occurred_at    AS phase2_filed_at,
    CAST(
        (julianday(e_p2.occurred_at) - julianday(e_close.occurred_at)) * 24
        AS INTEGER
    ) AS hours_to_phase2,
    r.mistake_type
FROM review r
JOIN trade tr ON r.trade_id = tr.id
JOIN thesis th ON tr.thesis_id = th.id
JOIN entity_events e_close
    ON e_close.entity_id = tr.id AND e_close.new_status = 'closed'
JOIN entity_events e_p2
    ON e_p2.entity_id = r.id AND e_p2.new_status = 'phase2'
WHERE r.phase2_created_at IS NOT NULL;
