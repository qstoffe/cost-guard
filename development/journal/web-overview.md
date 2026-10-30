# Web snapshot parity and navigation

Source revision: c87bd954decd5bc36ea06409abc1a78d3c7951c2
Checked revision: c87bd954decd5bc36ea06409abc1a78d3c7951c2
Last checked: 2026-10-30
Status: current

## Summary

In the 2026-10-28 investigation at `ad28c1e842447e6e66bb695cd6fc5cb2be552b99`, the owner's V2 Normal report produced 25 models in CLI,
but Web returned result_too_large. The failure was transport payload, not a
missing catalog row. Normal exported unused month-wide request identities; the
candidate removes that aggregate-only payload while preserving all root revisions,
account scopes, model selection and the unchanged 8 MiB security/resource limit.
Session/detail identity exports remain unchanged. Overview also needs its complete
table, rather than the shared 50-row page, and stable DOM across host heartbeats.

FR 000529 extends that continuity to all finite views: the ten-second authenticated
host probe is not a new report and must not rebuild Models, Sessions, Accounts,
date or deep-history DOM. Session-detail updates capture a visible anchor after
the response and compensate only inside the table. A pre-await document anchor
can otherwise undo native scrolling while HTTP is in flight. No CSS overflow or
wheel/key interception is necessary for these defects.

Detail attachment must also be idempotent: replacing a parent's children with its
already-connected root still disconnects/reinserts the subtree. The heartbeat
must not disturb native focus or internal scrolling simply to show unchanged
detail controls. Watch already follows the same parent-identity guard.

FR 000530 adds explicit finite Cost per Active Hour captures. Route navigation and
unit switching must not acquire history; period clocks/CCost come from Python.
Session rate health must update even if the source loses availability without a
new report revision. The last good value remains frozen and visibly retained.

## Evidence

CLI Normal was captured privately from the scratch clone with default config and
the already running V2 service. First cold capture exceeded a 180-second harness
deadline; a bounded 600-second retry completed without source/model mutations.
Web was started through cost-guard-web.py --foreground and opened in the built-in
Desktop browser using its normal one-use authorization flow.

Original compact result: 9,445,447 bytes, including 9,129,161 bytes of unused
request identities. Candidate repeat: 316,288 bytes; source revision evidence
alone remained 283,150 bytes. Counts are installation/time-specific, not budgets.
Application composition captured one canonical report; the CLI renderer and
application export consumed that exact report. The private export was loaded
into the real browser's shipped renderer without sending history to Git.
All 25 ordered model rows/four columns, phase costs, account scopes, native-money
and reset tokens matched. See the [sanitized matrix](../architecture/governance/verification/overview-real-installation.md)
for browser coverage and limits. Deterministic DOM cases include 0/1/49/50/51/123
rows, duplicate names across publishers, fallback ranking and unknown values.

On 2026-10-30 the new `integration/web_views.cjs` heartbeat regression failed before
the all-finite-view retention fix, then passed. An isolated Chromium 141 test over
shipped HTTP/security/SSE/assets and synthetic application data reproduced the old
session response race: a native 350px wheel moved the inner table 500→850 while
the document was at 578; old session.js then moved the document to 228. Candidate
session.js retained 578/850. This isolates a source-bound cause, not the original
colleague's unknown route/device. `integration/web_table_scroll.py` is approval-only,
not a new permanent gate. See the [scroll evidence](../architecture/governance/verification/web-table-scroll.md)
for the browser matrix and physical-input limits.

The subsequent detail attach regression failed with one parent replacement where
zero was expected, before the parent-identity guard was added. Fixture failures
were kept distinct: hash navigation can initially show the previous table;
rapid whole-document reloads exhaust the four SSE slots until closed sockets are
noticed on a write; and integer CSSOM extents can leave a fractional end pixel
that consumes the first boundary wheel. The harness waits for the routed result,
retains one EventSource and tests the next boundary gesture; no production key,
wheel or stream-limit workaround was introduced.

Decision Delegate clarified the retention assertion after the old new-activity
label expanded narrow controls: measured height +47.25px, native document offset
+47px, visible-row drift only +0.25px with focus/selection/horizontal offset intact.
This is legitimate visual anchoring, not the old unrelated document jump. The
blanket raw-scrollY assertion's failed run remains a failure. The corrected
focused rerun passed anchor-aware checks: measured control expansion explains the
page movement; subsequent stable-controls growth retained document/horizontal
900/100 and adjusted inner scroll to 1647, with -0.25px row drift. Geometry-neutral
updates must retain all raw offsets. This was a test interpretation, not a new
production control design or an FR waiver.

The full registered suite after the app fix passed 115/116 files; four Windows
PowerShell 5.1 subcases in `test_launcher_feedback.py` failed because scripts were
disabled (`SecurityError` / `UnauthorizedAccess`, exit 1 instead of 9009/17).
The intended 5.1 launcher behavior remains unverified, not proven pre-existing;
the corresponding pwsh.exe subcases passed. Decision Delegate approved a narrow
delivery exception for these unrelated policy-blocked subcases, conditional on
the relevant Web/browser checks and validator passing. No policy or unrelated
tests were changed or circumvented. Decision Delegate separately authorized only
session-isolated Playwright/Chromium provisioning and synthetic loopback tests;
no personal profiles, source acquisition, model calls or shared-service changes.

FR 000530's isolated headless Edge probe passed 20 assertions in each of four
1200px/360px light/dark cases: no scan on opening, capture/cancel, three scopes,
prepared USD/credits, frozen navigation/failed refresh, Snapshot/Live/Freeze/Follow,
same-revision stale state and layout/programmatic focus. This is synthetic HTTP
with scripted EventSource, not real SSE, physical keyboard or source/native proof.
Reproduce with `development/tests/integration/probe_web_active_hour.py` and an
explicit approved executable/output. The Decision Delegate authorized only exact
installed-browser discovery and owned profiles/loopback tests, renewing bounded
batches for concrete fixture repairs. All owned profiles/processes/server closed.

Earlier attempts remain unsuccessful: one 40-second TIMEOUT gave no assertion
result; four cases passed 13 assertions then failed a route-readiness fixture race;
four passed 16 then failed a fixture that reused an immutable one-shot service.
Wait for routed detail data, not old page text; prepare separate one-shot captures
at different clocks. Deterministic real SessionHistory tests independently verify
3000->7000ms advancement and frozen last-good time on source outage.

Decision Delegate separately approved the unchanged four Windows PowerShell 5.1
policy-blocked subcases for this delivery, contingent on relevant checks passing.
No host policy/test bypass was made; the suite must not be labeled an overall PASS.
Current scoped evidence and limits: [active-hour verification](../architecture/governance/verification/web-active-hour.md).

## Next investigations

Keep aggregate views independent of per-request payload growth. If root revision
evidence itself reaches the bound, investigate an explicit provenance transport
contract; do not silently truncate it or raise the limit. Physical outer-window
resize, physical devices and assistive technology remain distinct from headless
automated-input/layout evidence; never reinterpret the latter as physical proof.

## Rejected hypotheses

The 50-row slice cannot explain this capture's failure: CLI had only 25 models,
and the browser rejected the result before model rendering. It is still a real
boundary defect, covered independently. Shared DTO ownership alone is not parity
proof; actual DOM, payload size, status-driven redraw and source scope must be checked.

Pure table overflow removal would not fix a response-time document compensation
or health-triggered DOM replacement. Browser fixture navigation must wait for the
new route's completed data; an immediately visible old table is not readiness.
