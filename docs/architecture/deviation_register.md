# RCS Deviation Register
Generated: 2026-04-30

---

## 1. Schema Integrity

| Object | Expected | Actual | Match |
|---|---|---|---|
| Tables | 30 | 30 | ✓ |
| Triggers | 42 | 42 | ✓ |
| Views | 14 | 14 | ✓ |

All 30 tables present and match the CLAUDE.md DB Tables list exactly:
`schema_version`, `canvas`, `canvas_cross_currents`, `canvas_invalidation_conditions`,
`canvas_version_history`, `setup`, `setup_images`, `thesis`, `thesis_kill_conditions_macro`,
`thesis_kill_conditions_technical`, `thesis_decision_points`, `thesis_linked_canvases`,
`thesis_version_history`, `trade`, `trade_entries`, `trade_exits`, `trade_options_meta`,
`trade_option_legs`, `observation`, `observation_linked_canvases`, `observation_images`,
`setup_thesis_links`, `setup_observation_links`, `action`, `review`, `inbox`,
`entity_events`, `canvas_source_documents`, `export_watermarks`, `failed_exports`.

**No schema deviations.**

---

## 2. Unexpected Route Files

Expected routes (per spec): `canvas.py`, `thesis.py`, `setup.py`, `trade.py`, `observation.py`,
`review.py`, `action.py`, `ritual.py`, `inbox.py`, `entities.py`, `images.py`

Expected absent: `analytics.py`

Actual contents of `api/routes/`:
```
__init__.py   action.py   canvas.py   entities.py   images.py
inbox.py      observation.py   review.py   ritual.py   setup.py
thesis.py     trade.py
```
(`__pycache__` excluded as build artifact)

**No unexpected route files. `analytics.py` correctly absent.**

---

## 3. Protocol Implementation Status

Expected per CLAUDE.md: all four protocol files "not started".

Actual contents of `api/protocols/`:
- `__init__.py` — package init (expected)
- `protocol1.py` — **ABSENT** (expected to be "not started"; file does not exist)
- `protocol2.py` — **PRESENT with real implementation** (deviation — see below)
- `protocol3.py` — **PRESENT with real implementation** (deviation — see below)
- `protocol4.py` — **PRESENT with real implementation** (deviation — see below)

### protocol2.py
Implements `check_protocol2(db, thesis_id=None)`. Queries `thesis`, `thesis_kill_conditions_macro`,
`thesis_linked_canvases`, and `canvas`. Returns active theses with unfired macro kill conditions
where the linked canvas was reviewed in the last 7 days. Full async implementation.

### protocol3.py
Implements `check_protocol3(db, thesis_id=None)`. Queries `thesis` and `thesis_decision_points`.
Returns active theses with unfired decision points. Full async implementation.

### protocol4.py
Implements `check_protocol4(db, trade_id=None)`. Queries `trade`, `thesis`, and `review`.
Returns closed trades with no associated review. Full async implementation.

**Deviation: Protocols 2, 3, and 4 are implemented despite CLAUDE.md marking them "not started".
Protocol 1 remains absent. No corresponding task spec entries account for this work.**

---

## 4. Template Inventory Gaps

### Files present but no CLAUDE.md entry

| File | Status |
|---|---|
| `components/protocol_banner.html` | Present — no CLAUDE.md entry |

`protocol_banner.html` exists in `components/` but is not listed in the Component Status table.
Likely introduced alongside the protocol implementations (Protocols 2–4).

### CLAUDE.md entries marked complete whose files are absent

None — all other entries marked "complete" have corresponding files.

### CLAUDE.md entries marked "removed" verified correct

- `entities/list.html` — confirmed absent (replaced by `home.html` per change spec)

**One undocumented template: `components/protocol_banner.html`.**

---

## 5. Capture Component — Delta from Change Spec

### What the approved change spec (`rcs_change_spec_capture_and_home.md`) specified

Dropdown should contain 6 items linking to entity creation pages:

| Item | Navigates to |
|---|---|
| Canvas | `/canvas/new` |
| Thesis | `/thesis/new` |
| Observation | `/observation/new` |
| Setup | `/setup/new` |
| Trade | `/trade/new` |
| Action | `/action/new` |

### What `components/capture.html` actually contains

Dropdown contains 4 items:

| Item | Navigates to |
|---|---|
| Observation | `/ritual/evening?direct=1` |
| Setup | `/ritual/evening?direct=1` |
| Action | `/ritual/evening?direct=1` |
| Trade | `/trade/new` |

### Delta

- **Canvas removed** from dropdown — no change spec covers this
- **Thesis removed** from dropdown — no change spec covers this
- **Observation, Setup, Action rerouted** from `/entity/new` to `/ritual/evening?direct=1` — no change spec covers this
- **Trade correctly links** to `/trade/new` as per spec

Additionally, the quick-capture text input (left area) behavior changed:
- Spec: on submit → `POST /inbox` with `raw_text`
- Actual: `@keydown.enter.prevent` navigates to `/ritual/evening?direct=1&text=<encoded_text>` (no inbox POST)

**The CLAUDE.md version line for Task 016 documents these changes in prose but there is no formal change spec document covering them. All changes are undocumented beyond the CLAUDE.md version line.**

---

## 6. Evening Page — Delta from Task 014 Spec

Task 014 is not present in `docs/architecture/` or `docs/` as a standalone spec document.
The task spec file `rcs_task_spec_2.md` and `unified_build_spec_v2.md` are present but were
not audited in full — this section reports observable behaviour from the template itself.

### What `ritual/evening.html` currently does

1. **Page title:** "Capture" (not "Evening" or "Evening Review")
2. **Direct mode** (`?direct=1`): supported via `directMode` Alpine state. In direct mode,
   filing routes POST directly to entity endpoints (`/observation`, `/action`, `/setup`) rather
   than through inbox routing. This bypasses the inbox entirely.
3. **Prefill text:** URL param `?text=<encoded>` pre-populates the `captureText` Alpine field.
4. **Editable capture textarea:** fully editable (not read-only from inbox)
5. **4 route types:** Observation, Action, Setup, Thesis Update (2×2 grid)
6. **"Send to inbox" button:** absent — filing goes directly via `fileItem()`
7. **Nav-guard flash:** present — if `captureText` is non-empty and user navigates away,
   the textarea flashes with `nav-warn-flash` CSS class (600ms) on first attempt
8. **`beforeunload` guard:** present — browser dialog fires if text is unsaved
9. **Back button:** present at top of page

### Changes with no corresponding change spec document

| Behaviour | Change spec exists |
|---|---|
| Direct mode (`?direct=1`) bypassing inbox | No |
| URL `?text=` prefill from capture component | No |
| Nav-guard flash on textarea | No |
| `beforeunload` guard | No |
| "Send to inbox" button removed | No |
| Page renamed "Capture" | No |
| Page usable standalone (not only for inbox routing) | No |

All of the above are mentioned in the CLAUDE.md version line for Task 016/017 but no formal
change spec document exists for any of them.

---

## 7. Version Line Mismatches

The CLAUDE.md `Last updated` line records the most recent state. No cumulative version history
is preserved in CLAUDE.md itself; only the current line is present.

**Current version line:**
> Last updated: 2026-04-30 after Task 016 — Fix + dropdown broken links, unify capture into evening routing page with direct mode

**Mismatch: Task 017 reference in audit spec**

The audit spec (Step 7) states: *"The Task 017 version line reads: 'Capture Enter navigates to
evening direct mode with prefill; remove Send to inbox button; add nav-guard flash on evening.html'"*

The current CLAUDE.md version line attributes these changes to Task 016, not Task 017. One of
the following is true:
- The version line was updated to Task 016 after the audit spec was written, consolidating 016+017
- Task 017 was re-numbered or merged into 016

**Either way, the behaviours described (Enter→evening, prefill, remove inbox button, nav-guard)
are present in the code. The task number attribution is inconsistent between the audit spec
and CLAUDE.md.**

**Task number vs. described scope:**

| Task in CLAUDE.md | Described change | Matches stated scope |
|---|---|---|
| 016 | Fix + dropdown broken links, unify capture into evening routing page with direct mode | Partially — "fix broken links" is plausible task scope; the full unification (direct mode, prefill, nav-guard, button removal) suggests scope beyond a link fix |

The CLAUDE.md design amendments table lists Tasks 007–013 with accurate one-line descriptions.
Tasks 014, 015, 016 are not in the amendments table — only the version line reflects them.

---

## 8. Knowledge Library State

### Top-level structure

`knowledge-library/` contains: `db/`, `pipeline/`, `requirements.txt`, `vault/`

### `pipeline/`

Contents: `canvases/`, `observations/`, `reviews/`, `setups/`, `theses/` (all directories)

`research_exporter.py` — **ABSENT** (correctly absent; CLAUDE.md marks it "not started")

No Python files present in `pipeline/`. Only subdirectories (likely export output staging dirs).

### `db/`

Present but contents not listed in spec. No audit of contents required (not in scope of "not started" check).

### `vault/research/`

Path does not exist. `vault/` exists; `vault/research/` is absent.

**No unexpected files in the "not started" pipeline. `research_exporter.py` correctly absent.**

---

## 9. Test Suite Status

| File | Expected | Actual |
|---|---|---|
| `test_state_machines.py` | 58 tests, present | Present, 1097 lines |
| `test_analytics.py` | Not started | Correctly absent |

**Test run result:**
```
58/58 tests passed
ALL TESTS PASSED
```

All 58 state machine tests pass. Test suite is clean.

---

## 10. Summary: Bucket Classification

### Bucket A — Sanctioned deviations (in CLAUDE.md Intentional Deviations section)

1. One fresh DB per test (vs. shared in-memory DB) — explicitly documented
2. Bonus tests beyond spec (CHECK constraints, FK enforcement, etc.) — explicitly documented

### Bucket B — Unsanctioned ad hoc changes (no change spec, no formal approval)

1. **Protocols 2, 3, 4 implemented** — CLAUDE.md marks all as "not started"; actual files
   contain full async query implementations. No task spec covers this work.

2. **`components/protocol_banner.html` added** — no CLAUDE.md entry, no task spec.

3. **Capture component dropdown rerouted** — Canvas and Thesis removed; Observation/Setup/Action
   rerouted from `/entity/new` to `/ritual/evening?direct=1`. Change spec specifies 6 items
   to `/entity/new` paths; actual has 4 items with 3 pointing to evening routing page.

4. **Capture text input rerouted** — spec says submit → `POST /inbox`; actual navigates to
   `/ritual/evening?direct=1&text=<prefill>`. Inbox is bypassed entirely.

5. **Evening page direct mode** — `?direct=1` flag bypasses inbox routing entirely, posting
   directly to entity endpoints. No change spec document.

6. **URL prefill on evening page** — `?text=` parameter pre-populates capture textarea.
   No change spec document.

7. **Nav-guard flash + `beforeunload`** — unsaved-text warning on navigation. No change spec.

8. **"Send to inbox" button removed from evening page** — No change spec document.

9. **Evening page renamed "Capture"** — semantic scope change. No change spec.

10. **Task number attribution inconsistency** — audit spec references Task 017 for changes
    that CLAUDE.md attributes to Task 016. Version history is not cumulative, making this
    unverifiable.

### Bucket C — Spec tasks not started

1. `analytics.py` route — marked "not started"
2. `protocol1.py` — marked "not started" (protocols 2–4 are done; 1 is absent)
3. Protocol 1 implementation (`api/protocols/protocol1.py`) — not started
4. `knowledge-library/pipeline/research_exporter.py` — not started
5. `knowledge-library/run_ingestion.py` — not started
6. `research/tests/test_analytics.py` — not started

---

## 11. Protocol Gap Analysis

### Protocol 1
- **Implementation location:** Inline in `api/routes/canvas.py` (not a separate module). No `protocol1.py` file exists.
- **What it does:** On canvas narrative PATCH, queries `thesis_linked_canvases` + `thesis` to find active theses linked to the updated canvas and returns them in a `protocol_1` key in the JSON response.
- **JSON response wired:** YES — `canvas.py` PATCH handler returns `{"protocol_1": {"affected_theses": [...], "action_required": "..."}}`.
- **Banner rendered on canvas detail:** YES — `canvas/detail.html` line 21 has `<template x-if="protocol1">` with the banner markup.
- **Alpine round-trip verified:** BROKEN. The `prose_field.html` macro calls `showProtocol1(data.protocol_1)` as a **function call** (line 37), but `canvas/detail.html` defines `showProtocol1` as a **boolean data property** (`false`), not a function (line 14). The call will throw a TypeError and the banner will never appear. Additionally, the dismiss button at line 25 sets `showProtocol1 = false` (correct intent) but the `x-if` is bound to `protocol1` (the data object), not `showProtocol1` — so dismissing via `showProtocol1 = false` has no effect on the banner visibility.
- **Confirm-reviewed PATCH:** The `/canvas/{id}/reviewed` PATCH (hx-patch on line 48) uses HTMX `hx-swap="none"` — no protocol_1 response is surfaced from this trigger path, only from the narrative PATCH.

### Protocol 2
- **File:** `api/protocols/protocol2.py` — PRESENT
- **Function:** `async def check_protocol2(db, thesis_id: str = None) -> list[dict]`
- **Tables queried:** `thesis`, `thesis_kill_conditions_macro`, `thesis_linked_canvases`, `canvas`
- **Threshold:** 7 days (`c.last_reviewed >= datetime('now', '-7 days')`) — **matches spec** ("canvas reviewed in the last 7 days")
- **Call sites:** `api/routes/thesis.py` lines 160–162 — called in the thesis detail page load handler (`GET /thesis/{thesis_id}`) with `thesis_id` scoped to the current thesis.
- **Spec-required call sites covered:**
  - Thesis detail load: YES — wired at `thesis.py` line 160
  - Canvas update: NO — `canvas.py` contains no reference to `protocol2` or `check_protocol2`; the canvas PATCH handler does not invoke Protocol 2
- **Banner rendered on thesis detail:** YES — `thesis/detail.html` lines 23–25 loop over `protocol2_flags` and call `protocol_banner(2, ...)`.
- **Template variable injected by route:** YES — `thesis.py` line 177 passes `"protocol2_flags": protocol2_flags` to `TemplateResponse`.
- **Dismiss behaviour:** The `protocol_banner` macro defaults `dismissible=false` (confirmed in `protocol_banner.html` lines 7–9 comments: "No dismiss"). Banner has no dismiss button. Clears only on page reload after condition resolves. **Spec says:** "no dismiss, clears only when hold-vs-redeploy paragraph filed." The route contains no hold-vs-redeploy filing endpoint; the banner will persist as long as the DB condition is true, which is functionally equivalent but the spec's explicit "hold-vs-redeploy paragraph" action is not implemented. **Status: partially compliant** — no dismiss is correct; clear condition is by DB state change only (no dedicated hold-vs-redeploy action route).

### Protocol 3
- **File:** `api/protocols/protocol3.py` — PRESENT
- **Function:** `async def check_protocol3(db, thesis_id: str = None) -> list[dict]`
- **Tables queried:** `thesis`, `thesis_decision_points`
- **Threshold:** None — returns all unfired decision points (`fired_at IS NULL`) regardless of age.
- **Call sites:** `api/routes/thesis.py` lines 161–163 — called in thesis detail page load handler alongside Protocol 2.
- **Spec-required call sites covered:**
  - Thesis detail load: YES — wired at `thesis.py` line 161
- **Banner rendered on thesis detail:** YES — `thesis/detail.html` lines 26–28 loop over `protocol3_flags` and call `protocol_banner(3, ...)`.
- **Template variable injected by route:** YES — `thesis.py` line 178 passes `"protocol3_flags": protocol3_flags` to `TemplateResponse`.
- **Dismiss behaviour:** No dismiss (spec-compliant). Clears when `fired_at` is set on the decision point. The thesis detail template wires a decision-point fire action (`thesis/detail.html` line 310 — fetch with `deviation_note`) that calls a route at `thesis.py` line 402 (`SET fired_at = ?, deviation_note = ?`). Once fired, the record drops out of Protocol 3's query on next page load. **Status: spec-compliant** — no dismiss, clears on execution or deviation log.

### Protocol 4
- **File:** `api/protocols/protocol4.py` — PRESENT
- **Function:** `async def check_protocol4(db, trade_id: str = None) -> list[dict]`
- **Tables queried:** `trade`, `thesis` (LEFT JOIN), `review` (LEFT JOIN)
- **Threshold:** None — condition is binary: `status = 'closed' AND review.id IS NULL`.
- **Call sites:** `api/routes/trade.py` lines 132–133 — called in the trade detail page load handler with `trade_id` scoped to the current trade.
- **Spec-required call sites covered:**
  - Trade close (trigger): The spec says "on trade close, checks if review exists." The actual wiring is on **trade detail page load** (GET), not on the close mutation itself. Trade close is a PATCH to `/trade/{id}/close`; Protocol 4 is not called there. It is called only when the trade detail page is subsequently loaded.
  - This is functionally equivalent for surfacing the banner to the user, but is a call-site deviation from the spec trigger definition.
- **Banner rendered on trade detail:** YES — `trade/detail.html` lines 20–22 loop over `protocol4_flags` and call `protocol_banner(4, ...)` with an action link to `/review/new?trade_id=...`.
- **Template variable injected by route:** YES — `trade.py` line 145 passes `"protocol4_flags": protocol4_flags` to `TemplateResponse`.
- **Dismiss behaviour:** No dismiss (spec-compliant). Clears when a review is filed (`review.id` becomes non-null, dropping the trade from Protocol 4's query). The action link on the banner points to `/review/new?trade_id=...` which files Phase 1. **Status: spec-compliant** — no dismiss, clears on Phase 1 filing.

### Protocol 1 — Missing File Assessment
- **Spec required:** `protocol1.py` as a callable module (CLAUDE.md marks it "not started")
- **Current state:** Inline implementation inside `canvas.py` PATCH handler. Not a separate module.
- **Gap:** The inline implementation is functionally present but has a broken Alpine.js round-trip (see Protocol 1 section above). Additionally, the inline placement means Protocol 1 cannot be called from other routes without importing canvas logic. Whether the inline approach is "sufficient" per spec depends on whether spec required a standalone module — CLAUDE.md marks it "not started" implying a module was expected.

---

### Summary Table

| Protocol | File | Call Sites Wired | Banner Rendered | Variable Injected | Alpine Round-Trip | Spec-Compliant |
|---|---|---|---|---|---|---|
| 1 | Inline in canvas.py (no module) | YES — on canvas narrative PATCH only | YES — markup present | N/A (JSON response, not template var) | BROKEN — `showProtocol1` is a boolean, not a function; banner never fires | NO |
| 2 | Present | Thesis detail load: YES / Canvas update: NO | YES | YES | N/A (server-rendered) | PARTIAL — canvas update trigger missing |
| 3 | Present | Thesis detail load: YES | YES | YES | N/A (server-rendered) | YES |
| 4 | Present | Page load only (not on trade close mutation) | YES | YES | N/A (server-rendered) | PARTIAL — trigger point is page load, not close mutation |

### Critical Bugs

1. **Protocol 1 banner never fires** (`canvas/detail.html`): `prose_field.html` calls `showProtocol1(data.protocol_1)` as a function, but `canvas/detail.html` defines `showProtocol1: false` (a boolean). This will throw `TypeError: showProtocol1 is not a function` in the browser and silently suppress the Protocol 1 banner on every canvas narrative save.

2. **Protocol 2 missing canvas update trigger**: Spec requires Protocol 2 to fire when a canvas is updated (to surface kill conditions on linked theses). `canvas.py` PATCH handler does not call `check_protocol2`. The only call site is thesis detail page load — so the banner appears when you navigate to the thesis, but not proactively when you update the canvas.

### Minor Deviations

1. **Protocol 4 trigger point**: Spec says "on trade close"; implementation calls Protocol 4 on trade detail page load. Functionally equivalent for the user (banner appears when they next view the trade), but the trigger is passive (page load) rather than active (mutation hook).

2. **Protocol 1 as inline code**: No `protocol1.py` module exists. Logic is embedded in the canvas PATCH handler. Makes reuse and testing harder but does not affect current behaviour (beyond the Alpine bug above).
