# Optional Web runtime

Source revision: 1f2dee7603df95bbed6cb893126c65ed5a336799
Checked revision: 1f2dee7603df95bbed6cb893126c65ed5a336799
Last checked: 2026-10-26
Status: current

## Responsibility and ownership

`src/web/http.py` owns bounded loopback HTTP, fixed assets and routing; `src/web/security.py` owns one-use bootstrap/HttpOnly sessions/CSRF; `src/web/jobs.py` owns finite admission, process isolation, progress, cancellation and retention. `src/web/composition.py` creates fresh canonical ReportApplication integrations.

`src/web/host.py` is the single stop owner: HTTP/jobs run on its owned worker; native adapter run/close remain on the main thread. A failed worker signals the GUI, closes jobs/sockets and hands its original software fault to the main RuntimeErrors boundary. Managed faults use private app-data logs; foreground retains the normal reporter. Finite report children monitor multiprocessing's exact parent sentinel and exit nonzero if the host dies, even during blocked scans. No shared OpenCode service or Watch scheduler is owned here. Future live workers must join this same lifecycle, not create independent stop owners.

`src/web/lifecycle.py` owns deliberate launcher restart, overlap coalescing, bounded readiness/stop and detached spawn. `src/web/instance_state.py` owns canonical checkout/user identity, transition and lifetime OS locks, private atomic records and bounded allowlisted lifecycle diagnostics. `src/web/process_identity.py` owns native birth/image proof and safe termination handles. `src/web/change_guard.py` owns the allowlisted five-second runtime metadata baseline and terminal source_changed state; it never reloads/restarts code.

`src/web/native_windows.py` owns same-process main-thread GUI integration and one asynchronous registered-browser handoff. `src/web/win32_tray.py` owns typed in-box Win32 resources/message dispatch and Explorer taskbar recovery; `src/web/tray_icon.py` owns the original source-rendered artwork. `src/web/windows_launch.py` and `src/web/windows_launch.ps1` own Beta-only Python/configuration/native preflight and sanitized failure feedback; stable terminal launchers do not import them.

## Public contract

`cost-guard-web.py --foreground` is explicit icon-free developer mode, independent of managed discovery and CLI. Only 127.0.0.1 with an assigned port is supported; exact Host/Origin and authenticated sensitive reads are mandatory. Standard-library only, no installation, updater, generic proxy/shell/filesystem routes or browser-side calculator. Accounts/source/analysis readiness remain independent of HTTP-shell readiness.

`windows/Beta/Cost Guard Web.cmd` launches the managed Windows adapter; macOS is not yet shipped. Managed launch accepts only fixed approved adapters. Readiness follows usable icon/event loop, and stopping/stopped removes the icon; missing/failed GUI cannot leave an advertised unmanaged host. Windows preflight exercises the real native resources before shared lifecycle restart. Open hands off to the registered URL association without restart; Exit stops only the matching host. Popen detaches console/standard handles and uses private cwd. No packages, compiler, downloads, service or autostart; mocked flags alone are not native proof.

Overlapping clicks reuse a ready winner; later deliberate clicks restart even the same version. A lifetime lock prevents duplicates after launcher failure. Private records bind nonce, PID/birth/image, port, startup build/schema and a control secret. Wrong/corrupt identity is a conflict; stale/reused PIDs grant no kill authority. Graceful deadline is ten seconds. Windows force-stop uses a revalidated kernel handle, Linux pidfd; macOS currently refuses unsafe forced termination. No other checkout, CLI, browser, unknown port occupant or OpenCode process is stopped.

Private /control/status, /control/stop and /control/open require a separate secret header, exact Host, empty body and no Origin/Cookie. No control secret reaches browser storage or normal logs. Open issues a fresh one-use fragment without invalidating same-instance browser sessions; old-instance cookies/control fail against replacements. Browser-open failure is distinct from server failure and retryable via native Open.

Eight HTTP slots, five-second absolute wire deadlines, four outstanding jobs, one report process, sixteen retained results, 8 MiB/result and 120-second whole-job deadline bound work. Stop rejects new APIs and closes owned work only. Result DTOs retain decimal strings/null/provisional fields, never raw errors. This is not a same-user-malware boundary.

Guard membership/mtime_ns/size checks cover shipped Python/assets, Web Beta runtime launcher trees, root entries and manifests. Development/docs/user configuration/cache/log/bytecode/environment writes are excluded; links are never traversed. Stat errors retry honestly against the original baseline. Proven change immediately enters terminal source_changed and invokes the same shutdown without browser acknowledgement. Identical metadata can be missed; this is not atomic updating or a guarantee against Windows file locks. Manual launch alone starts changed code.

API fields, private adapter protocol, limits and recovery constraints: `docs/web-beta.md`. No permanent release gate is introduced.

## Allowed dependencies

HTTP/security/assets and lifecycle/process/state/guard depend on standard library and their Web owners. Jobs consume shared application/report contracts. Composition alone wires concrete source/config/cache/pricing/providers and reuses bootstrap integration wiring, never CLI dispatch/source wake or Watch. CLI and Diagnostics do not import Web. Application/reports never import Web.

## Entrypoints

`windows/Beta/Cost Guard Web.cmd`, `src/web/windows_launch.ps1`, `src/web/windows_launch.py`, `src/web/native_windows.py`, `src/web/win32_tray.py`, `src/web/tray_icon.py`, `cost-guard-web.py`, `src/web/main.py`, `src/web/host.py`, `src/web/lifecycle.py`, `src/web/instance_state.py`, `src/web/process_identity.py`, `src/web/change_guard.py`, `src/web/http.py`, `src/web/jobs.py`, `src/web/security.py`, `src/web/composition.py`, `src/web/assets/index.html`, `src/web/assets/app.js`, `src/web/assets/app.css`.

## Tests

`development/tests/test_web_lifecycle.py` covers synthetic source changes/exclusions/stat errors/metadata misses, private records/logs, OS locks and crash release, process birth/reuse/termination, different/Unicode/case-normalized checkouts, concurrent launch coalescing, same-build restart, failed startup/browser, control/browser separation, old sessions, GUI-main-thread contracts, fatal cleanup and a real force-stopped parent with a blocked child. `development/tests/test_runtime_errors.py` retains the execution-root inventory guard. Native Windows process handles/locks are exercised locally; GUI/detachment assertions are not native tray/macOS proof.

`development/tests/test_web_runtime.py` owns synthetic wire/security/DTO/bounds/cancellation tests with `development/tests/fixtures/web_reports.py`; `development/tests/test_application_reports.py` owns broader calculator parity. All are included in Full. Opt-in `development/tests/integration/probe_web_lifecycle.py` probes real read-only source/session acquisition and authenticated stop of only its own host, with no browser/model inference. Diagnostics is separate from default-denied live-model tests. `development/tests/test_windows_web.py` covers synthetic adapter readiness, asynchronous Open/Exit, worker faults, native preflight failure preserving the old host, and real PowerShell 5.1 Python discovery/argument and private-log contracts without UI. Opt-in `development/tests/integration/probe_windows_web.py` requires UI approval: native menu labels/WM_COMMAND delivery, failed browser notification, Exit/fault cleanup, offline shell, transient-console survival, overlap/restart, injected tray failure retaining a healthy instance, source-change exit, independent real CLI Watch and ShellExecute source-ZIP paths with spaces/Unicode. Windows 11/Python 3.14 native checks were observed on 2026-10-26; physical mouse double-click, visual light/dark review and macOS remain untested. No model inference or new permanent release gate.

## Native launcher maintenance notes

PowerShell 5.1 requires preserving `[array]$pythonArgs` after function return: a scalar single `-3` splat lost the intended native command in a real probe. Use DirectoryInfo.SetAccessControl with the private DACL, not Set-Acl: the latter required SeSecurityPrivilege on the tested workstation. Regression tests extract the actual production function/assignment with the PowerShell AST and verify a real py.exe handoff and private-log writes. Do not request elevation or modify global policy to repair either failure. These current owner facts replace a redundant journal/test log; existing journal history is unchanged.
