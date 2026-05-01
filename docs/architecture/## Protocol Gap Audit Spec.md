## Protocol Gap Audit Spec

**Goal:** Read-only. Surface the complete picture of what was implemented for Protocols 1–4, what was wired, what's missing, and what's inconsistent. Output appended to `docs/architecture/deviation_register.md` as a new section. No code changes.

---

### Step 1 — Read all protocol files in full

```bash
cat research/api/protocols/__init__.py
cat research/api/protocols/protocol2.py
cat research/api/protocols/protocol3.py
cat research/api/protocols/protocol4.py
# protocol1.py is expected absent — confirm:
ls research/api/protocols/protocol1.py 2>/dev/null && echo "EXISTS" || echo "ABSENT (expected)"
```

For each file that exists, record:
- Function signatures (name, parameters, return type)
- What tables it queries
- What it returns
- Any hardcoded thresholds or assumptions (e.g. "recently updated" — what does that mean in days?)

---

### Step 2 — Check registration in main.py

```bash
grep -n "protocol" research/api/main.py
```

Determine: are any protocol modules imported or called at app startup? Or are they only called on-demand from routes?

---

### Step 3 — Find every call site for each protocol function

```bash
grep -rn "protocol2\|check_protocol2" research/api/ --include="*.py" | grep -v __pycache__
grep -rn "protocol3\|check_protocol3" research/api/ --include="*.py" | grep -v __pycache__
grep -rn "protocol4\|check_protocol4" research/api/ --include="*.py" | grep -v __pycache__
grep -rn "protocol1\|protocol_1" research/api/ --include="*.py" | grep -v __pycache__
```

For each call site found, note: which route file, which route function, at what point in the handler (pre-query, post-query, on mutation, on page load).

---

### Step 4 — Verify spec-required call sites

The task spec (Task 015) required each protocol to be invoked at specific trigger points. Check each one:

**Protocol 2** — spec says: invoked on thesis detail page load and canvas update.
```bash
grep -n "protocol2\|check_protocol2" research/api/routes/thesis.py
grep -n "protocol2\|check_protocol2" research/api/routes/canvas.py
```

**Protocol 3** — spec says: invoked on thesis detail page load (unfired decision points).
```bash
grep -n "protocol3\|check_protocol3" research/api/routes/thesis.py
```

**Protocol 4** — spec says: on trade close, checks if review exists.
```bash
grep -n "protocol4\|check_protocol4" research/api/routes/trade.py
```

**Protocol 1** — implemented inline in canvas.py (not as a separate protocol file). Verify it's actually present and wired:
```bash
grep -n "protocol_1\|affected_theses\|Protocol 1" research/api/routes/canvas.py
```

---

### Step 5 — Verify banner rendering in templates

The spec required protocol banners to be rendered on relevant pages. Check each:

**Canvas detail** — Protocol 1 banner (on canvas update response):
```bash
grep -n "protocol.banner\|protocol_banner\|protocol_1\|protocol-banner" research/frontend/templates/canvas/detail.html
```

**Thesis detail** — Protocol 2 and Protocol 3 banners (on page load):
```bash
grep -n "protocol.banner\|protocol_banner\|protocol2\|protocol3\|protocol-banner" research/frontend/templates/thesis/detail.html
```

**Trade detail** — Protocol 4 banner (on page load for closed trades without review):
```bash
grep -n "protocol.banner\|protocol_banner\|protocol4\|protocol-banner" research/frontend/templates/trade/detail.html
```

---

### Step 6 — Verify template variable injection

For each page that renders protocol banners, check that the route handler actually fetches and passes the protocol data to the template.

**Thesis detail route** — must pass `protocol2_flags` and `protocol3_flags` to template:
```bash
grep -n "protocol2_flags\|protocol3_flags\|TemplateResponse" research/api/routes/thesis.py | head -20
```

**Trade detail route** — must pass `protocol4_flag` or equivalent to template:
```bash
grep -n "protocol4\|protocol_4\|review_required\|TemplateResponse" research/api/routes/trade.py | head -20
```

---

### Step 7 — Check banner dismiss/clear behaviour

The spec has specific clear conditions for each banner. Check what's actually implemented:

**Protocol 2** — spec: no dismiss, clears only when hold-vs-redeploy paragraph filed.
```bash
grep -n "dismissible\|dismiss\|protocol-banner-2" research/frontend/templates/components/protocol_banner.html
grep -n "hold.vs.redeploy\|hold_vs_redeploy" research/api/routes/thesis.py research/frontend/templates/thesis/detail.html
```

**Protocol 3** — spec: clears when decision executed or deviation logged.
```bash
grep -n "deviation\|decision.*executed\|log.*deviation" research/api/routes/thesis.py research/frontend/templates/thesis/detail.html
```

**Protocol 4** — spec: clears when Phase 1 filed.
```bash
grep -n "protocol4\|review_required" research/api/routes/trade.py research/frontend/templates/trade/detail.html
```

---

### Step 8 — Protocol 1 consistency check

Protocol 1 is special: it's implemented inline in `canvas.py` (not as a `protocol1.py` file) and returns data in the JSON response. But it also needs to surface as a banner in the canvas detail template.

The canvas detail template uses Alpine.js to display Protocol 1 from the PATCH response. Verify the full round-trip is wired:

```bash
# In the template: how does Protocol 1 response get displayed?
grep -n "protocol1\|protocol_1\|affected_theses" research/frontend/templates/canvas/detail.html

# In the PATCH handler: what does it return?
grep -A 10 "affected_theses" research/api/routes/canvas.py

# Is there an HTMX or fetch call in the template that handles the PATCH response?
grep -n "hx-patch\|fetch.*canvas\|PATCH" research/frontend/templates/canvas/detail.html
```

---

### Step 9 — Protocol 2 threshold audit

Protocol 2 checks for "active theses where the linked canvas was recently updated." The word "recently" is a hardcoded threshold. Find it:

```bash
grep -n "days\|hours\|interval\|julianday\|last_reviewed\|last_updated" research/api/protocols/protocol2.py
```

Compare against the spec description: "macro kill conditions on active theses where the linked canvas was reviewed in the last 7 days." Record whether the implementation matches the 7-day threshold.

---

### Step 10 — Compile findings and append to deviation register

Append a new section `## 11. Protocol Gap Analysis` to `docs/architecture/deviation_register.md` with the following structure:

```markdown
## 11. Protocol Gap Analysis

### Protocol 1
- Implementation location: [inline in canvas.py / absent / other]
- JSON response wired: [yes/no]
- Banner rendered on canvas detail: [yes/no]
- Alpine round-trip verified: [yes/no — describe how it works or what's missing]

### Protocol 2
- File: api/protocols/protocol2.py [present/absent]
- Function: [signature]
- Tables queried: [list]
- Threshold: [X days — matches spec / deviates]
- Call sites: [list of route + function, or NONE]
- Spec-required call sites covered: thesis detail load [yes/no], canvas update [yes/no]
- Banner rendered on thesis detail: [yes/no]
- Template variable injected by route: [yes/no]
- Dismiss behaviour: [spec-compliant / deviates / not implemented]

### Protocol 3
- [same structure as Protocol 2]

### Protocol 4
- [same structure as Protocol 2, substituting trade close for canvas update]

### Protocol 1 — Missing File Assessment
- Spec required: protocol1.py as a callable module
- Current state: inline implementation in canvas.py
- Gap: [none if inline is sufficient / describe what's missing if not]

### Summary Table

| Protocol | File | Call Sites Wired | Banner Rendered | Variable Injected | Spec-Compliant |
|---|---|---|---|---|---|
| 1 | inline/absent | ? | ? | ? | ? |
| 2 | present | ? | ? | ? | ? |
| 3 | present | ? | ? | ? | ? |
| 4 | present | ? | ? | ? | ? |
```

Fill every cell. Do not leave unknowns — if a grep returns no results, that is the answer (NO / NONE).

Do not make any code changes. Report only.