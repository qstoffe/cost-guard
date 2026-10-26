# Foreground Web Beta

Run `python cost-guard-web.py --foreground` using already installed Python 3.11+. It binds **127.0.0.1 only**, on an OS-assigned port. There is no LAN/proxy mode, install step, frontend build or automatic browser launch in this explicit developer mode. Leave the console open. Ctrl+C or a detected runtime-source change stops only this host and its owned finite reports; it does not stop OpenCode. Foreground instances are intentionally separate from managed launcher discovery. Everyday native launchers/icons follow in the OS-specific FRs; the shared lifecycle below is their foundation, not a currently shipped tray application.

## Browser session and privacy

Open the console's `/#bootstrap=…` link within 120 seconds. JavaScript immediately removes the fragment with `history.replaceState`, then POSTs it once to `/api/bootstrap`. The server issues an instance-scoped HttpOnly SameSite=Strict cookie with an eight-hour lifetime and a separate CSRF value held only in page memory. Reloads recover CSRF through the authenticated `/api/session` route. Replay, expiration and other instances are rejected. Restart this foreground host for a new bootstrap link. The console link is an intentional short-lived handoff to the foreground owner, not a reusable control token; do not save/share it or capture startup output in general-purpose logs.

Sensitive reads require the cookie. All POST requests require exact Origin and JSON content type; authenticated POSTs additionally require `X-CG-CSRF`. Every request checks the exact Host and assigned port, rejects foreign Origin/Fetch-Site, ambiguous framing and unsafe targets. No CORS access is granted. Packaged assets are fixed, local and symlink/junction-checked, not a general file server. Responses are no-store, deny frames/service workers and third-party runtime assets, and use restrictive CSP. Report text is inserted with `textContent`, never HTML. Access/error request logging is disabled; failures expose allowlisted codes, never source exception messages.

This is loopback HTTP, not a public server or protection against malware/other code executing as the same OS user. A separate persistent launcher/control credential exists only in private local instance state, never in page responses, browser storage or logs. Provider credentials never enter URLs or browser storage. No generic OpenCode proxy, source mutation, shell-command or arbitrary path API exists.

## Allowlisted routes

| Route | Method | Meaning |
| --- | --- | --- |
| `/`, `/app.js`, `/app.css` | GET | Fixed public Beta shell/assets, no history |
| `/health` | GET | Public HTTP-shell readiness only |
| `/api/bootstrap` | POST | One-use `{"credential":"…"}` exchange with exact Origin |
| `/api/session` | GET | Authenticated CSRF recovery, no control credential |
| `/api/status` | GET | Separate HTTP, analysis, source and account acquisition states |
| `/api/reports` | POST | Enqueue/coalesce a finite report; return job ID (202) |
| `/api/jobs/<id>` | GET | Authenticated status/progress/result |
| `/api/jobs/<id>/cancel` | POST | Cancel owned queued/running work with `{}` |

Reports select `kind`: `normal` (overview), `all-models` (catalog), `sessions`, `session`, `date` or `token-mix`. `session` requires an alphanumeric/underscore/hyphen `session_id` (max 200); `date` requires the existing CLI `date_text` syntax (max 32). `sessions` accepts `session_limit`: 1–10000 or null for all, default 20. Other fields are rejected. There are no query-string or arbitrary path parameters. Reports export the shared application's explicit DTOs, retaining exact decimal **strings**, null unknowns, provisional flags and CLI-projected labels; the page does not calculate costs. Empty acquired lists, acquisition errors, partial source evidence and genuine priced zero remain distinct. Account `reported` means inspect the report's independent observation statuses, not that all accounts are healthy or atomic with history.

## Resource and failure boundaries

- Eight HTTP workers/admitted sockets, bounded listen backlog; two-second socket timeouts and an absolute five-second request deadline, including dripping clients. Connections always close after one request.
- Request line <=2048 bytes, aggregate headers <=16 KiB, individual header lines <4096 bytes, JSON body <=4096 bytes. Duplicate headers/JSON keys, transfer encoding, non-JSON controls and unsupported methods are denied. No autoreload or directory listing.
- At most four queued/running reports and one spawned analysis process. Identical in-flight requests coalesce. Sixteen jobs retained; old completed/cancelled entries are evicted, so a missing ID is not an empty report.
- A fresh ReportApplication/ReportService owns each job's mutable integrations and one-shot account cleanup. Existing integration request timeouts apply; a 120-second hard process deadline bounds whole-job work. Cancellation/shutdown terminate and join only that owned process. No live scheduler is shared or cleaned by these one-shot jobs.
- Results are limited to 8 MiB per job. Oversize results return `result_too_large`; scope the request instead. Long historical Token Mix may time out; it never requires waiting for the scan to finish before shutdown. Job progress contains only approved phase/count values, not source text.

The shell remains reachable with offline/loading sources. It is intentionally an early report/API surface: no live dashboard, native tray or autostart yet. Tests use synthetic read-only sources; local read-only source probes are separate from paid/live-model tests.

## Shared managed lifecycle (native launcher integration contract)

`src/web/lifecycle.py:launch(root, gui_module)` is the trusted Python launcher interface. Only the fixed future `src.web.native_windows` / `src.web.native_macos` adapters are accepted. They are not shipped by this change; missing adapters fail before advertising a usable server. Do not manually use the private `--managed` child arguments as an unmanaged background mode. No third-party GUI package, service, autostart or downloaded helper is required or installed.

- Identity is SHA-256 of the resolved canonical checkout path (Windows case-normalized). Private state lives under `%LOCALAPPDATA%/CostGuard/Web/<identity>` on Windows, `~/Library/Application Support/CostGuard/Web/<identity>` on macOS, and `$XDG_STATE_HOME/CostGuard/Web/<identity>` (default `~/.local/state`) elsewhere. Protected owner-only inherited Windows DACLs or Unix 0700 directories/0600 files protect state; linked/reparse ancestors are rejected. Nonce, PID/birth/image, loopback port, schema/build, readiness timestamp and control secret are atomically persisted. Nothing is written to Git for instance ownership.
- An OS-held transition lock serializes launcher operations. A second lifetime lock held by the child prevents duplicates even if a launcher crashes before readiness. A click begun before the winner becomes ready reuses that winner; a later deliberate invocation restarts it even without a version change. Different checkouts have different identities/locks. Available ports are assigned by the OS; previous port occupants are never terminated.
- Restart requests authenticated graceful shutdown and waits up to ten seconds. Owned finite report jobs are cancelled/joined; HTTP sockets have a five-second hard deadline. Forced termination revalidates exact process birth/image using a retained Windows kernel handle or Linux pidfd. Platforms without an atomic process handle (currently macOS) refuse force-stop and report a conflict if graceful shutdown fails, rather than race PID reuse. A changed/dead PID is stale, not authority over its replacement. A responding wrong-nonce/auth/schema/build endpoint is a conflict, not authority to kill a port occupant.
- Corrupt/incompatible state is an explicit conflict: it cannot establish that no host exists. Do not blindly delete it and relaunch; first establish the old host has stopped. Stale valid records recover automatically. No scan/kill by process name, port, Python executable or OpenCode identity is used.
- Child stdin/stdout/stderr are detached to the null device, inherited handles are closed, and cwd is private app data, not the checkout. Windows uses `DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP`; Unix uses a new session. Owned lifecycle diagnostics contain only timestamp/allowlisted codes in a roughly 32 KiB rotating log; no URLs, bootstrap/control secrets, raw exceptions or account/source data. Browser failure is returned separately from server startup failure; native Open can retry without restarting.
- `WebHost.run_gui(gui)` stays on the main thread. The adapter's `run(owner)` must create the required native icon/event loop, call `owner.publish_ready()` only once usable, route Open to `owner.open_browser()`, route Exit to `owner.stop()`, and observe `owner.stopped` so a dead HTTP worker removes the icon. `gui.close()` is idempotent and runs on the main thread in all exit paths. HTTP/jobs run on the owned worker thread. A missing/failed/returned GUI stops the server, never silently falling back to an unmanaged background host. Future source/SSE/account workers must join this same stop owner; no live workers exist yet.
- Readiness means shell plus required GUI only, not account/history loading. A browser Open handoff receives a fresh 120-second one-use fragment via authenticated control; existing same-instance sessions stay valid. New instances have independent cookies, CSRF, nonce and control secrets, so old clients cannot control a replacement.

Private `/control/status` (GET), `/control/stop` and `/control/open` (POST) require `X-CG-Control`, exact Host, no Origin, no Cookie and empty bodies. They are not browser APIs and never use browser CSRF/session credentials. Public `/health` is not an ownership/readiness proof. Authenticated `/api/status` additionally exposes sanitized lifecycle instance/state/guard status, never the control secret.

## Best-effort source-change stop

Before normal serving, take a metadata baseline of `src/`, Web Beta runtime launcher trees `windows/Beta` and `macos/Beta`, root Python entrypoints, `config/default-config.jsonc`, `pyproject.toml` and `requirements.txt`. Owned code/asset extensions are explicitly enumerated in `SourceGuard`; membership, size and nanosecond mtime are compared every five seconds. Added/deleted/renamed runtime files stop the host. Symlinks/reparse points are inspected as links, never traversed to external code. CLI processes are never stopped.

Exclude development/docs, user configuration, Git, logs/cache/diagnostics, bytecode, virtual environments and dependency-installation trees. Transient stat errors expose `source_check_unavailable` and retry against the original baseline; they are not proof of a change. A proven change makes `source_changed` terminal, rejects new API work and initiates the same shutdown immediately without browser acknowledgement. There is **no** reload, automatic restart, Git operation, updater, file watcher dependency or deployment copy. Finish updating and invoke the launcher manually.

This can miss modifications with identical size/mtime, and a mixed-code interval can precede detection. It is not an atomic update protocol or guarantee against Windows file locks. Runtime reads do not retain open source handles. Native detachment, icon and terminal-lifetime behavior require platform-real proof in the following OS FRs; mocked spawn flags are not that proof.
