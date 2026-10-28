# FR 000521 completion

## Outcome

Implemented in Cost Guard v80.105: model-specific, prompt-weighted Relative CCost with verified-publisher/global fallback, shared tier-warning mixes and a second historical publisher Token Mix table in CLI and Web Beta. Comparison evidence is immutable shared report/application data, with help, tooltips and collapsed mobile-accessible provenance; JavaScript performs no pricing/mix calculation.

Candidate source: [b788aa556cc12a50fc2909968fc7fdea19e1bebf](https://github.com/qstoffe/cost-guard/commit/b788aa556cc12a50fc2909968fc7fdea19e1bebf). Original FR bytes are unchanged. Native delivery receipt owns verified merge truth; this document does not invent a merge SHA.

## Design and exclusions

- Prefer latest-100 exact-model evidence even outside the global latest-100 sample; count prompts, not calls. Blend normalized pooled fractions by prompt counts, not concatenated raw token pools.
- Catalog manufacturer metadata/aliases determine publishers, never request/provider/account routes. Historical publisher rows use the same shown requests and original per-request model/tier valuations; prompt counts are not additive.
- Compact per-root cache plus membership/revision-validated stable-root aggregates reuse canonical analysis and release deep snapshots. Active/unstable roots are not stable cache proofs. No second analyzer, private ledger, external dependency, model call or new provider endpoint.
- Dashboard/Watch usage mixes, billing/accounts/quotas, source read-only behavior, explicit history jobs/cancellation, finite-result bounds and Web Beta status are preserved. No launcher work, native UI automation, ZIP or GitHub Release.
- Architecture report contract updated through guarded source/hash edits; journal **no-update**: reproducible performance/verification evidence is linked below rather than duplicated as a session log.

## Verification and performance

- Full repository suite: **1,389 tests passed, zero skips/failures/errors, 114 files**, 57.2 seconds. Working-tree validator passed, with design warnings only and no raised hard caps.
- New deterministic tests cover weights/counts, mixed publisher requests, deduplication, telemetry/identity, older history, revision/deletion reuse, independent tier/reference expectations and shared publisher totals/filtering. Existing application/Web/CLI, context, account and source suites pass; Node DOM assertions cover both historical tables and model evidence.
- Real installation All Models report: **exit 0**, 15.986 seconds. Earlier timeout is not a PASS or a completed cold timing. No shared OpenCode service was stopped.
- Synthetic 1,000 roots / 20,000 prompts: Normal base→candidate cold **0.0708→30.7186 s**, warm **0.0216→0.0635 s**; All Models cold **0.0690→32.2399 s**, warm **0.0237→0.0454 s**. Exact sparse-model coverage requires cold hydration of 1,000 instead of 5 roots. Stable aggregate reuse repaired the initial ~2.1-second warm rebuild. Warm repeats hydrate no additional roots. This material cold cost is disclosed, not hidden behind truncated samples or a latency guarantee.

Full conditions, comparator, reproduction and limits: [verification evidence](../../../architecture/governance/verification/model-publisher-mix.md).

## Limits and follow-up

Deleted history is unavailable, manufacturer ambiguity stays unverified and personalized profiles are not same-task benchmarks or billing. Browser/physical mobile visual acceptance was **not run**; Node DOM/CSS/finite-job evidence is not a screenshot claim. Cold sparse-history acquisition remains intentionally more expensive; source-side targeted evidence would need trustworthy model-level revision/index support, not guessed session metadata. Parallel FR-only additions and identity watermark 532 are preserved; no pruning or unrelated backlog implementation.
