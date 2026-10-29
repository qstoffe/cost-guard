# Web table scroll investigation — FR 000529

Base: `a554d312fecc7d7db31ae6aebe7819418c18c11c`; checked 2026-10-29 on Windows.
Status: unfinished; real-browser reproduction and acceptance pending. This is not
a completion report or confirmation of the colleague's reported root cause.

## Source-bound defect and repair

Session detail polls captured the first row's document position before awaiting
HTTP. The `finally` block then compensated through `window.scrollBy`, including
unchanged responses and errors. A user could scroll the independently scrollable
table during that await; the resulting geometry delta incorrectly moved the
document. Internal table scrolling also did not disable Live follow, because only
window scroll and focus were observed.

`src/web/assets/session.js` now captures the first visible row immediately before
an actual DOM update, relative to the table's scroll container. Compensation uses
that container's vertical offset and leaves horizontal/document navigation alone.
Scrolling away from the internal list's bottom disables follow. No wheel/key
handlers, CSS overflow removal, acquisition, valuation, security, paging or frozen
snapshot changes were introduced. The existing keyed-row and selection/focus
guards remain. Architecture-boundary and journal assessment: no-update; the Web
module owner and this evidence document capture the relevant facts.

`development/tests/integration/web_session.cjs` adds deterministic cases for
scrolling during a pending page response, a visible row displaced by growth above
it, unchanged horizontal offset and internal-scroll follow cancellation. The
pending-response case failed against the base implementation (`window.scrollBy`
called once, expected zero), then passed after repair. VM geometry is deliberately
synthetic: it is not browser layout, wheel, touchpad or physical-device proof.

## Independent verification

- Focused `run_tests.py --pattern test_web_session_detail.py`: 9 tests passed.
- `run_tests.py --suite full`: all 116 test files passed, 56.7 seconds.
- `validate_package.py --working-tree`: 0 failures, 11 passes; four existing design
  budget warnings (README, analysis/context, reports/service, watch/coordinator).
- Read-only `probe_web_live.py --detail --reports`: V2, one acquisition owner,
  two streams, preserved run origin and advancing publication sequence. First and
  latest detail pages and frozen consistency passed. Normal, all-models, sessions
  and date reports completed; explicit deep history cancelled. Owned Live/HTTP
  workers closed; the shared OpenCode service was untouched. This observed only
  three detail rows and is not long-list or browser proof.

## Remaining mandatory browser work

Native `browser.tabs.list` returned `[browser.disconnected] No desktop browser is
connected to this session.` No external browser fallback, polling or restart was
attempted. Attach this same session in OpenCode Desktop, then perform one native
readiness check and continue real-browser reproduction before deciding whether
the source-bound repair addresses the reported problem or additional changes are
needed.

Cover Watch idle/changing Live rows, Sessions, Models, Accounts, deep Token Mix,
date reports and 50-row session Snapshot/Live pages. Verify list-to-end browsing,
wheel, available touchpad, PageUp/PageDown/arrows, horizontal movement, boundary
scroll chaining, sticky headings, filters/paging, resizing/360px, focus and text
selection across publications. Record unavailable physical inputs honestly;
synthetic DOM tests cannot fulfill that requirement. Existing natural browser
scrolling and reduced-motion CSS have not been modified speculatively.

No FR bundle/state/completion changes, PR or merge yet. Product version/history
and README current version must be updated against the fresh base in the eventual
delivery PR after acceptance. Preserve the selected owner and unfinished branch;
do not select another FR or delete its scratch workspace.
