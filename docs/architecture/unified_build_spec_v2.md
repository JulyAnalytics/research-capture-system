# Unified Build Specification — Research Capture System with Knowledge Library Integration v2

---

## Changes from v1

| # | Issue | Resolution |
|---|---|---|
| 1 | Migration runner splits trigger compound statements on `;` | Split file loading by role: `schema.sql`/`triggers.sql`/`views.sql` loaded via `executescript()` at init; migration runner handles numbered files only (simple DDL, no compound statements) |
| 2 | `get_library_db()` connection leaks on exception | Converted to `@asynccontextmanager`; all callers use `async with` |
| 3 | Knowledge gap query references undefined tables | Fixed with `ATTACH`-dependent joins through `library.documents` and `library.document_concepts`; prerequisite noted |
| 4 | Watermark advances on partial export failure | `failed_exports` table added; watermark advances only on zero failures; `--reconcile` extended to cover failed exports |
| 5 | `thesis_lifespan` view duplicates for re-invalidated theses | Fixed with correlated subquery returning most recent terminal event |
| 6 | `active_surveillance` cartesian explosion (N×M rows) | Rewritten with subqueries; 1 row per setup |
| 7 | `trade.review_id` soft FK undocumented | Added Design Decision 11; `trade_review_id_fk` trigger added |
| 8 | Path traversal in image serve endpoint | `is_relative_to(IMAGE_ROOT.resolve())` check added |
| 9 | `canvas_cross_currents` orphaned (no routes) | In scope: routes and Phase 8 coverage added |
| 10 | Trade events logged but never exported | Design Decision 12 added: trade events are analytics-only, not consumed by exporter |
| 11 | Emotional state trigger INSERT-only | `BEFORE UPDATE` trigger added |
| 12 | Sync connection contention during export | Documented under Design Decision 12; recommendation: run exporter with server idle |
| 13 | `library-search` no server-side min length | `len(q.strip()) < 2` check added to route handler |
| 14 | Migration comment stripping post-split | Comment stripping moved to pre-split pass |
| 15 | `--research` CLI flag undefined | Explicit `argparse` definition added; `--mode` flag with named choices |
| Q1 | `vault_path` / `obsidian_vault` ambiguity | Config maps `obsidian_vault` → `vault_path`; `_write_note` shown writing into `vault_path` subdirectories |
| Q2 | Duplicate setup↔thesis junction tables | `thesis_linked_setups` dropped; `setup_thesis_links` is canonical; queries navigate both directions |
| Q3 | Archived canvas notes orphaned in vault | Documented in out of scope: no deletion propagation |

---

## Design Decisions

### 1. Database Engine: SQLite + WAL

**Chosen:** SQLite with WAL mode.

Single-user, single-process system with no concurrency requirement. PostgreSQL's one relevant advantage — deferrable FK constraints — is insufficient to justify the operational cost. Raw SQL over an ORM preserves migration optionality: the schema translates cleanly if PostgreSQL is ever needed.

**When to revisit:** Multi-device access without a file sync layer.

---

### 2. Circular FK Resolution: Junction Tables

`setup` ↔ `thesis` and `setup` ↔ `observation` form circular dependencies. Junction tables (`setup_thesis_links`, `setup_observation_links`) are defined after all referenced tables, making all FK constraints valid at declaration. The `setup_taken_gate` trigger checks `setup_thesis_links` via subquery in the trigger body.

`thesis_linked_setups` is dropped — it was a directional duplicate of `setup_thesis_links`. `setup_thesis_links` is the canonical table; the thesis→setup direction is navigated by reversing the join.

---

### 3. Image Attachment: Upload Only

File upload to local filesystem; path stored in DB. URL ingestion and vision parsing are deferred. The `parsed_fields JSON` column on both image tables is a reserved slot — adding vision extraction later requires no schema migration.

---

### 4. Passed Setup Classification: Write-Time Explicit

`passed_reason_type` required at pass time, enforced by trigger. Keyword matching on free text produces unreliable distributions; classification is most accurate at the moment of decision.

---

### 5. Transaction Pattern: Explicit BEGIN / commit / rollback

`async with db.execute("BEGIN")` does not commit or rollback — it iterates a cursor and returns. Explicit try/except is used consistently across all multi-statement write paths.

---

### 6. Protocol 1: Route Response over Standing View

Canvas update route returns linked ready/active thesis IDs in the response body. A standing view cannot distinguish "updated 3 minutes ago" from "updated 3 days ago, already reviewed." The protocol belongs at the mutation site.

---

### 7. Zone 3: Two-Step Enforcement

Two separate endpoints — `zone3-clear` then `phase2` — with DB state checked between them. The second endpoint checks `OLD.zone_3_clear` in the DB, not the request, so the gate cannot be satisfied in the same call.

---

### 8. Event Log: Belongs in research.db

The event log records operational transitions, not knowledge artifacts. The library never needs to know it exists. The export pipeline reads it; the library's content concern is separate.

---

### 9. Canvas Source Documents: Explicit Provenance over Pure Inference

Semantic inference surfaces documents sharing vocabulary with a canvas. Explicit reference records which documents actually informed it. Both are useful; they answer different questions. Source documents live in `research.db` — the reference is an act of research, not a library artifact.

---

### 10. Incremental Export: Watermark Table

Named watermarks per entity type in `export_watermarks`. Resetting one watermark re-exports that category without affecting others. The watermark for a given entity type advances only when zero failures occur in the batch — partial failures are recorded in `failed_exports` and retried via `--mode reconcile`.

---

### 11. trade.review_id — Deliberate Soft FK

`review.trade_id` has an enforced FK constraint. `trade.review_id` is the reverse reference and creates a circular dependency. It is implemented as a bare `TEXT` column without a `REFERENCES` clause (consistent with the junction table approach used elsewhere for circular dependencies), with referential integrity enforced by the `trade_review_id_fk` trigger. This is an intentional structural decision, documented here to distinguish it from an oversight.

---

### 12. Trade Events — Analytics Only, Not Exported

Trade events (`event_trade_created`, `event_trade_closed`) are logged in `entity_events` for time-axis analytics. The exporter does not consume them — trades are surfaced through their linked theses and reviews. `export_watermarks` does not include a `trade` entry. The events accumulate as a queryable log with no export consumption path. This is intentional.

**Sync connection contention:** `ResearchExporter` uses a synchronous `sqlite3` connection that persists throughout the export run. WAL mode allows concurrent reads, but watermark UPDATEs acquire a brief exclusive lock. During long Ollama LLM passes, this can contend with FastAPI write paths. At personal scale this is acceptable but not invisible. Recommendation: run the exporter with the server idle, or schedule it nightly outside operating hours.

---

### 13. canvas_cross_currents — In Scope

Canvas cross-currents are in scope. Routes: `POST /canvas/{id}/cross-currents`, `DELETE /canvas/{id}/cross-currents/{target_id}`, `GET /canvas/{id}/cross-currents`. UI renders on the canvas detail page. Covered in Phase 8.

---

### 14. Schema Initialization vs. Migration

`schema.sql`, `triggers.sql`, and `views.sql` are loaded at application startup via `executescript()`. These files define the current state and are always loaded in full. `triggers.sql` and `views.sql` use `DROP ... IF EXISTS` before each `CREATE` so definition changes take effect on the next startup without a migration. Numbered migration files handle schema *changes* only (ALTER TABLE, CREATE INDEX, new simple tables) and must not contain compound statements. This separates "what exists now" from "how we got here."

---

## System Architecture

Two systems. One integration surface.

**Research Capture System** (`research/`) — FastAPI application. Primary write surface for all research data. Owns `research.db`. Enforces all state machines and protocols.

**Knowledge Library** (`knowledge-library/`) — Python ingestion pipeline. Owns `library.sqlite`, `chroma/`, and the Obsidian vault. Reads `research.db` via read-only connection for export. Never writes to `research.db`.

**Integration surface:**

| Mechanism | Direction | Purpose |
|---|---|---|
| `entity_events` | Research → Library (via exporter) | Incremental export: which entities changed since last watermark |
| `canvas_source_documents` | Research API (write); Library (read-only for validation) | Explicit provenance: library documents that informed a canvas |
| `export_watermarks` | Exporter (read/write) | Named watermarks per entity type |
| `failed_exports` | Exporter (write); reconcile runner (read/write) | Dead-letter queue for failed export runs |
| `get_library_db()` | Research API → Library (read-only) | Canvas source document search and validation |
| `ResearchExporter` | research.db → library.sqlite + ChromaDB + Obsidian | Nightly/manual export of terminal-state entities |

---

## Stack

### Research Capture System

| Layer | Choice |
|---|---|
| Database | SQLite (WAL mode) |
| Backend | FastAPI (Python 3.11+) |
| DB access | `aiosqlite` + raw SQL |
| Frontend | HTMX + Alpine.js + Jinja2 |
| Image storage | Local filesystem |
| Migrations | Custom `db/migrations/` runner (simple DDL only) |

### Knowledge Library

| Layer | Choice |
|---|---|
| Orchestration | Python 3.11+ (Mac) |
| LLM inference | Ollama / Mistral 7B or Llama 3.1 8B (3060 Ti) |
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2) |
| Vector store | ChromaDB |
| Vault interface | Obsidian + Dataview |
| PDF extraction | `pdfplumber` + tesseract fallback |

---

## Project Structure

```
research/
├── db/
│   ├── schema.sql            # Tables — IF NOT EXISTS; loaded via executescript() at startup
│   ├── triggers.sql          # Triggers — DROP IF EXISTS + CREATE; loaded at startup
│   ├── views.sql             # Views — DROP IF EXISTS + CREATE; loaded at startup
│   ├── init.py               # init_schema() — loads all three files at startup
│   └── migrations/
│       ├── runner.py         # Simple DDL only; no compound statements
│       └── 0001_initial.sql
├── api/
│   ├── main.py
│   ├── database.py           # get_db() + get_library_db() (async context manager)
│   ├── config.py
│   ├── models/
│   │   ├── canvas.py
│   │   ├── thesis.py
│   │   ├── trade.py
│   │   ├── observation.py
│   │   ├── setup.py
│   │   ├── action.py
│   │   ├── review.py
│   │   └── image.py
│   ├── routes/
│   │   ├── canvas.py         # Protocol 1; /cross-currents; /sources; /library-search
│   │   ├── thesis.py
│   │   ├── trade.py
│   │   ├── observation.py
│   │   ├── setup.py
│   │   ├── action.py
│   │   ├── review.py         # zone3-clear and phase2 as separate endpoints
│   │   ├── ritual.py
│   │   └── images.py
│   └── protocols/
│       ├── protocol1.py
│       ├── protocol2.py
│       ├── protocol3.py
│       └── protocol4.py
├── frontend/
│   ├── templates/
│   │   └── canvas/
│   │       └── detail.html   # cross-currents section + source documents section
│   └── static/
├── data/
│   ├── research.db
│   └── images/
│       ├── observations/
│       └── setups/
└── requirements.txt

knowledge-library/
├── run_ingestion.py          # main entry point; --mode flag with named choices
├── config.yaml               # includes research_db + obsidian_vault (= vault_path)
├── pipeline/
│   ├── scanner.py
│   ├── extractor.py
│   ├── metadata.py
│   ├── llm.py
│   ├── embedder.py
│   ├── writers.py
│   ├── research_exporter.py
│   └── logger.py
├── db/
│   ├── library.sqlite
│   └── chroma/
├── vault/                    # obsidian_vault root
│   └── research/
│       ├── canvases/         # exported canvas notes
│       ├── theses/           # exported thesis notes
│       ├── reviews/          # exported review notes
│       ├── observations/     # exported observation notes
│       └── setups/           # exported passed setup notes
└── requirements.txt
```

---

## Database Schema — research.db

### Table Ordering (FK-safe, load-bearing)

1. `canvas` and children
2. `setup` — no FKs to thesis/observation (junction tables follow)
3. `thesis` and children — FKs to `canvas` and `setup`
4. `trade` and children — FK to `thesis`
5. `observation` and children — FK to `thesis`
6. `setup_thesis_links`, `setup_observation_links` — after all referenced tables
7. `action`, `review`, `inbox`
8. `entity_events`, `canvas_source_documents`, `export_watermarks`, `failed_exports`

```sql
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
```

---

## Enforcement Triggers

```sql
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
WHEN NEW.status = 'active' AND OLD.status = 'ready'
BEGIN
    SELECT CASE
        WHEN NEW.linked_trade_id IS NULL
            THEN RAISE(ABORT, 'active gate: linked_trade_id required')
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
-- SETUP STATE MACHINE
-- ─────────────────────────────────────────

DROP TRIGGER IF EXISTS setup_state_machine;
CREATE TRIGGER setup_state_machine
BEFORE UPDATE OF status ON setup
WHEN OLD.status != NEW.status
BEGIN
    SELECT CASE
        WHEN OLD.status IN ('taken', 'passed')
            THEN RAISE(ABORT, 'taken and passed are terminal states')
        WHEN OLD.status = 'watching' AND NEW.status NOT IN ('taken', 'passed')
            THEN RAISE(ABORT, 'invalid transition: watching → taken or passed only')
    END;
END;

DROP TRIGGER IF EXISTS setup_taken_gate;
CREATE TRIGGER setup_taken_gate
BEFORE UPDATE OF status ON setup
WHEN NEW.status = 'taken' AND OLD.status = 'watching'
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM setup_thesis_links WHERE setup_id = NEW.id) = 0
            THEN RAISE(ABORT, 'taken gate: setup must be linked to a thesis before taking')
    END;
END;

DROP TRIGGER IF EXISTS setup_passed_gate;
CREATE TRIGGER setup_passed_gate
BEFORE UPDATE OF status ON setup
WHEN NEW.status = 'passed' AND OLD.status = 'watching'
BEGIN
    SELECT CASE
        WHEN (NEW.passed_reason IS NULL OR trim(NEW.passed_reason) = '')
            THEN RAISE(ABORT, 'passed gate: passed_reason required')
        WHEN NEW.passed_reason_type IS NULL
            THEN RAISE(ABORT, 'passed gate: passed_reason_type required (psychological or analytical)')
    END;
END;

-- ─────────────────────────────────────────
-- TRADE
-- ─────────────────────────────────────────

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
CREATE TRIGGER trade_rules_frozen
BEFORE UPDATE OF entry_rules_stated, exit_rules_stated ON trade
BEGIN
    SELECT RAISE(ABORT, 'entry_rules_stated and exit_rules_stated are frozen at open');
END;

DROP TRIGGER IF EXISTS trade_snapshot_frozen;
CREATE TRIGGER trade_snapshot_frozen
BEFORE UPDATE OF thesis_snapshot ON trade
BEGIN
    SELECT RAISE(ABORT, 'thesis_snapshot is frozen at open');
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
CREATE TRIGGER ao_observation_upd BEFORE UPDATE ON observation
BEGIN SELECT RAISE(ABORT, 'observation is append-only'); END;
DROP TRIGGER IF EXISTS ao_observation_del;
CREATE TRIGGER ao_observation_del BEFORE DELETE ON observation
BEGIN SELECT RAISE(ABORT, 'observation is append-only'); END;

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
    VALUES (lower(hex(randomblob(16))), 'trade', NEW.id, 'created', 'open');
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
        'status_changed', 'open', 'closed'
    );
END;

DROP TRIGGER IF EXISTS event_observation_created;
CREATE TRIGGER event_observation_created
AFTER INSERT ON observation
BEGIN
    INSERT INTO entity_events (id, entity_type, entity_id, event_type)
    VALUES (lower(hex(randomblob(16))), 'observation', NEW.id, 'created');
END;

DROP TRIGGER IF EXISTS event_setup_created;
CREATE TRIGGER event_setup_created
AFTER INSERT ON setup
BEGIN
    INSERT INTO entity_events (id, entity_type, entity_id, event_type, new_status)
    VALUES (lower(hex(randomblob(16))), 'setup', NEW.id, 'created', 'watching');
END;

DROP TRIGGER IF EXISTS event_setup_status_changed;
CREATE TRIGGER event_setup_status_changed
AFTER UPDATE OF status ON setup
WHEN OLD.status != NEW.status
BEGIN
    INSERT INTO entity_events (
        id, entity_type, entity_id, event_type, old_status, new_status
    ) VALUES (
        lower(hex(randomblob(16))), 'setup', NEW.id,
        'status_changed', OLD.status, NEW.status
    );
END;

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
```

---

## SQL Views

```sql
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

-- active_surveillance: 1 row per setup.
-- Uses subqueries rather than LEFT JOINs to avoid N×M row explosion when a setup
-- has multiple linked theses or observations.
-- thesis_link_count and observation_link_count expose the full cardinality.
-- The primary linked_thesis_id / linked_observation_id return an arbitrary single
-- linked record for display purposes; full link lists are queried via junction tables.
DROP VIEW IF EXISTS active_surveillance;
CREATE VIEW active_surveillance AS
SELECT
    s.id,
    s.instrument,
    s.setup_type,
    s.note,
    s.date,
    (
        SELECT stl.thesis_id FROM setup_thesis_links stl
        WHERE stl.setup_id = s.id LIMIT 1
    ) AS linked_thesis_id,
    (
        SELECT t.status FROM setup_thesis_links stl
        JOIN thesis t ON t.id = stl.thesis_id
        WHERE stl.setup_id = s.id LIMIT 1
    ) AS thesis_status,
    (
        SELECT sol.observation_id FROM setup_observation_links sol
        WHERE sol.setup_id = s.id LIMIT 1
    ) AS linked_observation_id,
    (SELECT COUNT(*) FROM setup_images       si  WHERE si.setup_id  = s.id) AS image_count,
    (SELECT COUNT(*) FROM setup_thesis_links stl WHERE stl.setup_id = s.id) AS thesis_link_count,
    (SELECT COUNT(*) FROM setup_observation_links sol WHERE sol.setup_id = s.id) AS observation_link_count
FROM setup s
WHERE s.status = 'watching'
ORDER BY s.date ASC;

-- ─── ANALYTICAL ──────────────────────────────────────────────────────────────

-- Protocol 1 is NOT a view — it fires from the canvas update route.

DROP VIEW IF EXISTS canvas_observation_backlinks;
CREATE VIEW canvas_observation_backlinks AS
SELECT olc.canvas_id, o.id AS observation_id, o.date, o.instrument,
       o.type, o.observation,
       (SELECT COUNT(*) FROM observation_images oi WHERE oi.observation_id = o.id) AS image_count
FROM observation_linked_canvases olc
JOIN observation o ON olc.observation_id = o.id
ORDER BY o.date DESC;

-- ─── LEARNING ────────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS passed_setup_analysis;
CREATE VIEW passed_setup_analysis AS
SELECT
    passed_reason_type,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM setup WHERE status = 'passed'), 1) AS pct
FROM setup
WHERE status = 'passed'
GROUP BY passed_reason_type;

DROP VIEW IF EXISTS passed_setup_detail;
CREATE VIEW passed_setup_detail AS
SELECT id, instrument, setup_type, passed_reason, passed_reason_type, date
FROM setup
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
```

---

## Schema Initialization

```python
# db/init.py

from pathlib import Path
import aiosqlite

DB_DIR = Path(__file__).parent


async def init_schema(conn: aiosqlite.Connection):
    """
    Load schema, triggers, and views at application startup.

    File loading strategy (Design Decision 14):
    - schema.sql:   CREATE TABLE IF NOT EXISTS throughout; idempotent.
    - triggers.sql: DROP TRIGGER IF EXISTS + CREATE before each trigger;
                    always reflects current file state; takes effect on next startup.
    - views.sql:    DROP VIEW IF EXISTS + CREATE before each view; same pattern.

    executescript() issues an implicit COMMIT before running. This is safe at
    startup (no open transaction) and harmless for DDL. Do not call this inside
    an open transaction.

    Numbered migration files in db/migrations/ handle schema CHANGES only
    (ALTER TABLE, new simple tables, CREATE INDEX). They must not contain compound
    statements (triggers, views) — those belong in the files above.
    """
    for filename in ('schema.sql', 'triggers.sql', 'views.sql'):
        sql = (DB_DIR / filename).read_text()
        await conn.executescript(sql)
```

---

## Migration Runner

```python
# db/migrations/runner.py

from pathlib import Path
import aiosqlite

MIGRATIONS_DIR = Path(__file__).parent


async def run_pending(conn: aiosqlite.Connection):
    """
    Run numbered migration files in order. Simple DDL only — no compound statements.
    Trigger and view changes go in db/triggers.sql and db/views.sql, not here.

    Comment stripping is done on the raw file text before splitting on semicolons,
    avoiding incorrect splits when comment text contains semicolons.
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """)
    await conn.commit()

    row = await conn.execute_fetchone("SELECT MAX(version) FROM schema_version")
    current = row[0] or 0

    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(f.stem.split("_")[0])
        if version <= current:
            continue

        # Strip single-line comments on the raw text before splitting.
        # Post-split stripping incorrectly handles lines like: SELECT 1 -- comment
        raw = f.read_text()
        lines = [line.split('--')[0] for line in raw.splitlines()]
        text = '\n'.join(lines)
        statements = [s.strip() for s in text.split(';') if s.strip()]

        await conn.execute("BEGIN")
        try:
            for stmt in statements:
                await conn.execute(stmt)
            await conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (version,)
            )
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            raise RuntimeError(f"Migration {f.name} failed: {e}") from e
```

---

## Application Layer

### database.py

```python
# api/database.py

import aiosqlite
from contextlib import asynccontextmanager
from api.config import settings


async def get_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA busy_timeout = 5000")
    return conn


async def get_db():
    """FastAPI dependency: read-write connection to research.db."""
    conn = await get_connection()
    try:
        yield conn
    finally:
        await conn.close()


@asynccontextmanager
async def get_library_db():
    """
    Read-only connection to library.sqlite. Used as an async context manager.
    Never used as a FastAPI dependency — callers manage scope explicitly.

    Usage:
        async with get_library_db() as lib:
            row = await lib.execute_fetchone(...)

    Raises RuntimeError if library_db_path is not configured.
    """
    if not settings.library_db_path:
        raise RuntimeError("library_db_path is not configured")
    conn = await aiosqlite.connect(
        f"file:{settings.library_db_path}?mode=ro", uri=True
    )
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()
```

### config.py additions

```python
# api/config.py additions

library_db_path: str = ""
# Path to library.sqlite. Empty string disables canvas source documents feature
# and makes get_library_db() raise RuntimeError.
```

### Canvas Routes

```python
# api/routes/canvas.py

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from ulid import ULID
from api.database import get_db, get_library_db
from api.config import settings

router = APIRouter()


# ─── CANVAS UPDATE (Protocol 1) ──────────────────────────────────────────────

class CanvasUpdate(BaseModel):
    narrative: str
    diff_summary: str


@router.patch("/{canvas_id}")
async def update_canvas(canvas_id: str, payload: CanvasUpdate, db=Depends(get_db)):
    await db.execute("BEGIN")
    try:
        await db.execute("""
            UPDATE canvas SET
                narrative = ?,
                last_reviewed = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE id = ?
        """, (payload.narrative, canvas_id))
        await db.execute("""
            INSERT INTO canvas_version_history (id, canvas_id, diff_summary)
            VALUES (?, ?, ?)
        """, (str(ULID()), canvas_id, payload.diff_summary))
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Protocol 1: surface affected theses at mutation site
    affected = await db.execute_fetchall("""
        SELECT t.id, t.instrument, t.status
        FROM thesis t
        JOIN thesis_linked_canvases tlc ON t.id = tlc.thesis_id
        WHERE tlc.canvas_id = ? AND t.status IN ('ready', 'active')
    """, (canvas_id,))

    return {
        "canvas_id": canvas_id,
        "protocol_1": {
            "affected_theses": [dict(r) for r in affected],
            "action_required": "Review kill conditions on each listed thesis against this canvas update."
        }
    }


# ─── CROSS-CURRENTS ──────────────────────────────────────────────────────────

class CrossCurrentPayload(BaseModel):
    target_canvas_id: str
    relationship_description: str


@router.post("/{canvas_id}/cross-currents")
async def add_cross_current(
    canvas_id: str, payload: CrossCurrentPayload, db=Depends(get_db)
):
    if canvas_id == payload.target_canvas_id:
        raise HTTPException(400, "Cannot link a canvas to itself")
    if not await db.execute_fetchone("SELECT id FROM canvas WHERE id = ?", (canvas_id,)):
        raise HTTPException(404, "Source canvas not found")
    if not await db.execute_fetchone("SELECT id FROM canvas WHERE id = ?", (payload.target_canvas_id,)):
        raise HTTPException(404, "Target canvas not found")

    cc_id = str(ULID())
    await db.execute("BEGIN")
    try:
        await db.execute("""
            INSERT INTO canvas_cross_currents
                (id, source_canvas_id, target_canvas_id, relationship_description)
            VALUES (?, ?, ?, ?)
        """, (cc_id, canvas_id, payload.target_canvas_id, payload.relationship_description))
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"id": cc_id}


@router.delete("/{canvas_id}/cross-currents/{target_canvas_id}")
async def remove_cross_current(canvas_id: str, target_canvas_id: str, db=Depends(get_db)):
    await db.execute(
        "DELETE FROM canvas_cross_currents WHERE source_canvas_id = ? AND target_canvas_id = ?",
        (canvas_id, target_canvas_id)
    )
    await db.commit()
    return {"deleted": True}


@router.get("/{canvas_id}/cross-currents")
async def list_cross_currents(canvas_id: str, db=Depends(get_db)):
    rows = await db.execute_fetchall("""
        SELECT cc.id, cc.target_canvas_id, c.name AS target_name,
               cc.relationship_description, cc.created_at
        FROM canvas_cross_currents cc
        JOIN canvas c ON c.id = cc.target_canvas_id
        WHERE cc.source_canvas_id = ?
        ORDER BY cc.created_at ASC
    """, (canvas_id,))
    return {"cross_currents": [dict(r) for r in rows]}


# ─── CANVAS SOURCE DOCUMENTS ─────────────────────────────────────────────────

class SourceDocumentLink(BaseModel):
    library_document_id: str
    note: str = None


@router.post("/{canvas_id}/sources")
async def link_source_document(
    canvas_id: str, payload: SourceDocumentLink, db=Depends(get_db)
):
    if not settings.library_db_path:
        raise HTTPException(503, "Library database not configured")
    if not await db.execute_fetchone("SELECT id FROM canvas WHERE id = ?", (canvas_id,)):
        raise HTTPException(404, "Canvas not found")

    async with get_library_db() as lib:
        doc = await lib.execute_fetchone(
            "SELECT id, title FROM documents WHERE id = ?",
            (payload.library_document_id,)
        )
    if doc is None:
        raise HTTPException(404, "Library document not found")

    await db.execute("BEGIN")
    try:
        await db.execute("""
            INSERT OR IGNORE INTO canvas_source_documents
                (canvas_id, library_document_id, note)
            VALUES (?, ?, ?)
        """, (canvas_id, payload.library_document_id, payload.note))
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"canvas_id": canvas_id, "library_document_id": payload.library_document_id,
            "title": doc["title"]}


@router.delete("/{canvas_id}/sources/{library_document_id}")
async def unlink_source_document(
    canvas_id: str, library_document_id: str, db=Depends(get_db)
):
    await db.execute(
        "DELETE FROM canvas_source_documents WHERE canvas_id = ? AND library_document_id = ?",
        (canvas_id, library_document_id)
    )
    await db.commit()
    return {"deleted": True}


@router.get("/{canvas_id}/sources")
async def list_source_documents(canvas_id: str, db=Depends(get_db)):
    if not settings.library_db_path:
        return {"sources": []}
    links = await db.execute_fetchall(
        "SELECT library_document_id, note, linked_at FROM canvas_source_documents "
        "WHERE canvas_id = ? ORDER BY linked_at DESC",
        (canvas_id,)
    )
    if not links:
        return {"sources": []}

    async with get_library_db() as lib:
        doc_ids = [r["library_document_id"] for r in links]
        placeholders = ",".join("?" * len(doc_ids))
        docs = await lib.execute_fetchall(
            f"SELECT id, title, authors, year, summary FROM documents WHERE id IN ({placeholders})",
            doc_ids
        )

    docs_by_id = {d["id"]: dict(d) for d in docs}
    return {
        "sources": [
            {
                **docs_by_id.get(r["library_document_id"], {"title": "[not found]"}),
                "library_document_id": r["library_document_id"],
                "note": r["note"],
                "linked_at": r["linked_at"]
            }
            for r in links
        ]
    }


@router.get("/library-search")
async def search_library_documents(q: str, limit: int = 10):
    if not settings.library_db_path:
        raise HTTPException(503, "Library database not configured")
    if len(q.strip()) < 2:
        raise HTTPException(400, "Query must be at least 2 characters")

    async with get_library_db() as lib:
        rows = await lib.execute_fetchall("""
            SELECT id, title, authors, year, summary
            FROM documents
            WHERE lower(title)   LIKE lower(?) OR
                  lower(summary) LIKE lower(?) OR
                  lower(authors) LIKE lower(?)
            ORDER BY year DESC
            LIMIT ?
        """, (f"%{q}%", f"%{q}%", f"%{q}%", limit))
    return {"results": [dict(r) for r in rows]}
```

### Image Serve — Path Traversal Fix

```python
# api/routes/images.py (serve endpoint only; upload endpoints unchanged)

@router.get("/images/{entity}/{entity_id}/{filename}")
async def serve_image(entity: str, entity_id: str, filename: str):
    if entity not in ("observations", "setups"):
        raise HTTPException(400, "Invalid entity")

    path = (IMAGE_ROOT / entity / entity_id / filename).resolve()

    # Prevent path traversal: crafted entity_id or filename sequences (e.g. ../../etc)
    # must not escape IMAGE_ROOT. Path division does not sanitize traversal sequences.
    if not path.is_relative_to(IMAGE_ROOT.resolve()):
        raise HTTPException(400, "Invalid path")

    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)
```

### Review — Two-Step Phase 2 (unchanged from v1)

```python
# api/routes/review.py

@router.patch("/{review_id}/zone3-clear")
async def set_zone3_clear(review_id: str, db=Depends(get_db)):
    review = await db.execute_fetchone(
        "SELECT locked_at, zone_3_clear FROM review WHERE id = ?", (review_id,)
    )
    if review is None:
        raise HTTPException(404)
    if review["zone_3_clear"] == 1:
        raise HTTPException(400, "Zone 3 already cleared")

    locked_at = datetime.fromisoformat(review["locked_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if now < locked_at + timedelta(hours=24):
        remaining = (locked_at + timedelta(hours=24)) - now
        raise HTTPException(423, {
            "error": "time_lock_active",
            "unlocks_at": (locked_at + timedelta(hours=24)).isoformat(),
            "remaining_seconds": int(remaining.total_seconds())
        })

    await db.execute("BEGIN")
    try:
        await db.execute(
            "UPDATE review SET zone_3_clear = 1, "
            "zone_3_cleared_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            (review_id,)
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"review_id": review_id, "zone_3_clear": True}


@router.patch("/{review_id}/phase2")
async def file_phase2(review_id: str, payload: Phase2Payload, db=Depends(get_db)):
    review = await db.execute_fetchone(
        "SELECT zone_3_clear FROM review WHERE id = ?", (review_id,)
    )
    if review is None:
        raise HTTPException(404)
    if not review["zone_3_clear"]:
        raise HTTPException(400, {
            "error": "zone_3_not_cleared",
            "message": "File zone3-clear first."
        })

    await db.execute("BEGIN")
    try:
        await db.execute("""
            UPDATE review SET
                phase2_created_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
                mistake_type = ?, analysis = ?,
                single_update = ?, what_not_changing = ?
            WHERE id = ?
        """, (payload.mistake_type, payload.analysis,
              payload.single_update, payload.what_not_changing, review_id))
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"review_id": review_id}
```

---

## Export Pipeline

### ResearchExporter

```python
# pipeline/research_exporter.py

import sqlite3
import yaml
import logging
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class ResearchExporter:
    def __init__(self, research_db_path, library_db_path, vault_path,
                 chroma_collection, ollama_client=None):
        self.research = sqlite3.connect(research_db_path)
        self.research.row_factory = sqlite3.Row
        self.library_db_path = library_db_path
        # vault_path is the obsidian_vault root from config.
        # Notes are written to vault_path/research/{entity_type}/filename.md
        # and are immediately visible in Obsidian.
        self.vault_path = Path(vault_path)
        self.collection = chroma_collection
        self.ollama = ollama_client

    def run(self, incremental: bool = True):
        self._run_llm_pass(incremental=incremental)
        self._run_embedding_pass()

    def _get_watermark(self, entity_type: str) -> str:
        row = self.research.execute(
            "SELECT last_exported_at FROM export_watermarks WHERE entity_type = ?",
            (entity_type,)
        ).fetchone()
        return row[0] if row else "1970-01-01T00:00:00Z"

    def _set_watermark(self, entity_type: str):
        now = datetime.now(timezone.utc).isoformat()
        self.research.execute(
            "UPDATE export_watermarks SET last_exported_at = ? WHERE entity_type = ?",
            (now, entity_type)
        )
        self.research.commit()

    def _record_failure(self, entity_type: str, entity_id: str, error: str):
        self.research.execute("""
            INSERT INTO failed_exports (id, entity_type, entity_id, error)
            VALUES (lower(hex(randomblob(16))), ?, ?, ?)
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                error = excluded.error,
                failed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
                resolved = 0
        """, (entity_type, entity_id, error))
        self.research.commit()

    def _run_llm_pass(self, incremental: bool = True):
        if incremental:
            self._export_from_events()
        else:
            for method in (self.export_canvases, self.export_completed_theses,
                           self.export_filed_reviews, self.export_observations,
                           self.export_passed_setups):
                method()

    def _export_from_events(self):
        """
        Incremental export. For each entity type, reads events since the watermark,
        exports affected entities.

        Watermark advances only if zero failures occurred in the batch.
        Failures are written to failed_exports and retried via reconcile_failed_exports().

        Trade events are present in entity_events but trade has no watermark entry
        and no exporter — those events are analytics-only (Design Decision 12).
        """
        entity_type_exporters = {
            "canvas":      self.export_canvas_by_id,
            "thesis":      self.export_thesis_by_id,
            "review":      self.export_review_by_id,
            "observation": self.export_observation_by_id,
            "setup":       self.export_setup_by_id,
        }

        for entity_type, exporter in entity_type_exporters.items():
            watermark = self._get_watermark(entity_type)
            events = self.research.execute("""
                SELECT DISTINCT entity_id FROM entity_events
                WHERE entity_type = ? AND occurred_at > ?
                ORDER BY occurred_at ASC
            """, (entity_type, watermark)).fetchall()

            if not events:
                continue

            failures = []
            for row in events:
                try:
                    exporter(row["entity_id"])
                except Exception as e:
                    log.error(f"Export failed: {entity_type} {row['entity_id']}: {e}")
                    failures.append((entity_type, row["entity_id"], str(e)))

            if failures:
                for ft, fid, ferr in failures:
                    self._record_failure(ft, fid, ferr)
                log.warning(
                    f"{len(failures)} export(s) failed for {entity_type}; "
                    f"watermark not advanced"
                )
            else:
                self._set_watermark(entity_type)

    def reconcile_failed_exports(self):
        """Retry all unresolved failed exports. Called via --mode reconcile."""
        entity_type_exporters = {
            "canvas":      self.export_canvas_by_id,
            "thesis":      self.export_thesis_by_id,
            "review":      self.export_review_by_id,
            "observation": self.export_observation_by_id,
            "setup":       self.export_setup_by_id,
        }

        rows = self.research.execute(
            "SELECT entity_type, entity_id FROM failed_exports WHERE resolved = 0"
        ).fetchall()

        for row in rows:
            exporter = entity_type_exporters.get(row["entity_type"])
            if not exporter:
                continue
            try:
                exporter(row["entity_id"])
                self.research.execute(
                    "UPDATE failed_exports SET resolved = 1 "
                    "WHERE entity_type = ? AND entity_id = ?",
                    (row["entity_type"], row["entity_id"])
                )
                self.research.commit()
                log.info(f"Reconciled: {row['entity_type']} {row['entity_id']}")
            except Exception as e:
                log.error(f"Reconcile failed: {row['entity_type']} {row['entity_id']}: {e}")

    def export_canvas_by_id(self, canvas_id: str):
        c = self.research.execute(
            "SELECT * FROM canvas WHERE id = ?", (canvas_id,)
        ).fetchone()
        if c is None or c["status"] != "active":
            # Archived canvas: note is orphaned in vault (not deleted).
            # See out-of-scope section.
            return

        doc_id = self._stable_doc_id("canvas", c["id"])

        linked_theses = self.research.execute("""
            SELECT t.instrument, t.id FROM thesis t
            JOIN thesis_linked_canvases tlc ON t.id = tlc.thesis_id
            WHERE tlc.canvas_id = ?
        """, (c["id"],)).fetchall()

        conditions = self.research.execute(
            "SELECT condition FROM canvas_invalidation_conditions WHERE canvas_id = ?",
            (c["id"],)
        ).fetchall()

        raw_topics = self._extract_topics(
            c["narrative"],
            [c["name"]] + [row["condition"] for row in conditions]
        )
        topics_with_salience = self._rank_salience(raw_topics)

        self._upsert_record(doc_id, c["id"], "canvas", c["name"], c["narrative"], "active")
        self._populate_concept_graph(doc_id, topics_with_salience, [
            (a, "relates_to", b)
            for i, (a, _) in enumerate(topics_with_salience)
            for b, _ in topics_with_salience[i+1:]
        ])

        explicit_sources = self._get_explicit_source_backlinks(c["id"])
        inferred_docs = self._find_related_documents(doc_id) if not explicit_sources else []

        explicit_doc_ids = [
            row["library_document_id"] for row in self.research.execute(
                "SELECT library_document_id FROM canvas_source_documents WHERE canvas_id = ?",
                (c["id"],)
            ).fetchall()
        ]
        self._backlink_documents(c["name"], explicit_doc_ids)

        frontmatter = {
            "id": doc_id,
            "research_entity_id": c["id"],
            "source_type": "canvas",
            "title": c["name"],
            "category": ["macro"],
            "topics": raw_topics,
            "summary": c["narrative"][:500],
            "status": c["status"],
            "last_reviewed": c["last_reviewed"],
            "related": (
                [f"[[Thesis — {t['instrument']} — {t['id'][:8]}]]" for t in linked_theses]
                + explicit_sources
                + inferred_docs
            ),
            "indexed": datetime.now(timezone.utc).isoformat()
        }

        self._write_note("research/canvases", self._note_filename([c["name"]]),
                         frontmatter, c["narrative"])

    def _get_explicit_source_backlinks(self, canvas_id: str) -> list[str]:
        sources = self.research.execute(
            "SELECT library_document_id FROM canvas_source_documents WHERE canvas_id = ?",
            (canvas_id,)
        ).fetchall()
        if not sources:
            return []
        try:
            lib = sqlite3.connect(f"file:{self.library_db_path}?mode=ro", uri=True)
            lib.row_factory = sqlite3.Row
            ids = [s["library_document_id"] for s in sources]
            docs = lib.execute(
                f"SELECT id, title FROM documents WHERE id IN ({','.join('?'*len(ids))})", ids
            ).fetchall()
            lib.close()
            return [f"[[{d['title']}]]" for d in docs]
        except Exception as e:
            log.warning(f"Could not resolve explicit source documents: {e}")
            return []

    def _write_note(self, subdir: str, filename: str, frontmatter: dict, body: str):
        """
        Write an Obsidian note to vault_path/subdir/filename.md.
        vault_path is the obsidian_vault root from config — notes land directly
        in the vault and are immediately visible in Obsidian.
        """
        note_dir = self.vault_path / subdir
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = note_dir / f"{filename}.md"
        fm_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
        note_path.write_text(f"---\n{fm_str}---\n\n{body}", encoding='utf-8')
```

### Analytical Queries

```sql
-- Time-axis analytics

-- Thesis lifespan
SELECT instrument, mistake_type, lifespan_days, created_at, terminal_at
FROM thesis_lifespan
ORDER BY lifespan_days ASC;

-- Review lag
SELECT instrument, hours_to_phase2, mistake_type
FROM review_lag
ORDER BY hours_to_phase2 DESC;

-- Type 2 error clustering by calendar period
SELECT strftime('%Y-%m', e.occurred_at) AS month, COUNT(*) AS type_2_count
FROM entity_events e
JOIN review r ON r.id = e.entity_id
WHERE e.entity_type = 'review'
  AND e.new_status = 'phase2'
  AND r.mistake_type = 'type_2'
GROUP BY month
ORDER BY month ASC;

-- Full provenance chain: library document → canvas → thesis → trade → review
-- Prerequisite: ATTACH DATABASE '/path/to/library.sqlite' AS library
SELECT
    d.title AS source_document,
    c.name  AS canvas,
    t.instrument AS thesis,
    tr.id   AS trade_id,
    e_close.occurred_at AS trade_closed_at,
    r.mistake_type
FROM canvas_source_documents csd
JOIN canvas c ON csd.canvas_id = c.id
JOIN thesis_linked_canvases tlc ON tlc.canvas_id = c.id
JOIN thesis t ON t.id = tlc.thesis_id
LEFT JOIN trade tr ON tr.id = t.linked_trade_id
LEFT JOIN entity_events e_close
    ON e_close.entity_id = tr.id AND e_close.new_status = 'closed'
LEFT JOIN review r ON r.trade_id = tr.id AND r.phase2_created_at IS NOT NULL
JOIN (SELECT id, title FROM library.documents) d ON d.id = csd.library_document_id
ORDER BY e_close.occurred_at DESC;

-- Knowledge gap: canvas concepts covered in the library but not explicitly linked
-- Prerequisites:
--   ATTACH DATABASE '/path/to/library.sqlite' AS library
--   library.documents must include research_entity_id and source_type columns
--     (populated by ResearchExporter._upsert_record)
--   library.document_concepts and library.concepts must be populated
SELECT
    c.name AS canvas,
    con.name AS concept,
    COUNT(DISTINCT other_dc.document_id) AS docs_in_library,
    COUNT(DISTINCT csd.library_document_id) AS docs_explicitly_linked
FROM canvas c
-- Canvas's exported library record, which carries its extracted topics as concepts
JOIN library.documents canvas_ld
    ON canvas_ld.research_entity_id = c.id
   AND canvas_ld.source_type = 'canvas'
JOIN library.document_concepts canvas_dc ON canvas_dc.document_id = canvas_ld.id
JOIN library.concepts con ON con.id = canvas_dc.concept_id
-- Other (non-canvas) library documents sharing those concepts
JOIN library.document_concepts other_dc ON other_dc.concept_id = con.id
JOIN library.documents other_doc
    ON other_doc.id = other_dc.document_id
   AND other_doc.source_type != 'canvas'
-- Compare against explicitly linked documents
LEFT JOIN canvas_source_documents csd
    ON csd.canvas_id = c.id
   AND csd.library_document_id = other_doc.id
WHERE c.status = 'active'
GROUP BY c.id, con.id
HAVING COUNT(DISTINCT other_dc.document_id) > COUNT(DISTINCT csd.library_document_id)
ORDER BY (COUNT(DISTINCT other_dc.document_id) - COUNT(DISTINCT csd.library_document_id)) DESC;
```

---

## CLI

```python
# run_ingestion.py

import argparse
from pathlib import Path
from pipeline.research_exporter import ResearchExporter


def parse_args():
    parser = argparse.ArgumentParser(description='Knowledge library ingestion pipeline')
    parser.add_argument(
        '--mode',
        choices=['full', 'incremental', 'research', 'reconcile', 'retry-failed'],
        default='incremental',
        help=(
            'full: re-export all library documents and all research entities. '
            'incremental: standard library incremental + research events since watermark. '
            'research: research events only (skips library document processing). '
            'reconcile: re-drive failed ChromaDB embeddings and failed_exports. '
            'retry-failed: reprocess failed library document ingestions.'
        )
    )
    return parser.parse_args()


args = parse_args()

if args.mode in ('full', 'incremental', 'research'):
    exporter = ResearchExporter(
        research_db_path=config['research_db'],
        library_db_path=config['db_path'],
        vault_path=Path(config['obsidian_vault']),
        chroma_collection=collection,
        ollama_client=ollama_client if ollama_available else None
    )
    incremental = (args.mode != 'full')
    exporter.run(incremental=incremental)

if args.mode == 'reconcile':
    exporter.reconcile_embeddings()
    exporter.reconcile_failed_exports()

if args.mode == 'retry-failed':
    retry_failed_ingestions()
```

---

## Config

```yaml
# config.yaml

research_db:    /path/to/research/data/research.db
image_root:     /path/to/research/data/images

onedrive_root:  /Users/yourname/OneDrive
obsidian_vault: /Users/yourname/knowledge-library/vault   # = vault_path in ResearchExporter
db_path:        /Users/yourname/knowledge-library/db/library.sqlite
chroma_path:    /Users/yourname/knowledge-library/db/chroma

# Integration: set to library.sqlite path to enable canvas source documents in the
# research API. Leave empty to run the research tool fully standalone.
library_db_path: /Users/yourname/knowledge-library/db/library.sqlite

ollama:
  host:    http://192.168.1.x:11434
  model:   mistral
  timeout: 60

extraction:
  excerpt_length_chars: 3000
  ocr_threshold_words:  100
  min_pages_for_ocr_check: 5

concept_graph:
  min_edge_weight:       0.4
  max_concepts_per_doc:  15
  max_relations_per_doc: 10
```

---

## Requirements

```
# research/requirements.txt
fastapi==0.111.0
uvicorn[standard]==0.29.0
aiosqlite==0.20.0
jinja2==3.1.4
python-ulid==2.7.0
python-multipart==0.0.9
pydantic==2.7.1
python-dotenv==1.0.1

# knowledge-library/requirements.txt
pdfplumber
pytesseract
ebooklib
chromadb
sentence-transformers
pyyaml
ollama
```

---

## Build Sequence

Phase gates are hard stops.

| Phase | Scope | Description | Hours |
|---|---|---|---|
| 1 | research.db | Schema + triggers + views. Exercise every state machine path, every gate, every append-only constraint. Verify `setup_taken_gate` via junction table subquery. Verify `thesis_lifespan` returns one row per thesis regardless of invalidation cycles. Verify `active_surveillance` returns exactly one row per watching setup. Verify all event log triggers fire. Verify `trade_review_id_fk` trigger. Verify both emotional state triggers (INSERT + UPDATE). Seed data covers all paths. | 14–18 |
| 2 | research API | FastAPI skeleton: DB connection with WAL pragma, `init_schema()` + migration runner in lifespan, stub routes, health check | 4–6 |
| 3 | research API | Core write paths: Canvas update (Protocol 1 response), Thesis state machine, Trade open with snapshot, Review Phase 1 | 12–16 |
| 4 | research API | Staleness views + `/ritual/morning` endpoint | 4–6 |
| 5 | research frontend | Ritual dashboard | 6–8 |
| 6 | research API + frontend | Image upload + path-traversal-safe serve endpoint | 4–6 |
| 7 | research frontend | Observation and Setup forms with file upload UI | 6–8 |
| 8 | research frontend | Canvas detail UI (cross-currents section + source documents section), Thesis UI, Trade UI | 14–18 |
| 9 | research API + frontend | Review Phase 1 + zone3-clear endpoint + Phase 2 endpoint with two-step UI | 6–8 |
| 10 | research API + frontend | Protocol implementations 2–4 with UI notifications | 6–8 |
| 11 | research frontend | Inbox quick-capture + evening routing UI | 4–6 |
| 12 | integration | `get_library_db()` context manager, `library_db_path` config, canvas source document routes (`/sources`, `/library-search`). Requires `library.sqlite` to be populated (complete knowledge library Phase 1–2 first). | 6–8 |
| 13 | integration | `ResearchExporter`: per-entity export methods, `_write_note()`, concept graph, Obsidian note generation for canvases/theses/reviews/observations/passed setups. Full export mode verified end-to-end. | 10–14 |
| 14 | integration | Watermark-based incremental export. `failed_exports` tracking. `reconcile_failed_exports()`. Verify watermark advances only on zero failures. Verify `--mode reconcile` retries failures and marks resolved. | 5–7 |
| 15 | integration | Provenance analytics: `thesis_lifespan`, `review_lag` views; full provenance chain query with ATTACH; knowledge gap query (requires `library.documents` to include `research_entity_id` and `source_type` columns). | 3–4 |
| **Total** | | | **108–145 hours** |

**Phase 12 dependency:** complete knowledge library pipeline phases 1–2 (`personal-knowledge-library-build.md`) before attempting Phase 12. The research tool runs fully standalone without `library_db_path` set.

**Phase 15 dependency:** the knowledge gap query requires `library.documents` to have `research_entity_id` and `source_type` columns populated by `ResearchExporter._upsert_record`. Verify these columns exist in `library.sqlite` before running that query.

---

## What's Out of Scope

- **Archived canvas note deletion.** When a canvas is archived, `export_canvas_by_id` returns without writing. The existing Obsidian note is orphaned — it remains in the vault but is no longer updated. No deletion propagation is implemented. Stale notes in `research/canvases/` should be manually removed when a canvas is archived.
- **Vol/options schema beyond trade-level fields.** The `vol` observation type captures sightings. A structured model for vol surfaces and term structure is a separate analytical tool.
- **P&L attribution.** Quantitative return attribution belongs in a separate layer, addressable via `trade_id` linkage.
- **Automated data feeds for invalidation conditions.** Manual assessment is sufficient for v1.
- **Canvas narrative version diffing.** Timestamps and summaries are logged; a diff view waits for a concrete use case.
- **Risk aggregation across trades.** Portfolio-level delta and correlation exposure are not v1 requirements.
- **Multi-device access.** The SQLite + file sync assumption holds at single-device scale.
