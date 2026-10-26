# Optional Web runtime

Source revision: f493998fdf1278af2ede23f63d5f97ccb96170bc
Checked revision: f493998fdf1278af2ede23f63d5f97ccb96170bc
Last checked: 2026-10-26
Status: current

## Responsibility and ownership

`src/web/http.py` owns bounded loopback HTTP, fixed assets and routing; `src/web/security.py` owns one-use bootstrap/HttpOnly sessions/CSRF; `src/web/jobs.py` owns finite admission, process isolation, progress, cancellation and retention. `src/web/composition.py` creates fresh canonical ReportApplication integrations.

`src/web/assets/app.js` owns fragment navigation, memory-only views and finite job refresh/stale/cancel state. `render.js` presents allowlisted DTOs as text-only tables. All-roots listing requests null session_limit; finite job limits fail explicitly. `session.js` owns explicit Snapshot/Live detail, one fetched 50-row page, canonical DOM identities, anchored paging, selection/focus protection and follow-latest. `src/application/session_detail.py` admits shared captures on the existing live thread, round-robins due sessions, freezes immutable report revisions and returns anchor-aware pages with complete totals. `src/reports/session_history.py` retains canonical observations outside persistent caches and reuses detailed report metrics; omissions freeze lifecycle/time, not falsely complete rows. Unchanged running evidence reuses attribution/valuation and updates only shared execution timing. No browser calculator, prompt cap or ledger. Remaining dedicated views stay honestly unavailable. Direction remains Web→application→reports; missing/archived/outage is not empty success.

`src/web/host.py` owns shutdown of HTTP/jobs and one `src/application/live.py` thread; GUI run/close stays on main. Composition transfers the Watch service to `src/watch/acquisition.py`; tabs only read detached values. Live persists without tabs, preserving engine-start origin and independent account cadence. Finite reports never borrow/close that context. Unexpected faults reach main RuntimeErrors (managed logs outside checkout); children monitor their exact parent sentinel. OpenCode is never stopped.

`src/web/events.py` publishes immutable full live/progress/terminal state with instance-bound IDs, 32-event/8 MiB replay and 2 MiB publications. `src/application/live_projection.py` allowlists Watch/tool/skill/context, subtotals and run/Today (not normal month/billing). `src/web/assets/live.js` owns one cookie-authenticated EventSource per tab. Gaps require HTTP resync; duplicates/older events cannot reset values; old instances require authorization. Terminal notices stop retry across gaps; offline retains evidence, never invents completion or launches servers.

`src/web/lifecycle.py` owns deliberate launcher restart, overlap coalescing, bounded readiness/stop and detached spawn. `src/web/instance_state.py` owns canonical checkout/user identity, transition and lifetime OS locks, private atomic records and bounded allowlisted lifecycle diagnostics. `src/web/process_identity.py` owns native birth/image proof and safe termination handles. `src/web/change_guard.py` owns the allowlisted five-second runtime metadata baseline and terminal source_changed state; it never reloads/restarts code.

`src/web/native_windows.py` owns same-process main-thread GUI integration and one asynchronous registered-browser handoff. `src/web/win32_tray.py` owns typed in-box Win32 resources/message dispatch and Explorer taskbar recovery; `src/web/tray_icon.py` owns the original source-rendered artwork. `src/web/windows_launch.py` and `src/web/windows_launch.ps1` own Beta-only Python/configuration/native preflight and sanitized failure feedback; stable terminal launchers do not import them.

`src/web/native_macos.py`, `macos_status.py` and `objc_bridge.py` own the experimental main-thread NSStatusItem, typed 64-bit callbacks/default-tracking pump, host-loss dismissal and asynchronous `/usr/bin/open`. `macos_launch.py` preflights in a bounded child; `macos_app.py` uses in-box osacompile for the optional fingerprinted/cache-verified Finder app. No new dependency/server owner. Native acceptance remains pending; exact limitations are in `docs/web-beta.md`.

## Public contract

`cost-guard-web.py --foreground` is explicit icon-free developer mode, independent of managed discovery and CLI. Only 127.0.0.1 with an assigned port is supported; exact Host/Origin and authenticated sensitive reads are mandatory. Standard-library only, no installation, updater, generic proxy/shell/filesystem routes or browser-side calculator. Accounts/source/analysis readiness remain independent of HTTP-shell readiness.

`windows/Beta/Cost Guard Web.cmd` and experimental `macos/Beta/Cost Guard Web.command` accept only approved adapters. Readiness requires a usable icon/event loop; GUI failure cannot advertise an unmanaged host. Native preflight precedes restart. Open uses the registered browser; Exit stops only its matching host. Detached handles/private cwd, no packages/downloaded compiler/service/autostart. macOS/Finder/Gatekeeper remains unverified; in-box osacompile is optional, never an SDK install. Mocks are not native proof.

Overlapping clicks coalesce; deliberate later launches restart. Private lifetime locks and nonce/PID/birth/image/port/build/schema/control records prevent duplicate or foreign ownership. Corrupt identity/reused PID is conflict, never kill authority. Graceful stop allows ten seconds; forced stop requires a revalidated Windows handle/Linux pidfd (macOS refuses). Other checkouts, CLI, browser, unknown port occupants and OpenCode are never stopped.

Private /control/status, /control/stop and /control/open require a separate secret header, exact Host, empty body and no Origin/Cookie. No control secret reaches browser storage or normal logs. Open issues a fresh one-use fragment without invalidating same-instance browser sessions; old-instance cookies/control fail against replacements. Browser-open failure is distinct from server failure and retryable via native Open.

Twelve HTTP slots admit four streams; ordinary requests have five-second absolute deadlines. Streams use sixty-second lifetimes, two-second writes, ten-second heartbeats/three-second reconnect. Finite work: four outstanding jobs, one process, sixteen results, 8 MiB/result, 120 seconds. Detail admission: sixteen observed trees, thirty-two handles; abandoned handles expire after five minutes, never rows/history. Stop publishes terminal state and joins owned work; retained `/api/live` stays readable while stopping. DTOs retain decimal strings/null/provisional values, not raw errors. No same-user-malware boundary.

Guard membership/mtime_ns/size checks cover shipped Python/assets, Web Beta runtime launcher trees, root entries and manifests. Development/docs/user configuration/cache/log/bytecode/environment writes are excluded; links are never traversed. Stat errors retry honestly against the original baseline. Proven change immediately enters terminal source_changed and invokes the same shutdown without browser acknowledgement. Identical metadata can be missed; this is not atomic updating or a guarantee against Windows file locks. Manual launch alone starts changed code.

API fields, private adapter protocol, limits and recovery constraints: `docs/web-beta.md`. No permanent release gate is introduced.

`development/tests/test_web_views.py` / `development/tests/integration/web_views.cjs` exercise served assets/HTTP/shared facade: long lists, full totals, snapshot isolation, lifecycle/partial/hostile text, missing versus empty and hash/deep-link navigation. Optional installed Node is a VM test tool, not a runtime/build dependency. Real browser layout/light-dark/resize/assistive technology remain owner validation.

## Allowed dependencies

HTTP/security/assets and lifecycle/process/state/guard depend on standard library and their Web owners. Jobs consume shared application/report contracts. Composition alone wires concrete source/config/cache/pricing/providers and the Watch acquisition driver, never CLI dispatch/source wake. LiveRuntime consumes that supplied driver and exports immutable values; application/reports never import Web. CLI and Diagnostics do not import Web.

## Entrypoints

Runtime: `cost-guard-web.py`, `src/web/main.py`, `src/web/host.py`, `src/web/composition.py`, `src/web/http.py`, `src/web/assets/index.html`, `src/web/assets/app.js`, `src/web/assets/session.js`. Supporting lifecycle/security/process/asset owners are named above.

Native entries: `windows/Beta/Cost Guard Web.cmd`, `src/web/windows_launch.ps1`, `macos/Beta/Cost Guard Web.command`, `macos/Beta/launcher.applescript`. Generated applets stay outside Git, source/product/OS/architecture/Python-fingerprinted and hash-checked; failures preserve the command fallback.

## Tests

`development/tests/test_web_live.py` covers shared CLI/global projections, terminal transitions, partial pricing, midnight/DST, source recovery and hint resync, account-only publication, detached exports, replay/overflow/old instances, actual HTTP stream bounds/terminal delivery and stop beside a slow finite report. `development/tests/integration/web_live.cjs` exercises client ordering/offline/terminal/safe rendering in an optional Node VM, not a browser. Read-only `development/tests/integration/probe_web_live.py` observed V2, one owner/two streams, preserved run origin and joined shutdown on Windows/Python 3.14 on 2026-10-26. No inference, shared-service stop or native/visual/macOS acceptance is implied.

`development/tests/test_web_lifecycle.py` covers metadata changes/exclusions/faults, private state/locks/process identity, concurrent launches/restart, control/browser separation, main-thread/cleanup and force-stopped parent/blocked child. It uses an idle acquisition fixture, never live providers. `development/tests/test_runtime_errors.py` retains execution-root inventory. Windows process handles/locks are exercised; GUI assertions are not native tray/macOS proof.

`development/tests/test_web_runtime.py` / `development/tests/fixtures/web_reports.py` own wire/security/DTO/bounds/cancellation; `development/tests/test_application_reports.py` owns calculator parity. Read-only `development/tests/integration/probe_web_lifecycle.py` starts/stops only its own host. `development/tests/test_windows_web.py` covers adapter failure/readiness/Open/Exit, PowerShell discovery/arguments and private logs without UI. Approval-only `development/tests/integration/probe_windows_web.py` covers native menu/WM_COMMAND, browser failure, shutdown, transient consoles, overlap/restart, old-host preservation, source-change, independent Watch and spaces/Unicode ZIP launches. Windows 11/Python 3.14 observations date to 2026-10-26; physical mouse/visual/macOS acceptance remains untested. No inference or new gate.

`development/tests/test_macos_web.py` / `development/tests/test_macos_app.py` cover typed callbacks/faults, main-thread/tracking timers, preflight/readiness/cleanup, asynchronous actions and cache/quoting/rebuild failures without AppKit/UI. Approval-only `development/tests/integration/probe_macos_web.py` was not run here. Finder/Gatekeeper/clone/ZIP/executable-bit/no-Terminal/browser/tracking/source-change/orphan/CPU-architecture checks remain pending as documented in `docs/web-beta.md`.

`development/tests/test_web_session_detail.py` / `development/tests/integration/web_session.cjs` cover 100/1,000/10,000-prompt first/middle/latest access, full totals, bounded pages/DOM, strict timestamp windows, unchanged work, row identity/anchor/focus/selection, transitions, omissions/outages/reconnect and late children/partial prices. `development/tests/integration/probe_web_live.py --detail` observed real V2 complete detail/freeze, one owner/two streams and joined shutdown on 2026-10-26. No browser or model was invoked. Copy/selection covers the fetched page; physical layout and screen-reader proof remain unclaimed.

## Native launcher maintenance notes

PowerShell 5.1 requires preserving `[array]$pythonArgs` after function return: a scalar single `-3` splat lost the intended native command in a real probe. Use DirectoryInfo.SetAccessControl with the private DACL, not Set-Acl: the latter required SeSecurityPrivilege on the tested workstation. Regression tests extract the actual production function/assignment with the PowerShell AST and verify a real py.exe handoff and private-log writes. Do not request elevation or modify global policy to repair either failure. These current owner facts replace a redundant journal/test log; existing journal history is unchanged.
