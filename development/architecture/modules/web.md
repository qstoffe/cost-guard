# Optional Web runtime

Source revision: 06520e102043dad097df82e05ca8a50478b051b0
Checked revision: 06520e102043dad097df82e05ca8a50478b051b0
Last checked: 2026-10-26
Status: current

## Responsibility and ownership

`src/web/http.py` owns bounded loopback HTTP, fixed assets and routing; `src/web/security.py` owns one-use bootstrap/HttpOnly sessions/CSRF; `src/web/jobs.py` owns finite admission, process isolation, progress, cancellation and retention. `src/web/composition.py` creates fresh canonical ReportApplication integrations.

`src/web/host.py` is the single stop owner: HTTP/jobs run on its owned worker; native adapter run/close remain on the main thread. A failed worker signals the GUI, closes jobs/sockets and hands its original software fault to the main RuntimeErrors boundary. Managed faults use private app-data logs; foreground retains the normal reporter. Finite report children monitor multiprocessing's exact parent sentinel and exit nonzero if the host dies, even during blocked scans. No shared OpenCode service or Watch scheduler is owned here. Future live workers must join this same lifecycle, not create independent stop owners.

`src/web/lifecycle.py` owns deliberate launcher restart, overlap coalescing, bounded readiness/stop and detached spawn. `src/web/instance_state.py` owns canonical checkout/user identity, transition and lifetime OS locks, private atomic records and bounded allowlisted lifecycle diagnostics. `src/web/process_identity.py` owns native birth/image proof and safe termination handles. `src/web/change_guard.py` owns the allowlisted five-second runtime metadata baseline and terminal source_changed state; it never reloads/restarts code.

## Public contract

`cost-guard-web.py --foreground` is explicit icon-free developer mode, independent of managed discovery and CLI. Only 127.0.0.1 with an assigned port is supported; exact Host/Origin and authenticated sensitive reads are mandatory. Standard-library only, no installation, updater, generic proxy/shell/filesystem routes or browser-side calculator. Accounts/source/analysis readiness remain independent of HTTP-shell readiness.

Managed launch accepts only the fixed future native Windows/macOS adapters. Their GUI must publish readiness only after the icon/event loop is usable and remove the icon when owner.stopped is set; missing/failed GUI cannot leave an advertised unmanaged host. Native modules and everyday launchers are delivered by the following OS FRs, not this foundation. Popen detaches handles/console/session and uses private cwd; mocked flags are not native GUI/terminal-lifetime proof.

Overlapping clicks reuse a ready winner; later deliberate clicks restart even the same version. A lifetime lock prevents duplicates after launcher failure. Private records bind nonce, PID/birth/image, port, startup build/schema and a control secret. Wrong/corrupt identity is a conflict; stale/reused PIDs grant no kill authority. Graceful deadline is ten seconds. Windows force-stop uses a revalidated kernel handle, Linux pidfd; macOS currently refuses unsafe forced termination. No other checkout, CLI, browser, unknown port occupant or OpenCode process is stopped.

Private /control/status, /control/stop and /control/open require a separate secret header, exact Host, empty body and no Origin/Cookie. No control secret reaches browser storage or normal logs. Open issues a fresh one-use fragment without invalidating same-instance browser sessions; old-instance cookies/control fail against replacements. Browser-open failure is distinct from server failure and retryable via native Open.

Eight HTTP slots, five-second absolute wire deadlines, four outstanding jobs, one report process, sixteen retained results, 8 MiB/result and 120-second whole-job deadline bound work. Stop rejects new APIs and closes owned work only. Result DTOs retain decimal strings/null/provisional fields, never raw errors. This is not a same-user-malware boundary.

Guard membership/mtime_ns/size checks cover shipped Python/assets, Web Beta runtime launcher trees, root entries and manifests. Development/docs/user configuration/cache/log/bytecode/environment writes are excluded; links are never traversed. Stat errors retry honestly against the original baseline. Proven change immediately enters terminal source_changed and invokes the same shutdown without browser acknowledgement. Identical metadata can be missed; this is not atomic updating or a guarantee against Windows file locks. Manual launch alone starts changed code.

API fields, private adapter protocol, limits and recovery constraints: `docs/web-beta.md`. No permanent release gate is introduced.

## Allowed dependencies

HTTP/security/assets and lifecycle/process/state/guard depend on standard library and their Web owners. Jobs consume shared application/report contracts. Composition alone wires concrete source/config/cache/pricing/providers and reuses bootstrap integration wiring, never CLI dispatch/source wake or Watch. CLI and Diagnostics do not import Web. Application/reports never import Web.

## Entrypoints

`cost-guard-web.py`, `src/web/main.py`, `src/web/host.py`, `src/web/lifecycle.py`, `src/web/instance_state.py`, `src/web/process_identity.py`, `src/web/change_guard.py`, `src/web/http.py`, `src/web/jobs.py`, `src/web/security.py`, `src/web/composition.py`, `src/web/assets/index.html`, `src/web/assets/app.js`, `src/web/assets/app.css`.

## Tests

`development/tests/test_web_lifecycle.py` covers synthetic source changes/exclusions/stat errors/metadata misses, private records/logs, OS locks and crash release, process birth/reuse/termination, different/Unicode/case-normalized checkouts, concurrent launch coalescing, same-build restart, failed startup/browser, control/browser separation, old sessions, GUI-main-thread contracts, fatal cleanup and a real force-stopped parent with a blocked child. `development/tests/test_runtime_errors.py` retains the execution-root inventory guard. Native Windows process handles/locks are exercised locally; GUI/detachment assertions are not native tray/macOS proof.

`development/tests/test_web_runtime.py` owns synthetic wire/security/DTO/bounds/cancellation tests with `development/tests/fixtures/web_reports.py`; `development/tests/test_application_reports.py` owns broader calculator parity. All are included in Full. Opt-in `development/tests/integration/probe_web_lifecycle.py` probes real read-only source/session acquisition and authenticated stop of only its own host, with no browser/model inference. Diagnostics is separate from default-denied live-model tests. Real native launcher/icon/terminal-lifetime verification belongs to the OS FRs.
