# RCS Change Spec: Capture Component + Home Entity List

**Status:** Approved for implementation
**Affects tasks:** 007, 010, 013
**Schema changes:** None
**New routes:** `GET /`, `GET /api/entities`

Include this document alongside the task spec at the start of every session for Tasks 007–013.
It supersedes the original spec wherever they conflict.

---

## Change 1: Capture Component

### What changes

The capture button in the left nav becomes a two-target component. The existing quick-capture
behaviour (raw inbox text) is preserved. A + button is added that opens a contextual dropdown
for direct entity creation.

### Component layout

```
[  Capture...          ] [+]
```

**Left area** (full width minus + button): clicking or focusing opens the existing quick-capture
inline textarea below the nav component. On submit: `POST /inbox` with `raw_text`. On cancel
or blur with empty field: collapses.

**Right area** (+ button, ~32×36px, separated by a 1px `--color-border` vertical divider):
clicking opens a contextual dropdown menu anchored below the button.

### Dropdown menu

```
+ Canvas
+ Thesis
+ Observation
+ Setup
+ Trade
+ Action
```

Each item navigates to the entity's creation page:

| Item | Navigates to |
|---|---|
| Canvas | `/canvas/new` |
| Thesis | `/thesis/new` |
| Observation | `/observation/new` |
| Setup | `/setup/new` |
| Trade | `/trade/new` |
| Action | `/action/new` |

### Trade creation page (`/trade/new`)

Trade requires a thesis, and thesis requires a canvas. The form enforces this upfront rather
than failing at the DB trigger.

**Step 1 — Select context**

- Canvas selector (typeahead, searches existing canvases by name)
- Thesis selector (filtered to theses linked to the selected canvas; populates after canvas selection)
- If no canvases exist: show "No canvases available. Create a canvas first." — only action is cancel.
- If canvas selected but no linked theses: show "No theses linked to this canvas." — only action is cancel.

**Step 2 — Trade fields**

Appears below once a valid thesis is selected.

- `instrument_type` (select: equity / option / future / fx / other)
- `entry_rules_stated` (textarea)
- `exit_rules_stated` (textarea)
- `thesis_snapshot` — populated server-side from the selected thesis narrative; not a form field

Submit: `POST /trade`. Cancel at any point: `history.back()`.

### Implementation notes

- Dropdown dismisses on outside click and on Escape (Alpine `@click.away` + `@keydown.window.escape`)
- Quick-capture textarea and + dropdown are mutually exclusive — opening one closes the other
- No new routes required for the capture component itself (creation pages already exist from Tasks 004–006)

---

## Change 2: Home Entity List

### What changes

`GET /` is the system home page. It renders an entity list with filtering and recency sorting.
There is no redirect. The `GET /entities` route described in the original Task 013 spec does not
need to be built as a separate page — it is the home page.

### Filter state

Stored in `localStorage` under key `rcs_entity_filter`. Shape:

```json
{ "type": "canvas", "sort": "recency" }
```

Default when key absent: `type: null` (all entities), `sort: "recency"`.

Filter chips in the left nav and filter chips on the home page share the same state.
Selecting either updates both via Alpine.js reactive state.

### Layout

Standard two-column layout (left nav + main content). No right context panel on this page.

```
[Page header: "Research"  --font-ui --text-xl]
[Filter chips: all · canvas · thesis · observation · setup · trade · review]
[Entity table]
```

### Entity table

Sorted by `last_updated` / `created_at` descending across all types when unfiltered.

**Common columns (always present):**

| Column | Detail |
|---|---|
| Type | Coloured entity-type badge |
| Name / Instrument | Canvas name or thesis / trade instrument |
| Status | Status badge per existing badge styles |
| Last updated | `--font-data`, amber if > 7d, danger if > 21d |
| Links | Per-type detail below |

**Per-type link column contents:**

| Type | Links shown |
|---|---|
| Canvas | Thesis count, observation backlink count |
| Thesis | Linked canvas names (truncated), trade indicator if active |
| Observation | Linked canvas name |
| Setup | Linked thesis name |
| Trade | Thesis instrument, review status indicator |
| Review | Trade instrument, phase indicator (P1 / P1+P2) |

### Row interaction

Click anywhere on row → navigate to full entity page (`/canvas/{id}`, `/thesis/{id}`, etc.).

Full entity pages get a back button (top-left, below breadcrumb) that calls `history.back()`.
No custom state management.

### API endpoint

`GET /api/entities`

Returns all entities across types, merged and sorted by recency.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `type` | string (optional) | Filter to entity type: `canvas`, `thesis`, `observation`, `setup`, `trade`, `review` |

**Response shape:**

```json
[
  {
    "entity_type": "canvas",
    "id": "01HXYZ...",
    "display_name": "OXY Q3 macro context",
    "status": "active",
    "last_updated": "2026-04-21T09:14:00Z",
    "links": {
      "thesis_count": 2,
      "observation_backlink_count": 5
    }
  }
]
```

The `links` object is type-specific and contains the counts and names listed in the table above.
This is a read-only endpoint. No new write paths.

### Empty states

- No entities at all: "Nothing here yet. Use + to create your first entity."
- Filter active with no results: "No [type] entities found."

---

## Per-Task Instructions

Read the section for the current task before starting. These instructions are additive —
follow the original task spec in full, then apply the deltas described here.

---

### Task 007

**Delta:** Add two items to the implementation.

1. Add `GET /` route to `api/routes/` (or directly in `main.py`) that renders the home template.
   The home template does not exist yet — return a minimal 200 HTML shell as a placeholder.
   The full home template is built in Task 010.

2. Add `GET /api/entities` endpoint to a new file `api/routes/entities.py`. Register it in
   `main.py`. This endpoint queries all entity tables, merges results, and returns them sorted
   by `last_updated` / `created_at` descending. Accepts optional `?type=` query param.
   Response shape is defined in the Change 2 section above.

**Smoke test addition:**

```bash
# Home route returns 200
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/)
[ "$STATUS" = "200" ] && echo "HOME ROUTE OK" || echo "FAIL: $STATUS"

# Entities endpoint returns JSON array
curl -sf http://localhost:8099/api/entities | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert isinstance(d, list), 'Expected list'
print(f'ENTITIES ENDPOINT OK — {len(d)} items')
"

# Type filter works
curl -sf 'http://localhost:8099/api/entities?type=canvas' | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert all(e['entity_type'] == 'canvas' for e in d), 'Filter not applied'
print('ENTITIES FILTER OK')
"
```

---

### Task 008

No changes. Implement exactly as specified.

---

### Task 009

No changes. Implement exactly as specified.

---

### Task 010

**Delta:** Three changes to the original spec.

**1. Capture component (replaces original capture button)**

In `base.html`, replace the single capture button with the two-target component described
in Change 1 above. Extract it into `frontend/templates/components/capture.html` as a Jinja2
macro or include so it is maintained in one place.

**2. Home template (new work)**

Create `research/frontend/templates/home.html` extending `base.html`. This is the full entity
list page described in Change 2 above. It is served by `GET /`.

The home template:
- Renders the entity table via HTMX (`hx-get="/api/entities"` on load, `hx-trigger="load"`)
- Filter chip clicks update localStorage and re-trigger the HTMX request with `?type=` param
- No right context panel
- No back button (this is the home)

**3. Root route**

Update `GET /` (added as a placeholder in Task 007) to render `home.html` via Jinja2
`TemplateResponse`. Pass initial entity data server-side to avoid a flash of empty content
on first load, or rely on the HTMX load trigger — either is acceptable.

**Smoke test additions:**

```bash
# Home page renders with expected structure
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/ -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "HOME PAGE RENDERS OK" || echo "FAIL: $STATUS"

curl -sf http://localhost:8099/ -H "Accept: text/html" | grep -c "rcs_entity_filter\|api/entities"
echo "(expect >= 1 — localStorage key or HTMX endpoint referenced)"

# Capture component present in nav
curl -sf http://localhost:8099/ritual/morning -H "Accept: text/html" | grep -c "capture\|inbox"
echo "(expect >= 1)"
```

---

### Task 011

**Delta:** Back button only.

Add a back button to `canvas/detail.html` (top-left, below breadcrumb):

```html
<button onclick="history.back()" class="btn-ghost btn-compact">← Back</button>
```

Style: ghost button, compact, `--color-text-secondary`. No routing logic — `history.back()` only.

All other implementation is as per original spec.

---

### Task 012

**Delta:** Back button only.

Add a back button to `thesis/detail.html` using the same pattern as Task 011.

All other implementation is as per original spec.

---

### Task 013

**Delta:** Significant scope change. Read carefully.

**Removed from scope:**

The original spec item 4 — `frontend/templates/entities/list.html` and the `GET /entities`
filtered entity list page — is removed. That page is now the home page, built in Task 010.
Do not create a separate entity list template or `GET /entities` route.

The original Task 013 smoke test line checking `GET /entities?type=canvas` is no longer
needed here (covered in Task 007). Remove it.

**Remaining scope (unchanged):**

1. `frontend/templates/observation/form.html` — as per original spec
2. `frontend/templates/setup/detail.html` — as per original spec
3. `frontend/templates/trade/detail.html` — as per original spec
4. Wire template-rendering routes for each page

**Addition — back buttons:**

Add `history.back()` back buttons (same pattern as Tasks 011–012) to:
- `observation/form.html` (top-left, before the form)
- `setup/detail.html` (top-left, below breadcrumb)
- `trade/detail.html` (top-left, below breadcrumb)
- `/trade/new` page (cancel button calls `history.back()`)

**Addition — trade creation page (`/trade/new`):**

This is new work not in the original spec. Create `frontend/templates/trade/new.html`:

- Two-step form as described in Change 1 above
- Step 1: canvas typeahead → thesis typeahead filtered by selected canvas
- Step 2: trade fields appear below once thesis is selected
- Empty state: message + cancel only when no canvases or no eligible theses exist
- Canvas typeahead: `GET /canvas?q={query}` (exists from Task 004)
- Thesis typeahead: `GET /thesis?canvas_id={id}&q={query}` — add `canvas_id` filter to
  the existing thesis list route if not already present
- Typeahead uses HTMX `hx-trigger="input changed delay:300ms"`

**Regression suite addition:**

```bash
# Trade new page renders
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/trade/new -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "TRADE NEW RENDERS OK" || echo "FAIL: $STATUS"

# Home page still works (built in Task 010, must not be broken)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/ -H "Accept: text/html")
[ "$STATUS" = "200" ] && echo "REGRESSION HOME PASS" || echo "REGRESSION HOME FAIL"
```

---

## Summary of All Changes by Task

| Task | Change |
|---|---|
| 007 | Add `GET /` placeholder route. Add `GET /api/entities` endpoint in `api/routes/entities.py`. |
| 008 | No change. |
| 009 | No change. |
| 010 | Replace capture button with two-target capture component (`components/capture.html`). Add `home.html` as full entity list page. Wire `GET /` to render `home.html`. |
| 011 | Add `history.back()` back button to canvas detail page. |
| 012 | Add `history.back()` back button to thesis detail page. |
| 013 | Remove standalone entity list page (now the home page). Add `/trade/new` two-step creation page. Add back buttons to observation, setup, trade, and trade/new pages. |

No tasks before 007 are affected. No schema changes. No new write paths beyond `GET /api/entities`.
