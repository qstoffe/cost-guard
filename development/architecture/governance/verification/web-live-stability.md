# Web Live stability — FR 000532

Windows, Python 3.14, OpenCode Desktop integrated Chromium, 2026-10-28.
Base: `b4177d63b09f8f000dd8cfe1e607c24f8b036555`; candidate code/tests ship together.
No inference or shared OpenCode stop. Runtime artifacts stay private, outside Git.

## Cause and repair

The old HTTP SSE loop deliberately ended after sixty seconds. The instrumented
real-source host/browser baseline recorded open at 1793216480402, error at
1793216540814 (60.412 s), then open at 1793216543889 (3.075 s later). Authenticated
HTTP snapshots remained 200. Source acquisition was still starting in this cold
baseline: this is proof of the timed transport interruption, not reproduction of
the owner's exact roughly thirty-second healthy-source interval. No proxy or
browser idle timer was established as another cause.

Remove forced healthy-stream rotation, not the error notice. Four-stream admission,
twelve HTTP slots, two-second writes, ten-second heartbeats, per-turn authentication,
bounded replay and terminal shutdown remain. HTTP probes cannot claim connected
while EventSource is interrupted. Recent healthy visibility returns revalidate
without first inventing an outage; genuinely stale returns still invalidate status.

## Real-source browser soak

`development/tests/integration/serve_web_soak.py --workspace <new owned directory>
--seconds 2400` runs production WebHost, ReportJobs and real `live_acquisition`.
Open its private ready origin at `/soak-entry` in the integrated browser; open
`/#/watch` in another tab after authorization. The fixture-only entry instruments
EventSource open/error/resync and snapshot timings without retaining payloads or
identities. It is not a shipped authorization endpoint. Never publish ready files,
thread logs, cookies, tokens or raw real-source page contents.

- Overview was observed continuously connected for over thirteen minutes at the
  first readback (780.117 s since page start); Watch for 641.589 s. Both used real V2.
- Overview recorded one EventSource construction, one open, one initial resync,
  eighty successful snapshot checks and 978 live events at that readback. No SSE
  error or post-connection reconnecting transition. Both banners were hidden.
- Later observations extend uninterrupted Overview connectivity to 23m16.836s
  after its first connected transition, Watch to 21m2.202s after its observer began.
  Each tab's network inventory contained exactly one SSE request. Watch retained
  its table/ten displayed rows; its long-task observer recorded zero long tasks.
- The cold finite Overview report reached its existing 120-second timeout while
  Live stayed connected. Explicit Refresh later succeeded with one frozen table;
  no empty report or false source outage was substituted. No timeout increase or
  unrelated acquisition change was made.
- A separate `probe_web_soak_health.py` measurement recorded 63 successful public
  shell-health checks over 620 seconds. This complements, not replaces, browser
  and authenticated/source evidence.
- Authorizing a subsequent fixture with the same checkout cookie name deliberately
  invalidated the earlier host's browser cookie. Both old pages became terminal
  authorization-required and closed their streams, retaining contents. That is
  an actual authorization loss, not later flapping or eight-hour expiry.
- The candidate host completed its forty-minute lifetime with one acquisition
  owner, HTTP and Live threads joined, and no runtime failure. The cold baseline
  stop exceeded the ten-second host join deadline while acquisition was starting;
  its process subsequently exited nonzero. Do not count that baseline cleanup as
  a successful joined shutdown. The warm candidate/native runs establish recovery.

## Controlled integrated-browser faults

`serve_web_connection.py --workspace <owned directory>` uses production HTTP/SSE
and canonical synthetic data. Local command-file faults affect only its own host.

| Case | Fresh observed result |
| --- | --- |
| Healthy | One compact `Live connected.` accessible status; banner hidden, zero height. |
| HTTP/source unavailable | Visible SOURCE UNAVAILABLE notice, frozen table retained; not transport offline. |
| `interrupt` | Owned server read fault closes SSE for one second. Connected → reconnecting → connected in 3.029 s; both synthetic rows retained and banner hidden again. Native EventSource owns recovery. |
| `new_identity` | Old page rejects the changed authenticated response identity, retains two rows, disables Refresh and becomes terminal. |
| `expire` | Real server session expiry yields terminal AUTHENTICATION EXPIRED with both Watch rows retained and acquisition disabled. |
| `crash` | Abrupt owned-process exit, no terminal notification: browser reaches OFFLINE within the twenty-second condition wait, retaining two rows and disabled Refresh. |
| Real source-guard stop | Changing candidate `src/version.py` stops the owned fixture; browser receives STOPPED — NOT LIVE / source_changed, keeps both rows and disables Refresh. |

The integrated browser also exercised shipped CSS at constrained 1200px/360px body
widths in both shipped color palettes (forcing only the existing color media rule).
Actionable notices were static, wrapped without horizontal overflow, kept polite
status semantics and collapsed timestamp details. Healthy notice height was zero.
This is real DOM/CSS evidence, **not** viewport/device emulation, OS-theme switching,
physical resize, screen-reader, macOS or suspend/resume proof. Visibility callbacks
and deterministic clocks do not establish physical OS suspension behavior.

## Regression and native checks

- Full suite: 114 files, zero failures, four workers, 51.0 s on the final run.
  The initial run failed one old text assertion equating an SSE error with HTTP
  offline; the revised assertion requires explicit interrupted-stream/reconnecting
  and retained/not-live wording instead. Focused suites also pass.
- Final working-tree validation: zero failures, eleven passes and four existing
  soft design-budget warnings (README and three unrelated Python modules).
  Adding the required version entry crossed the unchanged history hard cap;
  older pre-v80 notes were preserved verbatim in a linked documentation archive,
  then Full and validation were rerun successfully. No budget was raised.
- Virtual-clock client tests cover twenty healthy minutes, repeated errors without
  busy polling/duplicate streams, interrupted-stream/healthy-HTTP distinction,
  probe/open/resync coalescing, visibility age, terminal callbacks, source loss,
  auth and identity. Server regression crosses the old timer deadline while
  retaining heartbeat, terminal delivery and released admission.
- Approved `probe_windows_web.py --allow-native-ui` passed native menu labels,
  Open failure/retry, Exit, HTTP-fault icon removal, detached survival, console
  ownership, concurrent launch, deliberate restart, source-change GUI removal,
  independent CLI Watch, failed-preflight preservation and source-shaped launch
  from spaces/Unicode paths. Model requests: zero. Batch exit 0.027 s; host/tray
  readiness 1.198 s cold, 1.813 s restart. Browser paint/physical Explorer double
  click and visual OS-theme review were not measured.
- Native launch tests intentionally invoke normal browser handoffs repeatedly,
  opening several standard-browser tabs. They do not close arbitrary Chrome tabs.
  Reducing this test's UI/tab noise is deferred; no cross-repository proposal was
  published and no additional native invocation is needed for this delivery.
- Initial PR CI passed Full/validation/native on all three platforms but failed
  its rendered-browser smoke at an old assertion looking for the full STARTING
  message in the now-compact header. The harness now asserts the exact compact
  header plus the full source/terminal notice, visible terminal banner and disabled
  Refresh; it retains the real socket, network-loss, layout and shutdown checks.

Architecture boundaries: unchanged; the Web module's current lifetime/status
contract and user documentation are updated. Journal assessment: **no-update**;
this focused causal evidence is the durable owner record, not a new general topic.
