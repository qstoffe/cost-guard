# Optional Web runtime

Source revision: 8dc82a38dddd7f2999e7872d52e1e6a8a0949725
Checked revision: 8dc82a38dddd7f2999e7872d52e1e6a8a0949725
Last checked: 2026-10-27
Status: current

## Responsibility and ownership

`src/web/http.py` owns bounded loopback HTTP, fixed assets and routing; `src/web/security.py` owns one-use bootstrap/HttpOnly sessions/CSRF; `src/web/jobs.py` owns finite admission, process isolation, progress, cancellation and retention; at most 64 progress messages drain per host turn to prevent scan backpressure without starving control/Live. `src/web/composition.py` creates fresh canonical ReportApplication integrations.

`src/web/assets/app.js` owns finite refresh/stale/cancel state and memory-only observations; Overview/selectable Models/Accounts reuse one frozen normal report. `src/web/assets/reports.js` owns scope forms/catalog links and explicit-only deep-history admission. `render.js` presents DTOs with exact Decimal/vector sorting, presentation-only search and 50-row paging; totals never come from cells. `session.js` owns Snapshot/Live detail, canonical DOM identities, anchored paging, selection/focus protection and follow-latest. `src/application/session_detail.py` round-robins captures on the live thread and returns frozen revision-aware pages/full totals. `src/reports/session_history.py` retains canonical evidence outside durable caches; omissions freeze lifecycle/time rather than falsely complete rows. Unchanged running evidence reuses attribution/valuation. Web?application?reports is unchanged; missing/archive/outage is not empty success. Scope/cache/route inventory: `docs/web-beta.md`.

`src/web/host.py` owns shutdown of HTTP/jobs and one `src/application/live.py` thread; GUI run/close stays on main. Composition transfers the Watch service to `src/watch/acquisition.py`; tabs only read detached values. Live persists without tabs, preserving engine-start origin and independent account cadence. Finite reports never borrow/close that context. Unexpected faults reach main RuntimeErrors (managed logs outside checkout); children monitor their exact parent sentinel. OpenCode is never stopped.

`src/web/events.py` publishes immutable full live/progress/terminal state with instance-bound IDs, 32-event/8 MiB replay and 2 MiB publications. `src/application/live_projection.py` allowlists Watch/tool/skill/context, subtotals and run/Today (not normal month/billing). `src/web/assets/live.js` owns one cookie-authenticated EventSource per tab. Gaps require HTTP resync; duplicates/older events cannot reset values; old instances require authorization. Terminal notices stop retry across gaps; offline retains evidence, never invents completion or launches servers.

`src/web/lifecycle.py` owns deliberate launcher restart, overlap coalescing, bounded readiness/stop and detached spawn. `src/web/instance_state.py` owns canonical checkout/user identity, transition and lifetime OS locks, private atomic records and bounded allowlisted lifecycle diagnostics. `src/web/process_identity.py` owns native birth/image proof and safe termination handles. `src/web/change_guard.py` owns the allowlisted five-second runtime metadata baseline and terminal source_changed state; it never reloads/restarts code.

`src/web/native_windows.py` owns same-process main-thread GUI integration and one asynchronous registered-browser handoff. `src/web/win32_tray.py` owns typed in-box Win32 resources/message dispatch and Explorer taskbar recovery; `src/web/tray_icon.py` owns the original source-rendered artwork. `src/web/windows_launch.py` and `src/web/windows_launch.ps1` own Beta-only Python/configuration/native preflight and sanitized failure feedback; stable terminal launchers do not import them. The Windows Beta batch delegates immediately to hidden PowerShell with null standard handles; batch exit acknowledges delegation, never readiness. Direct PowerShell invocation retains visible timed status. No Windows compiler/cache/daemon is added; the managed pythonw host and lifecycle remain the only readiness/ownership authority. See [native handoff evidence](../governance/verification/windows-handoff.md).

`src/web/startup.py` owns fixed, flushed, elapsed-time launcher stage text shared by Windows/macOS. Lifecycle's optional progress sink reports arbitration/restart/host/browser boundaries without receiving secrets. PowerShell streams it with indeterminate activity rather than buffering Python output. Browser startup is static branded HTML until authorization; initial report activity remains separate from HTTP/source/account readiness. No new supervisor, auth route, acquisition owner or dependency boundary is introduced.

`src/web/native_macos.py`, `macos_status.py` and `objc_bridge.py` own the experimental main-thread NSStatusItem, typed 64-bit callbacks/default-tracking pump, host-loss dismissal and asynchronous `/usr/bin/open`. `macos_launch.py` preflights in a bounded child; `macos_app.py` uses in-box osacompile for the optional fingerprinted/cache-verified Finder app. No new dependency/server owner. Native acceptance remains pending; exact limitations are in `docs/web-beta.md`.

## Public contract

`cost-guard-web.py --foreground` is explicit icon-free developer mode, independent of managed discovery and CLI. Only 127.0.0.1 with an assigned port is supported; exact Host/Origin and authenticated sensitive reads are mandatory. Standard-library only, no installation, updater, generic proxy/shell/filesystem routes or browser-side calculator. Accounts/source/analysis readiness remain independent of HTTP-shell readiness.

`windows/Beta/Cost-Guard-Web.cmd` and experimental `macos/Beta/Cost-Guard-Web.command` accept only approved adapters. Readiness requires a usable icon/event loop; GUI failure cannot advertise an unmanaged host. Native preflight precedes restart. Open uses the registered browser; Exit stops only its matching host. Detached handles/private cwd, no packages/downloaded compiler/service/autostart. macOS/Finder/Gatekeeper remains unverified; in-box osacompile is optional, never an SDK install. Mocks are not native proof.

Overlapping clicks coalesce; deliberate later launches restart. Private lifetime locks and nonce/PID/birth/image/port/build/schema/control records prevent duplicate or foreign ownership. Corrupt identity/reused PID is conflict, never kill authority. Graceful stop allows ten seconds; forced stop requires a revalidated Windows handle/Linux pidfd (macOS refuses). Other checkouts, CLI, browser, unknown port occupants and OpenCode are never stopped.

Private /control/status, /control/stop and /control/open require a separate secret header, exact Host, empty body and no Origin/Cookie. No control secret reaches browser storage or normal logs. Open issues a fresh one-use fragment without invalidating same-instance browser sessions; old-instance cookies/control fail against replacements. Browser-open failure is distinct from server failure and retryable via native Open.

Twelve HTTP slots admit four streams; ordinary requests have five-second absolute deadlines. Streams use sixty-second lifetimes, two-second writes, ten-second heartbeats/three-second reconnect. Finite work: four outstanding jobs, one process, sixteen results, 8 MiB/result, 120 seconds. Detail admission: sixteen observed trees, thirty-two handles; abandoned handles expire after five minutes, never rows/history. Stop publishes terminal state and joins owned work; retained `/api/live` stays readable while stopping. DTOs retain decimal strings/null/provisional values, not raw errors. No same-user-malware boundary.

Guard membership/mtime_ns/size covers shipped Python/assets/Beta launchers/root entries/manifests, excluding development/docs/user config/cache/log/bytecode/environment. No links are followed; stat errors retry the original baseline. Proven change triggers terminal source_changed/shutdown without browser acknowledgement. Identical metadata can be missed; no atomic-update/file-lock guarantee. Changed code needs manual launch.

Wire/adapter/resource details: `docs/web-beta.md`. No new permanent gate.

v80.89 stabilization: `security.py` names cookies by canonical checkout (not port); opaque session/CSRF values remain instance-specific. `observations.py` owns bounded numeric API/source/lifecycle facts, persisted through InstanceStore's private atomic `diagnostics.json` at most every five seconds plus shutdown. `development/tools/diagnostic_web.py` reads this checkout's snapshot and allowlisted lifecycle codes without importing/starting Web or reading the control record; bad/missing/stale facts are not readiness proof. Shutdown retains diagnostic facts after instance removal. No account/cache schema or analysis boundary changes. Full parity/native/privacy inventory and explicit platform limits: [stabilization evidence](../governance/verification/web-beta-stabilization.md).

`development/tests/test_web_views.py` / `development/tests/integration/web_views.cjs` exercise served assets/facade: navigation, exact sorting, filters, tiers, independent accounts, deferred history, long lists and frozen/stale/empty/missing/hostile-text states. Node is optional VM tooling, not visual/assistive-technology proof.

The shared numeric display seam is `src/display.py` / `src/numbers.py` → terminal and `src/application/display.py` → immutable DTO `display` / `display_roles` → `render.js`. Raw exact values remain separate sort keys. Application never imports terminal presentation; formatting never acquires or values usage. `development/tests/test_web_display.py` and `development/tests/integration/web_display.cjs` pin CLI-derived goldens. The [per-view display baseline](../governance/verification/web-display-parity.md) distinguishes formatting coverage, browser-only interactions and page-specific remaining work; it is not visual acceptance.

Overview's Normal layout is presentation-only: three concept/metric groups, reference models and notices, then compact account cards with visible attribution/error warnings and expandable observation details. `test_web_overview.py` / `integration/web_overview.cjs` compare the CLI and rendered default/tier/fallback order and formatting, then exact user sorting, stable unknown handling and server-order restoration. No acquisition or architecture-boundary change. On 2026-10-27 a real-source Normal result measured 8,501,873 bytes with default JSON whitespace (request identities alone 8,220,000 bytes); `jobs.run_report` now uses compact separators, retaining every provenance record and the unchanged 8 MiB admission ceiling. The byte-boundary regression is in `test_web_runtime.py`; larger results must still fail explicitly.

Models retains that canonical order and independent priced-completed sample in both selectable/full catalogs. `render.js` owns aligned multiplier/tier cells, exact native-rate numeric sort keys and blank fallback presentation; `reports.js` marks the active catalog. Projection exports only a classified verified-empty availability flag, never raw source-warning prose. `test_web_models.py` / `integration/web_models.cjs` compare CLI membership/order and exact native precision. Explicit-browser `integration/probe_web_models.py` exercises 1200px/360px light/dark layout, complete long names, tiers, scroll, filtering and default-order restoration using synthetic canonical reports. Run browser-profile probes before, not concurrently with, whole-tree package-copy tests. [Models evidence](../governance/verification/models-display-parity.md) records proof limits; no pricing, acquisition or architecture boundary changes.

## Allowed dependencies

Accounts' Normal-only detailed mode reuses `overviewAccounts` and shared card/semantic styles, not a new acquisition owner. `src/display.py` now owns the unchanged CLI `format_reset`, re-exported by terminal accounts; `with_display` propagates frozen `now_ms` to quota reset tokens in the configured timezone. Exact raw fields remain untouched. `test_web_accounts.py`, `fixtures/account_views.py` and `integration/web_accounts.cjs` cover equivalent CLI/DTO/DOM states, native amounts, periods, Pace and private-field exclusions. Explicit synthetic browser/keyboard evidence and its limits: [Accounts parity](../governance/verification/accounts-display-parity.md). No application/presentation import, report scope, formula, freshness or source/privacy boundary change; journal assessment: no-update, these durable owner facts suffice.

Web Watch's persistent table owner is `src/web/assets/watch.js`, delegated by `render.js`.
It retains one canonical-order 50-row table, inline session dividers, controls/row identities,
selection/focus protection and a visible-row scroll anchor. Account cards reuse the shared
Overview presenter without report month/billing scope substitution. `app.js` retains valid rows
across viewless source failures and feeds transport status into Watch. `live_projection.py`
exports latest Watch model and observation-time running duration separately from frozen prompt
metrics, matching CLI Watch without browser lifecycle/valuation calculations. No acquisition,
security or architecture-boundary change. `test_web_live.py` compares the same projection's CLI
cost/calls/duration/context cells with the DOM; `test_web_display.py` pins latest-progress values.
Optional `integration/probe_web_watch.py --browser <explicit executable> --output <owned JSON>`
checks real headless Chromium DOM/layout/selection at desktop/light and 360px/dark sizes using
synthetic canonical data and fixture transport. This is not real-source browser SSE, physical
input, screen-reader or macOS acceptance; independent HTTP/real-source probes retain those limits.

HTTP/security/assets and lifecycle/process/state/guard depend on standard library and their Web owners. Jobs consume shared application/report contracts. Composition alone wires concrete source/config/cache/pricing/providers and the Watch acquisition driver, never CLI dispatch/source wake. LiveRuntime consumes that supplied driver and exports immutable values; application/reports never import Web. CLI and Diagnostics do not import Web.

## Entrypoints

Runtime: `cost-guard-web.py`, `src/web/main.py`, `src/web/host.py`, `src/web/composition.py`, `src/web/http.py`, `src/web/assets/index.html`, `src/web/assets/app.js`, `src/web/assets/session.js`. Supporting lifecycle/security/process/asset owners are named above.

Native entries: `windows/Beta/Cost-Guard-Web.cmd`, `src/web/windows_launch.ps1`, `macos/Beta/Cost-Guard-Web.command`, `macos/Beta/launcher.applescript`. Generated applets stay outside Git, source/product/OS/architecture/Python-fingerprinted and hash-checked; failures preserve the command fallback.

## Tests

`development/tests/test_web_live.py` covers shared CLI/global projections, terminal transitions, partial pricing, midnight/DST, source recovery and hint resync, account-only publication, detached exports, replay/overflow/old instances, actual HTTP stream bounds/terminal delivery and stop beside a slow finite report. `development/tests/integration/web_live.cjs` exercises client ordering/offline/terminal/safe rendering in an optional Node VM, not a browser. Read-only `development/tests/integration/probe_web_live.py` observed V2, one owner/two streams, preserved run origin and joined shutdown on Windows/Python 3.14 on 2026-10-26. No inference, shared-service stop or native/visual/macOS acceptance is implied.

`development/tests/test_web_lifecycle.py` covers metadata changes/exclusions/faults, private state/locks/process identity, concurrent launches/restart, control/browser separation, main-thread/cleanup and force-stopped parent/blocked child. It uses an idle acquisition fixture, never live providers. `development/tests/test_runtime_errors.py` retains execution-root inventory. Windows process handles/locks are exercised; GUI assertions are not native tray/macOS proof.

`development/tests/test_web_runtime.py` / `development/tests/fixtures/web_reports.py` own wire/security/DTO/bounds/cancellation; `development/tests/test_application_reports.py` owns calculator parity. Read-only `development/tests/integration/probe_web_lifecycle.py` starts/stops only its own host. `development/tests/test_windows_web.py` covers adapter failure/readiness/Open/Exit, PowerShell discovery/arguments and private logs without UI. Approval-only `development/tests/integration/probe_windows_web.py` covers native menu/WM_COMMAND, browser failure, shutdown, transient consoles, overlap/restart, old-host preservation, source-change, independent Watch and spaces/Unicode ZIP launches. Windows 11/Python 3.14 observations date to 2026-10-26; physical mouse/visual/macOS acceptance remains untested. No inference or new gate.

`test_web_diagnostics.py` checks real two-checkout HTTP cookie-jar coexistence, bounded/allowlisted diagnostic export, missing/corrupt/oversize facts, write failure and retained shutdown evidence; replacement credential rejection is in `test_web_runtime.py`. `integration/probe_web_bounds.py` measures 5,000 synthetic replay publications/three simulated tabs and virtual authentication expiry, not physical suspend or hours-long soak. Native source-change probes must not overlap real-source probes of the same checkout.

`development/tests/test_macos_web.py` / `development/tests/test_macos_app.py` cover typed callbacks/faults, main-thread/tracking timers, preflight/readiness/cleanup, asynchronous actions and cache/quoting/rebuild failures without AppKit/UI. Approval-only `development/tests/integration/probe_macos_web.py` was not run here. Finder/Gatekeeper/clone/ZIP/executable-bit/no-Terminal/browser/tracking/source-change/orphan/CPU-architecture checks remain pending as documented in `docs/web-beta.md`.

`development/tests/test_web_session_detail.py` / `development/tests/integration/web_session.cjs` cover 100/1,000/10,000-prompt first/middle/latest access, full totals, bounded pages/DOM, strict timestamp windows, unchanged work, row identity/anchor/focus/selection, transitions, omissions/outages/reconnect and late children/partial prices. `development/tests/integration/probe_web_live.py` with --detail --reports observed V2 detail/freeze, normal/all-models/sessions/date completion and cancelled deep history, preserving one owner/two streams/run origin and joined shutdown on 2026-10-26. No browser or model was invoked. Copy/selection covers the fetched page; physical layout and screen-reader proof remain unclaimed.

Remaining report presentation shares `display.history_tokens` for configured prompt clocks,
Next Ictx guidance and CLI historical mix category cells. `projection.token_mix` exports the
exact aggregate cost separately for sorting; JavaScript never totals displayed cells.
Session summary/footer use the same frozen block tokens; Freeze/Follow forces a mode-aware
redraw without changing canonical row IDs or page ownership. Date range prose omits raw
epoch boundaries. `test_web_remaining.py` / `integration/web_remaining.cjs` compare the same
CLI fixtures, including partial/unknown mix coverage. Approval-only
`integration/serve_web_remaining.py` serves the actual app over synthetic HTTP fixtures,
never a product host or provider. The [owner matrix](../governance/verification/remaining-web-parity.md)
records Windows built-in-browser inspection and remaining native/assistive limitations.
Architecture boundaries are unchanged; journal assessment: no-update, these owner facts
and the focused evidence are sufficient.

## Native launcher maintenance notes

PowerShell 5.1: preserve `[array]$pythonArgs` (scalar `-3` splatting lost the command in a real probe). Use DirectoryInfo.SetAccessControl/private DACL, not Set-Acl requiring SeSecurityPrivilege. AST-extracted production functions/assignments test real py.exe handoff/private logs. Never elevate or change global policy. These owner facts replace a redundant journal log; historical evidence is unchanged.
