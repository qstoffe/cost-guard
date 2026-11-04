# Sliding browser authorization — FR 000573

## Cause and ownership

At main `5e554de`, a controlled monotonic clock reproduced valid authorization at
28,799 seconds and rejection at 28,800 seconds despite an intervening valid check.
HTTP source independently set `Max-Age=28800` only on bootstrap. This establishes
the old eight-hour boundary, not the owner's unmeasured elapsed failure time.

`security.BrowserSession` now retains an independent stable bearer/deadline/cookie
renewal time for each browser. Only successful protected ordinary API responses
record activity. Pure authorization checks, errors, assets and SSE turns cannot
keep an abandoned browser alive. Existing valid credentials are reused on new
handoffs; expired records cannot revive, and host replacement rejects old values.
Instance CSRF remains stable behind the bearer/Host/Origin guards. Bootstrap still
uses monotonic 120-second, lock-serialized, one-use pending credentials.

Session activity uses wall time so host suspend counts even on platforms whose
monotonic clock excludes sleep. System-clock corrections remain a limitation;
physical sleep/clock-change behavior is not established by a controlled clock.
No source/account/report ownership, calculation, polling frequency, process,
dependency, port or native control boundary changed.

## Explicit storage exception

On 2026-11-04, **Decision Delegate** inspected the actual FR and security/HTTP/Live
owners and tests, and authorized this FR-only exception: cookie storage may use
**608400 seconds (seven days plus one hour)** while the server rejects each bearer
at **604800 inactive seconds**. Cookie headers are coalesced per browser on the
first successful API response after an hour. This waives literal cookie/server
expiry equality, **not** the seven-day effective authorization limit.

Reason: a seven-day cookie refreshed only hourly otherwise disappears up to an
hour before seven days since a browser's last valid request. The margin prevents
that early sign-out without per-poll headers, extra requests or a new service.
An active peer cannot extend another browser's deadline. Failures/public requests
never renew either side. No other requirement or test is waived.

An SSE response cannot update its opening headers. Existing ten-second Live sync
renews ordinary cookies. Concurrent initial handoffs can leave a stream using an
obsolete bearer after the browser has a valid replacement; `live.js` closes that
stream and validates the browser's current cookie before reopening or declaring
real expiry. Old-stream callbacks are identity-guarded. Genuine 401 remains terminal;
replacement-host identity stays a distinct terminal state.

## Verification on the local workstation

- Focused security/HTTP/connection run: **42 tests passed**, before the additional
  lifecycle assertion update. Clock-driven coverage crosses the old eight-hour
  boundary and three weeks; exact seven-day expiry, repeated windows, independent
  browsers, concurrent same-browser bootstrap and coalesced renewals, stable CSRF,
  suspend accounting and failure/public-request non-renewal are explicit.
- Actual HTTP `/api/live` and successful settings POSTs remain authorized through
  fifteen virtual days, without report jobs. SSE fixtures cross sixteen virtual
  days with normal activity, and emit authorization-required at seven idle days
  without normal activity. Stream checks themselves never extend inactivity.
- Hidden installed **Chrome and Edge**, separate disposable contexts/profiles:
  actual production HTTP/assets/Watch/SSE and browser-managed HttpOnly/Strict cookies
  pass **29 simulated days**. Cookie expirations are aged alongside the injected
  server clock; Chromium enforces the resulting expirations. Verified no early
  loss when closing just before hourly renewal and returning just before seven
  idle days, actual accepted renewed cookie headers, no per-poll renewal,
  independent-client expiry/rebootstrap, repeated daily renewals, Watch reload,
  CSRF-protected settings write and genuine-expiry recovery guidance. Browser and
  host cleanup completed. No personal profile, visible desktop, clipboard or
  account login was used. Settings writes stay inside the synthetic workspace.
- Initial browser harness attempts failed on early document evaluation and then
  waiting for a full load event on same-document navigation. The harness now waits
  for real document loads and explicitly reloads; no product assertion was weakened.
- Read-only real-installation probe: **V2, one acquisition owner, two SSE streams**,
  advancing sequence and preserved run origin; first source view **1.653s**.
  Owned HTTP/Live workers closed, zero owned threads/processes remained, and shared
  OpenCode was untouched. Two account-history cancellation phase errors occurred
  during shutdown; this does not prove complete Daily/history acquisition.
- Initial Full: 139 files, one failure: a legacy lifecycle test equated independent
  bootstrap bearer values. It now asserts both browsers remain authenticated and
  the same checkout's replacement host rejects the prior bearer. The changed
  contract is intentional; control authorization assertions remain intact.

- Final Full: **139 files, zero failures, 86.0s**. Final hidden Chrome and Edge
  probes both passed before this suite, with settings isolated to each fixture.
- `validate_package.py --working-tree`: **11 passes, zero failures, six advisory
  warnings** (existing public prose and unrelated module design budgets). No cap
  was raised and no new permanent gate or distribution artifact was introduced.

**Unperformed/unknown:** real eight-hour or multi-day elapsed browser soak, actual
physical host sleep/wake, Firefox/WebKit, native launcher/tray/clipboard acceptance
and macOS browser behavior. Simulated days are not elapsed uptime or desktop proof.
Integrated browser access was unavailable (`browser.disconnected`); hidden installed
Chrome/Edge supplied independent browser evidence without bypassing an identity or
permission boundary. No release ZIP or GitHub Release was created.
