# FR 000659 — Models visual cleanup: true table parity, source heading layout and Effort picker

**Owner-approved Ready Feature Request, 2026-11-09.** Permanent identity **000659**, Ready priority **000940**, after the existing Ready items FR000657 (000920) and FR000658 (000930). Preserve the separately owner-promoted FR000651 (000001) as highest priority. **FR-only publication:** create this FR and advance `development/backlog/identity-state.json` highWatermark **658 → 659** in one documentation-only commit. Do not modify production CSS/JS, tests, versions or releases in this publication.

## Problem and desired visual result

The recent FR000656 Models-page changes delivered the requested separate **GitHub Reference Pricing** and **Coding Benchmark – Cost per Task** sections, but the resulting layout looks visibly inconsistent. Despite being on the **same Web page**, the lower benchmark table does **not** share the upper table's visual table skin; the source labels, View source hyperlinks, Refresh buttons and Last fetched/status text wrap and align inconsistently; and the Effort dropdown's checkbox options appear in a horizontal/vertical flow instead of a clean single-column menu.

The owner wants **one shared visual design system** for both sections, a tidy heading/source hierarchy, two matching control rows, a compact Settings-like **multiselect** effort picker, and the Solved percentage moved to the **left edge** of its expandable last column. This is a **presentation and minor filter-option sorting FR**, not another benchmark/data acquisition refactor.

### Layout blueprint — same structure for both sections

```text
GitHub Reference Pricing (GitHub Copilot · View source)
[Refresh price list]  Last fetched: YYYY-MM-DD HH:mm     ☐ Show all Copilot-priced models  ☑ Latest versions only
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Publisher  │ Model             │ Relative Price List Cost │ Release date                           │
│ ...        │ ...               │ ...                      │ ...                                    │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

       [clear vertical spacing; no parent panel/card around benchmark section]

Coding Benchmark – Cost per Task (Terminal-Bench 4.0 · Harbor Hub · View source)
[Refresh benchmark]   Last fetched: YYYY-MM-DD HH:mm     [Effort levels · All ▾]  ☐ Show all... ☑ Latest...
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Publisher │ Model      │ Effort │ Relative Task Cost │ Solved                               │
│ ...       │ ...        │ Max    │             65.4x  │ 78.2%  [remaining width stays empty]   │
│ ...       │ ...        │ High   │             25.7x  │ 71.3%  [remaining width stays empty]   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

Effort levels dropdown, opened:
┌──────────────────────┐
│ ☑ Max                │
│ ☑ Extra High         │
│ ☑ High               │
│ ☑ Medium             │
│ ☑ Low                │
│ ☑ None               │
│ ☑ Other effort       │
└──────────────────────┘
```

The above values and the Other effort example are **illustrative layout placeholders**, not source-backed benchmark results or a demand to invent effort levels. The actual options remain based on the source's distinct available efforts.

## A. Both headings: smaller parenthesized source and inline link

1. Keep the exact section headings **GitHub Reference Pricing** and **Coding Benchmark – Cost per Task**. Their visible `h2` typography, weight, margin and vertical spacing must share the same CSS class/structural contract. Do not introduce a big outer card around either section.
2. On **the same heading row**, immediately after the title (with a natural small gap), show a **muted, considerably smaller** parenthesized source reference:
   - `(GitHub Copilot · View source)` next to **GitHub Reference Pricing**;
   - `(Terminal-Bench 4.0 · Harbor Hub · View source)` next to **Coding Benchmark – Cost per Task**.
   The parentheses and internal source text all use the **same small font size**; only the real View source text is a hyperlink. Keep the title at its existing heading size and do not make its source reference look like a subtitle, separate toolbar, badge or button. Small source text may wrap as a unit / flow beneath the heading on narrow viewports without clipping, overlapping or creating misaligned indents.
3. Keep exact official external targets, unchanged from FR000656:
   - GitHub: https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing
   - Harbor: https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4
   Both links are keyboard-focusable and safe (`noopener noreferrer` when opening a new tab). Do not put View source in the Refresh control line as well.

## B. One matching horizontal toolbar underneath **each** heading

Under the heading/source line, both sections use the **same shared CSS layout and semantics**, not merely similar margins:

- **Left group**, in order: one standard **Refresh price list** / **Refresh benchmark** button; the matching **Last fetched: YYYY-MM-DD HH:mm** timestamp; then its concise current refresh/result status text when applicable. The button must be **the leftmost control** and must never interrupt the source label. Keep the already-correct, server-prepared Swedish-style last-successful-fetch date, and do not change the backend.
- **Right group**: the corresponding two native Copilot model checkbox filters, consistently styled, with `margin-left: auto` / an equivalent two-group grid so they remain aligned to the **right edge on ordinary desktop widths**. GitHub row contains just these two checkboxes. Benchmark row has its **Effort levels dropdown first**, followed by **Show all Copilot-priced models**, then **Latest versions only**. Retain all existing defaults and independent filter states.
- Both rows share button size/min-height, font size/weight, link-independent CSS, line height, status placement, horizontal/vertical gaps and responsive breakpoints. **No benchmark-only `flex-direction: column`**, left-indented label or arbitrary `flex: 0 1 auto` override that makes the lower toolbar fundamentally different. Do not split into a second status/refresh bar.
- **Responsive exception:** when the full row genuinely cannot fit, let the right group wrap **as a coherent group** onto a following line, and then wrap checkbox controls within that line as necessary. It is preferable to retain left group first and consistent baseline rather than squeeze/truncate labels or send the Refresh button into the middle. At e.g. 360px, avoid page-level horizontal overflow; the tables alone may scroll horizontally inside their table shell. Preserve touch minimum target sizes.
- Status updates must not shove the filters around unnecessarily or shift table layout on every Refresh; reserve sensible status room or wrap quietly. Keep refresh busy/disabled/error functionality and distinct source independence; do **not** turn this into a new acquisition/refresh feature.

## C. Same actual visual table styling in both model tables

**This is a direct parity requirement, not a vague "similar look" request.** The lower `.benchmark-scroll`/`.benchmark-table` currently has hand-written partial styling but is absent from the common table-shell/semantic-cell selector group that styles `.overview-models`/`.overview-model-table`. The two structures must use the **same design tokens and shared CSS primitives** for:

- table-scroll shell **border, radius, background, overflow/panning, and scrollbar styling** (a *small table border is wanted*, unlike the previously removed big parent group card);
- table header `th` font-size/weight, text color, background, button presentation and sort-arrow treatment;
- row/cell **padding, row height, font/line-height, background, hover/focus states**, internal bottom separators and vertical separators, and last-row rounding/border behavior;
- consistent selected/numeric/help-link styling without accidentally flattening the separate **GitHub Relative Price List Cost** monospace/aligned ratio tracks, source-based `New` highlighting, tooltip triggers or accessible sort controls.

Prefer **shared classes/combined selectors** for these common tokens and **small semantic overrides** for different column widths/alignments. For instance bring `.benchmark-scroll` under the common table-shell design and `.benchmark-table` under the common model-data-table cell styles. Do not copy-paste a second diverging table skin. Keep the intentional compact five-column benchmark widths and dynamic horizontal panning. Match the table background to the upper table in Classic, Web light and Web dark.

**Keep the benchmark unboxed at the section level:** the only visible border behind the benchmark is the normal **table-shell border and its internal grid**—no new enclosing large panel or tinted block.

## D. Effort dropdown: compact Settings look, strict one-column list and sorting

1. The current benchmark `details.effort-picker > summary` is styled as a plain ad-hoc control. Style the **closed Effort selector like the existing Settings select UI** (same border color, surface, focus/hover, chevron/shape and polished compact control appearance), **but scale it to the ordinary Models/Refresh button's approximate font and height** (`~.8rem` text and `~2rem` min-height on desktop; larger tap target when coarse pointer). Do **not** globally modify Settings. This remains a **multi-checkbox dropdown**, not a native one-choice select or a new independent toolbar.
2. The popup is a vertical, single-column checklist: **exactly one checkbox + one label per row**, stretching to the popover's content width. No flow across a horizontal row, no multi-column CSS, no horizontal wrap before progressing vertically, no duplicate visible list. Override the inherited `.model-filters label` inline-flex rule inside `.effort-options` and explicitly use `display: grid; grid-template-columns: minmax(0,1fr)` (or equivalent) on the option list, block/flex row items at **100% width**. Keep natural predictable spacing, clear checked state and sensible hover background, popup border/shadow, bounded height with **vertical scroll** when necessary, **no horizontal scroll**. Do not clip the popup behind the benchmark table shell.
3. Sort source-provided **distinct effort choices** by conceptual priority **highest effort first**, regardless of case/spelling:
   `Max` → `Extra High` (`xhigh`, `x-high`, `extra high` when provided) → `High` → `Medium` → `Low` → `None` / `Not specified`.
   - This is **presentation order only**. Preserve **exact underlying source values and selected-state keys**; normalization for sorting/display must not conflate unrelated source levels or invent missing ones.
   - Any nonstandard/unrecognized source effort values appear **after** those known levels, ordered **alphabetically, case-insensitive**, with deterministic ties.
   - `Not specified` appears **only when genuinely needed** for missing/null upstream effort; do not create it when no source rows need it. With other unknown values present, keep those alphabetical last after the six known priority classes. Do not hardcode the set of selectable options.
4. Preserve existing checkbox behavior: all available levels selected by default, selecting e.g. only High filters to actual published High rows, zero checked yields an honest empty state, refresh reconciles changed options without unexpectedly changing a custom subset, and the collapsed summary accurately reports All/None/subset. Keyboard focus, Space, Enter, Escape, outside-click, scrolling, screen-reader label and touch must work. Do not close the dropdown each time a checkbox toggles or interfere with other controls.

## E. Solved column alignment, no schema changes

The benchmark's last **Solved** column is intentionally the elastic `minmax(...,1fr)` column; **keep it elastic**. But **both its heading and all percentage values must be LEFT-aligned at the start of that column**, immediately after normal cell padding and visually adjacent to **Relative Task Cost**. Do not align the percentage to the far right of the entire table/viewport merely because the last column fills the remaining width.

- Keep **Relative Task Cost numeric values right-aligned** inside their compact column; that is already acceptable.
- Use a column-specific selector for column 5 that wins over current broad `.benchmark-table :is(th, td):nth-child(n+4) { text-align: right; }` specificity; don't weaken numeric alignment for column 4. Percentage sort uses existing raw solved values; this is an alignment-only requirement.
- Maintain the five columns **Publisher | Model | Effort | Relative Task Cost | Solved**, compact width for columns 1–4 and the existing matched GitHub names, dynamic effort dropdown, row-value tooltips and client/price provenance. The default **Solved descending** sort is already covered by **FR000658**; implement in coordination with that FR, not a competing default in this one.

## F. UI and implementation quality gates

Likely code owners: `src/web/assets/render.js::overviewModels()` for the first heading/source/toolbar, `src/web/assets/benchmark.js::View` for second heading/source/toolbar, effort options and the benchmark table, and `src/web/assets/app.css` for shared table shell/controls/heading/dropdown styles. Use the existing `src/web/assets/settings.js` select styling as a **visual reference only**, not a reason to change Settings behavior. If a narrow shared CSS helper is needed, add it consistently rather than creating two near-identical, separate style piles.

**Acceptance must be visually proven**, not just passing JS tests: capture **both full tables on the same actual browser page** so their CSS can be compared in one screenshot. Validate the computed style of corresponding `thead/th`, ordinary `tbody/td`, table shell, refresh button, source link and status in the two sections. Prefer assertions of the shared design tokens/layout and computed styles to brittle pixel-exact screenshots.

1. Both section headings look the same; next to each title is only its correctly sized parenthesized **source name + View source** hyperlink. No View source text in the refresh toolbar and no giant parent panel.
2. Refresh buttons visibly align on the left with Last fetched and status after them. Both sections share the same one-row desktop layout; filter controls are aligned right and wrap responsibly on narrow screens. No Refresh button stranded mid-sentence or unexpected vertical offsets.
3. The two tables **share the same visual skin**: matching shell border/background/radius, header style, cell padding/font/row dividers and proper hover states in Classic and Web light/dark. Neither loses functional independent sorting, tooltips, accurate numbers, pricing/cached-source behavior or horizontal scroll.
4. Effort dropdown closed style resembles Settings select at **compact button height/font**; opened list is **one vertical column** with one checkbox/label per row. Source options follow Max → Extra High → High → Medium → Low → None/Not specified → alphabetical extras, with missing options omitted. All/High-only/none and refreshed choices work and retain user state.
5. Solved header and percentages are **left-aligned at the beginning of their elastic final track** while Relative Task Cost stays right-aligned. No floating percentage at the far-right page edge.
6. Real browser mouse/keyboard/touch and 360/768/1366/1920px widths plus 125–150% text zoom: popup fits/scrolls, control groups wrap cleanly, source parentheses remain legible, table scroll is internal, focus/hover/selection is intact. No page-level horizontal overflow or unintended vertical scroll jumping.
7. No new model API calls, price recalculation, filter semantics, benchmark relative-cost denominator change, data contract, model matching, settings redesign, release gate or unrelated product refactor. Update narrowly relevant UI tests, source docs and visual snapshots only as part of implementation.

**Reference layout prepared for owner review:** both headings contain their small source/link in parentheses, below each heading is a left-hand Refresh+Last fetched group and right-hand filters, and both grids use the same table skin. Any illustrative numbers in review mockups must not be treated as real source data.
