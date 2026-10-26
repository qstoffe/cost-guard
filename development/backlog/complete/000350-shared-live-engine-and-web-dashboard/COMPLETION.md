# FR 000350 — Shared Web live engine

## Outcome

Implemented in Cost Guard v80.86 (2026-10-26). One host-lifetime acquisition owner supplies the global Live page across tabs; CLI Watch remains independent. Original FR bytes are preserved. Candidate implementation: [2827029](https://github.com/qstoffe/cost-guard/commit/282702930cb65362996a20ef4852c41b11c23bc0); the eventual merge is recorded by native delivery.

## Changes and decisions

- Extracted the small renderer-independent `acquire_cycle` dispatch seam rather than copying analysis, retention, lifecycle or account logic. The application schedules one fresh Watch driver/service; tabs consume detached allowlisted exports. Engine-start run totals survive reconnect/tab closure and are labelled distinctly from CLI runs and normal account-month comparisons.
- Multiplexed same-origin-cookie SSE carries coherent live, job progress and terminal state. Instance/sequence IDs, detached HTTP snapshots and bounded replay prevent duplicate/older/foreign updates or gaps from fabricating continuation. Replay is 32 events/8 MiB, publications 2 MiB; source hints are bounded to 1024 and overflow requires authoritative resync.
- At most four streams use twelve HTTP slots, leaving eight ordinary/control slots. Header deadlines remain five seconds; authenticated streams alone use bounded writes, heartbeats and sixty-second reconnect. Received terminal notifications stop retry even across gaps. Unknown disconnect remains offline; no server startup, reusable query secret or browser persistence.
- Live retains selected-source recovery, deferred bounded history slices, independent account publication and Watch global retention/tool/skill/context/Today semantics. Finite reports retain isolated cancellable/deadline-bounded processes, not the live mutable context. Unexpected live/cleanup faults hand the original exception to the host fatal boundary.
- Updated affected architecture/owner routes and runtime execution-root policy. Journal assessment: **no-update**; current ownership/probe facts belong in the Web/Watch contracts, with no new generalized performance conclusion or duplicated daily log. No new dependency, paid-model test or permanent release gate.

## Verification

- `py -3 -B development/tools/run_tests.py --suite full`: **PASS**, 103 test files, zero failures (42.3 seconds observed on this workstation). New focused file has twelve deterministic tests, including canonical projections, terminal transitions, source recovery/hints, account-only updates, midnight/DST/partial pricing, replay/overflow, software-fault ownership, actual HTTP stream bounds and stop with an occupied finite-report process.
- Optional already-installed Node VM: **PASS** through Full; shipped client duplicate/older/gap/foreign-instance handling, terminal retry stop, offline state and literal safe live rendering. Existing static-view HTTP/DOM regression remains passing.
- `py -3 -B development/tools/validate_package.py --working-tree`: **PASS**, zero failures; four nonblocking design-budget warnings (README, analysis/context, reports/service, Watch coordinator). Hard caps were preserved; README growth was shortened rather than raising its cap.
- `py -3 -B development/tests/integration/probe_web_live.py`: **PASS**, real read-only V2 source, one acquisition owner, two streams, four retained rows and three account observations, unchanged run origin, advancing publications, joined live/HTTP shutdown. No inference, credential changes, UI automation or shared OpenCode restart/stop.
- Earlier failing checks were repaired: stale HTTP/thread inventory assertions, a missing composition clock argument found by the real probe, fixture scope assumptions and README overflow. These failures are not claimed as passing runs.

## Limits and follow-ups

Live session detail/unlimited logical history remains FR 000360; remaining dedicated report routes and cross-platform Beta stabilization remain FRs 000370/000380. A finite snapshot session link stays frozen until Refresh. Native browser/CSS/physical interaction and macOS Finder/AppKit/Gatekeeper checks were **NOT RUN**; no native acceptance or comparative performance claim. Oversized live publications fail explicitly rather than truncate or change global row scopes. Source/API loss never proves prompt completion, and upstream quota freshness remains independently observed/unknown.

Pending specifications remain intact and can build on the committed acquisition/export/event owners; no cross-FR recovery artifact exists only in scratch. No ZIP/tag/GitHub Release was created; current main remains the distribution.
