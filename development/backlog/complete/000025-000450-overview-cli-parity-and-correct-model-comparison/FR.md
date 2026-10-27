# FR 000450 — Rebuild Overview around CLI Normal report and fix its model table

## User-observed defects

Web Overview is much more verbose and differently arranged than the compact CLI Normal report. Loose subscription/account copy overwhelms the page; some explanatory lines/notices appear at the wrong position or in undifferentiated colors. The owner reports incorrect ordering by Relative CCost and a badly formatted model comparison column (raw long floating/decimal values without `x`). This is a presentation/order defect to investigate even though FR000380's shared numerical comparison tests passed.

## Required behavior

- Use CLI's **Normal report** as the reference for Overview's section inventory, default ordering, labels, visible table columns, summaries, notices, account blocks and relative visual hierarchy. Keep one coherent top-level report rather than dumping all server DTO fields into descriptive paragraphs. Compact meaningful context/help; move advanced detail to the appropriate Accounts/Models pages or expandable details without silently losing important warnings.
- Model comparison must follow the CLI's default **exact reference ranking** (including tier/relative-cost rules and fallback sorting), not lexicographic/display-rounded order. On user-click sorting, sort by raw canonical numeric/string keys with stable unknown handling; restoring/defaulting must restore server/CLI order.
- Render Relative CCost with CLI's one-decimal multiplier `x` suffix, arrow/tier transition and compact threshold/operator (e.g. `8.0x → 16.0x (>200K)`) including optional promotion markers. Do not display arbitrary decimal tails. Full catalog native price precision belongs on Models/all.
- Render all other figures (CCost, percentages, quota figures, dollars, durations) with FR000430 formatting semantics. Place relevant section explanations/warnings with the same contextual meaning and relative order as the CLI, not one giant wall of text. Preserve distinctions between valuation and actual bills; running/partial/unknown never masquerade as exact zero.
- Apply the shared polished visual system from FR000440 without replicating terminal-black backgrounds or ANSI formatting.

## Acceptance

- Deterministic CLI Normal versus Web Overview view fixtures show the same data, table membership, relevant notes and row order under equivalent conditions. Tests explicitly assert `x`, one decimal, threshold K/M, correct default ranking, stable user sorting and unknown handling.
- Owner can recognize the CLI Normal layout immediately in a clean modern browser view, with dramatically less unsolicited prose and more readable account/metric groups. Narrow and dark/light browser screenshots are examined.
- No changes to analytical pricing, sample eligibility, quota refresh cadence, stored state, or unrelated CLI output.

Relevant owners: `src/web/assets/render.js`, `app.css`, `src/presentation/report.py`, `model_comparison.py`, `src/application/projection.py`; coordinate with FR000430/000440.