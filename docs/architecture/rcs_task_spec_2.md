# Research Capture System — Claude Code Task Specification

**Source documents:**
- `unified_build_spec_v2.md` (architecture, schema, routes, exporter)
- `design_spec_rcs_v1.md` (visual design, components, templates)
- `gap_prevention_protocol.md` (integration verification discipline)
- `code-philosophy.md` (code quality principles)

**Applies to:** Every task below.

---

## How to Use This Document

Each task is scoped to fit within a single Claude Code session (~200k context, rate-limited). Tasks are strictly sequential — each depends on the outputs of the previous. Do not skip tasks or reorder them.

Every task follows the three mandatory sections from the gap prevention protocol: Pre-flight (Section A), Constraints (Section B), and Regression Suite (Section C). These are written inline per task rather than repeated as boilerplate — each task's sections contain only what is relevant to that task.

After completing any task, update `CLAUDE.md` per Fix 3 of the gap prevention protocol. Every completion report must include `CLAUDE.md updated: YES` or `CLAUDE.md updated: NO — reason: [reason]`.

---

## Task 000: Project Scaffold and CLAUDE.md

**Goal:** Create the directory structure, install dependencies, initialise CLAUDE.md.

### Pre-flight

```bash
# Confirm Python version
python3 --version  # Must be 3.11+

# Confirm working directory is clean
ls research/ 2>/dev/null && echo "CONFLICT: research/ exists" || echo "OK"
ls knowledge-library/ 2>/dev/null && echo "CONFLICT: knowledge-library/ exists" || echo "OK"
```

### Implementation

1. Create the full directory tree per the Project Structure section of the build spec:

```
research/
├── db/
│   ├── migrations/
├── api/
│   ├── models/
│   ├── routes/
│   └── protocols/
├── frontend/
│   ├── templates/
│   │   ├── components/
│   │   ├── ritual/
│   │   ├── canvas/
│   │   ├── thesis/
│   │   ├── observation/
│   │   ├── review/
│   │   └── entities/
│   └── static/
│       └── css/
├── data/
│   └── images/
│       ├── observations/
│       └── setups/
└── tests/

knowledge-library/
├── pipeline/
├── db/
└── vault/
    └── research/
        ├── canvases/
        ├── theses/
        ├── reviews/
        ├── observations/
        └── setups/
```

2. Create `research/requirements.txt` per the build spec.

3. Create `knowledge-library/requirements.txt` per the build spec.

4. Create `research/db/__init__.py` (empty).

5. Create `research/api/__init__.py` (empty), same for `models/`, `routes/`, `protocols/`.

6. Install research dependencies: `pip install -r research/requirements.txt`

7. Create `CLAUDE.md` at the project root with:
   - Component Status table (all components listed as `not started`)
   - Output Contracts section (empty, to be populated)
   - DB Tables section (empty)
   - Shared Utilities section (empty)
   - Deprecated Files section (empty)
   - Maintenance Protocol section (verbatim from gap prevention protocol Fix 3)

8. Create `docs/architecture/` directory. Copy `gap_prevention_protocol.md` and `code-philosophy.md` into it for reference.

### Constraints

- Do not create any config files yet — that is Task 001's scope.
- Do not create any `.sql` files yet.
- Do not install knowledge-library dependencies yet (Ollama, sentence-transformers, etc. have heavy system requirements).

### Smoke test

```bash
cd research
python3 -c "import fastapi, aiosqlite, jinja2, pydantic; print('deps OK')"
ls db/migrations/ && echo "migrations dir OK"
ls api/routes/ && echo "routes dir OK"
ls frontend/templates/components/ && echo "templates dir OK"
cat ../CLAUDE.md | head -5 && echo "CLAUDE.md exists"
```

### Regression suite

N/A — this is the first task. No prior functionality to regress.

---

## Task 001: Database Schema, Triggers, and Views

**Goal:** Create `schema.sql`, `triggers.sql`, `views.sql` per the build spec. All SQL is verbatim from the spec — no improvisation.

### Pre-flight

```bash
# Confirm directory exists
ls research/db/ || echo "MISSING: research/db/"

# Confirm no SQL files exist yet
ls research/db/*.sql 2>/dev/null && echo "CONFLICT: SQL files already exist" || echo "OK"
```

Read in full before writing:
- Build spec: Database Schema section (table ordering, all CREATE TABLE statements)
- Build spec: Enforcement Triggers section (all triggers)
- Build spec: SQL Views section (all views)

### Implementation

1. Create `research/db/schema.sql` — all tables from the build spec, in the exact order specified (canvas → setup → thesis → trade → observation → junction tables → action → review → inbox → entity_events → canvas_source_documents → export_watermarks → failed_exports). Include the `INSERT OR IGNORE INTO export_watermarks` seed.

2. Create `research/db/triggers.sql` — all triggers from the build spec. Every trigger must be preceded by `DROP TRIGGER IF EXISTS`. Include: thesis state machine (5 triggers), thesis touch triggers (5), setup state machine (3), trade_review_id_fk, action_cancel_note_required, review enforcement (4), frozen fields (2), append-only (9), entity event log (9). Total: ~37 triggers.

3. Create `research/db/views.sql` — all views from the build spec. Every view preceded by `DROP VIEW IF EXISTS`. Include: staleness views (4), active_surveillance, canvas_observation_backlinks, learning views (5), time-axis analytics (2). Total: ~12 views.

### Constraints

- Copy SQL verbatim from the build spec. Do not rename columns, change types, add defaults, or modify CHECK constraints.
- Do not add any tables, columns, or triggers not in the spec.
- Table ordering is load-bearing (FK dependencies). Do not reorder.
- `PRAGMA foreign_keys = ON` goes in `schema.sql` at the top.
- WAL mode is set in `database.py` (Task 002), not in schema.

### Smoke test

```bash
cd research
python3 -c "
import sqlite3, tempfile, os

db_path = tempfile.mktemp(suffix='.db')
conn = sqlite3.connect(db_path)
conn.execute('PRAGMA foreign_keys = ON')

for f in ('db/schema.sql', 'db/triggers.sql', 'db/views.sql'):
    sql = open(f).read()
    conn.executescript(sql)
    print(f'{f} loaded OK')

# Verify table count
tables = conn.execute(\"\"\"
    SELECT name FROM sqlite_master WHERE type='table'
    AND name NOT LIKE 'sqlite_%'
    ORDER BY name
\"\"\").fetchall()
table_names = [t[0] for t in tables]
print(f'Tables ({len(table_names)}): {table_names}')
assert len(table_names) >= 22, f'Expected >= 22 tables, got {len(table_names)}'

# Verify trigger count
triggers = conn.execute(\"\"\"
    SELECT name FROM sqlite_master WHERE type='trigger'
\"\"\").fetchall()
print(f'Triggers: {len(triggers)}')
assert len(triggers) >= 35, f'Expected >= 35 triggers, got {len(triggers)}'

# Verify view count
views = conn.execute(\"\"\"
    SELECT name FROM sqlite_master WHERE type='view'
\"\"\").fetchall()
print(f'Views: {len(views)}')
assert len(views) >= 12, f'Expected >= 12 views, got {len(views)}'

# Verify export_watermarks seed
wm = conn.execute('SELECT COUNT(*) FROM export_watermarks').fetchone()[0]
assert wm == 5, f'Expected 5 watermark rows, got {wm}'

os.unlink(db_path)
print('ALL SCHEMA CHECKS PASS')
"
```

### Regression suite

N/A — first database task.

---

## Task 002: Schema Init, Migration Runner, and DB Connection Layer

**Goal:** Create `db/init.py`, `db/migrations/runner.py`, `api/database.py`, `api/config.py`, and `api/main.py` (FastAPI skeleton with lifespan). Health check endpoint.

### Pre-flight

```bash
# Confirm schema files exist
ls research/db/schema.sql research/db/triggers.sql research/db/views.sql || echo "MISSING"

# Confirm no application files exist yet
ls research/api/main.py 2>/dev/null && echo "CONFLICT" || echo "OK"
ls research/api/database.py 2>/dev/null && echo "CONFLICT" || echo "OK"
ls research/api/config.py 2>/dev/null && echo "CONFLICT" || echo "OK"
ls research/db/init.py 2>/dev/null && echo "CONFLICT" || echo "OK"

# Confirm no duplicate DB connection logic
grep -r "aiosqlite.connect" --include="*.py" research/ | grep -v venv || echo "OK — no existing connections"
```

### Implementation

1. Create `research/api/config.py` — Pydantic settings class with `db_path`, `image_root`, `library_db_path` (default empty string). Load from environment or `.env`. Use `research/data/research.db` as the default db_path.

2. Create `research/db/init.py` — `init_schema()` function per the build spec. Loads `schema.sql`, `triggers.sql`, `views.sql` via `executescript()`.

3. Create `research/db/migrations/runner.py` — `run_pending()` per the build spec. Comment stripping before semicolon splitting.

4. Create `research/db/migrations/__init__.py` (empty).

5. Create `research/api/database.py` — `get_connection()`, `get_db()`, `get_library_db()` per the build spec. WAL mode, foreign_keys ON, busy_timeout 5000.

6. Create `research/api/main.py`:
   - FastAPI app with lifespan that calls `init_schema()` and `run_pending()`.
   - Health check: `GET /health` returns `{"status": "ok", "db": "connected"}`.
   - Mounts static files from `frontend/static/`.
   - Sets up Jinja2 template directory.

7. Create `research/db/migrations/0001_initial.sql` — empty placeholder (schema is created by `schema.sql`, not migrations).

### Constraints

- `api/config.py` is the only config file for the research system. Do not create a second one.
- `api/database.py` is the only place DB connections are created. Do not create helpers elsewhere.
- WAL mode is set in `database.py`, not in schema.sql.
- `get_library_db()` must be an `@asynccontextmanager`, never a FastAPI dependency.
- `init_schema()` uses `executescript()` — do not use `execute()` for DDL.

### Smoke test

```bash
cd research

# Start server and verify health
timeout 10 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -s http://localhost:8099/health | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['status'] == 'ok', f'Bad status: {d}'
assert d['db'] == 'connected', f'DB not connected: {d}'
print('HEALTH CHECK PASS')
"
kill %1 2>/dev/null

# Verify DB was created with schema
python3 -c "
import sqlite3
conn = sqlite3.connect('data/research.db')
tables = conn.execute(\"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'\").fetchone()[0]
assert tables >= 22, f'Expected >= 22 tables, got {tables}'
print(f'DB INIT PASS — {tables} tables')
conn.close()
"
```

### Regression suite

```bash
cd research

# Schema still loads cleanly (Task 001)
python3 -c "
import sqlite3, tempfile, os
db = tempfile.mktemp(suffix='.db')
conn = sqlite3.connect(db)
conn.execute('PRAGMA foreign_keys = ON')
for f in ('db/schema.sql', 'db/triggers.sql', 'db/views.sql'):
    conn.executescript(open(f).read())
print('REGRESSION 1 PASS — schema loads')
os.unlink(db)
"
```

---

## Task 003: State Machine Verification with Seed Data

**Goal:** Write a comprehensive test script that exercises every state machine transition, every gate, every append-only constraint, and every event log trigger. Seed data covers all paths.

### Pre-flight

```bash
# Confirm schema and init exist
python3 -c "from research.db.init import init_schema; print('OK')" 2>/dev/null || \
python3 -c "
import sys; sys.path.insert(0, 'research')
from db.init import init_schema; print('init_schema importable')
"

ls research/db/schema.sql research/db/triggers.sql research/db/views.sql || echo "MISSING"
```

Read in full:
- All trigger definitions in `triggers.sql`
- All view definitions in `views.sql`
- Build spec Design Decisions 2, 4, 5, 6, 7, 10, 11, 12

### Implementation

Create `research/tests/test_state_machines.py` — a standalone script (not pytest, to avoid adding a dependency this early) that:

1. Creates a fresh in-memory SQLite DB, loads schema + triggers + views.

2. **Thesis state machine:** Tests every valid transition (`building→ready→active→invalidated→building`, `building→ready→active→archived`, `ready→building`). Tests every invalid transition (e.g. `building→active`, `archived→building`). Each invalid test must catch the expected RAISE error.

3. **Thesis gates:**
   - `thesis_ready_gate`: Verify it fails without macro kill conditions, without decision points, without worst_case_dollar, without linked canvases. Verify it passes when all four are present.
   - `thesis_active_gate`: Verify it fails without linked_trade_id. Passes with it.
   - `setup_taken_gate`: Verify taken fails without `setup_thesis_links` entry. Passes with one.

4. **Setup state machine:** Valid transitions (`watching→taken`, `watching→passed`). Terminal states (taken/passed cannot transition). `setup_passed_gate`: fails without reason/type, passes with both.

5. **Frozen fields:** Verify `entry_rules_stated`, `exit_rules_stated`, `thesis_snapshot` cannot be updated on trade. Verify `option_legs_partial_update` allows only `exit_premium` and `date_closed` updates.

6. **Append-only tables:** Verify UPDATE and DELETE are rejected on `trade_entries`, `trade_exits`, `observation`, `canvas_version_history`, `thesis_version_history`.

7. **Review enforcement:**
   - `review_emotional_state_one_word_ins`: Verify INSERT with multi-word emotional_state fails.
   - `review_emotional_state_one_word_upd`: Verify UPDATE with multi-word fails.
   - `review_zone3_timelock`: Verify zone3_clear fails within 24h of locked_at.
   - `review_phase2_zone3_gate`: Verify phase2 fails without zone_3_clear committed.

8. **trade_review_id_fk:** Verify setting review_id to a nonexistent review fails.

9. **Entity event log:** After running through the transitions above, verify `entity_events` contains the expected rows: canvas created, thesis created/status_changed, trade created/closed, observation created, setup created/status_changed, review filed (phase1 + phase2).

10. **Views:**
    - `thesis_lifespan`: Insert a thesis, transition to invalidated, verify view returns one row with correct lifespan. Then rebuild (invalidated→building→ready→active→archived) and verify still one row with most recent terminal event.
    - `active_surveillance`: Insert setups in various states, verify the view returns exactly one row per watching setup with correct link counts.
    - `stale_canvases`: Insert canvas with old last_reviewed, verify it appears.
    - `passed_setup_analysis`: Insert passed setups with both reason types, verify percentages.

11. Print a summary: `X/Y tests passed`.

### Constraints

- This is a verification script, not a test framework. Use plain `assert` and try/except.
- All test data uses ULIDs (or hex randomblob for simplicity).
- Do not modify schema, triggers, or views.
- Tests run against a fresh in-memory DB — no side effects.

### Smoke test

```bash
cd research
python3 tests/test_state_machines.py
# Must print "ALL TESTS PASSED" with 0 failures
```

### Regression suite

```bash
# Schema loads (Task 001)
python3 -c "
import sqlite3, tempfile, os
db = tempfile.mktemp(suffix='.db')
conn = sqlite3.connect(db)
conn.execute('PRAGMA foreign_keys = ON')
for f in ('db/schema.sql', 'db/triggers.sql', 'db/views.sql'):
    conn.executescript(open(f).read())
print('REGRESSION 1 PASS')
os.unlink(db)
"

# Server starts and health check passes (Task 002)
cd research
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'; print('REGRESSION 2 PASS')"
kill %1 2>/dev/null
```

---

## Task 004: Canvas CRUD Routes + Protocol 1

**Goal:** Canvas create, read, update (with Protocol 1 response), archive, cross-currents CRUD, invalidation conditions CRUD.

### Pre-flight

```bash
cd research

# Confirm database layer exists
python3 -c "
import sys; sys.path.insert(0, '.')
from api.database import get_db, get_connection
from api.config import settings
print('database layer OK')
"

# Confirm no canvas route exists
grep -r "canvas" --include="*.py" api/routes/ | grep -v __pycache__ || echo "OK — no canvas routes"

# Confirm ULID is available
python3 -c "from ulid import ULID; print('ulid OK')"
```

Read in full:
- Build spec: Canvas Routes section (all route code)
- Build spec: Design Decision 6 (Protocol 1)
- Build spec: Design Decision 13 (cross-currents in scope)

### Implementation

1. Create `research/api/routes/canvas.py` per the build spec:
   - `POST /canvas` — create canvas (id via ULID, requires name + narrative + last_reviewed)
   - `GET /canvas/{id}` — full canvas with related data
   - `PATCH /canvas/{id}` — update narrative with Protocol 1 response (verbatim from spec)
   - `PATCH /canvas/{id}/archive` — set status to archived
   - Cross-currents: POST, DELETE, GET per the build spec
   - Invalidation conditions: POST, GET, PATCH (update last_assessed)

2. Create `research/api/models/canvas.py` — Pydantic models for request/response bodies: `CanvasCreate`, `CanvasUpdate`, `CrossCurrentPayload`, `InvalidationConditionCreate`.

3. Register canvas router in `main.py` under prefix `/canvas`.

### Constraints

- `CanvasUpdate` route must return Protocol 1 `affected_theses` in the response body per the spec.
- Cross-current self-link check (`source != target`) is enforced at the route level.
- Do not implement source document routes here — those belong to Task 015 (integration phase).
- Do not create `get_library_db()` calls in this task.
- All write paths use explicit `BEGIN` / `commit()` / `rollback()` — never rely on autocommit.

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Create canvas
CANVAS=$(curl -sf -X POST http://localhost:8099/canvas \
  -H "Content-Type: application/json" \
  -d '{"name":"US Rates","narrative":"Fed policy path analysis","last_reviewed":"2026-04-28T00:00:00Z"}')
CANVAS_ID=$(echo $CANVAS | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Created canvas: $CANVAS_ID"

# Read canvas
curl -sf http://localhost:8099/canvas/$CANVAS_ID | python3 -c "
import sys,json; d=json.load(sys.stdin)
assert d['name'] == 'US Rates'
print('GET canvas OK')
"

# Update canvas (Protocol 1)
curl -sf -X PATCH http://localhost:8099/canvas/$CANVAS_ID \
  -H "Content-Type: application/json" \
  -d '{"narrative":"Updated rates outlook","diff_summary":"Changed rate path"}' | python3 -c "
import sys,json; d=json.load(sys.stdin)
assert 'protocol_1' in d
assert 'affected_theses' in d['protocol_1']
print('PATCH canvas + Protocol 1 OK')
"

# Cross-currents
CANVAS2=$(curl -sf -X POST http://localhost:8099/canvas \
  -H "Content-Type: application/json" \
  -d '{"name":"EM FX","narrative":"EM currency analysis","last_reviewed":"2026-04-28T00:00:00Z"}')
CANVAS2_ID=$(echo $CANVAS2 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -sf -X POST http://localhost:8099/canvas/$CANVAS_ID/cross-currents \
  -H "Content-Type: application/json" \
  -d "{\"target_canvas_id\":\"$CANVAS2_ID\",\"relationship_description\":\"Rate differentials drive EM FX\"}" | python3 -c "
import sys,json; d=json.load(sys.stdin); assert 'id' in d; print('POST cross-current OK')
"

curl -sf http://localhost:8099/canvas/$CANVAS_ID/cross-currents | python3 -c "
import sys,json; d=json.load(sys.stdin); assert len(d['cross_currents'])==1; print('GET cross-currents OK')
"

kill %1 2>/dev/null
echo "ALL CANVAS ROUTE TESTS PASS"
```

### Regression suite

```bash
cd research

# State machines still pass (Task 003)
python3 tests/test_state_machines.py

# Health check (Task 002)
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
kill %1 2>/dev/null
```

---

## Task 005: Thesis and Setup Routes

**Goal:** Thesis CRUD with full state machine enforcement at the route level. Setup CRUD with state transitions. Junction table management for setup↔thesis and setup↔observation links.

### Pre-flight

```bash
cd research

# Canvas routes exist (needed for thesis_linked_canvases)
grep -r "router" api/routes/canvas.py | head -1 || echo "MISSING: canvas routes"

# No thesis/setup routes yet
grep -r "thesis\|setup" --include="*.py" api/routes/ | grep -v canvas | grep -v __pycache__ || echo "OK"

# Confirm junction tables exist in schema
grep "setup_thesis_links" db/schema.sql || echo "MISSING: setup_thesis_links table"
```

### Implementation

1. Create `research/api/routes/thesis.py`:
   - `POST /thesis` — create thesis (status defaults to building)
   - `GET /thesis/{id}` — full thesis with kill conditions, decision points, linked canvases, linked setups (via junction table), version history
   - `PATCH /thesis/{id}` — update narrative, win_condition, worst_case_dollar
   - `PATCH /thesis/{id}/status` — state transition endpoint. Accepts `{"status": "ready|active|invalidated|archived|building"}`. For `active`, also accepts `linked_trade_id`. Lets DB triggers enforce the gates — catches `IntegrityError` and returns the trigger message as a 400 error.
   - `POST /thesis/{id}/kill-conditions/macro` — add macro kill condition
   - `POST /thesis/{id}/kill-conditions/technical` — add technical kill condition
   - `PATCH /thesis/{id}/kill-conditions/{kc_id}/fire` — set fired_at
   - `POST /thesis/{id}/decision-points` — add decision point
   - `PATCH /thesis/{id}/decision-points/{dp_id}/fire` — fire with optional deviation_note
   - `POST /thesis/{id}/link-canvas/{canvas_id}` — add thesis_linked_canvases row
   - `POST /thesis/{id}/version-history` — add version history entry

2. Create `research/api/routes/setup.py`:
   - `POST /setup` — create setup
   - `GET /setup/{id}` — full setup with linked theses, observations, images
   - `PATCH /setup/{id}/status` — transition to taken or passed. For `passed`, requires `passed_reason` and `passed_reason_type`.
   - `POST /setup/{id}/link-thesis/{thesis_id}` — add setup_thesis_links row
   - `POST /setup/{id}/link-observation/{observation_id}` — add setup_observation_links row

3. Create corresponding Pydantic models in `api/models/thesis.py` and `api/models/setup.py`.

4. Register both routers in `main.py`.

### Constraints

- State machine enforcement is in the DB triggers, not in Python. The route catches the sqlite error and translates it to HTTP 400.
- `setup_thesis_links` is the only junction table for setup↔thesis. Do not create `thesis_linked_setups`.
- The `thesis→setup` direction is navigated by `SELECT FROM setup_thesis_links WHERE thesis_id = ?`.
- Do not implement observation routes yet (Task 006).

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Create canvas (prerequisite for thesis ready gate)
CANVAS_ID=$(curl -sf -X POST http://localhost:8099/canvas \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","narrative":"Test","last_reviewed":"2026-04-28T00:00:00Z"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Create thesis
THESIS_ID=$(curl -sf -X POST http://localhost:8099/thesis \
  -H "Content-Type: application/json" \
  -d '{"instrument":"SPY","narrative":"Bull thesis","win_condition":"SPY > 500"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Try building→ready without gates — should fail 400
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH http://localhost:8099/thesis/$THESIS_ID/status \
  -H "Content-Type: application/json" -d '{"status":"ready"}')
[ "$STATUS" = "400" ] && echo "GATE BLOCK OK" || echo "FAIL: expected 400, got $STATUS"

# Satisfy gates: add kill condition, decision point, worst_case, canvas link
curl -sf -X POST http://localhost:8099/thesis/$THESIS_ID/kill-conditions/macro \
  -H "Content-Type: application/json" -d '{"condition":"Fed reverses","linked_canvas_id":"'$CANVAS_ID'"}'
curl -sf -X POST http://localhost:8099/thesis/$THESIS_ID/decision-points \
  -H "Content-Type: application/json" -d '{"trigger":"SPY breaks 500","decision":"Add","instrument":"SPY","size_pct":"2%"}'
curl -sf -X PATCH http://localhost:8099/thesis/$THESIS_ID \
  -H "Content-Type: application/json" -d '{"worst_case_dollar":5000}'
curl -sf -X POST http://localhost:8099/thesis/$THESIS_ID/link-canvas/$CANVAS_ID

# Now building→ready should pass
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH http://localhost:8099/thesis/$THESIS_ID/status \
  -H "Content-Type: application/json" -d '{"status":"ready"}')
[ "$STATUS" = "200" ] && echo "THESIS READY OK" || echo "FAIL: expected 200, got $STATUS"

# Setup with link
SETUP_ID=$(curl -sf -X POST http://localhost:8099/setup \
  -H "Content-Type: application/json" \
  -d '{"instrument":"SPY","setup_type":"breakout","note":"Key level","date":"2026-04-28"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -sf -X POST http://localhost:8099/setup/$SETUP_ID/link-thesis/$THESIS_ID

# Setup taken (gate: must have linked thesis)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH http://localhost:8099/setup/$SETUP_ID/status \
  -H "Content-Type: application/json" -d '{"status":"taken"}')
[ "$STATUS" = "200" ] && echo "SETUP TAKEN OK" || echo "FAIL: expected 200, got $STATUS"

kill %1 2>/dev/null
echo "ALL THESIS/SETUP ROUTE TESTS PASS"
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
# Canvas routes still work
curl -sf -X POST http://localhost:8099/canvas \
  -H "Content-Type: application/json" \
  -d '{"name":"Reg","narrative":"Test","last_reviewed":"2026-04-28T00:00:00Z"}' | python3 -c "import sys,json; assert 'id' in json.load(sys.stdin); print('REGRESSION CANVAS PASS')"
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
kill %1 2>/dev/null
```

---

## Task 006: Trade, Observation, Review, and Action Routes

**Goal:** Complete the remaining entity CRUD routes. Trade with snapshot freezing. Observation (append-only). Review Phase 1, Zone 3, Phase 2. Action with cancellation.

### Pre-flight

```bash
cd research

# Thesis routes exist (trade requires thesis)
grep -r "router" api/routes/thesis.py | head -1 || echo "MISSING"

# No trade/observation/review/action routes yet
for f in trade observation review action; do
  ls api/routes/$f.py 2>/dev/null && echo "CONFLICT: $f.py exists" || echo "OK: $f"
done
```

### Implementation

1. Create `research/api/routes/trade.py`:
   - `POST /trade` — creates trade, captures `thesis_snapshot` (frozen copy of thesis narrative at open time), `entry_rules_stated`, `exit_rules_stated`. These are frozen by DB triggers.
   - `GET /trade/{id}` — full trade with entries, exits, options_meta, option_legs, linked review.
   - `PATCH /trade/{id}/close` — sets status to closed, closed_at timestamp.
   - `POST /trade/{id}/entries` — append trade entry (append-only).
   - `POST /trade/{id}/exits` — append trade exit (append-only).
   - `POST /trade/{id}/options-meta` — set or update options metadata.
   - `POST /trade/{id}/option-legs` — append option leg.
   - `PATCH /trade/{id}/option-legs/{leg_id}` — update only exit_premium and date_closed.

2. Create `research/api/routes/observation.py`:
   - `POST /observation` — create observation (append-only after creation).
   - `GET /observation/{id}` — full observation with linked canvases, images.
   - `POST /observation/{id}/link-canvas/{canvas_id}` — link to canvas.
   - No PUT/PATCH — observations are append-only per DB triggers.

3. Create `research/api/routes/review.py` per the build spec:
   - `POST /review` — Phase 1 filing (all Phase 1 fields required). Sets locked_at.
   - `GET /review/{id}` — full review.
   - `PATCH /review/{id}/zone3-clear` — Zone 3 clearance (24h timelock enforced in route + DB).
   - `PATCH /review/{id}/phase2` — Phase 2 filing (requires zone_3_clear committed in DB).

4. Create `research/api/routes/action.py`:
   - `POST /action` — create action.
   - `GET /action/{id}` — full action.
   - `PATCH /action/{id}/done` — mark done.
   - `PATCH /action/{id}/cancel` — cancel with required cancellation_note.

5. Create corresponding Pydantic models.

6. Register all routers in `main.py`.

### Constraints

- Trade `thesis_snapshot` must be populated by reading the thesis narrative at trade creation time, not passed in by the client.
- Review Phase 2 route must check `zone_3_clear` from the DB (OLD value), not from the request.
- Zone 3 time-lock check is done both in the route (for user-friendly error with `remaining_seconds`) and in the DB trigger (as the final gate).
- Observation has no UPDATE or DELETE endpoints — append-only.

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Setup prerequisite chain: canvas → thesis → ready → trade
CANVAS_ID=$(curl -sf -X POST http://localhost:8099/canvas -H "Content-Type: application/json" \
  -d '{"name":"T6","narrative":"Test","last_reviewed":"2026-04-28T00:00:00Z"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
THESIS_ID=$(curl -sf -X POST http://localhost:8099/thesis -H "Content-Type: application/json" \
  -d '{"instrument":"AAPL","narrative":"Bull case","win_condition":"Price > 200"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -sf -X POST http://localhost:8099/thesis/$THESIS_ID/kill-conditions/macro -H "Content-Type: application/json" -d '{"condition":"Recession"}'
curl -sf -X POST http://localhost:8099/thesis/$THESIS_ID/decision-points -H "Content-Type: application/json" -d '{"trigger":"Break 200","decision":"Buy","instrument":"AAPL","size_pct":"3%"}'
curl -sf -X PATCH http://localhost:8099/thesis/$THESIS_ID -H "Content-Type: application/json" -d '{"worst_case_dollar":3000}'
curl -sf -X POST http://localhost:8099/thesis/$THESIS_ID/link-canvas/$CANVAS_ID
curl -sf -X PATCH http://localhost:8099/thesis/$THESIS_ID/status -H "Content-Type: application/json" -d '{"status":"ready"}'

# Create trade
TRADE_ID=$(curl -sf -X POST http://localhost:8099/trade -H "Content-Type: application/json" \
  -d '{"thesis_id":"'$THESIS_ID'","instrument_type":"equity","entry_rules_stated":"Buy on breakout","exit_rules_stated":"Stop at 190"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Trade: $TRADE_ID"

# Verify snapshot is frozen
TRADE=$(curl -sf http://localhost:8099/trade/$TRADE_ID)
echo $TRADE | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['thesis_snapshot']=='Bull case'; print('SNAPSHOT FROZEN OK')"

# Create observation (append-only)
OBS_ID=$(curl -sf -X POST http://localhost:8099/observation -H "Content-Type: application/json" \
  -d '{"date":"2026-04-28","instrument":"AAPL","timeframe":"daily","type":"technical","observation":"Key level test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
# Verify UPDATE fails
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH http://localhost:8099/observation/$OBS_ID -H "Content-Type: application/json" -d '{"observation":"modified"}' 2>/dev/null)
echo "Observation update status: $STATUS (expect 404 or 405)"

# Create action
ACTION_ID=$(curl -sf -X POST http://localhost:8099/action -H "Content-Type: application/json" \
  -d '{"action":"Review position","due_date":"2026-04-29","linked_thesis_id":"'$THESIS_ID'"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -sf -X PATCH http://localhost:8099/action/$ACTION_ID/done | python3 -c "import sys,json; print('ACTION DONE OK')"

kill %1 2>/dev/null
echo "ALL TASK 006 TESTS PASS"
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py

timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
# Canvas + thesis still work
curl -sf -X POST http://localhost:8099/canvas -H "Content-Type: application/json" \
  -d '{"name":"Reg6","narrative":"t","last_reviewed":"2026-04-28T00:00:00Z"}' | python3 -c "import sys,json; assert 'id' in json.load(sys.stdin); print('REGRESSION CANVAS PASS')"
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
kill %1 2>/dev/null
```

---

## Task 007: Ritual Morning Endpoint + Inbox Routes

**Goal:** `/ritual/morning` endpoint returning staleness + positions + actions data. Inbox CRUD. Evening routing endpoint.

### Pre-flight

```bash
cd research
# Confirm staleness views exist
grep "stale_canvases\|stale_theses\|overdue_actions\|active_surveillance" db/views.sql | wc -l
# Expect >= 4

# No ritual or inbox routes
ls api/routes/ritual.py api/routes/inbox.py 2>/dev/null && echo "CONFLICT" || echo "OK"
```

### Implementation

1. Create `research/api/routes/ritual.py`:
   - `GET /ritual/morning` — queries `stale_canvases`, `stale_theses`, `stale_invalidation_conditions`, active theses (with kill condition counts), `overdue_actions`. Returns structured JSON.
   - `POST /ritual/morning/staleness/{entity_type}/{id}/confirm` — marks entity as reviewed (updates `last_reviewed` or `last_assessed`).
   - `POST /ritual/morning/position/{thesis_id}/clear` — marks thesis as checked (no-op log, or updates `last_updated`).

2. Create `research/api/routes/inbox.py`:
   - `POST /inbox` — quick capture (raw_text only).
   - `GET /inbox` — list unrouted items (`routed_at IS NULL`).
   - `GET /inbox/{id}` — single item.
   - `POST /inbox/{id}/route` — route to entity type. Accepts `route_type` (observation/action/setup/thesis-update) and the created entity data. Creates the target entity and updates the inbox row with `routed_to_*` and `routed_at`.

3. Register routers in `main.py`.

### Constraints

- `/ritual/morning` is read-only except for the confirm/clear actions.
- Inbox routing creates the target entity via the existing route logic (reuse the same DB write functions, don't duplicate).
- Do not implement the frontend templates yet — this is API-only.

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Morning ritual (empty DB — should return empty lists)
curl -sf http://localhost:8099/ritual/morning | python3 -c "
import sys,json; d=json.load(sys.stdin)
print('Morning ritual keys:', list(d.keys()))
print('RITUAL ENDPOINT OK')
"

# Inbox capture + list
curl -sf -X POST http://localhost:8099/inbox -H "Content-Type: application/json" \
  -d '{"raw_text":"AAPL showing strength at 200 level"}' | python3 -c "import sys,json; assert 'id' in json.load(sys.stdin); print('INBOX CAPTURE OK')"

curl -sf http://localhost:8099/inbox | python3 -c "
import sys,json; d=json.load(sys.stdin)
assert len(d['items']) >= 1
print(f'INBOX LIST OK — {len(d[\"items\"])} items')
"

kill %1 2>/dev/null
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
# Spot check: canvas, thesis, trade, action routes
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
curl -sf -X POST http://localhost:8099/canvas -H "Content-Type: application/json" \
  -d '{"name":"R7","narrative":"t","last_reviewed":"2026-04-28T00:00:00Z"}' | python3 -c "import sys,json; assert 'id' in json.load(sys.stdin); print('REGRESSION CANVAS PASS')"
kill %1 2>/dev/null
```

---

## Task 008: Image Upload and Serve Routes

**Goal:** Image upload for observations and setups. Path-traversal-safe serve endpoint.

### Pre-flight

```bash
cd research
# Confirm image directories exist
ls data/images/observations data/images/setups || echo "MISSING"

# No image route yet
ls api/routes/images.py 2>/dev/null && echo "CONFLICT" || echo "OK"

# Confirm config has image_root
grep "image_root" api/config.py || echo "MISSING: image_root in config"
```

### Implementation

1. Create `research/api/routes/images.py`:
   - `POST /images/{entity}/{entity_id}` — upload image file. Saves to `IMAGE_ROOT/{entity}/{entity_id}/{filename}`. Creates row in `observation_images` or `setup_images`. Returns image record.
   - `GET /images/{entity}/{entity_id}/{filename}` — serve image with path traversal protection per the build spec (`is_relative_to(IMAGE_ROOT.resolve())`).
   - `entity` must be in `("observations", "setups")` — reject anything else with 400.

2. Ensure `config.py` has `image_root` pointing to `research/data/images/`.

3. Register router in `main.py`.

### Constraints

- Path traversal check is mandatory: `if not path.is_relative_to(IMAGE_ROOT.resolve())` → 400.
- Image upload uses `python-multipart` (already in requirements).
- Do not add vision parsing or `parsed_fields` processing — that column is reserved for future use.
- Filenames are sanitised (no path separators allowed).

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Create a test image
echo "fake image data" > /tmp/test_chart.png

# Create an observation to attach to
OBS_ID=$(curl -sf -X POST http://localhost:8099/observation -H "Content-Type: application/json" \
  -d '{"date":"2026-04-28","instrument":"SPY","timeframe":"1h","type":"technical","observation":"Test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Upload
curl -sf -X POST http://localhost:8099/images/observations/$OBS_ID \
  -F "file=@/tmp/test_chart.png" | python3 -c "import sys,json; d=json.load(sys.stdin); print('UPLOAD OK:', d)"

# Serve
curl -sf -o /dev/null -w "%{http_code}" http://localhost:8099/images/observations/$OBS_ID/test_chart.png
echo " (expect 200)"

# Path traversal attempt
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/images/observations/../../../etc/passwd)
[ "$STATUS" = "400" ] && echo "PATH TRAVERSAL BLOCKED OK" || echo "FAIL: expected 400, got $STATUS"

kill %1 2>/dev/null
rm /tmp/test_chart.png
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
curl -sf http://localhost:8099/ritual/morning | python3 -c "import sys,json; print('REGRESSION RITUAL PASS')"
kill %1 2>/dev/null
```

---

## Task 009: Design System — CSS Tokens, Base, Layout

**Goal:** Implement the full CSS design system from the design spec. No templates yet — just the CSS files that all templates will reference.

### Pre-flight

```bash
cd research
ls frontend/static/css/ || echo "MISSING: css directory"

# No CSS files yet
ls frontend/static/css/*.css 2>/dev/null && echo "CONFLICT" || echo "OK"
```

Read in full:
- Design spec sections 2 (Colour System), 3 (Typography), 4 (Spacing)
- Design spec section 5 (Layout — shell, nav, panel)
- Design spec section 8 (Motion)
- Design spec section 10 (Accessibility)
- Design spec section 11 (CSS Architecture)

### Implementation

1. Create `research/frontend/static/css/tokens.css` — all custom properties from sections 2, 3, 4 of the design spec on `:root`. Colours, fonts, spacing scale, shadow scale.

2. Create `research/frontend/static/css/base.css`:
   - Google Fonts `@import` for Lora (400, 500, italic 400), Inter (400, 500), Fira Code (400).
   - CSS reset (minimal: box-sizing, margin/padding zero, inherit fonts).
   - `body` styles: `--color-bg` background, `--font-ui` default, `--text-base` size.
   - Focus ring: `0 0 0 2px var(--color-analytical)` on all interactive elements. Never `outline: none`.
   - `@media (prefers-reduced-motion: reduce)` — all transitions to 0ms.

3. Create `research/frontend/static/css/layout.css`:
   - Shell: left nav (200px fixed), main content (flex-1), right panel (260px fixed, hidden by default).
   - Left nav: `--color-recessed` background, right border, full-height.
   - Nav items: default/hover/active states per design spec.
   - Right panel: slide-in, `--shadow-panel`, z-index 10.
   - Main content margin-right transition when panel visible.

4. Create `research/frontend/static/css/components.css`:
   - Status badges (6.1): data-status attribute pattern.
   - Entity chips (6.2): with layer colour accent.
   - Prose fields (6.3 editable, 6.4 read-only).
   - Buttons (6.5): primary, secondary, danger, ghost, disabled, gate-blocked.
   - Form inputs (6.6): text, textarea, select, error state.
   - Tables (6.7): header, data rows, hover, warning/danger row states.
   - Cards (6.8).
   - Section headers (6.9).
   - Inline forms (6.10).
   - Protocol banners (6.11).
   - Passed setup classification (6.12).
   - Layer colour data-attribute pattern: `[data-layer="analytical"]`, etc.

5. Create `research/frontend/static/css/pages.css` — placeholder, to be populated with page-specific styles in later tasks.

6. Create `research/frontend/static/css/motion.css` — all transitions from section 8 of the design spec. Every animation listed, nothing not on the list.

### Constraints

- No hardcoded hex values outside `tokens.css`. All colours reference custom properties.
- No Tailwind, no component framework. Pure custom CSS.
- Minimum touch target: 44×44px on all interactive elements.
- Minimum contrast: 4.5:1 for all body text.
- Letter-spacing: 0.07em on uppercase section headers, normal everywhere else.
- `--text-prose: 16px / 1.85` line-height is non-negotiable for Lora.

### Smoke test

```bash
cd research

# All CSS files exist
for f in tokens base layout components pages motion; do
  ls frontend/static/css/$f.css || echo "MISSING: $f.css"
done

# No hardcoded hex outside tokens.css
grep -n "#[0-9A-Fa-f]\{3,6\}" frontend/static/css/base.css frontend/static/css/layout.css frontend/static/css/components.css frontend/static/css/motion.css 2>/dev/null
echo "(above should be empty — no hex outside tokens.css)"

# Custom properties defined
grep -c "^  --color-" frontend/static/css/tokens.css
echo "(expect >= 20 colour tokens)"
grep -c "^  --font-" frontend/static/css/tokens.css
echo "(expect >= 3 font tokens)"
grep -c "^  --space-" frontend/static/css/tokens.css
echo "(expect >= 8 spacing tokens)"
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
kill %1 2>/dev/null
```

---

## Task 010: Base Template + Morning Ritual Page

**Goal:** `base.html` template (shell, nav, content slot). Morning ritual page with staleness, positions, actions sections per design spec section 7.1.

### Pre-flight

```bash
cd research
# CSS files exist
ls frontend/static/css/tokens.css frontend/static/css/layout.css || echo "MISSING CSS"

# Ritual endpoint exists
grep "ritual" api/routes/ritual.py | head -1 || echo "MISSING ritual routes"

# No templates yet
ls frontend/templates/base.html 2>/dev/null && echo "CONFLICT" || echo "OK"
```

Read in full:
- Design spec section 5 (Shell structure, left nav)
- Design spec section 7.1 (Morning ritual)
- Design spec section 9 (HTMX and Alpine.js patterns)

### Implementation

1. Create `research/frontend/templates/base.html`:
   - HTML shell with CSS imports (all 6 CSS files).
   - Alpine.js and HTMX script tags (CDN).
   - Left nav per design spec section 5: system identity, capture button, inbox, ritual items, entity filter chips, system status.
   - `<main>` content block via Jinja2 `{% block content %}`.
   - Right panel container (hidden by default, toggled per-page).

2. Create `research/frontend/templates/components/badge.html` — Jinja2 macro for status badges.

3. Create `research/frontend/templates/components/table.html` — Jinja2 macro for table rendering.

4. Create `research/frontend/templates/ritual/morning.html`:
   - Extends `base.html`.
   - Section 1: Staleness sweep — table from `stale_canvases` + `stale_theses` + `stale_invalidation_conditions`. Per-row confirm button via HTMX.
   - Section 2: Active position check — one row per active thesis with kill condition counts. "All clear" / "Flag" buttons.
   - Section 3: Action dispatch — overdue actions table. "Done" button with optimistic row removal (fade out, HTMX delete on confirm).
   - "Ritual complete" row appears when all sections cleared.
   - Alpine.js for section collapse after completion.

5. Update ritual routes to serve HTML when `Accept: text/html`, JSON otherwise. Or add separate template-rendering routes (e.g., `GET /ritual/morning` returns HTML page, `GET /api/ritual/morning` returns JSON).

### Constraints

- No right panel on the morning ritual page.
- Mark-done is the only optimistic update — row fades immediately, server confirms asynchronously.
- Section collapse uses 250ms ease-in-out on height per motion spec.
- Danger row treatment for staleness > 21 days.
- All interactive elements: 44×44px minimum touch target.

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Page renders
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/ritual/morning -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "RITUAL PAGE RENDERS OK" || echo "FAIL: $STATUS"

# Contains expected CSS references
curl -sf http://localhost:8099/ritual/morning -H "Accept: text/html" | grep -c "tokens.css"
echo "(expect >= 1)"

# Contains Alpine and HTMX
curl -sf http://localhost:8099/ritual/morning -H "Accept: text/html" | grep -c "alpine\|htmx"
echo "(expect >= 2)"

kill %1 2>/dev/null
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
# API endpoints still return JSON
curl -sf http://localhost:8099/ritual/morning -H "Accept: application/json" | python3 -c "import sys,json; json.load(sys.stdin); print('REGRESSION RITUAL JSON PASS')"
kill %1 2>/dev/null
```

---

## Task 011: Canvas Detail Page + Right Panel

**Goal:** Canvas detail template per design spec 7.3. Right context panel with linked theses, observation backlinks, cross-currents, version history.

### Pre-flight

```bash
cd research
ls frontend/templates/base.html || echo "MISSING base template"
ls api/routes/canvas.py || echo "MISSING canvas routes"

# Confirm HTMX partial pattern is understood
grep "hx-target\|hx-swap" frontend/templates/base.html || echo "NOTE: add HTMX targets"
```

Read in full:
- Design spec section 7.3 (Canvas detail)
- Design spec section 5 (Right context panel — panel sections for canvas)
- Design spec sections 6.3, 6.4 (Prose fields), 6.11 (Protocol banners)

### Implementation

1. Create `research/frontend/templates/canvas/detail.html`:
   - Breadcrumb: "Canvas / {name}".
   - Entity identity bar: 3px analytical left border, name, status badge, staleness indicator, "Confirm reviewed" button.
   - Narrative section: editable prose field (6.3) with diff_summary input on save.
   - Cross-currents section: list with entity chips, delete affordance, add inline form with canvas typeahead.
   - Source documents section: renders only if `library_db_path` configured. Search input with 300ms debounce. Linked docs list. (Route wiring deferred to Task 015.)
   - Invalidation conditions section: table with inline add form.

2. Create `research/frontend/templates/canvas/panel.html` — HTMX partial for right panel:
   - Linked theses: navigable chips with status badges.
   - Observation backlinks: compact log.
   - Cross-currents: compact list.
   - Version history: collapsed by default, expandable.

3. Add canvas detail template-rendering route (or update existing canvas GET to serve HTML on Accept: text/html).

4. Create `research/frontend/templates/components/prose_field.html` — Jinja2 macro for editable and read-only prose fields.

5. Create `research/frontend/templates/components/chip.html` — entity chip macro.

6. Create `research/frontend/templates/components/inline_form.html` — inline form container macro.

### Constraints

- Protocol 1 banner appears above breadcrumb when canvas update returns affected theses.
- Prose field save on canvas requires diff_summary before commit.
- Right panel loads via HTMX `hx-get` targeting the panel container.
- No typeahead for library search yet — add the input but leave it non-functional until Task 015.

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Create a canvas
CANVAS_ID=$(curl -sf -X POST http://localhost:8099/canvas -H "Content-Type: application/json" \
  -d '{"name":"Test Canvas","narrative":"Narrative","last_reviewed":"2026-04-28T00:00:00Z"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Canvas detail page renders
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/canvas/$CANVAS_ID -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "CANVAS DETAIL RENDERS OK" || echo "FAIL: $STATUS"

# Contains expected design elements
curl -sf http://localhost:8099/canvas/$CANVAS_ID -H "Accept: text/html" | grep -c "data-layer\|prose-field\|panel"
echo "(expect >= 2)"

kill %1 2>/dev/null
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
# Morning ritual still works
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/ritual/morning -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "REGRESSION RITUAL PASS" || echo "REGRESSION RITUAL FAIL"
kill %1 2>/dev/null
```

---

## Task 012: Thesis Detail Page

**Goal:** Thesis detail template per design spec 7.4. Right panel with linked canvases, setups, decision points, protocol flags.

### Pre-flight

```bash
cd research
ls frontend/templates/canvas/detail.html || echo "MISSING: canvas detail (needed for pattern reference)"
ls api/routes/thesis.py || echo "MISSING: thesis routes"
```

Read in full:
- Design spec section 7.4 (Thesis detail)
- Design spec section 6.5 (Buttons — gate-blocked state)
- Build spec: thesis state machine transitions and gate conditions

### Implementation

1. Create `research/frontend/templates/thesis/detail.html`:
   - Entity identity bar: instrument in `--text-xl`, status badge, last_updated, state transition buttons (only valid next states rendered).
   - Gate-blocked "Mark ready" button: disabled with tooltip listing unmet gates.
   - `worst_case_dollar`: prominent display per design spec (`--text-2xl`, `--font-data`, `--color-danger`, 600 weight).
   - Narrative + Win condition: editable prose fields.
   - Kill conditions: two subsections (Macro / Technical) with tables. Fired rows in danger treatment. Inline add forms.
   - Decision points: table with fired status, deviation notes. Inline add form.

2. Create `research/frontend/templates/thesis/panel.html` — HTMX partial:
   - Linked canvases (chips).
   - Linked setups (chips with status badges).
   - Protocol flags.
   - Version history.

3. Add thesis detail template-rendering route.

4. Wire state transition buttons to HTMX PATCH calls with `hx-swap="outerHTML"` for badge replacement.

### Constraints

- State transition buttons: only valid next states from the current status. No "archive" button when status is "building".
- Gate tooltip content mirrors the trigger error messages.
- `worst_case_dollar` is never in a table cell — it gets its own prominent display area.
- Kill condition `fired_at` display uses `--color-danger` when populated.

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

THESIS_ID=$(curl -sf -X POST http://localhost:8099/thesis -H "Content-Type: application/json" \
  -d '{"instrument":"TSLA","narrative":"EV thesis","win_condition":"TSLA > 300"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/thesis/$THESIS_ID -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "THESIS DETAIL RENDERS OK" || echo "FAIL: $STATUS"

# Verify worst_case_dollar display
curl -sf http://localhost:8099/thesis/$THESIS_ID -H "Accept: text/html" | grep -c "worst.case\|text-2xl"
echo "(expect >= 1)"

kill %1 2>/dev/null
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
# Canvas detail still works
CANVAS_ID=$(curl -sf -X POST http://localhost:8099/canvas -H "Content-Type: application/json" \
  -d '{"name":"R12","narrative":"t","last_reviewed":"2026-04-28T00:00:00Z"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/canvas/$CANVAS_ID -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "REGRESSION CANVAS DETAIL PASS" || echo "FAIL"
kill %1 2>/dev/null
```

---

## Task 013: Observation Form, Setup Form, Trade Detail, Entity Lists

**Goal:** Observation capture form (7.5), Setup form with passed classification (6.12), Trade detail page, filtered entity list page.

### Pre-flight

```bash
cd research
ls frontend/templates/thesis/detail.html || echo "MISSING thesis detail"
ls api/routes/observation.py api/routes/trade.py api/routes/setup.py || echo "MISSING routes"
```

Read in full:
- Design spec sections 7.5 (Observation form), 6.12 (Passed setup classification)
- Design spec section 5 (Entity filter chips in nav)

### Implementation

1. Create `research/frontend/templates/observation/form.html`:
   - Type selection: three cards (technical/vol/flow) per design spec.
   - Fields: instrument, timeframe, observation text (prose font), linked_canvas typeahead, linked_thesis typeahead.
   - Image upload zone: dashed border, drag-drop.
   - Pre-file notice: "Observations cannot be edited after filing." — italic, tertiary.
   - Submit: "File observation" primary button.

2. Create `research/frontend/templates/setup/detail.html`:
   - Setup detail with passed classification form (6.12) when "Pass setup" selected.
   - Two large buttons: Analytical / Psychological with descriptors.
   - Linked theses and observations via chips.

3. Create `research/frontend/templates/trade/detail.html`:
   - Frozen fields (entry_rules_stated, exit_rules_stated, thesis_snapshot) with lock indicator.
   - Entries and exits as append-only tables with "Add entry" ghost row.
   - Options metadata and legs sections (if instrument_type = option).

4. Create `research/frontend/templates/entities/list.html`:
   - Filtered entity list used by nav entity chips.
   - Table with entity-type-appropriate columns.
   - Filter by type via URL parameter.
   - HTMX-powered: clicking a filter chip loads the filtered list.

5. Wire the template-rendering routes for each page.

### Constraints

- Observation form and evening routing form share the same field layout — use the form template as a Jinja2 include for both contexts.
- Image upload connects to the image routes from Task 008.
- Trade frozen fields use read-only prose field treatment (6.4) with lock indicator.
- Entity list in nav uses the filter chip pattern from design spec section 5.

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Observation form renders
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/observation/new -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "OBS FORM RENDERS OK" || echo "FAIL: $STATUS"

# Entity list renders
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/entities?type=canvas -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "ENTITY LIST RENDERS OK" || echo "FAIL: $STATUS"

kill %1 2>/dev/null
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
for page in "ritual/morning" "canvas" "thesis"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/$page -H "Accept: text/html" 2>/dev/null)
  echo "REGRESSION $page: $STATUS"
done
kill %1 2>/dev/null
```

---

## Task 014: Review UI + Zone 3 + Evening Routing

**Goal:** Review Phase 1 form (7.6), Zone 3 clearance button (7.7), Phase 2 form (7.7), Evening routing page (7.2).

### Pre-flight

```bash
cd research
ls api/routes/review.py || echo "MISSING review routes"
ls frontend/templates/observation/form.html || echo "MISSING obs form (needed for routing reuse)"
```

Read in full:
- Design spec sections 7.6, 7.7 (Review Phase 1, Zone 3, Phase 2)
- Design spec section 7.2 (Evening routing)
- Design spec section 8 (Motion — Zone 3 button fill, evening routing item transition)

### Implementation

1. Create `research/frontend/templates/review/phase1.html`:
   - Phase 1 fields: entry_fill, exit_fill, emotional_state (narrow input, max-width 160px), rules_followed (three-state), what_i_actually_did.
   - After submission: all Phase 1 fields become read-only (6.4 treatment). locked_at displayed.

2. Create `research/frontend/templates/review/phase2.html`:
   - Zone 3 clearance button: full-width, 52px height, progress fill (500ms ::before animation), mouseup activation.
   - Gate display when < 24h elapsed: countdown, dimmed Phase 2 section.
   - Phase 2 fields: mistake_type cards (Type 1/2/3 with definitions), analysis prose, single_update prose (with fail/pass examples), what_not_changing prose.

3. Create `research/frontend/templates/ritual/evening.html`:
   - One inbox item at a time. No queue list.
   - Route-as selection: 2×2 grid of entity-type cards.
   - Per-type fields (observation/action/setup/thesis-update) appear below on selection.
   - Typeahead for canvas/thesis linking — uses HTMX hx-trigger="input changed delay:300ms".
   - "File" primary button. Item fade-out → next item fade-in.
   - Empty state: "Inbox clear."

4. Wire template-rendering routes for review detail and evening routing.

### Constraints

- Zone 3 button: mouseup activation (not mousedown), 500ms progress fill. This is the one instance of weighted motion.
- Review Phase 2 checks `zone_3_clear` from DB state, not client state.
- Evening routing typeahead: minimum 2 characters, server returns rendered HTML partial of entity chips.
- Linking affordance (typeahead) must be visually prominent per design spec 7.2.

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Evening routing page
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/ritual/evening -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "EVENING ROUTING RENDERS OK" || echo "FAIL: $STATUS"

# Zone 3 button has expected CSS class/attribute
curl -sf http://localhost:8099/ritual/evening -H "Accept: text/html" | grep -c "zone.3\|progress.fill" || true

kill %1 2>/dev/null
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
for page in "ritual/morning" "ritual/evening"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/$page -H "Accept: text/html" 2>/dev/null)
  echo "REGRESSION $page: $STATUS"
done
kill %1 2>/dev/null
```

---

## Task 015: Protocol Implementations 2–4 + Source Document Routes

**Goal:** Protocols 2, 3, 4 as server-side checks that surface banners. Canvas source document routes (integration with library.sqlite). Protocol banner component.

### Pre-flight

```bash
cd research

# Confirm get_library_db exists
grep "get_library_db" api/database.py || echo "MISSING"

# Confirm library_db_path in config
grep "library_db_path" api/config.py || echo "MISSING"

# No protocol files yet
ls api/protocols/*.py 2>/dev/null | grep -v __init__ | grep -v __pycache__ && echo "CONFLICT" || echo "OK"

# Confirm no source document routes exist yet
grep "library.search\|sources" api/routes/canvas.py | head -3
```

### Implementation

1. Create `research/api/protocols/protocol2.py`:
   - Checks for observable kill conditions (macro kill conditions on active theses where the linked canvas was recently updated). Returns list of theses needing attention.
   - Invoked on thesis detail page load and canvas update.

2. Create `research/api/protocols/protocol3.py`:
   - Checks for decision point triggers (unfired decision points on active theses). Returns list.

3. Create `research/api/protocols/protocol4.py`:
   - On trade close: checks if review exists for the trade. If not, returns protocol flag.

4. Add source document routes to `api/routes/canvas.py` per the build spec:
   - `POST /canvas/{id}/sources` — link library document to canvas. Validates document exists in library.sqlite via `get_library_db()`.
   - `DELETE /canvas/{id}/sources/{library_document_id}` — unlink.
   - `GET /canvas/{id}/sources` — list linked documents with metadata from library.
   - `GET /canvas/library-search?q=` — search library documents. Minimum 2 characters enforced server-side.

5. Create `research/frontend/templates/components/protocol_banner.html` — Jinja2 macro for protocol banners per design spec 6.11. Four variants: Protocol 1 (warning), Protocol 2 (danger), Protocol 3 (analytical), Protocol 4 (warning).

6. Wire protocol checks into relevant page loads and display banners.

### Constraints

- Source document routes require `library_db_path` to be configured. Return 503 if not set.
- `get_library_db()` is always used as `async with` — never as a dependency.
- Library search minimum query length: 2 characters, enforced server-side.
- Protocol 2 banner has no dismiss — only clears when hold-vs-redeploy paragraph filed.
- Protocol 3 banner clears when decision executed or deviation logged.
- Protocol 4 banner clears when Phase 1 filed.

### Smoke test

```bash
cd research
timeout 15 python3 -m uvicorn api.main:app --port 8099 &
sleep 3

# Source document routes — should return 503 if library not configured
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/canvas/library-search?q=test)
echo "Library search without config: $STATUS (expect 503)"

# Library search min length
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8099/canvas/library-search?q=a")
[ "$STATUS" = "400" ] && echo "MIN LENGTH CHECK OK" || echo "FAIL: $STATUS"

# Protocol banner template exists
ls frontend/templates/components/protocol_banner.html && echo "BANNER TEMPLATE OK" || echo "MISSING"

kill %1 2>/dev/null
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"

# Canvas routes still work
CANVAS_ID=$(curl -sf -X POST http://localhost:8099/canvas -H "Content-Type: application/json" \
  -d '{"name":"R15","narrative":"t","last_reviewed":"2026-04-28T00:00:00Z"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -sf http://localhost:8099/canvas/$CANVAS_ID | python3 -c "import sys,json; json.load(sys.stdin); print('REGRESSION CANVAS GET PASS')"
kill %1 2>/dev/null
```

---

## Task 016: Research Exporter — Core

**Goal:** `ResearchExporter` class with per-entity export methods. Obsidian note generation for canvases, theses, reviews, observations, passed setups.

**Dependency:** This task requires `library.sqlite` to exist (from the knowledge library pipeline). If the knowledge library is not yet built, create a minimal `library.sqlite` with `documents`, `document_concepts`, and `concepts` tables for testing.

### Pre-flight

```bash
cd knowledge-library

# Confirm pipeline directory exists
ls pipeline/ || echo "MISSING: pipeline/"

# No exporter yet
ls pipeline/research_exporter.py 2>/dev/null && echo "CONFLICT" || echo "OK"

# Confirm research.db schema is loadable
cd ../research
python3 -c "
import sqlite3
conn = sqlite3.connect('data/research.db')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
assert 'entity_events' in tables
assert 'export_watermarks' in tables
print('research.db OK')
conn.close()
"
```

### Implementation

1. Create `knowledge-library/pipeline/research_exporter.py` per the build spec:
   - `ResearchExporter.__init__()` — sync sqlite3 connection to research.db, library_db_path, vault_path, chroma collection, ollama client.
   - `_get_watermark()`, `_set_watermark()`, `_record_failure()` — watermark and failure tracking methods.
   - `export_canvas_by_id()` — full implementation per the build spec: reads canvas + linked theses + invalidation conditions, extracts topics, generates frontmatter, writes Obsidian note via `_write_note()`.
   - `export_thesis_by_id()` — similar pattern for theses.
   - `export_review_by_id()` — for filed reviews.
   - `export_observation_by_id()` — for observations.
   - `export_setup_by_id()` — for passed setups only.
   - `_write_note()` — writes YAML frontmatter + markdown body to `vault_path/subdir/filename.md`.
   - `_stable_doc_id()`, `_note_filename()`, `_extract_topics()`, `_rank_salience()` — helper methods.
   - `_upsert_record()` — writes/updates record in library.sqlite (document with `research_entity_id` and `source_type`).
   - `_populate_concept_graph()` — writes concept relationships.
   - `_get_explicit_source_backlinks()` — reads canvas_source_documents, resolves titles from library.
   - `_find_related_documents()` — semantic search fallback when no explicit sources.
   - `_backlink_documents()` — adds backlinks to library documents.

2. Stub `_extract_topics()` and `_rank_salience()` to work without Ollama (return basic keyword extraction). Full LLM integration will depend on Ollama availability.

3. Create `knowledge-library/pipeline/__init__.py`.

### Constraints

- `ResearchExporter` uses sync `sqlite3`, not `aiosqlite` — it runs as a batch process, not inside FastAPI.
- `vault_path` is the `obsidian_vault` value from config — notes land directly in the vault.
- Archived canvases: `export_canvas_by_id` returns without writing. Existing note is orphaned (not deleted). Per out-of-scope.
- Trade events are not exported (Design Decision 12).

### Smoke test

```bash
cd research

# Seed some test data
python3 -c "
import sqlite3
from pathlib import Path

conn = sqlite3.connect('data/research.db')
conn.execute('PRAGMA foreign_keys = ON')

# Load schema
for f in ('db/schema.sql', 'db/triggers.sql', 'db/views.sql'):
    conn.executescript(Path(f).read_text())

# Create canvas
conn.execute(\"\"\"INSERT INTO canvas (id, name, narrative, last_reviewed)
    VALUES ('c1', 'US Rates', 'Fed policy outlook', '2026-04-28T00:00:00Z')\"\"\")
conn.commit()

# Verify event logged
events = conn.execute('SELECT * FROM entity_events WHERE entity_id = \"c1\"').fetchall()
assert len(events) >= 1, 'No events logged'
print(f'Seed data OK — {len(events)} events')
conn.close()
"

cd ../knowledge-library

# Create minimal library.sqlite for testing
python3 -c "
import sqlite3
conn = sqlite3.connect('db/library.sqlite')
conn.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, title TEXT, authors TEXT, year INTEGER, summary TEXT, research_entity_id TEXT, source_type TEXT)')
conn.execute('CREATE TABLE IF NOT EXISTS concepts (id TEXT PRIMARY KEY, name TEXT)')
conn.execute('CREATE TABLE IF NOT EXISTS document_concepts (document_id TEXT, concept_id TEXT, salience REAL, PRIMARY KEY(document_id, concept_id))')
conn.commit()
conn.close()
print('library.sqlite stub OK')
"

# Test exporter
python3 -c "
import sys
sys.path.insert(0, '.')
from pipeline.research_exporter import ResearchExporter
from pathlib import Path

exporter = ResearchExporter(
    research_db_path='../research/data/research.db',
    library_db_path='db/library.sqlite',
    vault_path='vault',
    chroma_collection=None,
    ollama_client=None
)
exporter.export_canvas_by_id('c1')
note = Path('vault/research/canvases').glob('*.md')
notes = list(note)
assert len(notes) >= 1, f'No notes written: {notes}'
print(f'EXPORT OK — {len(notes)} note(s) written')
print(notes[0].read_text()[:200])
"
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
kill %1 2>/dev/null
```

---

## Task 017: Incremental Export + Watermark + Failed Exports

**Goal:** `_export_from_events()` incremental export method. Watermark advancement (only on zero failures). `failed_exports` tracking. `reconcile_failed_exports()`. CLI with `--mode` flag.

### Pre-flight

```bash
cd knowledge-library

# Exporter exists
python3 -c "from pipeline.research_exporter import ResearchExporter; print('OK')"

# Watermark table exists in research.db
python3 -c "
import sqlite3
conn = sqlite3.connect('../research/data/research.db')
wm = conn.execute('SELECT COUNT(*) FROM export_watermarks').fetchone()[0]
assert wm == 5, f'Expected 5 watermarks, got {wm}'
print(f'Watermarks OK: {wm}')
conn.close()
"
```

### Implementation

1. Add `_export_from_events()` to `ResearchExporter` per the build spec — reads entity_events since watermark, exports affected entities, advances watermark only if zero failures.

2. Add `_run_llm_pass()` — dispatches to incremental or full based on flag.

3. Add `_run_embedding_pass()` — embeds exported documents into ChromaDB.

4. Add `reconcile_failed_exports()` per the build spec — retries all unresolved failed exports.

5. Add `reconcile_embeddings()` — re-embeds failed ChromaDB writes.

6. Add `run()` method — orchestrates LLM pass + embedding pass.

7. Create `knowledge-library/run_ingestion.py` per the build spec — argparse with `--mode` flag (full, incremental, research, reconcile, retry-failed).

### Constraints

- Watermark advances only on zero failures for that entity type.
- `failed_exports` uses `ON CONFLICT(entity_type, entity_id) DO UPDATE` — latest failure overwrites.
- Trade events exist in entity_events but have no watermark entry and no exporter (Design Decision 12).
- Sync sqlite3 connection for the exporter — per Design Decision 12, run with server idle.

### Smoke test

```bash
cd knowledge-library

# Run incremental export
python3 run_ingestion.py --mode research 2>&1 | tail -5
echo "INCREMENTAL EXPORT OK"

# Verify watermark advanced
python3 -c "
import sqlite3
conn = sqlite3.connect('../research/data/research.db')
wm = conn.execute(\"SELECT entity_type, last_exported_at FROM export_watermarks WHERE last_exported_at != '1970-01-01T00:00:00Z'\").fetchall()
print(f'Advanced watermarks: {len(wm)}')
for r in wm:
    print(f'  {r[0]}: {r[1]}')
conn.close()
"

# Verify reconcile mode runs
python3 run_ingestion.py --mode reconcile 2>&1 | tail -3
echo "RECONCILE MODE OK"
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
kill %1 2>/dev/null

cd ../knowledge-library
# Exporter still importable
python3 -c "from pipeline.research_exporter import ResearchExporter; print('REGRESSION EXPORTER IMPORT PASS')"
```

---

## Task 018: Provenance Analytics + Knowledge Gap Query

**Goal:** Provenance chain query (library document → canvas → thesis → trade → review). Knowledge gap query. Verify thesis_lifespan and review_lag views work end-to-end with real data.

### Pre-flight

```bash
cd research

# Views exist
grep "thesis_lifespan\|review_lag" db/views.sql || echo "MISSING views"

# Exporter exists and ran
cd ../knowledge-library
python3 -c "from pipeline.research_exporter import ResearchExporter; print('Exporter OK')"
```

### Implementation

1. Create `research/tests/test_analytics.py` — a standalone script that:
   - Seeds a full data chain: library document → canvas (with source doc link) → thesis (linked to canvas) → trade (with thesis) → close trade → review (Phase 1 + Phase 2).
   - Runs the `thesis_lifespan` view and verifies it returns correct data.
   - Runs the `review_lag` view and verifies hours_to_phase2 calculation.
   - Runs the provenance chain query (with ATTACH) and verifies the full chain resolves.
   - Runs the knowledge gap query (with ATTACH) and verifies it surfaces unlinked documents.

2. Create `research/api/routes/analytics.py`:
   - `GET /analytics/thesis-lifespan` — returns thesis_lifespan view data.
   - `GET /analytics/review-lag` — returns review_lag view data.
   - `GET /analytics/passed-setups` — returns passed_setup_analysis + passed_setup_detail views.
   - `GET /analytics/mistake-distribution` — returns review_mistake_distribution view.
   - `GET /analytics/decision-deviations` — returns decision_point_deviations view.
   - `GET /analytics/options-iv` — returns options_iv_comparison view.

3. Register analytics router in `main.py`.

### Constraints

- Provenance chain query requires `ATTACH DATABASE` — this runs as a standalone analytical query, not through the FastAPI async path.
- Knowledge gap query requires `library.documents` to have `research_entity_id` and `source_type` columns (populated by the exporter's `_upsert_record`).
- Analytics routes are read-only.

### Smoke test

```bash
cd research
python3 tests/test_analytics.py
echo "ANALYTICS TESTS PASS"

timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/analytics/thesis-lifespan | python3 -c "import sys,json; json.load(sys.stdin); print('LIFESPAN ENDPOINT OK')"
curl -sf http://localhost:8099/analytics/mistake-distribution | python3 -c "import sys,json; json.load(sys.stdin); print('MISTAKES ENDPOINT OK')"
kill %1 2>/dev/null
```

### Regression suite

```bash
cd research
python3 tests/test_state_machines.py
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health | python3 -c "import sys,json; assert json.load(sys.stdin)['status']=='ok'; print('REGRESSION HEALTH PASS')"
# All pages still render
for page in "ritual/morning" "ritual/evening"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/$page -H "Accept: text/html" 2>/dev/null)
  echo "REGRESSION $page: $STATUS"
done
kill %1 2>/dev/null

cd ../knowledge-library
python3 -c "from pipeline.research_exporter import ResearchExporter; print('REGRESSION EXPORTER PASS')"
```

---

## Integration Verification Checklist

*These assertions must all pass before the system is considered complete.*

### Prerequisites — must exist before the system runs
- [ ] Python 3.11+ installed
- [ ] `research/data/` directory exists with write permissions
- [ ] `research/data/images/observations/` and `research/data/images/setups/` exist
- [ ] All CSS files exist in `research/frontend/static/css/`
- [ ] `knowledge-library/db/library.sqlite` exists (for integration features)

### Outputs — must exist after a full run
- [ ] `research/data/research.db` created with >= 22 tables, >= 35 triggers, >= 12 views
- [ ] `export_watermarks` table has 5 rows (canvas, thesis, observation, review, setup)
- [ ] `knowledge-library/vault/research/` contains subdirectories for each entity type
- [ ] Obsidian notes have YAML frontmatter with `research_entity_id` and `source_type`

### Integration contracts — must not break
- [ ] `PRAGMA foreign_keys = ON` is set on every connection
- [ ] WAL mode is set in `database.py`, not in schema.sql
- [ ] `get_library_db()` is always used as `async with`, never as a FastAPI dependency
- [ ] All write paths use explicit `BEGIN` / `commit()` / `rollback()`
- [ ] State machine enforcement is in DB triggers, not Python
- [ ] Trade `thesis_snapshot` is frozen at open (DB trigger enforced)
- [ ] Observation is append-only (DB trigger enforced)
- [ ] Review Phase 2 checks `zone_3_clear` from DB (OLD value), not request

### No-duplication check
- [ ] `api/config.py` is the only config file for the research system
- [ ] `api/database.py` is the only place DB connections are created
- [ ] No hardcoded hex values outside `frontend/static/css/tokens.css`
- [ ] No hardcoded path strings outside `api/config.py`
- [ ] `setup_thesis_links` is the only junction for setup↔thesis (no `thesis_linked_setups`)
- [ ] No `localhost` hardcoded in test files (if Playwright tests are added later)

---

## Task Dependency Graph

```
000 (scaffold)
 └─ 001 (schema SQL)
     └─ 002 (init + DB layer + FastAPI skeleton)
         └─ 003 (state machine tests)
             └─ 004 (canvas routes)
                 └─ 005 (thesis + setup routes)
                     └─ 006 (trade + observation + review + action routes)
                         ├─ 007 (ritual + inbox routes)
                         │   └─ 008 (image routes)
                         │       └─ 009 (CSS design system)
                         │           └─ 010 (base template + morning ritual page)
                         │               └─ 011 (canvas detail page)
                         │                   └─ 012 (thesis detail page)
                         │                       └─ 013 (obs/setup/trade/entity pages)
                         │                           └─ 014 (review + evening routing pages)
                         │                               └─ 015 (protocols + source docs)
                         └─ 016 (research exporter)
                             └─ 017 (incremental export + watermark)
                                 └─ 018 (provenance analytics)
```

Tasks 007–015 (API + frontend) and Tasks 016–018 (exporter + analytics) can proceed in parallel after Task 006, as long as both branches merge before final integration testing.

---

*Last updated: 2026-04-28 after initial spec creation.*
*Reference gap_prevention_protocol.md at the top of every task before execution.*
