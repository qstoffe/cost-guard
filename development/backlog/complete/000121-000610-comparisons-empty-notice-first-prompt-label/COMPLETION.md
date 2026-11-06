# FR 000610 completion

Implemented on 2026-11-06 as Cost Guard v80.190, based on
`519712251290c878aa829d591617d9f7242154c9` (FR 000609's shared loader).

## Delivered behavior

- Each comparison group's existing safe preview reads `Prompt 1: <preview>`
  directly beneath its session-title/count heading, before the unchanged table.
  Existing truncation, literal text rendering and honest placeholders remain.
- The shared loader had already supplied Comparisons' empty-notice CSS rule.
  Regression checks now prove the empty notice has no rendered box, height or
  client rects across finished/refresh/navigation and failure/empty/partial states;
  meaningful notices, coverage status and unavailable alerts stay visible.
- First-input identity, backend preview preparation/privacy, all nine columns,
  repeated runs, accounting, acquisition and cache policy remain unchanged.
- Updated current user docs, version/date/history, the Comparisons journal and
  the selected ordinary-delivery progress state. The FR bundle remains intact.

## Verification

- Full registered suite: 153 test-file executions, zero failures (103.0s).
- Focused matching file: 17 tests, including safe preview edge cases and a later
  identical prompt in a different-first-input root being excluded from the pair.
- Package validation: 11 passes, zero failures; six existing advisory/design
  budget warnings, no raised budgets.
- Extended hidden-browser Comparisons probe: PASS, 12 Classic/Web light/dark
  layouts at 360/1366/1920px. Covers label/hierarchy/escaping/placeholders,
  zero-layout empty notice, meaningful status, no page overflow, exact table,
  quiet refresh DOM/focus, paging, Back, no matches, partial and failure states.
- Existing shared-loader hidden-browser probe: PASS, 10 checks / 24 layouts.
- Read-only real installation: cold 83.026s, warm 5.014s; both finite jobs
  completed with full observed coverage, 2,764 roots / 293 groups. No model
  inference, source mutation or shared OpenCode service stop.

Evidence and reproduction details are in
`development/journal/web/comparisons.md`, including logical owned-scratch paths.

## Limits and exceptions

No requirement/test exceptions. Integrated browser unavailable; hidden fresh-profile
Chrome supplied computed layout and accessibility-tree evidence. Initial relative
profile-path launches timed out before assertions; the probe now resolves the
output/profile path absolutely. Synthetic preview/status cases and real acquisition
are separate proofs; no private prompts were exported. Physical desktop appearance,
screen-reader speech, other engines and native macOS were not certified.
Architecture boundaries are unchanged; no overview/module-contract update needed.
