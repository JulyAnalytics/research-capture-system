-- Migration 005: add insight entity
--
-- DECISION: insight uses a polymorphic link pattern (linked_entity_type +
-- linked_entity_id TEXT columns) rather than six junction tables. SQLite
-- cannot enforce FK integrity on a polymorphically identified row. This is
-- acceptable because: (a) no entity in this system is ever hard-deleted;
-- (b) the route layer verifies entity existence at link-write time;
-- (c) the exporter will include a pre-export orphan check. Do not treat
-- this as an oversight in future tasks.
-- Date: 2026-05-02.
--
-- TRANSACTION SAFETY NOTE: runner.py wraps each migration in its own
-- BEGIN/COMMIT transaction. This migration MUST NOT include its own BEGIN/COMMIT
-- — doing so causes "cannot start a transaction within a transaction".
-- The entity_events table rebuild below (DROP + RENAME sequence) is fully
-- protected by the runner's transaction. If the migration fails between
-- DROP and RENAME, runner.py rolls back and the original entity_events table
-- is restored. Date: 2026-05-02.

CREATE TABLE IF NOT EXISTS insight (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL DEFAULT '',
    note               TEXT NOT NULL,
    -- Polymorphic link to any entity. Both columns are NULL when
    -- the insight is standalone (not linked to a specific entity).
    -- linked_entity_type must be one of:
    --   canvas | thesis | observation | setup | trade | review
    -- Enforced at the route layer, not the DB layer (see DECISION above).
    linked_entity_type TEXT,
    linked_entity_id   TEXT,
    -- Optional freeform context tag (e.g. 'pre-trade', 'post-review',
    -- 'macro', 'process'). Not a CHECK-constrained enum — kept open
    -- to allow organic tag vocabulary to develop.
    context_tag        TEXT,
    created_at         TEXT NOT NULL
                           DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Export watermark for insight (6th row)
INSERT OR IGNORE INTO export_watermarks (entity_type) VALUES ('insight');

-- Rebuild entity_events to include 'insight' in the entity_type CHECK.
-- SQLite does not support ALTER CHECK — full table rebuild required.
CREATE TABLE IF NOT EXISTS entity_events_new (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL
                    CHECK(entity_type IN (
                        'canvas', 'thesis', 'trade',
                        'observation', 'review', 'setup', 'insight'
                    )),
    entity_id   TEXT NOT NULL,
    event_type  TEXT NOT NULL
                    CHECK(event_type IN (
                        'created', 'status_changed', 'updated', 'filed'
                    )),
    old_status  TEXT,
    new_status  TEXT,
    occurred_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

INSERT INTO entity_events_new
    SELECT id, entity_type, entity_id, event_type,
           old_status, new_status, occurred_at
    FROM entity_events;

DROP TABLE entity_events;
ALTER TABLE entity_events_new RENAME TO entity_events;

-- Recreate indexes (dropped with the old table)
CREATE INDEX IF NOT EXISTS idx_entity_events_occurred_at
    ON entity_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_entity_events_entity
    ON entity_events(entity_type, entity_id);
