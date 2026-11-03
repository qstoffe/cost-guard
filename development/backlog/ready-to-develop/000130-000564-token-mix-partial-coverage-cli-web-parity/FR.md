# FR 000564 — Reconcile partial Token Mix coverage between CLI reports and Web Watch

## Evidence and decision

**Owner-requested follow-up from the 2026-11-03 post-delivery review.** Permanent identity **000564**, Ready priority **000130**, after FR000561, FR000562 and the separate deep-report follow-up FR000563.

Completed [FR000558 / PR #139](https://github.com/qstoffe/cost-guard/pull/139) added live per-prompt I/C/W/O Token Mix % to both Web Watch prompt tables. Its [completion](../../complete/000070-000558-web-watch-prompt-tables-live-token-mix/COMPLETION.md) and [journal](../../../journal/web/watch-prompt-tables.md) explicitly document a narrow Decision Delegate exception: **for a completed prompt with incomplete token categories, CLI may show numeric mix percentages while Web shows `N/A`**. A semantic discrepancy remains and was not claimed solved.

Relevant implementation: `src/reports/watch_capture.py::capture_rows` clears `token_mix_percent` when an observed entry lacks any `MIX_FIELDS` token category, so Web does not silently treat missing telemetry as known zero. The existing CLI completed prompt projection has a different coverage policy. The same underlying source evidence must not appear equally complete in one surface and unavailable in another without clearly defined semantics/provenance.

This is a genuine bounded follow-up, **not** a claim that FR000558's live streaming or fully-known 100/0/0/0 → 25/75/0/0 → 20/60/0/20 tests failed. No change is required to canonical raw token totals, prices, CCost, attempts, source capture frequency or model calls.

## Required outcome

Establish one well-defined and truthful contract for Token Mix numerator, denominator, rounding and data coverage across canonical per-prompt projections used by **CLI session reports and Web Watch**, including completed and still-running prompts.

- Inspect whether incomplete four-category counters produce a meaningful percentage of *known tokens* or an unjustified full-prompt percentage. Do not assume either `N/A` or existing CLI numbers are always right before proving the underlying coverage.
- If the share is not defensibly complete, present unknown/partial truth consistently instead of silently assuming missing = zero. If a partial-known share is useful, make its limited denominator/provenance explicit and consistent to users and tests. Make a documented, justified single policy; do not introduce a browser-only algorithm.
- Preserve correct calculation/rounding for fully observed Input, Cached input, Cache write and Output, child calls, multiple models, compaction, reasoning→Output, zero-token evidence, usage corrections and source generation freshness.
- Keep prompt CCost, Calls, Δ Ctx, native quota summaries, history ordering, terminal lifecycle and actual data unaffected. Do not broaden this into FR000561/562 UI changes or a provider telemetry acquisition change.

## Acceptance criteria

1. Build a **baseline-red** shared source/analysis fixture that reproduces completed partial-data divergence: same prompt identity and source data, numeric CLI mix versus Web `N/A`. Also cover fully known, zero, completely missing, multi-call partial, late correction/replacement and long-lived running capture.
2. Choose and document the canonical partial-coverage behavior with defensible denominator/provenance. Assert **CLI/Web agreement in meaning** on each fixture (including explicit partial/unknown labels if a visual difference remains intentional); no false complete percentages.
3. Preserve currently correct live update behavior, stale-SSE rejection/reconnect, terminal freeze and the CLI's existing fully-known formatting. No new browser math, extra catalog scan, provider polling or dropped calls.
4. Run focused projection/presentation/DOM tests plus the applicable Full/validation suite; provide before/after examples and real-source read-only evidence when feasible. Any unobserved natural live token-category transition remains explicitly unverified, not marked PASS.
5. Update existing Watch Token Mix documentation/journal and clearly close the exact FR000558 delegate-exception discrepancy; do not claim an older task retroactively failed or silently rely on another scope waiver.

This follow-up does not override the higher-priority Ready Web Watch changes FR000561/562, or the distinct historical-report task FR000563.
