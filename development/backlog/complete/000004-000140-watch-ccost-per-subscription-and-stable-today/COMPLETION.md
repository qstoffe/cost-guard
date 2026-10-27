# FR 0140 completion — account-period CCost and stable Today

Implemented in Cost Guard v80.74 (2026-10-25).

## Delivered behavior

- Overall Watch uses `CCost · Watch: ... · Total today: ...` (overnight local date preserved), without a deleted-session suffix. README/reference retain the history caveat.
- First daily accounting can be Pending. Subsequent same-day enrichment/failure/recovery keeps the complete published value until atomic replacement, including downward corrections; midnight starts a new scope.
- Monthly/fixed account quotas show daily CCost before Remaining. Duration-bearing windows show independent CCost immediately after their quota percentage; unavailable percentages keep textual CCost. Existing responsive bars, units, resets, status and warnings remain.
- Normal account reports explain local-day, independent rolling-window and local calendar-month-to-date CCost. Watch has no monthly comparison row. Native reset windows and explicit not-started trailing lookbacks remain distinguishable.
- Canonical provider grouping never uses model publishers or merges Claude subscriptions with direct Anthropic API. Verified request accounts stay separate; one compatible account permits a provider estimate, multiple candidates remain account-unknown. Provider-only totals are explained once, never allocated repeatedly. CCost never proves billing, entitlement or native consumption.
- Shared deduplicated valuation uses cached prefix indexes. Watch enriches relevant daily/rolling history in finite batches, retains observed requests in process memory and performs no history I/O during quota-only publication. Idle date/window queries do not force timestamp-only redraws.

## Verification

Tested shipped source revision: `a97a6c8a13a845bda25624acd9fefbea27761373`.

- Full/local deterministic suite: **PASS**, 93 files, zero failures (including the registered period-accounting regressions).
- Working-tree product validator: **PASS**, zero failures; four design-budget warnings remain, with all hard caps unchanged and passing.
- Final read-only live Diagnostics: real OpenCode V2 service reachable; normal report succeeded in approximately 11.2 seconds with warm cache. Headless Watch initialized in approximately 1.14 seconds, completed daily enrichment around 1.86 seconds, and had no flowing-text overflow at 80/120/160 columns. These uncontrolled observations are not universal performance guarantees. The first cold month-history acquisition was substantially slower (approximately 86.8 seconds); subsequent report/Watch work reused cached analysis.
- Deterministic coverage includes first Pending/publication, repeated refresh holding, failure/recovery/correction, midnight/DST, deletion/restart retention, rolling overlap versus calendar month, equivalent report/Watch scopes, source-provider aliases, direct-API separation, account ambiguity, partial pricing, clone deduplication, ANSI/plain widths, missing percentages and unchanged-history quota reuse.

No paid live-model tests, credential mutations, shared-service stops, persistent billing ledger or product-release archive were introduced. Raw local Diagnostics stay outside this source bundle and are not published.

## Knowledge and dependencies

Architecture/source contracts updated through the guarded knowledge helper for the period index, acquisition, publication and tests; existing layer boundaries remain intact. Journal assessment: **no-update** — implementation contracts carry the reusable facts; uncontrolled live samples are not a durable benchmark.

The selected specification is preserved unchanged. No unfinished cross-FR dependency, attachment or unrelated user work is required for this delivery. Native maintenance count advances to four; fresh default identity reservations are preserved and retention prunes nothing. Independently authored FR 0150 remains pending, without changing this selected transaction. Prior account-switch work is preserved; this change does not reimplement it.
