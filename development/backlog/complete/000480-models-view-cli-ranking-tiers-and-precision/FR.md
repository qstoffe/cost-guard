# FR 000480 — Models page: correct CLI ranking, tiers and professional comparison UI

## Problem

The owner reports that Models is relatively compact but visibly badly formatted and inconsistent with CLI. The current browser renderer displays raw relative `Decimal` strings and numeric fields with no purpose-built multiplier/threshold formatter, while the CLI has aligned relative CCost tiers, compact K/M boundaries and explicit promotional/superseded styling. Models must be useful on its own, not a raw dump of projected server values.

## Required behavior

- Use CLI Normal/selectable-model and `--all-models` as separate reference views. Match their model membership, publisher/model column naming/order, exact default pricing rank, promotion markers, release information, availability warnings, tier/supersession notices and distinct optional native USD/M I/C/W/O price column. No invented availability, prices or release dates.
- Honor the existing independent priced-completed-prompt sample and exact server ranking. Default display order must match CLI; user-initiated sort uses canonical unrounded numeric keys and predictable tie/unknown behavior. Do not accidentally sort by visible `8.0x` strings.
- Format relative ratios as one-decimal `x` and maintain arrows/threshold direction/K/M like CLI. Retain **exact** native published USD reference rates in the full-catalog view when exact precision is meaningful. Clear table labels distinguish Relative CCost from billed USD.
- Make the comparison scannable through consistent spacing, numeric right alignment, restrained highlighting, clear selectable/full catalog control and responsive table scrolling rather than prose. Preserve CLI status/color semantics using FR000430 role formatting and FR000440 theme.
- Keep model comparisons informational: no server/pricing formula changes, no hidden model list pruning, no account/provider mutations.

## Acceptance

- Deterministic fixtures compare CLI and Web on model membership, default rank, tier thresholds, non-priced/unknown handling, promotional/superseded rendering, model availability fallback and full-price precision. Regression explicitly checks the missing `x` and excessive raw decimal observations.
- Actual browser Models/selectable/all views remain clear with long model names, multi-tier entries, dark/light, narrow screens and sorting/filtering. No unrelated Web/CLI side effects.

Relevant owners: `src/presentation/model_comparison.py`, `src/reports/models.py`, `src/web/assets/render.js`, `reports.js`, `app.css`, model comparison and Web view tests.