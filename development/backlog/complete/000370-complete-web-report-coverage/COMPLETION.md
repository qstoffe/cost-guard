# FR 000370 completion

## Outcome

Implemented for v80.88, 2026-10-26. Every existing finite report kind now has a discoverable Web route alongside global Live and complete session Snapshot/Live. The selected FR bytes are preserved; no attachments were changed or added.

Implementation candidate: [c982393](https://github.com/qstoffe/cost-guard/commit/c982393f29dacdf41560cc3f7c845cab739fdfe6).

## Changes and decisions

- Local scope controls expose selectable/all catalog Models, Accounts, Sessions N/all, configured-local inclusive date/range Reports and historical Token Mix. Hash/deep-link navigation and retained page-memory snapshots preserve Back/Forward. Date prompt links open complete session detail; Back retains the range. Overview/Models/Accounts reuse a retained normal-report observation rather than reacquiring accounts to change presentation.
- Canonical Python projections retain independent sample eligibility, exact server ranking, tiers/native full-catalog rates, release/promotion facts and availability warnings. Conservative model supersession classification is shared through analysis with the CLI compatibility export, not duplicated in JavaScript.
- Accounts show provider/account labels, observation freshness/status/method errors, native quota windows/units/remaining, Pace, billing, report Today/local-month CCost and Copilot Unaccounted usage (including unknown). Account-only partial-subtotal policy remains distinct from global/prompt completeness markers; normal month figures are not inserted into Watch.
- Date validation rejects impossible, reversed, overflow and noncanonical API dates. Shared local-calendar/DST valuation and union duration remain authoritative. Selected-range totals are not labeled full-session totals or summed from visible cells.
- Historical Token Mix starts only on explicit Refresh, shows actual phase/count progress, supports cancellation and renders per-model prompts/calls/token/cost/mix/price coverage plus canonical totals. Frozen results remain in page memory; recapture reuses only source/config/pricing-bound analysis cache entries. Missing history is never reconstructed.
- Global/per-table search, stable exact Decimal/vector sorting and 50-row paging are presentation-only, with explicit filtered/page/full-report counts. Complete paged session detail keeps its own browsing controls; the global filter is disabled rather than pretending it searches unloaded history.
- Dense accessible tables, system palette, scope forms, modest older-stable fading and no optional charts were chosen to avoid a second metric engine. These visual decisions are documented for owner feedback, not claimed design approval.

## Verification and repairs

- `py -3 development/tools/run_tests.py --suite full`: **PASS**, 104 files, zero failures, 41.1 s final run. Includes V1/current V2 parity for every report kind, independent scopes, account ambiguity/errors/freshness, missing prices, tiers, local periods/DST, archived/empty history, history cache invalidation and cancellation/resource bounds.
- `py -3 development/tools/validate_package.py --working-tree`: **PASS**, zero failures; four advisory design-budget warnings (README and existing context/report/Watch modules). README was shortened to preserve the hard cap rather than raising it.
- Served-asset/real-HTTP Node VM checks demonstrate overview → sessions → session detail → Models → Accounts → date report, reload/Back-equivalent hashes, N/all pagination, explicit-only deep scans, frozen/refresh/stale/missing/empty states, exact near-equal/exponent Decimal ordering, tiers, independent account errors and hostile text. No browser, external assets or persistent browser storage is used.
- `py -3 development/tests/integration/probe_web_live.py --detail --reports`: **PASS** against the real V2 installation: one acquisition owner, two streams, preserved run origin, detail capture/freeze, successful normal/all-models/sessions/date reports, cancelled historical scanning and joined owned shutdown. Shared OpenCode was not stopped; no inference or UI was invoked.
- The first real normal-report probe timed out. Source inspection found that consuming one IPC progress message per host turn could backpressure a scan into its deadline. A bounded 64-message drain now coalesces progress while preserving host turns; a deterministic 130-message regression verifies bounded drain/completion. The repeated real-source probe passed. This is not a before/after throughput benchmark.

## Knowledge and boundaries

Architecture update: relevant Web/report ownership pages now route finite scopes, shared classification, bounded progress and verified source probes. The major dependency graph and existing gates are unchanged. Journal: **no-update**; no separate reusable journal topic beyond these owner contracts. The detailed mode-to-view inventory and visual choices are in [Web Beta](../../../../docs/web-beta.md#navigation-and-static-reports).

No provider/OpenCode mutation, login/editor, credential export, dependency, updater, remote sharing, PDF, new integration, ZIP or GitHub Release was introduced. CLI output and existing launchers remain independent. Prerequisite Web foundation/Live/detail work is already delivered; no unfinished implementation dependency is stored only in scratch.

## Limitations and follow-up

Real browser layout, mouse/keyboard/screen-reader and native macOS acceptance were **NOT RUN**; VM navigation is not visual proof. Existing 8 MiB/120-second finite-result limits remain explicit errors, never truncated success. The real history probe proves cancellation beside Live, not a completed scan of the entire installation; deterministic canonical history fixtures prove complete report semantics. Closing/reloading/evicting page memory discards frozen views; no private history is persisted in browser storage. Cross-platform Beta stabilization remains the separate pending FR 000380.
