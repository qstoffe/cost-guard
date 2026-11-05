# Completion — FR 000595

Implemented 2026-11-05 · v80.175 · base `7d2565a7eb98a17f00d80f942aa7082a50588e3d`.
Delivery PR: https://github.com/qstoffe/cost-guard/pull/181

## Result

- Removed the Reports link, date form/dispatch, date-only rendering and unused form
  CSS. Shared `reports.js` still owns surviving route/control definitions.
- Retired Reports hashes replace the current history entry with scope-free Sessions
  before view creation or acquisition. Dates and other query parameters are
  discarded, not silently applied. Keyboard focus moves to the target content;
  reload and Back/Forward are stable. No hidden date job or date filter remains.
- Kept live Sessions and detail/Watch links, shared report engines/APIs/jobs,
  security/source/privacy behavior and other Web routes. Updated current user docs,
  architecture route/code/help inventories and obsolete browser-probe routes;
  historical FRs, releases and verification evidence retain their original facts.
- Incremented product version and included the selected ordinary-delivery state
  (`ordinaryCount: 45`, `lastOrdinaryId: fr/000595`) for publication on merged main.

## Verification and limits

- Full local bounded suite: 1,708 passed, one existing Windows zsh/PTY platform
  skip, zero failures/errors; 145 files/groups, 1,709 tests, 98.9s.
- Working-tree validator: zero failures, 11 passes, six existing advisory size
  warnings; no cap increase or release ZIP.
- Fresh headless Edge: valid/invalid/absent date queries, cold reload, Back/Forward,
  actual 1920px/360px navigation, default activity order/no date filter, all-prompt
  detail, exact synthetic global sort and surviving explicit capture/refresh/cancel
  passed. No browser runtime exception, personal profile or desktop effect.
- Read-only real V2 probe: Normal/all-models/Sessions/date API reports completed,
  deep history cancelled, shared Live origin/streams stayed intact and owned
  threads/processes closed. No inference or shared OpenCode stop.

[Detailed evidence](../../../architecture/governance/verification/web-reports-retired.md)
records commands, timings and limitations. The inherited cold real-catalog scalar
index remained pending (4/2,720); two history-stage exceptions were observed without
failing the requested report/stream/detail checks. Real full-catalog metric readiness,
physical desktop, screen-reader and macOS UI acceptance were not established here.
These are proof limits, not fabricated PASS results or changed backend requirements.
No new user/Decision-Delegate requirement or test exception was requested or used.

Architecture updated in place. Journal: no-update; the affected ownership facts and
retained verification above are sufficient for this focused UI retirement.
