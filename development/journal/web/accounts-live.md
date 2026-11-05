# Shared live Accounts cards

2026-11-05 · FR 000594 · implementation based on `a75846ed6af307f0a55a7f620b8263167fd26761`.

`account-cards.js` owns both Watch and Accounts subscription rendering. Account IDs
select retained cards; value changes update bound metric/reset/help nodes. Only real
quota-slot/track structure changes rebuild a card's contents. The publication's
`accounts.now_ms` is excluded from card signatures. Route/settings changes consume
retained app-level Live, never Normal reports, provider work or another connection.
Acquisition, attribution, source security and native Diagnostics are unchanged.

## Observed checks

- Full deterministic suite: 145 isolated test-file/class groups, zero failures
  (93.1 seconds). The initial run exposed two stale test integrations: the old
  Accounts→Normal expectation and Mini's missing extracted-asset load. Both were
  corrected, without weakening product expectations, before the clean full rerun.
- Working-tree validator: zero failures, six existing advisory design/prose-budget
  warnings; product version v80.174. No budget was raised and no ZIP was built.
- `probe_accounts_live.cjs` passed with hidden owned Edge 156.0.4314.58 and Chrome
  156.0.8078.80. Shipped HTTP/assets/CSP/auth/SSE and disposable fixture config:
  initial Accounts without Watch DOM, loading vs empty, exact Watch/Accounts card
  markup/geometry, route links, one SSE, zero route-created reports, stable focus,
  selection/help/nodes across repeated publications, settings/defaults, retained
  provider failure, actual empty/membership recovery, secondary quotas, idle windows
  and the actual host-stop event. Six layouts per browser cover Classic/Web light/dark,
  1200/360 CSS pixels, reduced motion and DPR 1.5; cards measured 298 CSS pixels
  (447 raster pixels), with subgrid and no document horizontal overflow.
- Read-only `probe_web_live.py --accounts --watch-cards` passed against the real V2
  installation: three accounts, one account-refresh owner, one Live owner, advancing
  publications, two verified test streams, preserved engine origin and no finite jobs
  or model calls. Shutdown left zero owned threads/processes; shared OpenCode stayed
  running. The first run passed account ownership but failed the old two-second
  stream-continuity assumption. The repaired probe waits up to 15 seconds for an
  actual later publication; the complete rerun passed (8.90 seconds including close).
- Deterministic DOM tests cover shared values, unchanged publication clocks, changed
  reset/warning nodes, reversible units/orientation, account identity/reordering,
  failed-empty retention and confirmed empty removal. Legacy report-helper/DTO tests
  remain separate from the new live route.

Raw local evidence: `scratch:/accounts-live.json`, `scratch:/accounts-live-chrome.json`,
the corresponding theme/width PNGs, and `scratch:/real-live-recheck.txt`.
These are bounded observations, not a guaranteed provider-refresh SLA or a long-duration
production soak. Synthetic browser faults are not real credential expiry. Existing
authentication/terminal regressions retain that boundary. No physical desktop,
screen-reader, touch-device or macOS acceptance is claimed; no requirement/test
exception was requested or applied.
