# FR 000450 — Completed

Implemented in v80.94 (2026-10-27), delivered through [PR #78](https://github.com/qstoffe/cost-guard/pull/78). Candidate implementation: [d6dec5c](https://github.com/qstoffe/cost-guard/commit/d6dec5ce2559ca4872f21e548791e7bf18ec1ad2). Original FR bytes are preserved; no selected attachments were added or modified.

## Outcome and decisions

- Overview follows CLI Normal's ordered CCost / Token Mix % / Relative CCost groups, pricing metadata, reference table, promotion/new-model notices, Accounts Overview and final notes. Definition help and independent account observations are expandable. Compact account cards retain period CCost, native quotas/remaining/used/reset, Pace and known bills; source/account/attribution warnings stay visible. Removed redundant whole-report account totals and quota-table prose, not canonical data.
- Kept server/CLI exact model/tier/boundary/fallback ranking, not a second browser ranking implementation. Shared display tokens retain one-decimal `x`, arrow transitions, K/M boundaries and promotion markers; no-sample Overview leaves synthetic multipliers blank. Exact user sorting is stable with unknown scalar values last; third column click or CLI default order restores original server order.
- Real-source verification exposed an existing Normal report response just over 8 MiB because of JSON whitespace (8,501,873 bytes; request provenance 8,220,000). Compact serialization fixed admission without omitting records, changing analytical eligibility or raising resource limits. Added a boundary regression alongside the unchanged actual-oversize rejection test.
- No valuation/pricing, sample eligibility, account refresh cadence, persisted state schema or CLI output changes. Watch/other dedicated page redesigns remain separate pending FRs. Shared column sort restoration is intentionally common table behavior.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, 108 files, zero failures, 44.6 seconds after transport repair; includes CLI/export/rendered Overview exact-order/tier/fallback fixtures, unknown/tie/user-sort restoration and warning/account scope assertions.
- `py -3 development/tools/validate_package.py --working-tree`: PASS (zero failures; four existing design-budget warnings: root README, analysis/context.py, reports/service.py, watch/coordinator.py).
- `py -3 development/tests/integration/probe_web_live.py --reports`: initial Normal capture hit `result_too_large`; after compact serialization, PASS on real V2: one owner/two streams, Normal 10.721s, all-models 2.035s, sessions 1.015s, date 12.938s, deep-history cancellation and joined owned shutdown. Shared OpenCode was untouched. These are observations, not universal latency promises.
- Examined actual Edge before/after PNGs in 1440px/360px and light/dark; metric/account groups wrap and warnings remain visible, with narrow tables scrolling locally. [Synthetic screenshots and reviewed hashes](../../../tests/evidence/web-overview/README.md) are outside the immutable bundle. No private history, account details or browser profile is published. No attachment audit is required for this text-only completion.
- No paid/live-model calls, ZIP, tag, GitHub Release, PR self-review, physical-device/assistive-technology or owner approval claimed. macOS consumer acceptance remains pending independently.

## Knowledge and follow-up

Architecture-boundary assessment: no change; formatting stays in Web/shared display, acquisition and provenance stay server-owned. Updated the code-map test route and existing Web module facts with the reproducible whitespace-size finding. Journal: explicit no-update; no new independent journal topic or duplicate release log is useful. Remaining page-specific work is not implemented here. The native selected nextState is staged unchanged; retention requests no pruning.
