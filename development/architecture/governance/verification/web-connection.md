# Web host-state verification — FR 000500

Observed on Windows / Python 3.14 / OpenCode Desktop's built-in Chromium browser,
2026-10-27–28. Base: `8a4fcccc6a9567ab430f7115fc6e924e7ee91e71`;
candidate source and tests are delivered together in this FR's PR.

## Reproducible setup

With explicit browser approval, start `development/tests/integration/serve_web_connection.py
--workspace <owned scratch directory>` from the checkout. Read its `ready.json` origin
and navigate the built-in browser to `/probe-entry`, then open `/#/watch` in another tab.
This fixture uses production WebHost, HTTP/security/assets/EventHub/SSE with synthetic
canonical reports/Watch. Its fixture-only entry asset exchanges a one-use credential
without printing it. It adds no production route, uses no personal profile/history,
and self-stops after ten minutes. Never publish the runtime fixture directory.

Write `{"action":"<action>"}` to its local `command.json` for `recovering`, `running`,
`expire`, `new_identity`, `menu`, `source_changed` or `crash`. These affect only the
owned test process. `crash` deliberately exits without terminal notification or child jobs.

## Observed browser outcomes

| Case | Actual result |
| --- | --- |
| Authorized Overview and Watch | Finite Overview captured; Watch displayed one canonical table; connected banner showed separate host-check/source timestamps. |
| `recovering`, HTTP still up | SOURCE UNAVAILABLE, not connected acquisition; Overview table and Watch rows retained with stale lifecycle wording. |
| Temporary authenticated snapshot-request interruption | A browser-local fetch fault plus resync showed RECONNECTING immediately, then OFFLINE; two table rows remained, Refresh disabled and no Watch Updating text. Restoring fetch and dispatching visibilitychange revalidated before returning to connected. No second EventSource was created by the client. |
| `expire` | Actual server session expiry became terminal AUTHENTICATION EXPIRED; Watch rows retained, no Updating, acquisition disabled. |
| `new_identity` | Changed authenticated response identity was rejected before accepting replacement data; Overview retained its table and became terminal identity_changed. This is a controlled identity replacement, not a physical launcher restart. |
| `crash` | Actual abrupt owned-process exit, no terminal SSE event: both tabs reached OFFLINE within the bounded wait (20 seconds), each retaining its table/two rows with Refresh disabled and no Updating claim. |
| `menu` | Production menu-stop method sent terminal SSE to both tabs: STOPPED — NOT LIVE, retained rows, Refresh/Cancel disabled, manual OS-launcher instruction. |
| `source_changed` | Production source-change stop sent terminal SSE to both tabs: same frozen/disabled behavior, explicit reason; the notice also said not updating. |

The source-change investigation also exposed the stream close/read race: a close after
an empty read could return without a terminal frame. The focused deterministic regression
forces exactly that interleaving and now verifies one source_changed terminal frame.
Fallback OFFLINE remained visible even when the old client missed the notification.

## Deterministic and real-installation evidence

- `py -3 development/tools/run_tests.py --suite full`: 112 files, zero failures,
  final functional run 45.0 seconds, four isolated workers. Includes the new connection
  test in the explicit suite inventory.
- `web_connection.cjs`: virtual-clock watchdog bounds, no-view startup, progress not
  freshening failed health, recovery, idle revalidation, instance rejection, auth expiry,
  terminal timer cancellation and initially unavailable host recovery.
- `web_views.cjs`: terminal common-shell banner/notice, exact retained finite contents,
  disabled acquisition and inert scope controls. Reload contexts wait for their own
  authorization/result instead of borrowing another context's stale DOM.
- `test_web_live.py`: authenticated identity header and unauthenticated exclusion,
  real bounded HTTP/SSE and terminal shutdown beside an owned slow report.
- `py -3 development/tests/integration/probe_web_live.py`: real OpenCode V2, one owner,
  two streams, four retained rows, three account observations, preserved run origin,
  advancing sequence; shell 0.046 s / source view 4.772 s. Owned workers joined;
  shared OpenCode was not stopped. No inference was requested.

## Limits and assessment

The first hosted browser run failed an obsolete readiness assertion: its finite-report-only
host has no Live owner, yet expected Live connected. The probe now independently requires
the actual authenticated SSE socket and STARTING/source-pending status. After its synthetic
source-unavailable publication, network recovery must show SOURCE UNAVAILABLE/HTTP connected,
not healthy acquisition. This changes fixture expectations to the FR contract without
weakening the real socket, retained-report, offline/reconnect or terminal assertions.

No physical tray click, OS suspension/long-idle soak, screen-reader, dark/narrow viewport,
real launcher restart/new-cookie browser combination or native macOS proof is claimed.
Menu/source-change checks call the same production stop owner without native UI automation;
existing lifecycle/security tests separately cover replacement credentials and restart.
Visibility-event and virtual-clock checks are not hours-long suspend proof. A newly
navigated page after a dead server may show the browser's own network-error page; without
a service worker, a dead host cannot serve a new dashboard. Already-loaded pages mark loss.

No model calls, browser storage, private-control credentials, network scan, new acquisition
owner or CLI behavior change. Journal: **no-update**, no new general engineering topic.
Architecture boundaries/routes: **no-update**, existing Web/Live/security owners remain;
current behavior and evidence are documented in `docs/web-beta.md` and this record.
The optional knowledge helper rejected the existing oversized Web module (>12 KiB);
it was not patched or treated as a required product failure. Consolidating that legacy
module is deferred, not a reason to expand this feature or change helper limits.
