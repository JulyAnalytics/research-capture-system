-- db/schema.sql
-- Loaded via executescript() at startup. All tables use IF NOT EXISTS.
-- WAL mode set in database.py, not here.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ─────────────────────────────────────────
-- CANVAS
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS canvas (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    narrative     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active'
                      CHECK(status IN ('active', 'archived')),
    last_reviewed TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS canvas_cross_currents (
    id                       TEXT PRIMARY KEY,
    source_canvas_id         TEXT NOT NULL REFERENCES canvas(id),
    target_canvas_id         TEXT NOT NULL REFERENCES canvas(id),
    relationship_description TEXT NOT NULL,
    created_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    CHECK(source_canvas_id != target_canvas_id),
    UNIQUE(source_canvas_id, target_canvas_id)
);

CREATE TABLE IF NOT EXISTS canvas_invalidation_conditions (
    id             TEXT PRIMARY KEY,
    canvas_id      TEXT NOT NULL REFERENCES canvas(id),
    condition      TEXT NOT NULL,
    type           TEXT NOT NULL CHECK(type IN ('necessary', 'sufficient')),
    probability    TEXT NOT NULL CHECK(probability IN ('low', 'medium', 'high')),
    lead_time_days INTEGER NOT NULL,
    last_assessed  TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS canvas_version_history (
    id           TEXT PRIMARY KEY,
    canvas_id    TEXT NOT NULL REFERENCES canvas(id),
    timestamp    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    diff_summary TEXT NOT NULL
    -- append-only: BEFORE UPDATE and BEFORE DELETE triggers enforce
);

-- ─────────────────────────────────────────
-- SETUP
-- No FKs to thesis or observation — those are in junction tables below.
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS setup (
    id                 TEXT PRIMARY KEY,
    instrument         TEXT NOT NULL,
    setup_type         TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'watching'
                           CHECK(status IN ('watching', 'taken', 'passed')),
    note               TEXT NOT NULL,
    passed_reason      TEXT,
    passed_reason_type TEXT CHECK(passed_reason_type IN ('psychological', 'analytical')),
    date               TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS setup_images (
    id            TEXT PRIMARY KEY,
    setup_id      TEXT NOT NULL REFERENCES setup(id),
    filename      TEXT NOT NULL,
    filepath      TEXT NOT NULL,
    caption       TEXT,
    parsed_fields TEXT,   -- reserved for future vision extraction
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ─────────────────────────────────────────
-- THESIS
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS thesis (
    id                TEXT PRIMARY KEY,
    instrument        TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'building'
                          CHECK(status IN ('building', 'ready', 'active', 'invalidated', 'archived')),
    narrative         TEXT NOT NULL,
    win_condition     TEXT NOT NULL,
    worst_case_dollar REAL,
    linked_trade_id   TEXT,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_updated      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS thesis_kill_conditions_macro (
    id               TEXT PRIMARY KEY,
    thesis_id        TEXT NOT NULL REFERENCES thesis(id),
    condition        TEXT NOT NULL,
    linked_canvas_id TEXT REFERENCES canvas(id),
    fired_at         TEXT,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS thesis_kill_conditions_technical (
    id              TEXT PRIMARY KEY,
    thesis_id       TEXT NOT NULL REFERENCES thesis(id),
    condition       TEXT NOT NULL,
    linked_setup_id TEXT REFERENCES setup(id),
    fired_at        TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS thesis_decision_points (
    id             TEXT PRIMARY KEY,
    thesis_id      TEXT NOT NULL REFERENCES thesis(id),
    trigger        TEXT NOT NULL,
    decision       TEXT NOT NULL,
    instrument     TEXT NOT NULL,
    size_pct       TEXT NOT NULL,
    fired_at       TEXT,
    deviation_note TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS thesis_linked_canvases (
    thesis_id  TEXT NOT NULL REFERENCES thesis(id),
    canvas_id  TEXT NOT NULL REFERENCES canvas(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (thesis_id, canvas_id)
);

-- NOTE: thesis_linked_setups is intentionally absent.
-- setup_thesis_links (below) is the canonical junction for setup↔thesis links.
-- The thesis→setup direction is navigated by reversing the join on setup_thesis_links.

CREATE TABLE IF NOT EXISTS thesis_version_history (
    id           TEXT PRIMARY KEY,
    thesis_id    TEXT NOT NULL REFERENCES thesis(id),
    timestamp    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    diff_summary TEXT NOT NULL
    -- append-only
);

-- ─────────────────────────────────────────
-- TRADE
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trade (
    id                 TEXT PRIMARY KEY,
    thesis_id          TEXT NOT NULL REFERENCES thesis(id),
    instrument_type    TEXT NOT NULL
                           CHECK(instrument_type IN ('equity', 'option', 'future', 'fx', 'other')),
    entry_rules_stated TEXT NOT NULL,   -- frozen at open
    exit_rules_stated  TEXT NOT NULL,   -- frozen at open
    thesis_snapshot    TEXT NOT NULL,   -- frozen at open
    status             TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
    review_id          TEXT,
    -- review_id is a soft FK (no REFERENCES clause) due to trade↔review circular dependency.
    -- Referential integrity is enforced by the trade_review_id_fk trigger. See Design Decision 11.
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    closed_at          TEXT
);

CREATE TABLE IF NOT EXISTS trade_entries (
    id         TEXT PRIMARY KEY,
    trade_id   TEXT NOT NULL REFERENCES trade(id),
    date       TEXT NOT NULL,
    price      REAL NOT NULL,
    size       REAL NOT NULL,
    note       TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    -- append-only
);

CREATE TABLE IF NOT EXISTS trade_exits (
    id         TEXT PRIMARY KEY,
    trade_id   TEXT NOT NULL REFERENCES trade(id),
    date       TEXT NOT NULL,
    price      REAL NOT NULL,
    size       REAL NOT NULL,
    note       TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    -- append-only
);

CREATE TABLE IF NOT EXISTS trade_options_meta (
    trade_id             TEXT PRIMARY KEY REFERENCES trade(id),
    strategy_type        TEXT NOT NULL CHECK(strategy_type IN ('single', 'spread', 'ratio', 'other')),
    delta_at_entry       REAL,
    gamma_at_entry       REAL,
    theta_daily_at_entry REAL,
    vega_at_entry        REAL,
    iv_at_entry          REAL NOT NULL,
    iv_rank_at_entry     REAL NOT NULL,
    delta_at_exit        REAL,
    gamma_at_exit        REAL,
    theta_daily_at_exit  REAL,
    vega_at_exit         REAL,
    iv_at_exit           REAL,
    max_loss_defined     INTEGER NOT NULL CHECK(max_loss_defined IN (0, 1)),
    max_loss_dollar      REAL,
    theta_decay_relevant INTEGER NOT NULL CHECK(theta_decay_relevant IN (0, 1))
);

CREATE TABLE IF NOT EXISTS trade_option_legs (
    id            TEXT PRIMARY KEY,
    trade_id      TEXT NOT NULL REFERENCES trade(id),
    direction     TEXT NOT NULL CHECK(direction IN ('long', 'short')),
    type          TEXT NOT NULL CHECK(type IN ('call', 'put')),
    strike        REAL NOT NULL,
    expiry        TEXT NOT NULL,
    contracts     INTEGER NOT NULL,
    entry_premium REAL NOT NULL,
    exit_premium  REAL,
    date_opened   TEXT NOT NULL,
    date_closed   TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    -- partial update allowed: only exit_premium and date_closed may be modified (trigger enforced)
);

-- ─────────────────────────────────────────
-- OBSERVATION
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS observation (
    id               TEXT PRIMARY KEY,
    date             TEXT NOT NULL,
    instrument       TEXT NOT NULL,
    timeframe        TEXT NOT NULL,
    type             TEXT NOT NULL CHECK(type IN ('technical', 'vol', 'flow')),
    observation      TEXT NOT NULL,
    linked_thesis_id TEXT REFERENCES thesis(id),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    -- append-only
);

CREATE TABLE IF NOT EXISTS observation_linked_canvases (
    observation_id TEXT NOT NULL REFERENCES observation(id),
    canvas_id      TEXT NOT NULL REFERENCES canvas(id),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (observation_id, canvas_id)
);

CREATE TABLE IF NOT EXISTS observation_images (
    id             TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL REFERENCES observation(id),
    filename       TEXT NOT NULL,
    filepath       TEXT NOT NULL,
    caption        TEXT,
    parsed_fields  TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ─────────────────────────────────────────
-- SETUP JUNCTION TABLES
-- Canonical setup↔thesis and setup↔observation links.
-- Defined after all referenced tables — resolves circular FK dependency.
-- setup_thesis_links is the sole junction for both directions; thesis_linked_setups
-- does not exist. To query setups linked to a thesis: SELECT from setup_thesis_links
-- WHERE thesis_id = ?
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS setup_thesis_links (
    setup_id   TEXT NOT NULL REFERENCES setup(id),
    thesis_id  TEXT NOT NULL REFERENCES thesis(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (setup_id, thesis_id)
);

CREATE TABLE IF NOT EXISTS setup_observation_links (
    setup_id       TEXT NOT NULL REFERENCES setup(id),
    observation_id TEXT NOT NULL REFERENCES observation(id),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (setup_id, observation_id)
);

-- ─────────────────────────────────────────
-- ACTION
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS action (
    id                TEXT PRIMARY KEY,
    instrument        TEXT,
    action            TEXT NOT NULL,
    due_date          TEXT NOT NULL,
    linked_thesis_id  TEXT REFERENCES thesis(id),
    linked_setup_id   TEXT REFERENCES setup(id),
    status            TEXT NOT NULL DEFAULT 'open'
                          CHECK(status IN ('open', 'done', 'cancelled')),
    cancellation_note TEXT,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ─────────────────────────────────────────
-- REVIEW
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS review (
    id                    TEXT PRIMARY KEY,
    trade_id              TEXT NOT NULL REFERENCES trade(id),
    -- Phase 1 (immediate, at position close)
    closed_at             TEXT NOT NULL,
    entry_fill            TEXT NOT NULL,
    exit_fill             TEXT NOT NULL,
    thesis_at_entry       TEXT NOT NULL,   -- copied snapshot; never updated
    exit_rules_as_written TEXT NOT NULL,   -- copied snapshot; never updated
    what_i_actually_did   TEXT NOT NULL,
    emotional_state       TEXT NOT NULL,   -- single word; trigger enforced on INSERT and UPDATE
    rules_followed        TEXT NOT NULL CHECK(rules_followed IN ('yes', 'no', 'partial')),
    locked_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    -- Phase 2a: zone 3 clearance (separate endpoint, min 24h after Phase 1)
    zone_3_cleared_at     TEXT,
    zone_3_clear          INTEGER CHECK(zone_3_clear IN (0, 1)),
    -- Phase 2b: analysis (separate endpoint, requires zone_3_clear = 1 committed to DB)
    phase2_created_at     TEXT,
    mistake_type          TEXT CHECK(mistake_type IN ('type_1', 'type_2', 'type_3')),
    analysis              TEXT,
    single_update         TEXT,
    what_not_changing     TEXT
);

-- ─────────────────────────────────────────
-- INBOX
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS inbox (
    id                       TEXT PRIMARY KEY,
    raw_text                 TEXT NOT NULL,
    created_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    routed_to_observation_id TEXT REFERENCES observation(id),
    routed_to_action_id      TEXT REFERENCES action(id),
    routed_to_setup_id       TEXT REFERENCES setup(id),
    routed_to_thesis_id      TEXT REFERENCES thesis(id),
    routed_at                TEXT
);

-- ─────────────────────────────────────────
-- ENTITY EVENT LOG
-- Append-only. Populated exclusively by AFTER triggers.
-- No application-layer write paths.
-- Trade events are logged for analytics but not consumed by the exporter.
-- See Design Decision 12.
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entity_events (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL
                    CHECK(entity_type IN (
                        'canvas', 'thesis', 'trade',
                        'observation', 'review', 'setup'
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

CREATE INDEX IF NOT EXISTS idx_entity_events_occurred_at
    ON entity_events(occurred_at);

CREATE INDEX IF NOT EXISTS idx_entity_events_entity
    ON entity_events(entity_type, entity_id);

-- ─────────────────────────────────────────
-- CANVAS SOURCE DOCUMENTS
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS canvas_source_documents (
    canvas_id           TEXT NOT NULL REFERENCES canvas(id),
    library_document_id TEXT NOT NULL,   -- SHA256 id from library.sqlite documents table
    note                TEXT,
    linked_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (canvas_id, library_document_id)
);

-- ─────────────────────────────────────────
-- EXPORT WATERMARKS
-- entity_type values match exporter's entity_type_exporters keys.
-- 'trade' is intentionally absent — trade events are not exported.
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS export_watermarks (
    entity_type      TEXT PRIMARY KEY,
    last_exported_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00Z'
);

INSERT OR IGNORE INTO export_watermarks (entity_type) VALUES
    ('canvas'), ('thesis'), ('observation'), ('review'), ('setup');

-- ─────────────────────────────────────────
-- FAILED EXPORTS
-- Dead-letter queue for export failures.
-- Watermark does not advance for an entity type if any exports failed.
-- Retried via --mode reconcile.
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS failed_exports (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    error       TEXT NOT NULL,
    failed_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    resolved    INTEGER NOT NULL DEFAULT 0,
    UNIQUE(entity_type, entity_id)   -- latest failure record per entity; ON CONFLICT REPLACE
);
