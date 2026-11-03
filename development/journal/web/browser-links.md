# Windows browser handoff links

## Ownership and security

FR 000568 adds only a Windows tray action between Open and Exit. The native host
mints the existing fragment URL; HTTP routes are unchanged. An already-loaded
authorization-error tab can receive a same-document fragment navigation when a
user pastes the link. `app.js` now erases that explicit handoff before exchanging
it through the existing guarded endpoint, then reloads the clean Models URL.
Sixteen lock-protected in-memory credentials can remain pending independently for
120 seconds. Overflow fails without evicting another pending link. Failed copies
discard only their own credential; redemption preserves active session/CSRF values.

The clipboard worker uses typed Win32 Unicode/movable-memory APIs, bounded busy
retries and explicit OS memory transfer/freeing. It opts out of Windows clipboard
history/cloud upload before publishing the text. It never reads the clipboard;
notifications are fixed non-sensitive strings on the native main-thread pump.
Other clipboard monitors and same-user malware remain outside the trust boundary.

## Verification

- Initial focused local run: 58 tests passed; later focused run: 63 passed after
  strengthening software-fault and same-document handoff regressions. Coverage
  includes security, Windows adapter/real hidden native menu resources, simulated
  clipboard ownership/failures, host handoff and real HTTP/JavaScript facade.
- Final Full: **138 test files, zero failures, 83.3s**. An earlier Full found two
  changed inventories (new worker/native test selections), corrected with explicit
  expectations and a new worker-fault test. A subsequent overlapping browser run
  saw a historical 872-root timing-sensitive catalog count of 4 versus 2/3; the final
  Full passes that unchanged assertion without overlapping browser work. No
  production history policy or assertion was weakened.
- `validate_package.py --working-tree`: **11 checks passed**, zero failures and six
  advisory existing prose/module-budget warnings. No raised hard caps, ZIP or new
  permanent validation gate.
- Installed headless **Chrome 156.0.8078.80** and **Edge 156.0.4314.58**: **12 checks
  passed** through production HTTP/assets/security, with synthetic canonical
  reports/live publications and disposable profiles. Verified Chrome plain-URL tab
  duplication; fresh Edge plain-URL rejection; same-tab pasted handoff into Edge's
  authorization-error page; fragment/history erasure; no Web Storage credentials;
  same instance; Models/Watch navigation; older pending Open link in a private
  context after later Copy; replay rejection; unchanged Chrome session/CSRF; both
  existing application SSE streams continuing after handoffs. Clipboard callback
  captured the URL only in memory; OS clipboard and visible desktop were untouched.
  Initial browser work exposed the receiving-page defect above. A later harness
  incorrectly requested extra SSE streams beside temporary contexts, reaching the
  existing cap; final evidence observes the two real app streams instead. No server
  stream limit was changed. Owned browsers/host were closed.
- Read-only real-installation probe: V2, one acquisition owner, two SSE streams,
  preserved run origin and advancing sequence; 1.369s first source view. All owned
  workers closed (zero remaining processes/threads), shared OpenCode untouched.
  Account-history cancellation recorded two phase errors during shutdown; this is
  not evidence of completed daily-history acquisition or a broad data-quality PASS.

## Isolated clipboard setup failure and explicit verification exception

The **Decision Delegate**, not the user, first requested a non-disruptive native
clipboard probe on a private, noninteractive Windows window station **and** desktop.
A fresh hidden child attempted `CreateWindowStationW` before any clipboard/GUI work;
Windows returned **WinError 5 (Access Denied)**. Setup stopped immediately. No
station/desktop was switched, no clipboard was accessed, and owned resources were
released. No elevation, identity switch, rights retry or access workaround was used.
This is **setup failed**, neither a clipboard product-test failure nor PASS.

After that result, on **2026-11-04** the **Decision Delegate explicitly superseded
the earlier successful-isolation prerequisite** and authorized FR 000568 completion
and ordinary PR/checks/squash merge with a task-only verification exception, also
valid for legitimate continuation of this FR. Substantial inspected deterministic,
native-resource, browser, Full and validator evidence plus the isolation denial
made user-desktop disruption or holding delivery disproportionate. This is not
blanket authority or user approval, and it waives no other tests/Git protections.

**Unverified:** actual Win32 clipboard text transfer, contention/retry, memory
ownership transfer and post-owner-cleanup behavior; actual shell enforcement of
history/cloud exclusions; physical launcher→tray→Edge paste; 150% mouse/keyboard
popup interaction; notification/DND visibility; actual Explorer restart and
interactive tray cleanup. Mocks, hidden native menu resources and headless browsers
do not establish those facts. No shared-clipboard or visible desktop testing is
authorized by this exception. Delivery is implemented with these explicit
verification exceptions, **not full physical acceptance**.
