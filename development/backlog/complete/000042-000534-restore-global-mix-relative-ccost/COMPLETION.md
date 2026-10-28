# Completion — FR 000534

Implemented for Cost Guard v80.111 on 2026-10-29 from base `1b0fd64375bfc10c6653dda86dea41e2d0c1eb88`.

## Delivered behavior

Every model/context tier uses one pooled global I/C/W/O mix from the latest up to 100 distinct eligible completed priceable prompts. Warning-first and report-first tier comparisons share this policy and the existing warning observation cache. Raw Decimal pricing/sorting, positive cheapest-base denominator, hidden no-data ordering, publisher labels and actual/reference separation remain unchanged. Ordinary lists no longer acquire deep model-specific comparison evidence.

CLI Normal/All Models and Web Overview/Models explain the shared sample and actual count, not personalized blends. Historical Token Mix by model/publisher, absolute Tokens, display units and explicit/cancellable Web history remain intact. FR 000527 is not edited; FR 000528 and other pending work are preserved.

## Verification and repairs

- Full local suite: **116 files, zero failures**, four workers, 52.1 seconds.
- Working-tree validator: **zero failures**, four design-budget warnings; no hard caps raised.
- Read-only real OpenCode V2 `--all-models`: exit zero, actual 100 completed-priceable-prompt global sample and model/tier table rendered; no model calls or shared-service interruption.
- Focused final workload/presentation run: 25 tests passed. Independent expectations cover common pooled prices, identical-price untried models, 0/1/99/100/121 samples, older own-history exclusion and warning-first parity. Existing full-suite attribution/eligibility/tier/publisher/absolute-token/display-unit and Node DOM regressions pass.

Initial runs exposed obsolete deep-hydration/golden expectations, documentation cap overruns and two test-edit errors; all were causally repaired and rerun, without changing assertions to arbitrary tolerances or weakening gates. The new warning-first fixture was corrected to avoid overlapping root times. [Detailed evidence and limits](../../../architecture/governance/verification/global-relative-mix.md).

## Knowledge, dependencies and scope

Updated report/analysis module facts and performance journal; old deep-scan timing conclusions are explicitly historical. Architecture-boundary/diagram assessment: **no update needed**. Exact native nextState and retention identity are preserved, with no pruning or invented completion ordinal. Selected specification is byte-preserved; evidence lives outside this bundle. Initial optional next-work observation timed out and remains unknown; it did not replace the available exact selected transaction.

No new dependencies, live-model evaluations, ZIP/release, browser visual/native proof, background sampling or cross-repository publication. Browser pixels, physical accessibility and general latency improvement are not claimed. No additional suggestion was published; retained performance investigations remain deferred.
