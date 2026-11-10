# Completion — FR 000658

Implemented 2026-11-10 in Cost Guard v81.8; approved FR preserved unchanged.
PR: [262](https://github.com/qstoffe/cost-guard/pull/262). Main remains the supported
source distribution; no ZIP, tag or GitHub Release.

## Delivered scope

- Reproduced the synthetic rejected-pin **80% → Waiting for source** loop across
  actual browser/dispatcher/job/report/source ownership. Comparisons now escapes
  generic retry, rebases once to page1 and retires the rejected pin's demand.
- Explicit paging alone has three recovery backoffs and45s without advancing work.
  Actual stages/counts renew that budget; duplicate callbacks do not. Healthy work
  has no total deadline. Failure retains the last-good page and awaits explicit
  Retry; unrelated host jobs are not cancelled.
- Sessions/Comparisons share the responsive three-zone pager and centered polite
  range summary, correct units, disabled actions and guarded focus restoration.
- Models starts at top with non-scrolling focus only on new-route entry. Same-route
  scrolling/filter/sort/refresh and Session-detail scrolling remain intact.
- Coding Benchmark initially sorts raw numeric Solved descending. Manual retained
  sorting, score/ratio math, filters and GitHub reference-price fonts are unchanged.

## Verification

- Local Windows Full **181/181 groups PASS**,0failures,129.8s; per-file receipt
  `scratch:/full-stall-marker.json`. Validator **11PASS/0FAIL/7 existing advisories**;
  no budget/baseline raised. Earlier failed harness runs were repaired and rerun.
- [Common CI](https://github.com/qstoffe/cost-guard/actions/runs/42732344744)
  on `e3d14ab`: Quick **645/645**, validator and actual Chromium browser PASS.
  [Windows/macOS ARM/macOS Intel CI](https://github.com/qstoffe/cost-guard/actions/runs/42732344583)
  all PASS. Normal final-head checks remain merge prerequisites.
- Actual321-group source/job paging: Next11–20, Previous1–10, page18 171–180,
  page33 321–321 under the same pin; final Next disabled. Slow previews emitted
  measured1/10,5/10,8/10 progress. Busy/source/preview faults exhausted the bounded
  budget, retained page1 and recovered with Retry. Changed pin rebased deliberately.
- Real stalled-source failure completed in **47.37s** under the production45s
  no-progress policy; page1 retained, route navigation interactive, explicit Retry
  reached page2. Empty/one-group cases passed. A source-owned marker synchronizes
  this test because legitimate100ms IPC coalescing may leave its stage unpublished.
- Shared pager matrix:24 viewport/theme/media layouts at360/1366/1920px, no overflow,
  centered polite summaries, mouse/keyboard/emulatedtouch and focus checks.
- Exact historical/current app comparison: all five scrolled origin routes landed
  at123px with baseline versus0px/contentfocus with current. Cold/delayed publication
  and benchmark insertion remain0; same-route/manual-sort/detail-refresh retain500px.
  Actual per-tab125% zoom shrank un-emulated width780→624/DPR1→1.25; scrolled
  Sessions→cold/delayed Models remained0 through rendered publication frames.
- Read-only real installation:3056roots/321groups; pinned revision rejected with
  typed nonretryable error, unpinned rebase and pinned last page succeeded. This is
  **not** a successful real-source page2 claim or proof of the owner's exact incident.

## Limits and decisions

[Paging/navigation journal](../../../journal/web/paging-navigation.md) separates
historical failed trials, causal fixtures, real-source outcomes and final evidence.
Integrated browsing was disconnected; Decision Delegate authorized normal hosted
CI as the non-disruptive alternative, not an acceptance waiver. An accidental empty
delivery observation changed native bookkeeping before merge; the Delegate allowed
the already-authorized active task to finish using Git/PR truth, without repairing
or bypassing the rejected continuation call. No test or Git protection was waived.

Emulated touch is not physical-device or screen-reader proof; actual Chromium zoom
is not native OS scaling or non-Chromium certification. No source-history writes,
paid inference, raw prompts/titles, account changes, shared OpenCode stop, executable
rediscovery, implementation agents or feature-PR self-review occurred.
