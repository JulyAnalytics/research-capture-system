# Project Invariant Addendum
**Applies to:** Research Capture System (RCS)
**Repo root:** `/Users/jun/Library/CloudStorage/OneDrive-Personal/Trading/research-capture-system`
**Protocol base:** `docs/architecture/gap_prevention_protocol_v3.md`
**Last updated:** 2026-05-02 after Mode 4 Session B — insight entity complete; §5 schema integrity updated (insight in required tables, views >= 15, wm == 6); §7 item 9 added

> This document is loaded into every Claude.ai spec authoring session alongside
> the base protocol. Together they replace all placeholders in the protocol
> templates with project-literal values. The authoring session must not produce
> a spec that contains an unresolved `[placeholder]` from either document.
>
> This document is maintained by the spec author against CLAUDE.md.
> It is not updated by the model during task execution.
> Update triggers are listed in Section 6.

---

## How to Use This Document

**When authoring a spec in Claude.ai:**
Load this document and the base protocol into the session before writing anything.
For every template placeholder in the base protocol, substitute the literal value
from the matching section below. If a section below is marked `NONE`, the placeholder
is not applicable to this project — omit the corresponding line from the spec rather
than leaving it blank or generalised.

**When updating this document:**
Consult CLAUDE.md first. Every value here must match what CLAUDE.md currently
describes. If they diverge, CLAUDE.md is authoritative — update this document
to match, then continue.

---

## Section 1: Environment

```
REPO_ROOT:         /Users/jun/Library/CloudStorage/OneDrive-Personal/Trading/research-capture-system
WORKING_DIR_CMD:   cd /Users/jun/Library/CloudStorage/OneDrive-Personal/Trading/research-capture-system/research
DEV_SERVER_CMD:    python3 -m uvicorn api.main:app
DEV_SERVER_PORT:   8099
DEV_SERVER_WAIT:   3
TEST_CMD:          python3 tests/test_state_machines.py
TEST_PASS_SIGNAL:  ALL TESTS PASSED
HEALTH_ENDPOINT:   /health
HEALTH_PASS_CHECK: python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok' and d['db']=='connected'; print('OK')"
LANG_EXT:          py
EXCLUDE_DIRS:      venv|__pycache__
```

**Notes:**
- Shell state does not persist between tool calls. Every bash block must begin with `cd .../research` explicitly.
- The application root is `research/` — all Python imports and uvicorn invocations run from inside it.
- Knowledge-library commands run from `knowledge-library/` and are not part of the standing regression suite until `research_exporter.py` is implemented.

**Substitution example — port clear + server start block:**
```bash
cd /Users/jun/Library/CloudStorage/OneDrive-Personal/Trading/research-capture-system/research
lsof -ti:8099 | xargs kill -9 2>/dev/null; sleep 1
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
```

---

## Section 2: Canonical Files

```
CONFIG_FILE:           api/config.py
CONFIG_IMPORT:         from api.config import settings
CONFIG_LOCKED_FIELDS:  db_path, image_root, library_db_path
                       (model_config env_file settings must not change)

DB_UTILITY_FILE:       api/database.py
DB_UTILITY_IMPORT:     from api.database import get_db, get_connection, get_library_db
DB_UTILITY_LOCKED_FNS: get_connection(), get_db(), get_library_db()
                       (WAL mode, foreign_keys ON, busy_timeout 5000 must remain in get_connection;
                        get_library_db() must remain an @asynccontextmanager, never a FastAPI dependency)

ADDITIONAL_UTILITIES:
  - file:   db/init.py
    import: from db.init import init_schema
    locked: init_schema() — must load schema.sql, triggers.sql, views.sql via executescript() in that order

  - file:   db/migrations/runner.py
    import: from db.migrations.runner import run_pending
    locked: run_pending() — comment stripping must precede semicolon split; simple DDL only

  - file:   db/schema.sql
    import: N/A (loaded via executescript)
    locked: All table definitions and their column sets. Table ordering is FK-load-bearing.
            See CLAUDE.md DB Tables for the canonical list.

  - file:   db/triggers.sql
    import: N/A (loaded via executescript)
    locked: All state machine triggers. DROP TRIGGER IF EXISTS must precede every CREATE.

  - file:   db/views.sql
    import: N/A (loaded via executescript)
    locked: All view definitions. DROP VIEW IF EXISTS must precede every CREATE.

  - file:   frontend/static/css/tokens.css
    import: N/A
    locked: All custom property declarations. No hex values may appear in any other CSS file.
```

**Do Not Create rule (copy verbatim into every spec Constraints section):**
```
### Do not create
- Any new config file — api/config.py is the only config for the research system
- Any new DB/connection utility — api/database.py is the only place connections are created
- Any constant that duplicates something already in api/config.py
- Any second schema/trigger/view loading mechanism — db/init.py is the only one
- Any hardcoded hex colour value outside frontend/static/css/tokens.css
```

---

## Section 3: Hardcoded Value Prohibitions

```
PATH_CONSTANTS:
  - literal: data/research.db
    use_instead: settings.db_path
  - literal: data/images
    use_instead: settings.image_root
  - literal: research/data
    use_instead: settings.db_path or settings.image_root

URL_CONSTANTS:
  - literal: http://localhost:8099
    use_instead: construct from DEV_SERVER_PORT at test time only; never in source files
  - literal: localhost
    use_instead: never hardcoded in source files; test bash blocks only

THRESHOLD_CONSTANTS:
  - literal: 8099
    use_instead: DEV_SERVER_PORT (in bash blocks); settings does not expose port — uvicorn flag only
  - literal: 24 (hours — Zone 3 timelock)
    use_instead: ZONE3_LOCK_HOURS constant already defined in api/routes/review.py line 15

OTHER_CONSTANTS:
  - literal: any hex colour (#XXXXXX)
    use_instead: CSS custom property from frontend/static/css/tokens.css
  - literal: any SQL table name as a bare string in Python application logic
    use_instead: route-level query strings already present in the relevant route file
```

**No-duplication grep block (copy verbatim into every spec pre-flight):**
```bash
# ── Confirm absent — hardcoded values ──────────────────────────────────
cd /Users/jun/Library/CloudStorage/OneDrive-Personal/Trading/research-capture-system/research

# No hardcoded db path
HITS=$(grep -r "data/research\.db\|data/images" --include="*.py" . | grep -v venv | grep -v __pycache__ | grep -v "config\.py")
[ -z "$HITS" ] || { echo "HARDCODED PATH — STOP:"; echo "$HITS"; exit 1; }
echo "NO-HARDCODE PASS — db/image paths"

# No hardcoded hex outside tokens.css
HITS=$(grep -rn "#[0-9A-Fa-f]\{3,6\}" --include="*.css" frontend/static/css/ | grep -v "tokens\.css")
[ -z "$HITS" ] || { echo "HARDCODED HEX OUTSIDE TOKENS — STOP:"; echo "$HITS"; exit 1; }
echo "NO-HARDCODE PASS — hex colours"

# No duplicate DB connection logic outside database.py
HITS=$(grep -rn "aiosqlite\.connect" --include="*.py" . | grep -v venv | grep -v __pycache__ | grep -v "api/database\.py")
[ -z "$HITS" ] || { echo "DUPLICATE DB CONNECTION — STOP:"; echo "$HITS"; exit 1; }
echo "NO-DUPLICATION PASS — aiosqlite.connect"
```

---

## Section 4: Read List — Project Invariants

```
ALWAYS_READ:
  - path:    api/config.py
    confirm: "db_path default = [value], image_root default = [value], library_db_path default = ''"

  - path:    api/database.py
    confirm: "get_connection() sets: journal_mode=WAL, foreign_keys=ON, busy_timeout=5000;
              get_library_db() is @asynccontextmanager"

  - path:    CLAUDE.md
    confirm: "Last updated: 2026-05-02 after Mode 4 Session B — insight routes/models/templates complete"
```

**Read list block (copy into every spec pre-flight, then append task-specific files):**
```
### Read these files in full and emit the confirm value for each

- `api/config.py` — emit: db_path default value and image_root default value
- `api/database.py` — emit: the four PRAGMA statements set in get_connection() and the decorator on get_library_db()
- `CLAUDE.md` — emit: the exact Last updated version line

[Task-specific files appended here by spec author:]
- `[exact file path]` — emit: [what reading this file must produce as output]
```

---

## Section 5: Standing Regression Suite

This block is copied verbatim at the start of every spec's Regression Suite section.
Task-specific assertions are appended after the final comment line.

```bash
# ── Standing regression suite ──────────────────────────────────────────
cd /Users/jun/Library/CloudStorage/OneDrive-Personal/Trading/research-capture-system/research
lsof -ti:8099 | xargs kill -9 2>/dev/null; sleep 1

# Full test suite
python3 tests/test_state_machines.py 2>&1 | tail -3 | grep -q "ALL TESTS PASSED" \
  || { echo "REGRESSION TESTS FAIL"; exit 1; }
echo "REGRESSION TESTS PASS"

# Server health
timeout 8 python3 -m uvicorn api.main:app --port 8099 &
sleep 3
curl -sf http://localhost:8099/health \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok' and d['db']=='connected'; print('OK')" \
  || { echo "REGRESSION HEALTH FAIL"; kill %1 2>/dev/null; exit 1; }
echo "REGRESSION HEALTH PASS"

# Canonical imports resolve
python3 -c "from api.config import settings; print('config OK')" \
  || { echo "REGRESSION IMPORT FAIL — api/config.py"; kill %1 2>/dev/null; exit 1; }
python3 -c "from api.database import get_db, get_connection, get_library_db; print('database OK')" \
  || { echo "REGRESSION IMPORT FAIL — api/database.py"; kill %1 2>/dev/null; exit 1; }
python3 -c "from db.init import init_schema; print('init OK')" \
  || { echo "REGRESSION IMPORT FAIL — db/init.py"; kill %1 2>/dev/null; exit 1; }

# Key routes return expected status codes
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/ -H "Accept: text/html")
[ "$STATUS" = "200" ] \
  || { echo "REGRESSION ROUTE FAIL — GET / returned $STATUS"; kill %1 2>/dev/null; exit 1; }
echo "REGRESSION 1 PASS — GET / (home)"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/exposure -H "Accept: text/html")
[ "$STATUS" = "200" ] \
  || { echo "REGRESSION ROUTE FAIL — GET /exposure returned $STATUS"; kill %1 2>/dev/null; exit 1; }
echo "REGRESSION 2 PASS — GET /exposure (exposure board)"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/ritual/evening -H "Accept: text/html")
[ "$STATUS" = "404" ] \
  || { echo "REGRESSION ROUTE FAIL — GET /ritual/evening returned $STATUS (expected 404)"; kill %1 2>/dev/null; exit 1; }
echo "REGRESSION 3 PASS — GET /ritual/evening returns 404"

curl -sf http://localhost:8099/api/entities \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list); print('entities OK')" \
  || { echo "REGRESSION ROUTE FAIL — GET /api/entities"; kill %1 2>/dev/null; exit 1; }
echo "REGRESSION 4 PASS — GET /api/entities"

# Schema integrity
python3 -c "
import sqlite3
from api.config import settings
conn = sqlite3.connect(settings.db_path)
tables = {r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'\").fetchall()}
required = {'canvas','thesis','trade','observation','setup','review','action',
            'entity_events','export_watermarks','failed_exports',
            'observation_thesis_links','observation_setup_links',
            'setup_thesis_links','setup_linked_canvases','insight'}
missing = required - tables
assert not missing, f'Missing tables: {missing}'
assert 'inbox' not in tables, 'inbox table present — was not dropped'
triggers = conn.execute(\"SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'\").fetchone()[0]
assert triggers >= 40, f'Expected >= 40 triggers, got {triggers}'
views = conn.execute(\"SELECT COUNT(*) FROM sqlite_master WHERE type='view'\").fetchone()[0]
assert views >= 15, f'Expected >= 15 views, got {views}'
wm = conn.execute('SELECT COUNT(*) FROM export_watermarks').fetchone()[0]
assert wm == 6, f'Expected 6 watermarks, got {wm}'
conn.close()
print('SCHEMA OK')
" || { echo "REGRESSION SCHEMA FAIL"; kill %1 2>/dev/null; exit 1; }
echo "REGRESSION 7 PASS — schema integrity"

kill %1 2>/dev/null
# ── End standing regression suite ──────────────────────────────────────

## Add for this task
# [assertion that verifies the primary output of this task]
# [assertion that verifies the primary integration contract of this task]
```

---

## Section 6: Maintenance Triggers

| Event | Section to update |
|---|---|
| Server start command or port changes | Section 1: Environment |
| Test command or pass signal changes | Section 1: Environment |
| New canonical config file created or renamed | Section 2: Canonical Files |
| New shared utility created | Section 2: Canonical Files |
| Config field locked or unlocked | Section 2: Canonical Files |
| New hardcoded value prohibition identified | Section 3: Hardcoded Value Prohibitions |
| New file becomes always-required reading | Section 4: Read List |
| New live component added (routes, templates, exporters) | Section 5: Standing Regression Suite |
| Existing component retired or renamed | Section 5: Standing Regression Suite |
| DB table added, renamed, or dropped | Section 5: Standing Regression Suite (schema assertion) |
| CLAUDE.md updated | All sections — verify alignment; update Last updated line here |

**Alignment check (run after any CLAUDE.md update):**
Every value in this document must match what CLAUDE.md currently describes.
If any value is stale, update this document before authoring the next spec.
CLAUDE.md is authoritative. The addendum must match it, not the reverse.

---

## Section 7: Spec Validity Gate

Before handing any spec to Claude Code, verify all of the following.

```
[ ] No [placeholder] strings remain in the spec
[ ] Read list is a closed enumeration with a confirm value per file — no "and any other files"
[ ] Every MODIFY step has a literal Insert-after anchor, not a positional description
[ ] Every multi-fetch or conditional POST handler is provided as literal code, not prose
[ ] Constraints has both "Do not create" and "Do not modify" subsections,
    each with at least one explicit entry
[ ] Regression suite section opens with the standing block copied verbatim from §5,
    followed by a filled two-assertion task entry
[ ] No conditional repair path in any implementation step (repair logic is pre-flight)
[ ] Every integration checklist item has a paired bash assertion, not prose only
[ ] CLAUDE.md update section is present and enumerates exact rows/fields to change
[ ] Port-clear line (lsof -ti:8099 | xargs kill -9 ...) precedes every server start
    in pre-flight, smoke tests, and regression suite
```

---

## Project-Specific Notes

### Intentional deviations documented in CLAUDE.md

The following are confirmed intentional departures from the original task spec.
They are not errors. Do not attempt to "fix" them in future tasks without an
explicit change spec:

1. `observation` is the state-machine entity (watching/taken/passed); `setup` is append-only analytical.
2. `trade` statuses are idea/active/closed/discarded (not open/closed).
3. `thesis_active_gate` requires linked trade status = 'active' (not merely non-null trade id).
4. Protocol 2 canvas-update trigger is unscoped — surfaces flags for all active theses system-wide.
5. Protocol 1 Alpine round-trip is broken (`showProtocol1` is a boolean, not a function) — documented in deviation_register.md, not yet fixed.
6. Inbox deprecated — table dropped (migration 004), route deleted (inbox.py removed),
   nav entries removed from base.html, evening template inbox queue branch removed.
   /ritual/evening returns 404. Capture dropdown updated by Mode 1 — all seven
   entities now link to /entity/new pages.

8. Morning ritual renamed to Exposure Board — URL moved from /ritual/morning to /exposure.
   Evening routing page removed (/ritual/evening returns 404). ritual.py retained as the
   route file (not renamed). GET /exposure/counts added for nav badge population.

9. Insight entity added (Mode 4) — ambient learning capture, polymorphic link to
   any entity. VALID_ENTITY_TYPES enforced at route layer. 6th export watermark row
   added. Exporter orphan check deferred to Tasks 016–018.

### Components not yet started

These must not be assumed to exist in pre-flight prerequisite checks:
- `knowledge-library/pipeline/research_exporter.py`
- `knowledge-library/run_ingestion.py`
- `research/api/routes/analytics.py`
- `research/api/protocols/protocol1.py` (inline only; no module)
- `research/tests/test_analytics.py`

### junction table canonical names

| Direction | Table |
|---|---|
| observation → thesis | `observation_thesis_links` |
| observation → setup | `observation_setup_links` |
| setup → thesis | `setup_thesis_links` |
| setup → canvas | `setup_linked_canvases` |
| thesis → canvas | `thesis_linked_canvases` |

`thesis_linked_setups` and `observation_linked_canvases` do not exist. Do not reference them.
