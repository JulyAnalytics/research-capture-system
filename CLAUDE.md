# Research Capture System — Project Map

**Last updated: 2026-04-30 after Task 017 — Capture Enter navigates to evening direct mode with prefill; remove Send to inbox button; add nav-guard flash on evening.html**

---

## Component Status

| Component | Location | Status |
|---|---|---|
| Directory scaffold | `research/`, `knowledge-library/` | complete |
| `research/requirements.txt` | `research/requirements.txt` | complete |
| `knowledge-library/requirements.txt` | `knowledge-library/requirements.txt` | complete |
| Python package init files | `research/db/`, `api/`, `api/models/`, `api/routes/`, `api/protocols/` | complete |
| Database schema | `research/db/schema.sql` | complete — 30 tables |
| Database triggers | `research/db/triggers.sql` | complete — 42 triggers |
| Database views | `research/db/views.sql` | complete — 14 views |
| Schema init | `research/db/init.py` | complete |
| Migration runner | `research/db/migrations/runner.py` | complete |
| DB connection layer | `research/api/database.py` | complete |
| App config | `research/api/config.py` | complete |
| FastAPI app | `research/api/main.py` | complete — lifespan, health check, static mount, GET / renders home.html with entity data, canvas/thesis/setup/trade/observation/review/action/ritual/inbox/entities/images routers |
| Canvas routes | `research/api/routes/canvas.py` | complete — CRUD + Protocol 1 + cross-currents + invalidation conditions + HTML rendering + panel + search + confirm-reviewed |
| Thesis routes | `research/api/routes/thesis.py` | complete — CRUD + state transitions + kill conditions + decision points + canvas links + version history + HTML rendering + panel + search with canvas_id filter |
| Setup routes | `research/api/routes/setup.py` | complete — CRUD + state transitions + thesis/observation links + HTML rendering |
| Trade routes | `research/api/routes/trade.py` | complete — CRUD + close + entries + exits + options-meta + option-legs + HTML rendering + new trade page |
| Observation routes | `research/api/routes/observation.py` | complete — create + read + canvas links (append-only, no update/delete) + form page |
| Review routes | `research/api/routes/review.py` | complete — Phase 1 + Zone 3 clearance + Phase 2 |
| Action routes | `research/api/routes/action.py` | complete — CRUD + done + cancel with note |
| Ritual routes | `research/api/routes/ritual.py` | complete — morning ritual (staleness sweep, active positions, overdue actions) + confirm/clear + HTML rendering via Accept header |
| Inbox routes | `research/api/routes/inbox.py` | complete — capture, list, get, route to observation/action/setup/thesis-update |
| Entities route | `research/api/routes/entities.py` | complete — GET /api/entities with type filter and per-type links + reusable _fetch_entities() |
| Image routes | `research/api/routes/images.py` | complete — upload + serve with path traversal protection for observations and setups |
| Analytics routes | `research/api/routes/analytics.py` | not started |
| Protocol 1 | `research/api/protocols/protocol1.py` | not started |
| Protocol 2 | `research/api/protocols/protocol2.py` | not started |
| Protocol 3 | `research/api/protocols/protocol3.py` | not started |
| Protocol 4 | `research/api/protocols/protocol4.py` | not started |
| Canvas models | `research/api/models/canvas.py` | complete |
| Thesis models | `research/api/models/thesis.py` | complete |
| Setup models | `research/api/models/setup.py` | complete |
| Trade models | `research/api/models/trade.py` | complete |
| Observation models | `research/api/models/observation.py` | complete |
| Review models | `research/api/models/review.py` | complete |
| Action models | `research/api/models/action.py` | complete |
| Image models | `research/api/models/image.py` | complete |
| CSS design system | `research/frontend/static/css/` | complete — 6 files (tokens, base, layout, components, pages, motion) |
| Base template | `research/frontend/templates/base.html` | complete — shell, left nav, two-target capture component, entity filter chips, Alpine.js + HTMX |
| Capture component | `research/frontend/templates/components/capture.html` | complete — + dropdown links Observation/Setup/Action to /ritual/evening?direct=1, Trade to /trade/new; Canvas/Thesis removed from dropdown |
| Morning ritual template | `research/frontend/templates/ritual/morning.html` | complete — staleness sweep + positions + actions sections with collapse |
| Evening routing template | `research/frontend/templates/ritual/evening.html` | complete — renamed "Capture", editable capture text, 4 route types, direct mode (?direct=1) for + dropdown, typeahead for canvas/thesis |
| Canvas detail template | `research/frontend/templates/canvas/detail.html` | complete — narrative prose field + cross-currents + invalidation conditions + back button + right panel |
| Canvas panel template | `research/frontend/templates/canvas/panel.html` | complete — linked theses + observation backlinks + cross-currents + version history |
| Thesis detail template | `research/frontend/templates/thesis/detail.html` | complete — identity bar + worst_case_dollar + narrative + win condition + kill conditions + decision points + back button + right panel |
| Thesis panel template | `research/frontend/templates/thesis/panel.html` | complete — linked canvases + linked setups + protocol flags + version history |
| Observation form template | `research/frontend/templates/observation/form.html` | complete — type selection cards + fields + canvas/thesis typeahead + image upload + back button |
| Setup detail template | `research/frontend/templates/setup/detail.html` | complete — identity bar + passed classification form + linked theses/observations + back button |
| Trade detail template | `research/frontend/templates/trade/detail.html` | complete — frozen fields + entries/exits append-only tables + options section + close button + back button |
| Trade new template | `research/frontend/templates/trade/new.html` | complete — two-step form (canvas→thesis→trade fields) + cancel button |
| Entity list template | `research/frontend/templates/entities/list.html` | removed — replaced by home.html (see change spec) |
| Home template | `research/frontend/templates/home.html` | complete — full entity list with filter chips and Alpine.js reactivity |
| Review new template (Phase 1 form) | `research/frontend/templates/review/phase1_new.html` | complete — Phase 1 creation form at GET /review/new?trade_id=... |
| Review detail template (Phase 1 read-only + Zone 3 + Phase 2) | `research/frontend/templates/review/phase1.html` | complete — Phase 1 read-only, Zone 3 button (500ms hold enforced), Phase 2 form with mistake type cards |
| Component macros | `research/frontend/templates/components/` | complete — badge, table, capture, prose_field, chip, inline_form macros |
| State machine tests | `research/tests/test_state_machines.py` | complete — 58 tests, covers all spec items 2–10 |
| Analytics tests | `research/tests/test_analytics.py` | not started |
| Research exporter | `knowledge-library/pipeline/research_exporter.py` | not started |
| Ingestion CLI | `knowledge-library/run_ingestion.py` | not started |

---

## Output Contracts

*Populated as components go live.*

---

## DB Tables

All in `research/data/research.db` (created at startup by `db/init.py`).

| Table | Purpose |
|---|---|
| `schema_version` | Migration tracking |
| `canvas` | Macro thesis canvases |
| `canvas_cross_currents` | Canvas↔canvas relationships |
| `canvas_invalidation_conditions` | Canvas invalidation conditions |
| `canvas_version_history` | Append-only canvas narrative history |
| `canvas_source_documents` | Explicit library document provenance |
| `setup` | Trade setups |
| `setup_images` | Images attached to setups |
| `setup_thesis_links` | Canonical setup↔thesis junction |
| `setup_observation_links` | Setup↔observation junction |
| `thesis` | Trading theses with state machine |
| `thesis_kill_conditions_macro` | Macro kill conditions |
| `thesis_kill_conditions_technical` | Technical kill conditions |
| `thesis_decision_points` | Decision points with deviation tracking |
| `thesis_linked_canvases` | Thesis↔canvas links |
| `thesis_version_history` | Append-only thesis narrative history |
| `trade` | Trades linked to theses |
| `trade_entries` | Append-only trade entries |
| `trade_exits` | Append-only trade exits |
| `trade_options_meta` | Options greeks and IV |
| `trade_option_legs` | Option legs (partial update: exit_premium, date_closed only) |
| `observation` | Append-only market observations |
| `observation_linked_canvases` | Observation↔canvas links |
| `observation_images` | Images attached to observations |
| `action` | Actions with cancellation enforcement |
| `review` | Trade reviews — Phase 1, Zone 3, Phase 2 |
| `inbox` | Quick capture queue |
| `entity_events` | Append-only event log (populated by triggers only) |
| `export_watermarks` | Per-entity-type export watermarks (5 rows: canvas/thesis/observation/review/setup) |
| `failed_exports` | Dead-letter queue for export failures |

---

## Shared Utilities

| Utility | Location | Purpose |
|---|---|---|
| DB connection | `research/api/database.py` | `get_db()`, `get_library_db()` — only place connections are created |
| App config | `research/api/config.py` | Only config file for the research system |

---

## Deprecated Files

| File | Replaced by | Date |
|---|---|---|
| `research/tests/test_schema.py` | `research/tests/test_state_machines.py` | 2026-04-28 |

---

## Design Amendments
rcs_change_spec_capture_and_home.md located in docs/architecture

TaskChange
007 | Add GET / placeholder route. Add GET /api/entities endpoint in api/routes/entities.py.
008 | No change.
009 | No change.
010 | Replace capture button with two-target capture component (components/capture.html). Add home.html as full entity list page. Wire GET / to render home.html.
011 | Add history.back() back button to canvas detail page.
012 | Add history.back() back button to thesis detail page.
013 | Remove standalone entity list page (now the home page). Add /trade/new two-step creation page. Add back buttons to observation, setup, trade, and trade/new pages.

---

## Shell Execution

The project root is `/Users/jun/Library/CloudStorage/OneDrive-Personal/Trading/research-capture-system`.
The application root is `research/` inside it.

**Shell state does not persist between tool calls.** Each Bash invocation starts in the project root.

For any command that needs the Python module path to resolve (uvicorn, python imports, pytest), prefix with `cd research &&`:

```
cd research && python3 -m uvicorn api.main:app --port 8099
cd research && python3 tests/test_state_machines.py
cd research && python3 -c "from api.config import settings; print(settings.db_path)"
```

For commands that just need file paths, use the full relative path from project root:
```
rm -f research/data/research.db
ls research/frontend/templates/
```

---

## Intentional Deviations from Task Spec

These are deliberate departures from the task spec that were validated as improvements:

1. **Task 003 — one fresh DB per test** (spec says "fresh in-memory DB" which could mean one shared DB): Each test function gets its own `_fresh_db()` connection, ensuring full isolation. This is strictly better than sharing a DB across tests where trigger side-effects from one test could leak into another.

2. **Task 003 — bonus tests not in spec**: The test file includes extra tests beyond the spec requirements: CHECK constraint tests (canvas status, trade instrument_type, observation type), FK enforcement on child tables (canvas_invalidation_conditions, setup_images, thesis_kill_conditions_macro, observation_images), thesis touch triggers, canvas cross-currents self-reference and unique constraint, option legs append-only delete, and export watermarks seed verification. These validate schema integrity not covered by the spec's state machine focus.

---

## Maintenance Protocol

This file must be updated as the last step of every task.

After completing any task that:
- Adds a component or file to `systems/` — update Component Status table
- Writes a new file to `data/outputs/` — add its schema to Output Contracts
- Creates a new DB table — add it to the DB Tables section
- Deprecates or renames a file — add it to the Deprecated Files section
- Adds a constant to `config.py` — note it in Shared Utilities if shared

**Version line** (update on every change):
`Last updated: [date] after Task [NNN] — [one sentence describing change]`

**Completion report requirement:**
Every task completion report must include one of:
  `CLAUDE.md updated: YES`
  `CLAUDE.md updated: NO — reason: [reason]`

A missing or stale CLAUDE.md is a build error, not an oversight.
