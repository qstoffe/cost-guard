# FR 000573 — implementation and verification

Completed implementation: 2026-11-04, product **v80.153**.

## Result

- Replaced the absolute eight-hour server deadline with independent stable browser
  bearers and a rolling seven-day successful-activity deadline on the running host.
- Successful protected API replies renew server activity and coalesce each browser's
  cookie headers hourly. Existing Live sync supplies liveness without new polling,
  report scans, processes, ports, dependencies or authentication UI.
- Bootstrap stays one-use/120-second/instance-bound. Existing valid browser bearers
  and instance CSRF remain stable through handoffs, renewals and concurrent requests;
  anonymous/failed/foreign/expired requests do not extend authorization.
- SSE checks remain non-renewing. An obsolete stream revalidates the browser's
  current cookie before reopening or showing genuine terminal expiry; late callbacks
  cannot disconnect its replacement. Host identity changes remain distinct.
- Updated user guide, architecture ownership, journal, version/date/history/README
  and the selected maintenance progress proposal (ordinary count 24). The original
  FR bundle was moved intact using next current Complete ordinal 000085.

## Actual verification

- Before edits: controlled clock reproduced valid authorization immediately before
  eight hours and rejection at eight hours; HTTP source confirmed cookie age 28800.
- Focused run: **42 tests passed**. Added exact inactivity boundaries, three virtual
  weeks, independent browsers, simultaneous renewal/handoff, stable CSRF,
  success-only renewal, suspend-clock accounting, HTTP Live/settings and SSE checks.
- Final **Full: 139 test files, zero failures, 86.0s**. The initial Full had one
  intentional-contract mismatch in a legacy shared-bearer-equality assertion;
  corrected it to require both independent clients remain authenticated and a
  same-checkout replacement reject the old bearer. Security assertions were retained.
- Final working-tree validator: **11 passes, zero failures, six advisory warnings**;
  no hard caps raised. No ZIP, tag or GitHub Release.
- Hidden installed **Chrome and Edge**: actual production HTTP/Watch/SSE/assets,
  two isolated client contexts each, real HttpOnly/Strict browser cookies and settings
  POSTs passed **29 simulated days**. Proved throttled accepted renewal, full idle
  window despite departure before renewal, inactive-peer rejection, repeated renewal,
  reload and terminal recovery guidance. Clock/cookie age was simulated, not elapsed.
- Real-installation read-only probe: **V2, one acquisition owner, two SSE streams**,
  advancing sequence/preserved run origin, first source view 1.653s; zero owned
  threads/processes after cleanup. Shared OpenCode was untouched. Shutdown recorded
  two account-history cancellation phase errors, not a completed Daily/history claim.

## Explicit exception and remaining uncertainty

**Decision Delegate**, after inspecting this FR and the current source/tests on
2026-11-04, authorized **608400-second cookie storage** (seven days plus one hour),
while **server authorization still expires at 604800 inactive seconds**. This is an
FR-only waiver of literal cookie/server expiry equality: hourly renewal otherwise
loses the cookie before a full seven days since last activity. It does not extend
authorization, authorize a permanent handoff link or waive other requirements/tests.

**Unperformed:** real elapsed eight-hour/multi-day browser soak, physical host
sleep/wake, Firefox/WebKit, native launcher/tray/clipboard and macOS browser checks.
System-clock corrections can affect wall-time inactivity. Integrated browser access
was disconnected; hidden installed browsers used fresh owned profiles with no
desktop/clipboard/personal-profile effects. These results are not full physical
or multi-platform acceptance. See [detailed evidence](../../../journal/web/browser-sessions.md).
