# Research Capture System — Design Specification v1

## Purpose of this document

This specification defines all visual, layout, interaction, and component decisions
for the Research Capture System frontend. It is intended to be read alongside
`unified_build_spec_v2.md` and used as the primary reference for frontend
implementation in Claude Code. Every decision recorded here has been explicitly
confirmed. Nothing is a default or an assumption.

The stack is HTMX + Alpine.js + Jinja2 templates. All CSS is written as custom
properties and utility classes — no Tailwind, no component framework. The design
system is defined entirely in this document.

---

## 1. Design Character

**Archival Warm.** The aesthetic reference is a well-maintained research journal
that has been thoughtfully adapted to screen. The system is a knowledge graph that
occasionally produces trades as outputs — the design prioritises the research and
analytical character over the operational one. Warmth and precision in equal measure.

Every decision follows from three principles:
- Content is primary. Chrome is invisible when working correctly.
- Delineation has semantic meaning. Borders, shadows, and tonal variation each mean
  something specific and are never used interchangeably.
- The system's rules are expressed visually. Append-only fields look different from
  editable fields. Gated transitions communicate their conditions. The UI does not
  require documentation to understand what is and isn't permitted.

---

## 2. Colour System

### Base palette

```
--color-bg:           #FAF8F3   Page background. Warm off-white. Never used for
                                 content surfaces.

--color-surface:      #FFFFFF   Content cards, canvas/thesis detail containers,
                                 form field backgrounds on focus. Pure white appears
                                 slightly elevated against the warm background.

--color-recessed:     #F2EFE9   Secondary content: version history, metadata blocks,
                                 read-only field backgrounds, table header rows.

--color-border:       #E2DDD5   Structural borders within surfaces. 1px only.
                                 Used for: card edges, table row dividers, section
                                 rules, horizontal dividers.

--color-border-light: #EBE7E0   Lighter variant for internal subdivisions where
                                 --color-border would be too heavy. Table cell
                                 separators, sub-section dividers.
```

### Text

```
--color-text-primary:   #2C2A26   All body text, headings, labels, form values.
--color-text-secondary: #7A7368   Metadata, timestamps, placeholder text, secondary
                                   labels, helper text.
--color-text-tertiary:  #A89F96   Fine print, disabled states, empty state messages.
```

### Layer identity

Layer colours are attribute signals, not organisational containers. They appear as
2px left borders on badges, chips, and nav items — never as background fills on
layout regions.

```
--color-analytical:       #2B5F8F   Ink blue.   Canvas, Thesis, Observation.
--color-analytical-bg:    #EEF4FA   Tint for analytical badges and hover states.
--color-analytical-text:  #1D4270   Dark variant for text on analytical tint.

--color-operational:      #9B5A1A   Brown-amber. Trade, Setup, Action.
--color-operational-bg:   #FBF3E8   Tint for operational badges and hover states.
--color-operational-text: #6B3D0F   Dark variant for text on operational tint.

--color-learning:         #5B4A7A   Dusty violet. Review.
--color-learning-bg:      #F2EFF8   Tint for learning badges and hover states.
--color-learning-text:    #3D3054   Dark variant for text on learning tint.
```

### Semantic states

```
--color-active:     #2B6B4A   Muted green. Active thesis, taken setup, done action.
--color-active-bg:  #EBF5EF

--color-warning:    #8F6B1A   Amber. Staleness flags, Protocol 1 banners,
--color-warning-bg: #FDF6E3   watching setup, partial rules-followed.

--color-danger:     #8B2218   Deep red. Kill conditions fired, overdue actions,
--color-danger-bg:  #FCECEA   invalidated thesis, critical staleness (>21d).

--color-neutral:    #5A5650   Building/watching status where no urgency is implied.
--color-neutral-bg: #F0EDE8
```

### Shadow scale

Shadows are used exclusively on surfaces that float above the page. Never on
elements that are part of the page structure.

```
--shadow-card:   0 1px 3px rgba(44, 42, 38, 0.07)
                 Card surfaces that sit slightly above the page background.
                 Used on: content cards, entity detail containers.

--shadow-panel:  0 4px 16px rgba(44, 42, 38, 0.11)
                 The contextual right panel when visible. Signals that it floats
                 above the main content surface.

--shadow-modal:  0 8px 32px rgba(44, 42, 38, 0.16)
                 Reserved for modal/overlay elements (Phase 9 review states).
```

---

## 3. Typography

### Typefaces

```
--font-prose:  'Lora', Georgia, serif
               Used for: canvas narrative, thesis narrative, win condition,
               review analysis, review what-not-changing, single-update field,
               thesis kill condition descriptions (when in prose context),
               inbox raw capture display.

--font-data:   'Fira Code', 'Courier New', monospace
               Used for: instruments (OXY, TLT, BITX), timestamps, prices,
               sizes, percentages, status labels in badges, form field values
               for structured data (dates, numbers), version history timestamps,
               diff summaries, phase 1 review fill fields.

--font-ui:     'Inter', system-ui, sans-serif
               Used for: navigation labels, table headers, button labels,
               form labels, section headings, page headings, badge text,
               breadcrumbs, helper text, empty states, all UI chrome.
```

### Scale

```
--text-xs:   11px / 1.5   Fine print, timestamps in tables, image count badges.
             Font: --font-data for data, --font-ui for labels.

--text-sm:   13px / 1.6   Secondary labels, table cell content, badge text,
             nav items, metadata, breadcrumb text.
             Font: context-dependent (see above).

--text-base: 15px / 1.7   Primary UI text: form labels, helper text, button
             labels, list items.
             Font: --font-ui.

--text-prose: 16px / 1.85  All prose field content (Lora). This line-height is
              non-negotiable — Lora requires generous leading at text sizes.

--text-lg:   18px / 1.5   Section headings within entity detail pages.
             Font: --font-ui, weight 500.

--text-xl:   22px / 1.3   Page/entity titles. Canvas name, Thesis instrument.
             Font: --font-ui, weight 500.

--text-2xl:  28px / 1.2   Reserved for the worst_case_dollar display on thesis
             detail — the one field that needs visual prominence above all others.
             Font: --font-data, weight 600.
```

### Weight

```
Regular: 400   All body text, prose fields, secondary labels.
Medium:  500   Headings, active nav items, emphasis labels, button text.
Semibold: 600  worst_case_dollar figure only.
```

No other weights are used.

### Letter spacing

```
Section headers (uppercase labels): letter-spacing: 0.07em
All other text: letter-spacing: normal (never tracked)
```

---

## 4. Spacing

Base unit: 8px. All spacing values are multiples of 4px (half-unit permitted for
tight internal spacing only).

```
--space-1:  4px    Internal component spacing: icon-to-label gaps, tight badge padding.
--space-2:  8px    Between related inline elements. Button internal padding (vertical).
--space-3:  12px   Between form field label and input. Between table header and first row.
--space-4:  16px   Standard content padding. Between form fields. Card internal padding.
--space-5:  20px   Between sections within a card.
--space-6:  24px   Between cards. Section padding (top/bottom).
--space-8:  32px   Between major page sections. Ritual step gap.
--space-10: 40px   Page-level top padding.
--space-12: 48px   Large section separation.
```

### Component-level standards

```
Content area padding (cards):          16px all sides
Table row height:                       44px
Table cell padding:                     10px vertical, 14px horizontal
Form field height (inputs, selects):    40px
Form field internal padding:            0 12px
Gap between form fields:                16px
Nav item height:                        34px
Nav item padding:                       0 10px
Right panel content padding:            16px
Section heading margin-bottom:          12px
Prose field minimum height:             120px (expands with content)
```

---

## 5. Layout

### Shell structure

```
┌─────────────────────────────────────────────────────────────┐
│ LEFT NAV (200px, fixed)  │ MAIN CONTENT (flex-1)            │
│                          │                    │ RIGHT PANEL │
│                          │                    │ (260px,     │
│                          │                    │ contextual) │
└─────────────────────────────────────────────────────────────┘
```

The left nav is fixed width, fixed position, full viewport height. It never
collapses on desktop. The main content area takes all remaining width. The right
context panel is not a persistent column — it is absolutely positioned and slides
in over the main content on entity detail pages where relational context is
relevant (canvas detail, thesis detail). It is absent on all workflow pages
(morning ritual, evening routing, inbox).

### Left navigation

Width: 200px. Background: --color-recessed. Right border: 1px solid --color-border.

```
Structure (top to bottom):

[System identity]
  14px, --font-data, --color-text-secondary
  "research capture" in lowercase
  Padding: 20px 16px 16px

[Divider]

[CAPTURE button]
  Full-width within nav. Height 36px. Background --color-surface.
  Border: 1px solid --color-border. Border-radius: 4px.
  Text: "Capture" in --font-ui 13px 500. --color-text-primary.
  Margin: 12px 10px.
  On click: opens quick-capture inline form below the button.
  This is the most prominent affordance in the nav.

[INBOX item]
  Standard nav item with unrouted count badge (amber) when > 0.

[Divider]

[Mode items — workflow]
  Morning ritual   (amber count badge if incomplete today)
  Evening routing  (amber count badge if inbox > 0)

[Divider]

[Entity section header]
  "ENTITIES" — 10px --font-ui, 500, letter-spacing: 0.07em,
  --color-text-tertiary, uppercase.

[Entity filter chips — horizontal wrap]
  canvas · thesis · observation · setup · trade · review
  Chips in --font-ui 11px. Active chip: filled --color-surface,
  border 1px --color-border, --color-text-primary.
  Inactive chip: no background, no border, --color-text-secondary.
  Below chips: filtered entity list.

[Spacer — flex-grow]

[System status — bottom of nav]
  Active theses count, open actions count.
  12px --font-ui --color-text-tertiary.
  Padding: 12px 16px.
```

### Nav item states

```
Default:    Background transparent. Text --color-text-secondary.
Hover:      Background --color-surface. Text --color-text-primary.
Active:     Background --color-surface. Text --color-text-primary. Weight 500.
            2px left border in layer colour (if entity item) or
            --color-text-primary (if mode item).
```

### Right context panel

Width: 260px. Position: fixed, right: 0, top: 0, height: 100vh.
Background: --color-surface. Left border: 1px solid --color-border.
Box-shadow: --shadow-panel.
z-index: 10 (above main content, below any modal).

Appears on: canvas detail, thesis detail.
Absent on: morning ritual, evening routing, inbox, observation list,
setup list, trade detail, review detail.

Entry transition: translateX(260px) → translateX(0), 200ms ease-out.
Exit transition: translateX(0) → translateX(260px), 150ms ease-in.

When panel is visible, main content right margin adjusts to 260px to prevent
content being obscured. Transition: margin-right 200ms ease-out.

Panel sections (canvas detail):
  Linked theses (navigable chips with status badges)
  Observation backlinks (compact log, read-only)
  Cross-currents (compact list, navigable)
  Version history (timestamps + diff summaries, collapsed by default)

Panel sections (thesis detail):
  Linked canvases (navigable chips)
  Linked setups (navigable chips with status badges)
  Decision points (compact, fired status shown inline)
  Protocol flags (any active protocol conditions for this thesis)

Each panel section:
  Section header: 10px --font-ui 500 uppercase letter-spaced
  --color-text-tertiary. Padding 14px 16px 8px.
  Content: 13px --font-ui --color-text-secondary.
  Padding: 0 16px 14px.
  Divider between sections: 1px --color-border-light.

---

## 6. Component Library

### 6.1 Status badges

Monochrome with colour accent. Consistent shape; colour is a secondary signal.

```
Structure:
  Container: inline-flex, align-items center, height 22px,
             padding: 0 8px 0 6px, border-radius: 4px.
  Background: --color-neutral-bg (uniform across all statuses).
  Left border: 2px solid [status colour] (see mapping below).
  Text: 11px --font-data, --color-text-primary.

Status → left border colour mapping:
  building      --color-neutral
  ready         --color-analytical
  active        --color-active
  invalidated   --color-danger
  archived      --color-text-tertiary
  watching      --color-neutral
  taken         --color-active
  passed        --color-text-secondary
  open          --color-neutral
  done          --color-active
  overdue       --color-danger
  cancelled     --color-text-tertiary
  type_1        --color-danger
  type_2        --color-warning
  type_3        --color-neutral
  technical     --color-analytical
  vol           --color-learning
  flow          --color-operational
```

### 6.2 Entity chips

Navigable references to linked entities. Used in the right context panel and
on entity detail pages for cross-references.

```
Structure:
  Container: inline-flex, align-items center, gap 6px,
             height 28px, padding: 0 10px 0 8px,
             border-radius: 4px, border: 1px solid --color-border,
             background: --color-surface, cursor: pointer.

  Left accent bar: 3px wide, height 14px, border-radius 1px,
                   in layer colour of the linked entity.

  Text: 12px --font-ui --color-text-primary.

  Status badge: appended inline if status is relevant.

Hover: background --color-recessed.
Transition: background 120ms ease.
```

### 6.3 Prose fields (editable)

Canvas narrative, thesis narrative, win condition, review analysis,
single_update, what_not_changing.

```
Read state:
  Font: --font-prose 16px --text-prose.
  Colour: --color-text-primary.
  Background: transparent.
  Border: none.
  Padding: 12px 0.
  Cursor: default.
  No edit affordance visible.

Hover state:
  Background: --color-surface.
  Border-radius: 4px.
  Padding: 12px.
  Cursor: text.
  Transition: background 150ms ease, padding 150ms ease.
  A small "edit" label appears top-right of the field in
  10px --font-ui --color-text-tertiary. Not a button —
  a passive signal.

Active/focus state:
  Background: --color-surface.
  Box-shadow: 0 0 0 2px --color-analytical (focus ring).
  Border-radius: 4px.
  Padding: 12px.
  Below the field: save button + discard link appear with
  a 150ms fade-in.

Save button: "Save" — standard primary button (see 6.5).
Discard: plain text link, 13px --font-ui --color-text-secondary.
         "Discard changes". No border, no background.

On save:
  Canvas narrative: requires diff_summary input (see canvas detail spec).
  Thesis narrative: fires last_updated touch via trigger.
  Review fields: no additional requirements.
```

### 6.4 Prose fields (append-only / read-only)

Observations (all fields), frozen trade fields (entry_rules_stated,
exit_rules_stated, thesis_snapshot), Phase 1 review fields after lock.

```
Read state:
  Font: --font-prose 16px --text-prose (for narrative content)
        or --font-data 14px (for structured data fields).
  Colour: --color-text-secondary (slightly muted to signal non-editable).
  Background: --color-recessed.
  Border-radius: 4px.
  Padding: 12px.
  No hover state change.
  No cursor change.

Lock indicator (for frozen trade fields):
  Small lock icon (SVG, 12px) + "Frozen at open" label in
  10px --font-ui --color-text-tertiary, positioned top-right
  of the field container.

Append-only indicator (for observation fields):
  Not shown on individual fields. Shown once at the top of
  the observation detail: "Observations cannot be edited after
  filing." — 12px --font-ui --color-text-tertiary, italic.
```

### 6.5 Buttons

```
Primary:
  Height: 36px. Padding: 0 16px. Border-radius: 4px.
  Background: --color-text-primary (#2C2A26).
  Text: 13px --font-ui 500, #FFFFFF.
  Border: none.
  Hover: background #1A1917 (slightly darker).
  Active: scale(0.98).
  Transition: background 120ms ease.

Secondary:
  Height: 36px. Padding: 0 14px. Border-radius: 4px.
  Background: transparent.
  Text: 13px --font-ui 500, --color-text-primary.
  Border: 1px solid --color-border.
  Hover: background --color-recessed.
  Active: scale(0.98).

Danger:
  Height: 36px. Padding: 0 14px. Border-radius: 4px.
  Background: transparent.
  Text: 13px --font-ui 500, --color-danger.
  Border: 1px solid --color-danger (at 50% opacity).
  Hover: background --color-danger-bg.

Ghost (text-only):
  No background, no border. Text 13px --font-ui
  --color-text-secondary. Hover: --color-text-primary.
  Used for: "Discard changes", cancel actions, secondary nav.

Disabled state (all variants):
  Opacity: 0.4. Cursor: not-allowed. No hover effect.

Gate-blocked state (thesis ready button when gates unmet):
  As disabled, but with a tooltip on hover listing unmet gates.
  The tooltip text comes from the gate failure messages in
  the thesis_ready_gate trigger.
```

### 6.6 Form inputs

```
Text input / Textarea:
  Height: 40px (textarea: auto, min-height 80px).
  Background: transparent (read) / --color-surface (focus).
  Border: none (at rest).
  Border-radius: 4px.
  Padding: 0 12px.
  Font: 14px --font-ui --color-text-primary.
  Placeholder: --color-text-tertiary.

  Focus state:
    Background: --color-surface.
    Box-shadow: 0 0 0 2px --color-analytical.
    Transition: box-shadow 150ms ease, background 150ms ease.

  Error state:
    Box-shadow: 0 0 0 2px --color-danger.
    Error message: 12px --font-ui --color-danger,
    displayed below the field with 4px margin-top.

Select:
  Same as text input. Custom arrow: SVG chevron in
  --color-text-secondary. No browser default appearance.

Single-word input (emotional_state field):
  Same styles. Max-width: 160px. The constraint is enforced
  at the DB level; the narrow width signals it visually.

```

### 6.7 Tables

```
Container: width 100%. Border-collapse: collapse.
Border: 1px solid --color-border (outer only — on the container,
not on individual cells).
Border-radius: 6px. Overflow: hidden.

Header row:
  Background: --color-recessed.
  Font: 11px --font-ui 500, letter-spacing 0.06em, uppercase,
        --color-text-secondary.
  Height: 36px. Padding: 0 14px.
  Border-bottom: 1px solid --color-border.

Data rows:
  Height: 44px. Padding: 10px 14px.
  Font: 13px. Mixed --font-ui (labels) and --font-data (values).
  Border-bottom: 1px solid --color-border-light.
  Last row: no border-bottom.

Row hover: background --color-recessed. Transition: 100ms ease.

Row states:
  Warning row (staleness ≥ 14d, passed setup psychological):
    Background: --color-warning-bg. No border change.
  Danger row (staleness ≥ 21d, overdue, kill condition fired):
    Background: --color-danger-bg. No border change.

Navigable row (click navigates to entity):
  Cursor: pointer. Hover as above.

Append-only table (trade_entries, trade_exits, option_legs):
  Existing rows: font-colour --color-text-secondary.
  No hover state on existing rows.
  "Add entry" affordance: a ghost row at the bottom with a
  "+" icon and "Add entry" text in --color-text-tertiary.
  On click: inline form row appears at the bottom.
```

### 6.8 Cards

```
Background: --color-surface.
Border: 1px solid --color-border.
Border-radius: 6px.
Box-shadow: --shadow-card.
Padding: 16px.
Margin-bottom: 16px.
```

### 6.9 Section headers (within entity detail pages)

```
Font: 10px --font-ui 500, letter-spacing 0.08em, uppercase.
Colour: --color-text-tertiary.
Margin: 24px 0 10px.
No background, no border, no decoration.
```

### 6.10 Inline form rows (for adding kill conditions, decision points, etc.)

No modal. Form appears inline within the relevant section.

```
Container: background --color-recessed, border-radius 4px,
           padding 12px, margin-top 8px,
           border: 1px solid --color-border-light.

Fields: standard inputs as per 6.6, laid out in a single row
        where fields are short, or stacked where fields are long.

Actions: Save (primary button, compact: height 32px, padding 0 12px)
         + Cancel (ghost button).

On save: container collapses with 200ms ease, new row appears
         in the table above with 150ms fade-in.
```

### 6.11 Protocol banners

Contextual banners that surface protocol conditions. Not toasts —
persistent until explicitly dismissed or resolved.

```
Container: full width of content area (not full page width),
           padding 10px 16px, border-radius 0 (spans the top
           of the content area below the breadcrumb).
           Border-bottom: 1px solid [variant border].

Protocol 1 (canvas updated, theses flagged):
  Background: --color-warning-bg.
  Border-bottom: 1px solid --color-warning (at 30% opacity).
  Text: 13px --font-ui --color-warning.
  Label: "Protocol 1 —" in 500 weight.
  Actions: "Review theses →" (ghost button in warning colour)
           + "Dismiss" (ghost button).

Protocol 2 (kill condition observable, write logic before acting):
  Background: --color-danger-bg.
  As above but in danger colour.
  No dismiss — only clears when hold-vs-redeploy paragraph
  has been filed.

Protocol 3 (decision point trigger met):
  Background: --color-analytical-bg.
  As above in analytical colour.
  No dismiss — clears when decision executed or deviation logged.

Protocol 4 (trade closed, review required):
  Background: --color-warning-bg.
  As Protocol 1. No dismiss — clears when Phase 1 filed.
```

### 6.12 Passed setup classification form

Appears inline when "Pass setup" is selected. Not a modal.

```
Container: as 6.10 (inline form row).

why_passing: textarea, label "Why are you passing this setup?"
             Prose font, minimum 3 lines. Required.

Classification: two large buttons side by side.
  "Analytical"    — Secondary button style but full-width within
  "Psychological"   its half of the container. Height 48px.
                    Each button has a one-line descriptor below
                    the label in 11px --font-ui --color-text-tertiary:
                    Analytical:    "The setup no longer meets your criteria."
                    Psychological: "You are avoiding this for non-analytical reasons."
  Selected state: background --color-recessed,
                  border: 1px solid --color-text-primary, weight 500.
```

---

## 7. Page Templates

### 7.1 Morning ritual

No right context panel. Full content width.

```
URL: /ritual/morning

Breadcrumb: none. Page header: "Morning ritual" in --text-xl,
+ current date in --font-data --text-sm --color-text-secondary.

Structure: three sections, stacked. Each section is a card (6.8).
Each completed section collapses to a single row (instrument name +
"complete" badge) with 250ms ease on height. Uncollapsed sections
are fully visible.

Section 1: Staleness sweep
  Header label: "Staleness" (section header style 6.9).
  Content: table (6.7) rendering stale_canvases + stale_theses +
  stale_invalidation_conditions views combined, sorted by days_stale
  descending. Danger row treatment for > 21d.
  Per-row action: single "Review" or "Confirm" button (ghost, compact)
  that navigates to the entity or marks confirmed.
  If no stale items: single row with "No staleness flags." in
  --color-text-tertiary. Section header shows green dot.

Section 2: Active position check
  Header label: "Positions" (section header style 6.9).
  Content: one row per active thesis. Columns: instrument, status badge,
  kill conditions (count of macro + technical, any fired shown in danger
  colour), last_updated (--font-data, amber if > 7d). Per-row: "All clear"
  button (marks reviewed) and "Flag" button (creates action item).
  Binary scan design — minimum interaction to clear.

Section 3: Action dispatch
  Header label: "Actions" (section header style 6.9).
  Content: table rendering overdue_actions view. Danger row for overdue.
  Per-row: "Done" button (marks action done, row fades out 150ms).
  Mark-done is optimistic: immediate UI update, server confirmation
  on response.

Below sections: "Ritual complete" confirmation row — appears when all
three sections are cleared. Green dot + "Ritual complete" in --font-ui
--color-active. No button — passive confirmation.
```

### 7.2 Evening routing

No right context panel. Full content width. Triage queue design.

```
URL: /ritual/evening

One inbox item fills the working area at a time. Previous items are
not visible — no list, no queue indicator beyond a count.

Item display:
  Raw capture text in --font-prose 16px, full readable width.
  Created timestamp in --font-data --text-xs --color-text-tertiary.

Route-as selection: four entity-type cards in a 2×2 grid.
  observation · action · setup · thesis-update
  Each card: height 64px, border 1px --color-border, border-radius 6px,
  background --color-surface. Entity name in --font-ui 14px 500.
  One-line descriptor in 11px --color-text-secondary.
  On selection: card background --color-recessed, border colour
  deepens to --color-text-primary. Relevant fields appear below
  with 200ms ease-in.

Fields (observation):
  instrument (text), timeframe (text), type (three-button toggle:
  technical / vol / flow — same style as passed setup classification),
  observation text (pre-filled with raw capture), linked_canvas
  (typeahead search of existing canvases).

Fields (action):
  instrument (text, optional), action text (pre-filled), due_date,
  linked_thesis (typeahead).

Fields (setup):
  instrument, setup_type, note (pre-filled), linked_thesis (typeahead).

Fields (thesis-update):
  Select thesis (typeahead), freetext note (routes to version history
  diff_summary).

Linking affordance (critical):
  The canvas/thesis typeahead uses a fuzzy search across all entities
  of the relevant type. Trigger: typing in the link field, minimum
  2 characters. Results appear as a dropdown of entity chips (6.2).
  The act of selecting a link is the primary value-creation moment
  of the evening routing session — the field should be visually
  prominent, not incidental.

File button: primary button, "File". On file: current item fades out
150ms, next item fades in 150ms. If inbox empty: "Inbox clear" state.
```

### 7.3 Canvas detail

Right context panel visible (see panel sections in layout spec).

```
URL: /canvas/{id}

Breadcrumb: "Canvas / {name}" — 13px --font-ui. Canvas in
--color-text-secondary. Name in --color-text-primary 500.

Entity identity bar (below breadcrumb):
  Left: 3px vertical bar in --color-analytical. Canvas name in
  --text-xl. Status badge (6.1) inline after name. Staleness
  indicator: if last_reviewed > 14d, show "last reviewed Xd ago"
  in --font-data --text-sm --color-warning.
  Right: "Confirm reviewed" primary button (updates last_reviewed,
  clears staleness flag).

Section: Narrative
  Section header (6.9): "Narrative"
  Prose field (6.3 — editable with subtle reveal).
  On save: diff_summary input appears inline below the field
  before the save can be committed. Label: "Summarise this update"
  in 12px --font-ui. Single text input. Required. On confirm:
  saves narrative + writes canvas_version_history row + fires
  Protocol 1 (surfaced as protocol banner above breadcrumb if
  linked theses exist).

Section: Cross-currents
  Section header: "Cross-currents"
  List: each cross-current as a row. Left: target canvas chip (6.2
  in analytical colour). Right: relationship_description in 13px
  --font-ui --color-text-secondary. Delete: small "×" ghost button
  on row hover.
  Add: ghost row at bottom "+ Add cross-current". On click: inline
  form (6.10) with canvas typeahead + relationship description field.

Section: Source documents
  Only renders if library_db_path is configured.
  Section header: "Source documents"
  Search input (full-width): placeholder "Search knowledge library…"
  300ms debounce, hits /library-search?q=. Results: compact list of
  document chips — title (--font-ui 13px), authors + year
  (--font-data 11px --color-text-secondary). Click to link with
  optional note inline.
  Linked documents list: each as a row. Title + authors/year.
  Note in --font-prose 13px --color-text-secondary if present.
  Unlink: "×" ghost button on hover. Linked_at timestamp in
  --font-data --text-xs.
  Null state: "No source documents linked." in --color-text-tertiary.

Section: Invalidation conditions
  Section header: "Invalidation conditions"
  Table (6.7): condition, type badge, probability badge, lead_time_days
  (--font-data), last_assessed (--font-data, danger colour if > 21d).
  Danger row treatment for > 21d last_assessed.
  Append: inline form at bottom of table.

(Right panel contains: observation backlinks, linked theses, version
history — see layout spec section 5.)
```

### 7.4 Thesis detail

Right context panel visible.

```
URL: /thesis/{id}

Entity identity bar:
  Left: 3px vertical bar in --color-analytical. Instrument in --text-xl.
  Status badge (6.1) inline. last_updated in --font-data --text-sm.
  Right: state transition buttons. Only valid next states rendered.
  building → "Mark ready" (disabled with gate tooltip if gates unmet).
  ready → "Open trade → Active" (primary).
  ready → "← Return to building" (secondary).
  active → "Fire kill condition" (danger button).
  invalidated → "Rebuild thesis" (secondary).

Gate-blocked state for "Mark ready":
  Button is disabled. On hover: tooltip listing unmet gates as a
  compact list. Gate messages sourced from thesis_ready_gate trigger
  error strings.

worst_case_dollar:
  Displayed prominently between the identity bar and the narrative
  section. Full width, centred or left-aligned.
  Label: "Worst case" in 10px --font-ui uppercase --color-text-tertiary.
  Value: --text-2xl --font-data --color-danger 600 weight.
  "$24,000" — never hidden, never in a table cell.

Section: Narrative (editable prose field 6.3)
Section: Win condition (editable prose field 6.3)

Section: Kill conditions
  Two subsections: Macro / Technical (separated by a light divider,
  not tabs).
  Table per subsection (6.7): condition, linked canvas/setup chip
  (navigable), fired_at (--font-data, blank if not fired, danger
  colour if fired). Fired rows: danger row treatment.
  Append: inline form per subsection.

Section: Decision points
  Table (6.7): trigger, decision, instrument (--font-data), size_pct
  (--font-data), fired_at (--font-data if fired, blank if not).
  If fired_at present: row is muted (--color-text-secondary).
  If deviation_note present: secondary row below the main row,
  indented, in --font-prose 13px --color-warning.
  Append: inline form.

(Right panel contains: linked canvases, linked setups, protocol
flags, version history.)
```

### 7.5 Observation capture form

Used both as a standalone form (/observation/new) and inline within
evening routing.

```
Type selection (prominent, before all other fields):
  Three cards in a row. Each: height 72px, border 1px --color-border,
  border-radius 6px.
  technical: "Technical" label + "Chart structure, price action,
              key levels" descriptor.
  vol:       "Vol" label + "IV, skew, options chain readings" descriptor.
  flow:      "Flow" label + "Order flow, unusual activity, positioning"
              descriptor.
  Selected: border-colour --color-analytical, background
  --color-analytical-bg.

Fields: instrument, timeframe, observation text (--font-prose,
min-height 100px), linked_canvas (typeahead), linked_thesis (typeahead,
optional).

Image upload: below observation text. "Attach chart or screenshot" —
dashed border zone, --color-border-light, --color-text-tertiary text.
Drag-drop or click. Thumbnail preview with caption input below.

Pre-file notice (above submit button):
  "Observations cannot be edited after filing."
  12px --font-ui --color-text-tertiary. Italic.
  Not a warning. A statement.

Submit: primary button "File observation".
```

### 7.6 Review — Phase 1

Triggered by trade close (Protocol 4). Accessed via /review/{id}.

```
Phase 1 fields are editable. After submission, all Phase 1 fields
become read-only (append-only treatment, 6.4). locked_at is displayed
as "Locked at {timestamp}" in --font-data --text-xs --color-text-tertiary.

Phase 2 section is visible but gated. Gated state:
  Background: --color-recessed. Reduced opacity: 0.5.
  Gate message: "Available after Zone 3 clearance (24h minimum)."
  Countdown: if < 24h elapsed, show "Unlocks in Xh Ym" in --font-data
  --text-sm --color-text-tertiary. Updates on page load, not real-time.
```

### 7.7 Review — Zone 3 clearance and Phase 2

```
Zone 3 clearance button:
  Not a checkbox. A full-width button, height 52px.
  Background: --color-recessed.
  Border: 1px solid --color-border.
  Border-radius: 6px.
  Text (--font-prose, 15px, centred):
    "I have processed the emotional content from this trade.
     Zone 3 is clear."
  On click: button is replaced by "Zone 3 cleared at {timestamp}"
  confirmation in --font-data --text-sm --color-active.
  The button must require a deliberate, considered click. No
  accidental activation. Consider: the button activates on mouseup,
  not mousedown, and shows a 500ms progress fill before firing
  (CSS transition on ::before pseudo-element). This is the one
  instance of motion used for psychological weight rather than
  information.

Phase 2 fields (visible after zone 3 clear):
  mistake_type: three large cards (not radio buttons). Full width,
  stacked. Each card: height auto, padding 16px.
    Type 1: "Process failure — I broke my rules."
    Type 2: "Model failure — my rules were followed, my model was wrong."
    Type 3: "Variance — correct process, losing outcome."
  Definition in 12px --font-ui --color-text-secondary below the label.
  Selected: border-colour --color-text-primary, background
  --color-recessed.

  analysis: editable prose field (6.3). Label matches mistake_type
  once selected (e.g. "Type 2 analysis").

  single_update: prose field. Label: "Single update — written as a
  rule, not a principle." Below label, in 11px --font-ui italic
  --color-text-tertiary: "Fails: 'Be more patient.'  Passes: 'When
  thesis invalidates on open position, write hold-vs-redeploy logic
  before acting.'"

  what_not_changing: prose field. Label: "What I am not changing."
```

---

## 8. Motion Specification

Functional motion only. Every transition is listed; nothing not on
this list is animated.

```
Right panel entry:     transform translateX(260px→0),  200ms ease-out
Right panel exit:      transform translateX(0→260px),  150ms ease-in
Main content margin:   margin-right (0→260px),         200ms ease-out
                       (synchronised with panel entry)

Status badge update:   opacity (1→0→1),                150ms ease
                       (for in-place status transitions, e.g. thesis
                       status change after button click)

Row mark-done:         opacity (1→0), height (44px→0), 150ms ease
                       (action row removal after marking done)

Inline form expand:    height (0→auto), opacity (0→1), 200ms ease-out
Inline form collapse:  height (auto→0), opacity (1→0), 200ms ease-in

Ritual section collapse: height (auto→44px),           250ms ease-in-out
                          (completed section collapses to summary row)

Protocol banner entry: height (0→auto), opacity (0→1), 200ms ease-out
Protocol banner exit:  height (auto→0), opacity (1→0), 150ms ease-in

Evening routing item:  opacity (1→0),                  150ms ease-in
                       followed by next item:
                       opacity (0→1),                  150ms ease-out

Zone 3 button fill:    ::before width (0→100%),        500ms linear
                       (the single instance of weighted motion)

Typeahead dropdown:    opacity (0→1), translateY(-4px→0), 120ms ease-out
```

No other elements animate. Page navigations are full HTMX swaps with
no transition. Form validation errors appear instantly (no animation).

---

## 9. HTMX and Alpine.js Patterns

### HTMX targets

```
hx-target="main-content"   Full main content area swap (navigation).
hx-target="closest .card"  In-place card refresh (mark done, confirm reviewed).
hx-target="closest tr"     Table row replacement (status updates).
hx-swap="afterbegin"       New rows in append-only tables (trade entries, exits).
hx-swap="outerHTML"        Status badge replacement after transition.
```

### Alpine.js scope

Alpine is used for:
- Inline form show/hide (x-show, x-transition)
- Typeahead dropdown state (x-data, x-model, x-show)
- Passed setup classification selection state
- Mistake type card selection state
- Zone 3 button progress fill timing

Alpine is not used for data fetching or state management beyond
local component UI state. All data operations go through HTMX.

### Optimistic updates

Mark action done: immediate row fade-out. On server error: row
reappears with inline error message. No other optimistic updates.

---

## 10. Accessibility

```
Minimum touch target:   44×44px (all interactive elements)
Minimum contrast:       4.5:1 for all body text against background
                        (#2C2A26 on #FAF8F3 = 13.4:1 — well above threshold)
                        (#7A7368 on #FAF8F3 = 4.6:1 — passes AA)
Focus ring:             0 0 0 2px --color-analytical on all interactive
                        elements. Never suppressed (no outline: none).
Keyboard navigation:    Tab order follows visual reading order.
                        Status transition buttons accessible by keyboard.
                        Morning ritual completable without mouse.
Screen reader:          All status badges have aria-label with full
                        status text (not just colour signal).
                        Append-only fields have aria-readonly="true".
                        Protocol banners have role="status".
                        Zone 3 button has descriptive aria-label.
Reduced motion:         @media (prefers-reduced-motion: reduce) —
                        all transitions set to 0ms duration except
                        Zone 3 button (retained as it is intentionally
                        weighted, but reduced to 200ms).
```

---

## 11. CSS Architecture

### File structure

```
static/
├── css/
│   ├── tokens.css         Custom properties (sections 2, 3, 4 of this spec).
│   ├── base.css           Reset, body, font-face declarations.
│   ├── layout.css         Shell, nav, main content, right panel.
│   ├── components.css     All component styles (sections 6.1–6.12).
│   ├── pages.css          Page-specific overrides (sections 7.1–7.7).
│   └── motion.css         All transition declarations (section 8).
```

### Font loading

```css
/* Load from Google Fonts — add to base.css <link> or @import */
/* Lora: weights 400, 500 — regular and medium only */
/* Inter: weights 400, 500 — regular and medium only */
/* Fira Code: weight 400 only */

@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400&family=Inter:wght@400;500&family=Fira+Code:wght@400&display=swap');
```

### Custom property declaration pattern

All tokens declared on :root. Semantic aliases reference base tokens.
No hardcoded hex values outside tokens.css.

```css
:root {
  --color-bg: #FAF8F3;
  /* ... all tokens from section 2 ... */

  --font-prose: 'Lora', Georgia, serif;
  --font-data:  'Fira Code', 'Courier New', monospace;
  --font-ui:    'Inter', system-ui, sans-serif;

  --space-1: 4px;
  /* ... all spacing from section 4 ... */

  --shadow-card:  0 1px 3px rgba(44, 42, 38, 0.07);
  --shadow-panel: 0 4px 16px rgba(44, 42, 38, 0.11);
  --shadow-modal: 0 8px 32px rgba(44, 42, 38, 0.16);
}
```

---

## 12. Implementation notes for Claude Code

The following are constraints and clarifications specific to the
HTMX + Jinja2 + FastAPI stack.

**No JavaScript framework.** Alpine.js handles component-local state
only. No React, no Vue, no Svelte.

**Jinja2 template structure:**
```
templates/
├── base.html              Shell, nav, main content slot.
├── components/
│   ├── badge.html         Status badge macro.
│   ├── chip.html          Entity chip macro.
│   ├── table.html         Table macros (header row, data row, etc.)
│   ├── prose_field.html   Editable and read-only prose field macros.
│   ├── inline_form.html   Inline form container macro.
│   └── protocol_banner.html  Protocol banner macro.
├── ritual/
│   ├── morning.html
│   └── evening.html
├── canvas/
│   ├── detail.html
│   └── panel.html         Right panel content (HTMX partial).
├── thesis/
│   ├── detail.html
│   └── panel.html
├── observation/
│   └── form.html
├── review/
│   ├── phase1.html
│   └── phase2.html
└── entities/
    └── list.html          Shared filtered entity list.
```

**HTMX partial responses:** Panel content is a separate template
rendered as an HTMX partial. The right panel's content is loaded
via hx-get on canvas/thesis page load, targeting the panel container.
This keeps the panel server-rendered and avoids client-side state.

**Typeahead implementation:** Use HTMX hx-trigger="input changed
delay:300ms" on the search input, targeting a dropdown container.
Server returns a rendered HTML partial of matching entity chips.
Alpine.js manages the open/closed state of the dropdown.

**Spacing iteration:** All spacing uses CSS custom properties from
tokens.css. To shift from comfortable to compact post-implementation:
update --space-3 through --space-6 values in tokens.css only. No
template changes required provided templates reference variables
not hardcoded values.

**Layer colour on nav items:** Applied via data attribute.
`data-layer="analytical"` on nav items and entity chips. CSS:
`[data-layer="analytical"] { --layer-color: var(--color-analytical); }`
The left border on active nav items and chips uses `--layer-color`.
This avoids per-class duplication.

**Status badge left border:** Applied via data attribute.
`data-status="active"`. CSS custom property maps status to border
colour. Same pattern as layer colour above.

---

*End of design specification v1.*
*Read alongside unified_build_spec_v2.md.*
*All decisions confirmed unless annotated otherwise.*
