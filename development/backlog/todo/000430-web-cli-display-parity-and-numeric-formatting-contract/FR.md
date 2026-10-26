# FR 000430 — Make CLI output the Web Beta display contract

## Problem and objective

The owner wants Web Beta to start as a **webified equivalent of the CLI**, not a competing dashboard: same report scopes, sections, tables, displayed columns, values, ordering, labels, precision, statuses, warnings and semantic emphasis for equivalent source/config/catalog/clock snapshots. The browser can use a different visual theme and native web interactions.

Code inspection already shows a concrete display-gap risk: `src/web/assets/render.js` uses `known(value) => String(value)` and concatenates `row.relative_cost` / tier levels as raw decimal strings. By contrast, CLI `src/presentation/model_comparison.py` uses one-decimal `x` multipliers and compact K/M threshold labels. Other cost/money/quota/percentage/duration fields similarly need an explicit formatting audit rather than assuming exported numeric strings are presentation-ready. **Do not change the underlying canonical numbers just to fix their display.**

## Required behavior

- Inventory the current CLI Normal/Overview, Watch, Sessions/list and detail, Models/selectable/all, Accounts, Date/Range and Token Mix output against Web views using *identical synthetic inputs and scopes*. Publish a compact field/section mapping and a list of intentional browser-only differences. CLI remains the information source of truth; existing numeric semantic tests do not prove visual/display parity.
- Establish one reusable, testable browser-facing display contract for CCost, relative multipliers/thresholds, USD, quota amounts/units, percentages, token counts, durations, timestamps and unknown/incomplete/provisional/status values. Reuse CLI-owned formatting semantics via safe server-provided display tokens or equivalent shared assertions, not duplicate business calculations in JavaScript. Preserve raw exact values separately for sorting, filtering and computation already decided by Python.
- Match CLI rounding, precision and presentation meaning (e.g. `1.0x`, `8.0x → 16.0x (>200K)`; `N/A` / `—` / Unknown where the CLI distinguishes them; appropriate fixed decimals for money), never raw unbounded Decimal/double output in user-visible cells. Do not lose valid catalog-native *exact* price precision in all-models reference-rate columns.
- Preserve the CLI's **ordering, grouping, placement of notices above/below the appropriate table**, sparsity of normal overview, and emphasis/color *roles* for running, partial, warnings, thresholds, new/promotional/superseded data. Web may map these roles to a different accessible palette; no information-bearing emphasis may vanish into default body text.
- For every view, retain current canonical missing/estimated/partial/cost-versus-billing semantics, exact sorting (not rounded string sort), independent normal samples and Watch scopes. No feature invention or expanded provider calls as part of formatting.

## Acceptance

- Golden semantic/display examples derived from the existing CLI renderers cover boundary values, deep decimals, negative/zero/missing values, tier transitions, warning roles, correct section placement and order. Web output matches CLI **display semantics**, while retaining native web sorting/paging.
- No visible `0.123456789...`-style accidental raw values or missing `x` suffixes in the comparison view; no silent truncation of intentionally exact native price references.
- The result is a documented baseline that individual page FRs 000450–000510 can use without asking the owner to report every mismatch. Keep app dependencies standard-library/no frontend build, privacy and security unchanged.

Relevant owners: `src/presentation/`, `src/numbers.py`, `src/application/projection.py`, `src/web/assets/render.js`, `reports.js`, `app.js`, and existing presentation/application/Web tests.

This FR is the shared **parity foundation**, not a complete redesign of all views.