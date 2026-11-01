# FR 000530 — Web-only AI reference CCost per active hour

## Outcome

Show what observed AI-assisted coding corresponds to in **reference cost per active execution hour**. Build on Cost Guard's canonical OpenCode CCost and overlap-safe execution duration; this is not actual provider billing, a consultant invoice or a claim about human hours saved.

This is a deliberately **low-priority Web feature** for a later, stabilized Web Beta. There is no new CLI report, command-line option or default CLI section. Per-model comparisons, model selectors and human salary/savings estimates are explicitly outside this first version.

## User experience

- A Web-only **Cost per Active Hour** view shows **Today**, **current local calendar month to date**, and **rolling 30 days** (the last 30 × 24 hours at observation time), with a brief per-session rate in the existing complete session Snapshot/Live detail.
- For each scope show reference **CCost**, **active execution duration**, and **CCost/hour** together with scope, observation time and clear complete/partial/provisional/unavailable state. Keep the presentation compact, accessible and consistent with the existing Web design, with links to sessions where useful.
- Use the existing FR000526 credits/reference-USD display semantics and FR000528 Web toggle. Label credits as `CCost/h` (or `credits/h`) and USD as `$/h`, with the agreed $ and two decimals. Keep Billed and native quotas distinct.
- A visible rate is computed with unrounded Decimal inputs as `CCost / (active milliseconds / 3,600,000)`; round only for display. Do not calculate valuation or the rate in JavaScript.

## Accurate time and cost semantics

1. **Active time is execution, not session age.** Reuse `src/analysis/duration.py` and established prompt/compaction source boundaries. Include attributable subagents, tool/test/Explore activity and verified background work, while excluding idle gaps, passive human time and unverified intervals. Never invent timing for incomplete records.
2. **No double counting.** Union overlapping execution intervals within a session; for period totals also union overlapping activity across different sessions. Simultaneously incurred distinct model requests still contribute their CCost once each. The metric is therefore reference spending per hour of *observed concurrent activity*, not the sum of agent-worker-hours.
3. **Correct periods.** Respect the configured timezone, local midnight/month boundary and DST. Clip proven execution intervals to the selected time window before unioning; never count a whole cross-midnight session in one day. The rolling window is exactly the trailing 30 × 24 hours, not a second calendar-month view. Reuse canonical deduplicated per-request period CCost accounting and explain its event-time allocation when a request spans a boundary; do not invent proportional token billing.
4. **Missing data is not zero.** Unknown or zero duration produces no hourly rate; incomplete/unpriceable CCost must not become an apparently exact rate. True priced zero CCost with positive known duration can yield zero. Running sessions may show a clearly provisional frozen/Live snapshot; source disconnection never proves completion. Deleted/pruned history cannot be recovered.
5. **Bounded, read-only processing.** Build the metric in shared Python analysis/application projections consumed by Web. Do not scan all history automatically on opening a page or repeatedly during normal Watch polling. Reuse bounded explicit capture/progress/cancel and dependency-aware cache where suitable. Do not add new provider requests, model calls, browser persistence, historical ledgers or OpenCode writes.

## Dependencies, priority and acceptance

- **Queue priority 001000 (low)**, intentionally leaving room for additional fixes/features before this work. Evaluate only after Web Beta UX/stability is satisfactory, particularly FR000529, and after FR000526/FR000528 establish display-unit consistency. This priority is not permission to promote Web out of Beta.
- Synthetic tests verify the formula, per-session and period totals, root/child and multi-session concurrency, request deduplication, compaction, tools, running/abort states, unknown pricing/duration, and zero denominators.
- Period tests cover month boundaries, DST, cross-period long-running work and the precise rolling-30-day edge; cost and duration scopes are documented and no invented precision is displayed.
- Browser tests verify Snapshot/Live/frozen and stale behavior, 360px/desktop layouts, keyboard access, route navigation, view-scoped capture/cancel and that account/Watch refreshes remain unaffected. Existing CLI output/arguments remain byte-for-byte functionally unchanged.

Relevant owners: `src/analysis/duration.py`, existing reports/period CCost boundaries, `src/application/`, `src/web/`, Web assets and established duration/history/Web tests.
