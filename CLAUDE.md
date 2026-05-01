# Research Capture System — Project Map

**Last updated: 2026-05-01 after Mode 3 Session B — trade routes/models/templates complete; idea/active/closed/discarded fully operational**

---

## Component Status

| Component | Location | Status |
|---|---|---|
| Directory scaffold | `research/`, `knowledge-library/` | complete |
| `research/requirements.txt` | `research/requirements.txt` | complete |
| `knowledge-library/requirements.txt` | `knowledge-library/requirements.txt` | complete |
| Python package init files | `research/db/`, `api/`, `api/models/`, `api/routes/`, `api/protocols/` | complete |
| Database schema | `research/db/schema.sql` | complete — 30 tables; trade updated to idea/active/closed/discarded |
| Database triggers | `research/db/triggers.sql` | complete — trade_state_machine, trade_active_gate, updated frozen/event triggers added |
| Database views | `research/db/views.sql` | complete — 14 views |
| Schema init | `research/db/init.py` | complete |
| Migration runner | `research/db/migrations/runner.py` | complete |
| DB connection layer | `research/api/database.py` | complete |
| App config | `research/api/config.py` | complete |
| FastAPI app | `research/api/main.py` | complete — lifespan, health check, static mount, GET / renders home.html with entity data, canvas/thesis/setup/trade/observation/review/action/ritual/inbox/entities/images routers |
| Canvas routes | `research/api/routes/canvas.py` | complete — CRUD + Protocol 1 + cross-currents + invalidation conditions + HTML rendering + panel + search + confirm-reviewed |
| Thesis routes | `research/api/routes/thesis.py` | complete — CRUD + state transitions + kill conditions + decision points + canvas links + version history + HTML rendering + panel + search with canvas_id filter; linked_setups query updated to new setup column set (name, type) |
| Setup routes | `research/api/routes/setup.py` | complete — GET /new, POST, GET /{id}, POST /{id}/link-thesis/{tid}, POST /{id}/link-canvas/{cid}; no PATCH (append-only) |
| Trade routes | `research/api/routes/trade.py` | complete — POST /trade (idea + fast-path), PATCH /activate (thesis substitution guard), /discard, /close, entries, exits, options-meta, option-legs |
| Observation routes | `research/api/routes/observation.py` | complete — GET /new, POST, GET /{id}, PATCH /{id}/status, POST /{id}/link-thesis/{tid}, POST /{id}/link-setup/{sid} |
| Review routes | `research/api/routes/review.py` | complete — Phase 1 + Zone 3 clearance + Phase 2 |
| Action routes | `research/api/routes/action.py` | complete — CRUD + done + cancel with note |
| Ritual routes | `research/api/routes/ritual.py` | complete — morning ritual (staleness sweep, active positions, overdue actions) + confirm/clear + HTML rendering via Accept header |
| Inbox routes | `research/api/routes/inbox.py` | complete — capture, list, get, route to observation/action/setup/thesis-update |
| Entities route | `research/api/routes/entities.py` | complete — GET /api/entities with type filter and per-type links + reusable _fetch_entities(); updated for obs/setup swap (setup_linked_canvases, observation_thesis_links, new column names) |
| Image routes | `research/api/routes/images.py` | complete — upload + serve with path traversal protection for observations and setups |
| Analytics routes | `research/api/routes/analytics.py` | not started |
| Protocol 1 | `research/api/protocols/protocol1.py` | complete — check_protocol1(db, canvas_id), extracted from canvas.py inline; read-only, no side effects |
| Protocol 2 | `research/api/protocols/protocol2.py` | complete (partial) — check_protocol2(db, thesis_id=None), called from thesis detail load and canvas PATCH; canvas PATCH call is unscoped (see Intentional Deviations #4) |
| Protocol 3 | `research/api/protocols/protocol3.py` | complete — check_protocol3(db, thesis_id=None), called from thesis detail load |
| Protocol 4 | `research/api/protocols/protocol4.py` | complete — check_protocol4(db, trade_id=None), called from trade detail load; COALESCE on thesis_instrument |
| Protocol banner component | `research/frontend/templates/components/protocol_banner.html` | complete — four variants (1 warning/dismissible, 2 danger, 3 analytical, 4 warning with action link) |
| Canvas models | `research/api/models/canvas.py` | complete |
| Thesis models | `research/api/models/thesis.py` | complete |
| Setup models | `research/api/models/setup.py` | complete — SetupCreate (append-only, no status transition) |
| Trade models | `research/api/models/trade.py` | complete — TradeCreate, TradeActivate (force_thesis_change), TradeClose |
| Observation models | `research/api/models/observation.py` | complete — ObservationCreate, ObservationStatusTransition |
| Review models | `research/api/models/review.py` | complete |
| Action models | `research/api/models/action.py` | complete |
| Image models | `research/api/models/image.py` | complete |
| CSS design system | `research/frontend/static/css/` | complete — 6 files (tokens, base, layout, components, pages, motion) |
| Base template | `research/frontend/templates/base.html` | complete — shell, left nav, two-target capture component, entity filter chips, Alpine.js + HTMX |
| Capture component | `research/frontend/templates/components/capture.html` | complete — dropdown links all 6 entities to /entity/new; capture Enter → /observation/new?title= |
| Morning ritual template | `research/frontend/templates/ritual/morning.html` | complete — staleness sweep + positions + actions sections with collapse |
| Evening routing template | `research/frontend/templates/ritual/evening.html` | complete — renamed "Capture", editable capture text, 4 route types, direct mode (?direct=1) for + dropdown, typeahead for canvas/thesis |
| Canvas detail template | `research/frontend/templates/canvas/detail.html` | complete — narrative prose field + cross-currents + invalidation conditions + back button + right panel |
| Canvas panel template | `research/frontend/templates/canvas/panel.html` | complete — linked theses + setup backlinks (canvas_setup_backlinks view) + cross-currents + version history |
| Thesis detail template | `research/frontend/templates/thesis/detail.html` | complete — identity bar + worst_case_dollar + narrative + win condition + kill conditions + decision points + back button + right panel |
| Thesis panel template | `research/frontend/templates/thesis/panel.html` | complete — linked canvases + linked setups (chip updated: s.name/s.instrument, no s.setup_type/s.status) + protocol flags + version history |
| Observation new template | `research/frontend/templates/observation/new.html` | complete — lightweight capture form (name, instrument, note, date, optional thesis link) |
| Observation detail template | `research/frontend/templates/observation/detail.html` | complete — state machine detail: status badge, take/pass transitions, linked theses/setups with inline add |
| Setup new template | `research/frontend/templates/setup/new.html` | complete — structured analytical form (type cards, timeframe, setup_note, optional canvas/thesis link) |
| Setup detail template | `research/frontend/templates/setup/detail.html` | complete — append-only structured detail; linked theses/canvases; images; no edit affordances |
| Trade detail template | `research/frontend/templates/trade/detail.html` | complete — idea affordance (activate form + discard), 409 two-click confirm, active status throughout; frozen fields only when status != idea |
| Trade new template | `research/frontend/templates/trade/new.html` | complete — single-step idea form, optional fast-path section (canvas→thesis→entry/exit rules) |
| Entity list template | `research/frontend/templates/entities/list.html` | removed — replaced by home.html (see change spec) |
| Home template | `research/frontend/templates/home.html` | complete — full entity list with filter chips and Alpine.js reactivity |
| Review new template (Phase 1 form) | `research/frontend/templates/review/phase1_new.html` | complete — Phase 1 creation form at GET /review/new?trade_id=... |
| Review detail template (Phase 1 read-only + Zone 3 + Phase 2) | `research/frontend/templates/review/phase1.html` | complete — Phase 1 read-only, Zone 3 button (500ms hold enforced), Phase 2 form with mistake type cards |
| Component macros | `research/frontend/templates/components/` | complete — badge, table, capture, prose_field, chip, inline_form macros |
| State machine tests | `research/tests/test_state_machines.py` | complete — 72 tests, covers all spec items 2–10 + obs/setup swap semantics + Mode 3 Session A trade state machine |
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
| `setup` | Structured analytical entity — technical/vol/flow, append-only, many-to-many thesis |
| `setup_images` | Images attached to setups (unchanged) |
| `setup_thesis_links` | Setup↔thesis junction (new, starts empty) |
| `setup_linked_canvases` | Setup↔canvas junction (renamed from observation_linked_canvases; data migrated) |
| `thesis` | Trading theses with state machine |
| `thesis_kill_conditions_macro` | Macro kill conditions |
| `thesis_kill_conditions_technical` | Technical kill conditions |
| `thesis_decision_points` | Decision points with deviation tracking |
| `thesis_linked_canvases` | Thesis↔canvas links |
| `thesis_version_history` | Append-only thesis narrative history |
| `trade` | Trades — idea/active/closed/discarded; thesis_id nullable (set at activation) |
| `trade_entries` | Append-only trade entries |
| `trade_exits` | Append-only trade exits |
| `trade_options_meta` | Options greeks and IV |
| `trade_option_legs` | Option legs (partial update: exit_premium, date_closed only) |
| `observation` | Lightweight ambient capture — state machine (watching/taken/passed), many-to-many thesis |
| `observation_thesis_links` | Observation↔thesis junction (renamed from setup_thesis_links; data migrated) |
| `observation_setup_links` | Observation→setup junction (renamed from setup_observation_links; data migrated) |
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
| `research/frontend/templates/observation/form.html` | `research/frontend/templates/observation/new.html` | 2026-04-30 |

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

2. **Task 003 — bonus tests not in spec**: The test file includes extra tests beyond the spec requirements: CHECK constraint tests (canvas status, trade instrument_type), FK enforcement on child tables (canvas_invalidation_conditions, setup_images, thesis_kill_conditions_macro), thesis touch triggers, canvas cross-currents self-reference and unique constraint, option legs append-only delete, and export watermarks seed verification. These validate schema integrity not covered by the spec's state machine focus. Note: observation_images FK test removed — that table was dropped in the obs/setup swap.

3. **Protocol 4 trigger point** — spec says "on trade close"; implementation calls check_protocol4 on trade detail page load. Functionally equivalent: banner appears when user next views the trade. No behaviour change planned.

4. **Protocol 2 canvas PATCH call is unscoped** — check_protocol2 accepts thesis_id for scoping, not canvas_id. The canvas PATCH handler calls it without a scope argument, so it returns flags for all active theses system-wide, not only those linked to the updated canvas. Correct fix requires either adding a canvas_id param to check_protocol2 or a JOIN in the caller. Deferred — address before Task 016.

5. **Observation ↔ Setup semantic swap — complete.** Phase 1 (schema) and Phase 2 (routes/models/templates) both complete. observation is the lightweight state-machine entity (watching/taken/passed); setup is the structured append-only analytical entity. Junction tables: observation_thesis_links, observation_setup_links, setup_thesis_links, setup_linked_canvases. observation_images dropped. No further breakage.

6. **Phase 2 out-of-scope edit: `thesis.py` and `thesis/panel.html`** — The Phase 2 spec listed `thesis.py` in "do not modify" constraints, but the Phase 1 schema swap had left two `linked_setups` queries in `thesis.py` (in `get_thesis` and `thesis_panel`) selecting `s.setup_type` and `s.status` — columns that no longer exist on `setup`. The panel chip in `thesis/panel.html` referenced the same dead columns. These were failing silently on any thesis with linked setups. Both were corrected during Phase 2 (queries updated to `s.name, s.type`; chip updated to `s.name ~ " — " ~ s.instrument`). The "do not modify" constraint was a blast-radius guard against accidental drift, not a prohibition on fixing direct Phase 1 breakage in thesis. Recorded here so future specs know `thesis.py` was last touched in Phase 2.

7. **Trade state machine expanded** — idea/active/closed/discarded. 'active' replaces 'open' throughout. thesis_id nullable at creation; required at idea→active (trade_active_gate trigger). thesis_active_gate requires trade.status = 'active'. Thesis substitution during activation allowed with force_thesis_change=true (two-click confirm pattern, no modal). thesis_snapshot captures narrative only — see schema DECISION comment.

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
