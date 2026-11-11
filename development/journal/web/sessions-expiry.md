# Silent Sessions lease recovery — FR000679

2026-11-11 · v81.28. Focused browser recovery repair, not a new acquisition owner.

## Reproduced causes and repair

- `View.load()` already reopened once after `catalog_expired`, safely abandoning
  unproven older membership while retaining sort intent. `update()` then set
  `this.rebased = true` forever and chose an amber expired-catalog message on every
  later publication. The deterministic regression failed on that exact text before
  the repair. Removing the persistent flag and warning at their source leaves
  `recovering` false and the status/live region empty after accepted publication.
- Real installed-source browser verification found a second coherence defect:
  focus on an older-page link made `rows()` preserve the protected old membership
  while the recovered URL/pager identified page 1. `update()` now compares actual
  DOM membership/order with the accepted replacement. When recovery changes it,
  incompatible selection/focus is released before keyed reconciliation; matching
  rows retain DOM/focus. No hidden CSS warning or page reload is used.
- Source-qualified backend pages, globally correct sorting, fifty-row limits,
  scalar caches and the shared index/interest worker are unchanged. The ordinary
  five-second cadence, one bounded reopen per poll, request cancellation and
  actionable navigation/failure controls keep their existing owners.

## Verification

- Full: **184 isolated groups, 2,293 tests, zero failing groups**, 145.1 seconds.
  Two existing native macOS zsh/PTY skips on Windows. The changed VM covers offsets
  0/50, CCost both directions, exact fallback URL/epoch/header/pager, stable keyed
  rows, three later polls and normal cadence, bounded repeated expiry, failure
  recovery and incompatible focused membership. Existing navigation races remain.
- Package validator on v81.28: **11 passes, zero failures, seven existing advisory
  size warnings**; no budgets/baselines raised. Runtime version and README/history
  updated; no ZIP, tag or GitHub Release.
- Hidden Chrome **157.0.8103.39**, fresh disposable profile:
  `probe_web_help.cjs --sessions-quiet-refresh` passes shipped route DOM/AX checks
  for expiry on first/older pages, three later polls, delayed refresh retaining
  table/pager, changed visible metrics, stable cell/row/focus/scroll and truthful
  offline failure followed by automatic recovery. Replies in this probe are
  deliberately synthetic, not evidence of backend acquisition.
- `probe_web_sessions.cjs --catalog-navigation-only` passes real HTTP over
  synthetic 3,217 roots: seven global sorts in both directions, changed source
  generations, pending progress, mouse/keyboard/touch Cancel, late response
  rejection, outage/Retry, pager and exact seventeen-row last page.
- `--live-only` passes running/terminal transitions, visible metric/CTX changes,
  arrival, retained focus/selection/scroll, outage/reconnect and three themes,
  three widths, two zooms.
- **Real installed source, read-only host/HTTP/shipped route:**
  `--catalog-real-recovery` observed **3,126 roots**. Client-only invalid lease
  tokens elicited two actual HTTP `catalog_expired` responses, one on offset 0 and
  one on a populated offset-50 page. Both retained usable rows during acquisition
  and atomically applied a coherent fifty-row page 1 with a new token/epoch,
  matching header, URL and pager; status empty, `recovering` false, no `rebased`.
  First-page matching focus survived; incompatible older-page focus retired;
  scroll stayed stable. Three subsequent polls per case, an actual normal-cadence
  poll, hidden/visible return and Settings/Sessions return remained quiet. No
  source mutation, inference, personal browser profile or shared service stop.

Owned evidence: `scratch:/full-tests.json`, `scratch:/sessions-quiet-refresh.json`,
`scratch:/real-recovery.json`, `scratch:/navigation.json`, `scratch:/live-sessions.json`.
No row IDs, titles, transcripts, bootstrap credentials or private history exported.

## Failed attempts and limits

The broad older `--quiet-refresh` driver reached and passed the updated Sessions
checks but later failed an unrelated Models promotion tooltip exact-text assertion
(current help includes price tiers and Token Mix). That full cross-report driver is
**not claimed PASS**; no Models behavior/assertion was changed. The dedicated
Sessions mode runs the applicable assertions independently, with an explicit scope.
An obsolete assertion that no progress node existed was corrected to require the
existing operation loader hidden and retained grid/pager visible, plus an actual
offline error; completed/pending operations remain distinguishable.

The first real older-page attempt exceeded the synthetic driver's 30-second wait
while preparing 13/50 summaries. Its read-only wait now permits 120 seconds for
that step only; no product deadline changed. A later probe counted expired-interest
errors as page-read expiries; its counter now counts page requests only. Those
attempts were not PASS. The real focused-row mismatch was a product defect and
received the repair and a deterministic regression, not a waived assertion.

No delegated exceptions or acceptance exclusions. This is not proof of natural
five-minute elapsed expiry, every source failure, a completed real full-history
metric index, spoken assistive behavior or physical/macOS/browser-engine acceptance.
The real check uses an owned host against the installed source, not a reload or
modification of an already-running user browser/host. Backend non-scan and sort
guarantees rely on unchanged owners plus deterministic/navigation coverage, not
an invented real-source enumeration audit.
