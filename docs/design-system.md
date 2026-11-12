# I-ITSM design system

Group 67 · CS F213 OOP project. Written 2026-11-12. Owner: Anirudh (frontend), reviewed by Amith.

There is no Figma file for this project, so this document is the source of truth. Build to these
numbers. If something is not specified here, ask in the group before inventing it.

## The look we are going for

An operations console, not a product landing page. Think airline ops board, trading terminal, a
hospital triage screen. Dense, flat, high contrast, information first. The person using this is an
overworked technician with 14 open tickets, not a visitor being sold something.

Three decisions define the whole thing:

1. **Colour means status and nothing else.** The interface chrome is black, white and grey. The only
   saturated colour on screen is a priority, an SLA state or a destructive action. If something is
   red, it is late. If a screen has colour in five places, five things are wrong.
2. **Borders, not shadows.** Separation comes from 1px hairlines and background steps. Two elements
   in the entire app are allowed to float.
3. **Machine data is set in mono.** Incident IDs, timestamps, durations, counts and SLA countdowns
   are IBM Plex Mono with tabular numerals. Prose is IBM Plex Sans. This single rule does more for
   making the app look like real infrastructure than anything else in this file.

## Things that make a UI look generated, banned here

Listed so nobody wastes a day building one of them.

- Purple or indigo gradients. Any gradient.
- A centered hero with a big headline and two buttons, on an internal tool.
- Four identical stat cards in a row, each with a coloured icon in a circle.
- Glassmorphism, backdrop blur, translucent panels.
- Large radius everywhere (12px, 16px, "rounded-2xl"). Ours is 4.
- A shadow on every card.
- Emoji as icons.
- Pastel badge pills in six different hues on the same screen.
- Centered body text, or a 1200px wide page with everything centered inside 700px.
- Inter. It is the default font of generated UI. We use Plex.
- "Welcome back!" as a page heading.
- Em dashes in copy. Period and a new sentence, or a comma.

## Colour

Components use semantic tokens. Primitives are the raw values behind them. No raw hex in a
`section-*.css` file.

### Chrome

| Semantic | Primitive | Hex | CSS variable |
|---|---|---|---|
| text/primary | ink-900 | `#16181D` | `--c-text` |
| text/secondary | grey-600 | `#5C6370` | `--c-text-2` |
| text/muted (labels, meta) | grey-500 | `#767E8B` | `--c-text-3` |
| text/disabled | grey-400 | `#9AA1AC` | `--c-text-off` |
| text/inverse | white | `#FFFFFF` | `--c-text-inv` |
| bg/app | paper-50 | `#F7F8F9` | `--c-bg` |
| bg/surface | white | `#FFFFFF` | `--c-surface` |
| bg/raised (table head, rail) | paper-100 | `#EFF1F3` | `--c-surface-2` |
| bg/inverse (primary button, nav rail) | ink-900 | `#16181D` | `--c-inverse` |
| bg/hover (row, menu item) | paper-100 | `#EFF1F3` | `--c-hover` |
| border/hairline | line-200 | `#E3E6EA` | `--c-line` |
| border/strong (inputs, focus ring base) | grey-300 | `#C3C8D0` | `--c-line-2` |
| focus ring | focus-500 | `#2B6CB0` | `--c-focus` |

### Status

These are the only saturated colours in the app. Each has a text value and a 8% tint for badge
backgrounds. They are deliberately desaturated, closer to print than to a default framework palette.

| Semantic | Hex | Tint | Used for |
|---|---|---|---|
| priority/P1 critical | `#C1352B` | `#FBEEEC` | P1 badge, breached SLA, destructive confirm |
| priority/P2 high | `#B4690E` | `#FCF2E3` | P2 badge, SLA at risk |
| priority/P3 medium | `#1F5FA8` | `#EAF1F9` | P3 badge, informational |
| priority/P4 low | `#767E8B` | `#EFF1F3` | P4 badge, no-op states |
| state/ok | `#1E7A50` | `#E9F4EE` | Resolved, closed, SLA on track |
| state/open | `#16181D` | `#EFF1F3` | Open, assigned, in progress |

Rules for status colour:

- A priority colour appears only on a priority badge, a priority filter chip, and the 3px left edge
  of a P1 row. Nowhere else.
- Never colour a whole row background. The 3px left edge is the only row-level signal, and only P1
  gets it.
- Resolved and closed are green text on a tint, not a green row, not a green checkmark circle.
- Status is never communicated by colour alone. Every badge carries a word. P1 reads `P1 CRITICAL`.

## Type

IBM Plex Sans (400, 500, 600) and IBM Plex Mono (400, 500). Load only those six faces from Google
Fonts, with `display=swap`. IBM designed Plex for enterprise systems interfaces, which is also the
answer when the evaluator asks why this font.

Size / line height / weight / tracking.

| Style | Desktop (1440) | Mobile (393) | Used for | Family |
|---|---|---|---|---|
| Page-Title | 22 / 28 · 600 · -1% | 20 / 26 · 600 · -1% | One per screen, in the content header | Sans |
| Section | 15 / 20 · 600 · 0 | 15 / 20 · 600 · 0 | Panel headings, fieldset legends | Sans |
| Body | 14 / 21 · 400 · 0 | 14 / 21 · 400 · 0 | Paragraphs, descriptions, notes | Sans |
| Body-Strong | 14 / 21 · 500 · 0 | 14 / 21 · 500 · 0 | Incident titles in a table | Sans |
| Small | 13 / 18 · 400 · 0 | 13 / 18 · 400 · 0 | Table cells, secondary copy | Sans |
| Label | 12 / 16 · 500 · 0 | 12 / 16 · 500 · 0 | Form labels, above the field | Sans |
| Meta | 12 / 16 · 400 · 0 | 12 / 16 · 400 · 0 | Timestamps, author lines, counts | Mono |
| Caption | 11 / 15 · 400 · +2% | 11 / 15 · 400 · +2% | Help text, footnotes | Sans |
| Badge | 11 / 14 · 500 · +6% | 11 / 14 · 500 · +6% | Status badges, uppercase | Mono |
| Column-Head | 11 / 14 · 500 · +8% | 11 / 14 · 500 · +8% | Table headers, uppercase, text/muted | Sans |
| ID | 13 / 18 · 500 · 0 | 13 / 18 · 500 · 0 | `INC-1024`, `EMP007`, `T205` | Mono |
| Metric | 28 / 32 · 500 · -1% | 24 / 28 · 500 · -1% | The number in a stat block | Mono |
| Countdown | 15 / 20 · 500 · 0 | 15 / 20 · 500 · 0 | SLA time remaining | Mono |

Everything mono gets `font-variant-numeric: tabular-nums`. Without it the countdowns jitter as they
tick and it looks amateur.

Nothing on screen is larger than 28px. There is no display type in this app.

## Space

8px base. Only these values exist. If you need 13, you need 12 or 16.

| Token | px | | Token | px |
|---|---|---|---|---|
| space-0 | 0 | | space-5 | 20 |
| space-1 | 4 | | space-6 | 24 |
| space-2 | 8 | | space-8 | 32 |
| space-3 | 12 | | space-10 | 40 |
| space-4 | 16 | | space-12 | 48 |

Fixed measurements:

| Thing | Desktop | Mobile |
|---|---|---|
| Nav rail width | 220 | full width top bar |
| Top bar height | 52 | 52 |
| Page rail (side padding) | 24 | 16 |
| Table row height | 36 | 44 |
| Table header height | 32 | 32 |
| Control height (input, select, button) | 32 | 40 |
| Control height, large (primary form submit) | 36 | 44 |
| Form column max width | 560 | full |
| Reading column max width | 720 | full |
| Panel padding | 20 | 16 |
| Gap between panels | 16 | 16 |

Tables are full bleed to the page rail. They are the point of the app, do not put them in a 720px
centered column.

## Radius, elevation, grid

- **Radius:** 4 is the default (buttons, inputs, panels, badges). 2 for the SLA bar and chips. 0 for
  table cells and the nav rail. Nothing is a pill. Nothing is a circle except the avatar initial.
- **Elevation:** two allowed. Dropdown menus and modals get `0 4px 16px rgba(22,24,29,.12)` with a
  1px hairline. Everything else is flat with a hairline. No hover shadows.
- **Focus:** `0 0 0 2px #FFFFFF, 0 0 0 4px var(--c-focus)` on every interactive element. Never
  `outline: none` without a replacement. This gets checked.
- **Grid:** Desktop 1440: 220 rail + 24 page rail, 12 columns, 16 gutter. Mobile 393: 16 rail, 4
  columns, 16 gutter. Breakpoint at 900. Below 900 the nav rail becomes a top bar and tables become
  stacked rows.

## Bootstrap

Bootstrap 5 is already linked in the templates. Keep it for reboot and the grid. Do not use its
look.

- Allowed: `container-fluid`, `row`, `col-*`, `d-*`, `gap-*`, the reboot.
- Banned: `btn btn-primary`, `card`, `badge bg-*`, `alert`, `shadow-*`, `rounded-pill`, `navbar`,
  `table-striped`, `form-control` as-is.
- Override Bootstrap's CSS variables in `tokens.css`, do not fight it with `!important`.

Default Bootstrap blue on a button is as much of a tell as a purple gradient. Our primary button is
black.

## Components

Build each of these once in `static/css/components.css`, then never restyle them per page.

- **Button.** Height 32, padding 0 12, radius 4, Label type, 6px gap before an icon.
  Primary = ink-900 fill, white text. Secondary = white fill, 1px border/strong, text/primary.
  Ghost = no fill, no border, text/secondary, hover gets bg/hover.
  Danger = white fill, 1px P1 border, P1 text. Fill only turns red on the confirm step inside a modal.
  One primary button per screen. If you think you need two, one of them is secondary.
- **Input / select / textarea.** Height 32 (textarea min 80), 1px border/strong, radius 4, padding
  0 10, Body type. Label sits above at Label type, 4px gap. Help text below at Caption, text/muted.
  Error state: P1 border, message below in P1 at Caption, with the field name in it.
- **Status badge.** Inline block, height 20, padding 0 6, radius 4, Badge type, uppercase, tint
  background, status text colour, 1px border of the status colour at 20% alpha. Two words max.
- **Priority badge.** Same shell, always reads `P1 CRITICAL`, `P2 HIGH`, `P3 MEDIUM`, `P4 LOW`.
- **Table.** Header row bg/raised, Column-Head type, 1px hairline under it. Rows 36 tall, 1px
  hairline between, hover bg/hover, no striping. Text left, numbers and durations right, nothing
  centered. ID column first in Mono, 110 wide. Title column takes the remaining width and truncates
  with ellipsis. Sortable headers get a 10px caret. P1 rows get a 3px P1 left edge.
- **SLA meter.** 4px tall, 2px radius, full width of its cell, track line-200, fill is state/ok
  under 75% elapsed, P2 from 75 to 100, P1 over 100. Countdown in Mono beside it reading `2h 14m`
  or `-0h 42m` when breached. Never a donut, never a percentage ring.
- **Stat block.** Not a card. Label in Column-Head above, Metric below, optional delta in Meta. Four
  of them sit in a row separated by vertical hairlines, inside one bordered panel. No icons, no
  individual boxes, no colour.
- **Activity timeline.** The audit trail, on the incident detail page. One row per event. Left: time
  in Meta mono, 64 wide, right aligned. Then a 1px vertical rule with a 5px square node on it.
  Then actor and action in Small, state change rendered as `OPEN -> ASSIGNED` in Mono. No avatars,
  no bubbles, no cards. This should read like a log file that has been typeset.
- **Filter bar.** One row above a table, 40 tall, hairline below. Search input 240 wide on the left,
  then select controls, then a Ghost "Clear" that only appears when a filter is set. Active filters
  show as chips under the bar with an x.
- **Empty state.** Every table and list has one. Left aligned inside the panel, 32px padding. One
  line of Body text saying what would be here, one secondary button with the action. No illustration,
  no icon, no "Oops!".
- **Toast.** Bottom left, 320 wide, white, hairline, one of the two allowed shadows, 4s auto
  dismiss. Body text plus an optional Ghost action. Status colour appears only as a 3px left edge.
- **Modal.** 480 wide, radius 4, 20px padding. Title in Section type, body in Body, buttons bottom
  right with the secondary on the left. Destructive confirms require typing nothing, but the primary
  is Danger and is not autofocused.
- **Side sheet.** 420 wide, slides from the right, used for incident quick view from a table. Same
  internals as the detail page, nothing new to style.
- **Nav rail.** ink-900, 220 wide. Items 32 tall, 12px padding, Small type at 72% white, active item
  gets full white text and a 2px white left edge. Group labels in Column-Head at 48% white. The
  role name sits at the bottom above the user block, not in a badge.

## Screens

Section order per screen. Anirudh builds these in this order, see the README for the rest of the split.

### Sign in, sign up

The only centered screen in the app. 360 wide card on bg/app, white surface, hairline, no shadow,
32px padding. Wordmark in Section type at the top left of the card, not centered, not a logo image.
Fields stacked, full width, 36 tall. Primary button full width. One line below linking to the other
page. Errors appear above the fields in a P1 tinted strip, not as a toast.

### Employee: my incidents (landing after sign in)

1. Top bar: breadcrumb `Incidents`, search, bell, user.
2. Page header: Page-Title "My incidents", primary button "Report an incident" on the right.
3. Stat row: Open, Awaiting my input, Resolved this month. Three blocks, one panel.
4. Filter bar: search, status select, priority select.
5. Table: ID, Title, Service, Priority, Status, SLA, Updated. Row click opens the side sheet.
6. Empty state: "You have not reported any incidents." plus the report button.

### Employee: report an incident

Single 560 column, no stepper, no wizard. Fields in this order: Title, Description, Service,
Category, Impact, Urgency, Affected users. Under the last field, a read only panel showing the
priority the system computed, updating live as impact, urgency and service change. Label it
"Calculated priority" with the inputs listed beneath in Meta, for example
`impact HIGH x urgency HIGH x criticality 5`. That panel is the single best thing in this app for the
demo, it makes the strategy pattern visible. Duplicate warnings appear directly above the submit
button as a P2 tinted strip listing up to three similar incidents with their IDs.

### Employee: incident detail

Two columns, 1fr and 320. Left: title, badges, description, resolution panel when resolved, feedback
form when resolved, then the activity timeline. Right: a definition list of fields (reporter,
service, category, priority, assigned technician, created, SLA), then the comment composer. On mobile
the right column moves above the timeline.

### Technician: queue

Same shell as the employee table, different columns and default sort. Columns: ID, Title, Priority,
Service, Reporter, SLA, Status, Age. Default sort priority then SLA remaining. Tabs above the filter
bar: Assigned to me, Unassigned, All. Bulk acknowledge via row checkboxes, the action bar replaces
the filter bar when anything is selected.

### Technician: work view

The split screen where the job gets done. Left 1fr: incident facts, description, attachments,
activity timeline. Right 360, sticky: the action panel. Current status at the top, then only the
buttons that the state machine allows right now, stacked and full width, with the reason the others
are missing shown in Caption. A technician never sees a disabled button, they see fewer buttons.
Below that, SLA meter, the suggested resolutions from similar incidents, and workload.

### Admin: operations overview

1. Stat row: Total, Open, P1 open, Resolved, SLA violations. Five blocks, one panel, hairline
   separated.
2. Two panels side by side: Technician workload (table, name, active, resolved 7d, skills) and
   Service analysis (table, service, incidents, criticality, open).
3. SLA violations panel: the breached and at-risk list, P1 first.
4. Recent activity: the last 20 audit entries using the timeline component.

No charts in v1. If there is time at the end, one chart, a bar chart of incidents by category, drawn
in inline SVG with the status palette. Not a pie chart, not a donut, not a gradient area chart.

### Admin: settings

Plain stacked panels, one per concern: Assignment strategy (radio list of the strategies, with the
active one and a one line description of each), SLA policies (editable table), Categories, Services,
Users. The assignment strategy radio list is worth building properly, it is the strategy pattern made
clickable and the evaluator will ask about it.

## Copy rules

- Sentence case everywhere. Not Title Case, not ALL CAPS except badges and column heads.
- Buttons name the verb and the object: "Assign technician", "Resolve incident", "Add note". Never
  "Submit", "OK", "Continue".
- Time is absolute with relative as secondary: `14:32, 12 Nov` then `2h ago` in text/muted. Never
  relative alone, a technician needs the real time.
- Durations are `2h 14m`, not `2.23 hours`.
- IDs always carry their prefix: `INC-1024`, `EMP007`, `T205`.
- Errors say what happened and what to do. "Cannot close an incident that is not resolved. Resolve it
  first." Not "Invalid state transition" and not "Something went wrong".
- No exclamation marks. No "Oops". No "Great!". Nobody is happy to be here, there is an outage.
- No em dashes, ever. Period and a new sentence, or a comma.

## Rules enforced in review

A PR that breaks one of these gets sent back, even if it works.

1. Colour is status only. Chrome is ink, grey, white.
2. No gradients. No glass. No blur. No decorative illustration.
3. Two shadows exist, on dropdowns and modals. Nothing else floats.
4. Radius is 4, or 2 on bars and chips. Nothing is a pill.
5. IDs, times, durations, counts and metrics are Mono with tabular numerals.
6. Numbers right aligned, text left aligned, nothing centered in a table.
7. Every list and table has an empty state with an action.
8. Icons are 16px stroke SVG from one set, drawn in currentColor. No emoji.
9. Every interactive element has a visible focus ring.
10. One primary button per screen.
11. Status is never colour alone, always colour plus a word.
12. No hardcoded hex, px font size or ad hoc gap. Tokens only.
13. Contrast: body text passes 4.5:1, badge text on its tint passes 4.5:1. Check the three you
    invent, do not assume.
14. Every screen gets checked at 393 and 1440 before the PR, screenshots of both in the PR.

## Mobile

Scoped deliberately rather than universally, because mobile is not in the rubric and the deadline is
real.

**Responsive, and tested at 393:** sign in, sign up, my incidents, report an incident, incident
detail. That is the employee's whole journey, and the employee is the role that actually files a
ticket from a phone while standing in front of a broken printer.

**Target 1024 and up:** the technician queue and every administrator screen. They work at tablet
width and are usable on a phone, but the column sets and the side by side panels are built for a
desk. Say so in the report as a scoping decision rather than leaving it to be found.

What that means in the build:

1. **Tables become stacked rows below 900.** `.table-wrap` hides and `.rows` shows. Each incident is
   a 72px block: line 1 is the reference in mono on the left and the priority badge on the right,
   line 2 is the title in Body-Strong on one line, line 3 is the status badge plus service plus the
   SLA meter. The whole block is the tap target. Implemented once in the `incident_table` macro, so
   every screen that lists incidents gets it.
2. **Inputs go to 16px below 900.** Anything smaller makes iOS Safari zoom the page on focus, which
   throws the layout out every time somebody taps a field. This is the one place the type scale is
   overridden by viewport.
3. **The nav rail becomes a horizontally scrolling top bar**, not a hamburger overlay. Fewer taps,
   no overlay state to manage.
4. **Row height goes 36 to 44 and control height 32 to 40**, which is the 44pt touch minimum.
5. **Sticky elements use `100dvh`, never `100vh`**, or mobile browser chrome clips them.
6. The two column detail grid collapses at 1199, one breakpoint above the main one, because 320px of
   facts plus a table does not fit on a tablet either.

## Open questions

- Dark mode: out of scope for v1. The nav rail being ink already gives the screenshots contrast.
- Icon set: pick one and commit, Lucide or Phosphor, download the 12 we need as SVG snippets rather
  than loading a font or a CDN.
- The technician work view on mobile: currently it stacks, which means scrolling past the
  description and the timeline to reach the action panel. A sticky bottom action bar would fix it.
  Not built, because the technician screens are scoped to 1024 and up.
- Google Fonts is loaded with a render blocking `<link>`. If the demo venue has no internet the page
  waits for the request to time out before painting. The font stack falls back to system sans, so
  nothing breaks, but consider recording the video on a known connection.
