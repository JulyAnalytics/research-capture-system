# Gap Prevention Protocol
**Applies to:** All architecture specs, Claude Code task specs, and CLAUDE.md
**Purpose:** Prevent the four gap categories identified in Task 000 from recurring:
missing infrastructure, diverging configs, duplicate constants, broken output contracts.
Extended in Fix 4 to cover browser/E2E tests via Playwright Test (VS Code).

---

## The Root Cause

All four gaps shared the same origin: specs described *intent* and *construction*
but not *verification*. Architecture docs described what to build. Task specs
described how to build it. Neither asked whether what was built actually integrated
correctly with what already existed.

The three fixes below address this at each document layer. Fix 4 applies the
same discipline to browser tests.

---

## Fix 1: Every Architecture Spec Gets an Integration Verification Checklist

Add this section to the bottom of every architecture `.md` produced in Claude.ai.
Write it at architecture time, not after the build. It forces the question
"what does correct integration look like?" before any code is written.

The checklist has three parts: what must exist before this component runs,
what must exist after it runs, and what must not have broken.

```markdown
## Integration Verification Checklist
*These assertions must all pass before this component is considered complete.
Copy this block verbatim into the final step of the Claude Code task spec.*

### Prerequisites — must exist before this component runs
- [ ] `data/outputs/regime_state.json` exists and written_at < 12h ago
- [ ] `from config import OUTPUTS_DIR` resolves
- [ ] `from systems.utils.db import get_connection` resolves
- [ ] [any other upstream output this component reads]

### Outputs — must exist after this component runs
- [ ] `data/outputs/[this_component].json` written with schema:
      [paste exact schema here]
- [ ] `[table_name]` table exists in macro.db with > 0 rows for today
- [ ] [any other file or table this component produces]

### Integration contracts — must not break existing behaviour
- [ ] `regime_state.json` still valid after this run (Marcus untouched)
- [ ] `from config import OUTPUTS_DIR` still resolves
- [ ] `from systems.utils.db import get_connection` still resolves
- [ ] [any other shared utility this component imports]

### No-duplication check — run before writing any new constant or utility
- [ ] No constant being added already exists in config.py:
      `grep -r "[CONSTANT_NAME]" --include="*.py" . | grep -v venv`
- [ ] No DB connection logic outside systems/utils/db.py
- [ ] No hardcoded path strings outside config.py:
      `grep -r "data/processed\|data/outputs" --include="*.py" . | grep -v venv | grep -v config`
```

**The no-duplication check is the most important part.** The `COMPONENT_WEIGHTS`
duplication and the two-config problem both would have been caught by running
grep before creating new constants. Write the specific grep for whatever
constant or utility the architecture is introducing.

---

## Fix 2: Every Task Spec Gets Three Mandatory Sections

These three sections are currently absent from all task specs. Add them
to every spec, in this order, before the implementation steps.

---

### Section A: Pre-flight

What Claude Code must read and confirm before touching any code.
The prerequisite checks must be assertions that fail loudly, not
documentation that gets skimmed.

```markdown
## Pre-flight (run before writing any code)

### Read these files in full
- `config.py` (root) — confirm OUTPUTS_DIR and DUCKDB_PATH are defined
- `systems/utils/db.py` — confirm get_connection() signature
- [every file this task will modify or import from]

### Confirm these do NOT already exist
Run each grep before creating any new function, constant, or table:
```bash
grep -r "[NEW_CONSTANT]" --include="*.py" . | grep -v venv
grep -r "def [new_function]" --include="*.py" . | grep -v venv
```
If found: report location and do not recreate. Use the existing one.

### Confirm prerequisites DO exist
```bash
python -c "from config import OUTPUTS_DIR; print('OK')"
python -c "from config import DUCKDB_PATH; print('OK')"
python -c "
import os, json
from pathlib import Path
from config import OUTPUTS_DIR
p = Path(OUTPUTS_DIR) / 'regime_state.json'
assert p.exists(), f'MISSING: {p}'
data = json.loads(p.read_text())
assert 'regime_state' in data
print('OK — regime_state:', data['regime_state'])
"
```
If any prerequisite is missing: stop and report. Do not proceed.
```

---

### Section B: Constraints

What must not change. Written explicitly so Claude Code cannot make
reasonable-seeming changes that break the integration contract.

```markdown
## Constraints (do not violate)

### Do not create
- Any new config file — root config.py is the only config
- Any new DB connection utility — systems/utils/db.py is the only one
- Any constant that duplicates something already in config.py

### Do not modify
- `config.py` DUCKDB_PATH
- `systems/utils/db.py` get_connection() signature
- `data/outputs/regime_state.json` schema
- Any existing table schema in macro.db
- [any other locked contract relevant to this task]

### Do not hardcode
- Any path string — use config.OUTPUTS_DIR, config.DUCKDB_PATH
- Any threshold value — use config.REGIME_THRESHOLDS
- Any ticker list — use config.TICKERS
- Any weight value — use config.COMPONENT_WEIGHTS
```

---

### Section C: Regression Suite

Runs existing functionality after the new build to confirm nothing broken.
This is separate from the task's own smoke tests, which only test what
was just built. The regression suite tests what already existed.

```markdown
## Regression Suite (run after your own smoke tests pass)
These verify nothing that was already working has broken.
All must pass. If any fail, fix before reporting complete.

```bash
# Marcus still classifies correctly
python -c "
from systems.signals.regime_classifier import RegimeClassifier
clf = RegimeClassifier()
r = clf.classify(persist=False)
assert r.regime in [
    'RISK_ON_LOW_VOL','RISK_ON_ELEVATED_VOL',
    'NEUTRAL','CAUTION','RISK_OFF_STRESS','CRISIS'
]
print('REGRESSION 1 PASS — regime:', r.regime)
"

# Output contract still valid
python -c "
import json
from pathlib import Path
from config import OUTPUTS_DIR
data = json.loads((Path(OUTPUTS_DIR) / 'regime_state.json').read_text())
assert 'regime_state' in data and 'component_scores' in data
print('REGRESSION 2 PASS — regime_state.json intact')
"

# Shared utilities unchanged
python -c "
from systems.utils.db import get_connection, get_latest, get_series_history
from config import DUCKDB_PATH, OUTPUTS_DIR, COMPONENT_WEIGHTS
print('REGRESSION 3 PASS — shared utilities importable')
"
```
```

The regression suite should grow with the project. Each new component
that goes live adds one regression test to this standard block. By the
time Sarah and Jordan are built, the suite will cover all live components
with a single copy-paste.

---

## Fix 3: CLAUDE.md Gets a Maintenance Protocol

CLAUDE.md is currently a static document updated manually. It needs a
rule that makes Claude Code responsible for updating it as part of task
completion — so it stays current rather than drifting.

Add this section to the bottom of CLAUDE.md:

```markdown
---

## Maintenance Protocol

This file must be updated as the last step of every task.

After completing any task that:
- Adds a component or file to `systems/` → update Component Status table
- Writes a new file to `data/outputs/` → add its schema to Output Contracts
- Creates a new DB table → add it to the DB Tables section
- Deprecates or renames a file → add it to the Deprecated Files section
- Adds a constant to `config.py` → note it in Shared Utilities if shared

**Version line** (update on every change):
`Last updated: [date] after Task [NNN] — [one sentence describing change]`

**Completion report requirement:**
Every task completion report must include one of:
  `CLAUDE.md updated: YES`
  `CLAUDE.md updated: NO — reason: [reason]`

A missing or stale CLAUDE.md is a build error, not an oversight.
```

---

## Fix 4: Browser Tests Use Playwright Test (VS Code) — Three Rules

This fix applies the same discipline as Fixes 1–3 to E2E and browser tests.
The toolchain is the Playwright Test VS Code extension. Tests must be runnable
both from the VS Code Test Explorer and from the CLI (`npx playwright test`).
If it only works one way, it's not done.

---

### Rule 4a: `playwright.config.ts` Is the Only Browser Config

Treat `playwright.config.ts` the same way the backend treats `config.py`:
one file, never duplicated, never overridden inline.

**What must live in `playwright.config.ts` and nowhere else:**
- `baseURL` — never hardcode `http://localhost:3000` in a test file
- browser projects (`chromium`, `firefox`, `webkit`) and their options
- `testDir` — the single directory that contains all `.spec.ts` files
- `webServer` config if the app is started by Playwright
- retry and timeout defaults

**No-duplication check before adding any new config value:**
```bash
grep -r "localhost" --include="*.spec.ts" .
grep -r "baseURL\|timeout\|viewport" --include="*.spec.ts" .
```
If found: move it to `playwright.config.ts` and reference it. Do not proceed
with a test file that hardcodes values that belong in config.

**The VS Code extension reads `playwright.config.ts` directly.** If config
exists in multiple places, the extension and the CLI will behave differently —
this is the browser equivalent of the two-config gap.

---

### Rule 4b: Pre-flight for Any Task That Adds or Modifies Browser Tests

Add this block to Section A (Pre-flight) of any task spec that touches
test files.

```markdown
## Pre-flight — Browser Tests

### Confirm Playwright is installed and browsers are present
```bash
npx playwright --version
# Must return a version string. If not: npx playwright install
ls $(npx playwright install --dry-run 2>&1 | grep "Install location" | awk '{print $3}') 2>/dev/null \
  || echo "Run: npx playwright install"
```

### Confirm config is the single source of truth
```bash
# Must return zero results. Any hits are violations to fix before proceeding.
grep -rn "localhost" --include="*.spec.ts" .
grep -rn "baseURL\|viewport\|timeout" --include="*.spec.ts" .
```

### Confirm no selector duplication
```bash
# Find selectors used in more than one spec file — these belong in a page object or fixture
grep -rh "getByRole\|getByTestId\|getByLabel\|locator(" --include="*.spec.ts" . \
  | sort | uniq -d
```
If duplicates found: extract to a shared fixture or page object before adding more.
If a page object already exists for this area: read it in full before writing new selectors.

### Confirm test names will be meaningful in VS Code Test Explorer
Every `test()` and `test.describe()` block must have a name that identifies:
- Which feature or route it covers
- What the expected outcome is
Bad:  `test('works')`
Good: `test('dashboard — regime banner shows RISK_OFF when score < 0.3')`
```

---

### Rule 4c: Regression Suite Entry for Every New Spec File

Every spec file that ships adds one CLI regression check to the regression suite.
This ensures the VS Code extension and CLI stay in sync and that new tests don't
silently break existing ones.

```markdown
## Regression Suite — Browser Tests (append after Python regression checks)

```bash
# All Playwright tests pass (CLI must match VS Code Test Explorer results)
npx playwright test --reporter=line
# Expected: X passed, 0 failed
# If any test is legitimately skipped, document why here:
# SKIP: [test name] — reason: [reason], ticket: [ref]

# Config is still the single source of truth
grep -rn "localhost" --include="*.spec.ts" . && echo "VIOLATION: hardcoded URL" || echo "REGRESSION PW-1 PASS"
grep -rn "baseURL\|viewport\|timeout" --include="*.spec.ts" . && echo "VIOLATION: inline config" || echo "REGRESSION PW-2 PASS"
```
```

**The regression command must match what VS Code Test Explorer runs.** If
`npx playwright test` passes but the extension shows failures (or vice versa),
that is a blocker — it means config or environment has diverged.

---

### Fix 4 Addendum: CLAUDE.md Maintenance for Browser Tests

Add these triggers to the CLAUDE.md Maintenance Protocol (Fix 3):

```markdown
After completing any task that:
- Adds a `.spec.ts` file → add its feature area and file path to a Browser Tests section
- Adds a page object or fixture → note it and its covered selectors
- Changes `playwright.config.ts` → update any documented base URL, project list, or timeout
- Marks a test as skipped → document reason and ticket reference inline
```

---

## How the Four Fixes Work Together

The architecture checklist (Fix 1) surfaces integration requirements
*at design time* — before any spec is written. The task spec sections
(Fix 2) enforce those requirements *at build time* — before any code
is written and after it runs. The CLAUDE.md protocol (Fix 3) keeps the
project map current *after each build* — so the next task's pre-flight
checks have accurate information to work from. The Playwright rules
(Fix 4) apply the same three-phase discipline to browser tests, with
`playwright.config.ts` as the single source of truth equivalent to
`config.py`.

Each gap from Task 000 maps to a specific check that would have caught it:

| Gap | Caught by |
|-----|-----------|
| `data/outputs/` didn't exist | Task spec Pre-flight: prerequisite assertion fails loudly |
| Two config files diverging | Architecture checklist: no-duplication grep before creating config |
| `COMPONENT_WEIGHTS` duplicated | Task spec Pre-flight: grep for constant before creating it |
| `regime_state.json` never written | Architecture checklist: output contract check in verification section |
| Hardcoded `localhost` in spec files | Fix 4 Pre-flight: grep catches it before the test file ships |
| VS Code Test Explorer and CLI disagree | Fix 4 Regression Suite: both must pass before task is complete |
| Selector repeated across spec files | Fix 4 Pre-flight: `uniq -d` grep flags it, forces page object extraction |

---

*Add this document to `docs/architecture/gap_prevention_protocol.md`.
Reference it at the top of every new architecture spec and task spec.*
