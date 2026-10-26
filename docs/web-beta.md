# Foreground Web Beta

Run `python cost-guard-web.py` using already installed Python 3.11+. It binds **127.0.0.1 only**, on an OS-assigned port. There is no LAN/proxy mode, install step, frontend build or automatic browser launch. Leave the console open. Ctrl+C stops only this host and its owned finite reports; it does not stop OpenCode. Single-instance/background/native launcher ownership is deferred, so do not treat this foreground developer entry as an everyday detached launcher.

## Browser session and privacy

Open the console's `/#bootstrap=…` link within 120 seconds. JavaScript immediately removes the fragment with `history.replaceState`, then POSTs it once to `/api/bootstrap`. The server issues an instance-scoped HttpOnly SameSite=Strict cookie with an eight-hour lifetime and a separate CSRF value held only in page memory. Reloads recover CSRF through the authenticated `/api/session` route. Replay, expiration and other instances are rejected. Restart this foreground host for a new bootstrap link. The console link is an intentional short-lived handoff to the foreground owner, not a reusable control token; do not save/share it or capture startup output in general-purpose logs.

Sensitive reads require the cookie. All POST requests require exact Origin and JSON content type; authenticated POSTs additionally require `X-CG-CSRF`. Every request checks the exact Host and assigned port, rejects foreign Origin/Fetch-Site, ambiguous framing and unsafe targets. No CORS access is granted. Packaged assets are fixed, local and symlink/junction-checked, not a general file server. Responses are no-store, deny frames/service workers and third-party runtime assets, and use restrictive CSP. Report text is inserted with `textContent`, never HTML. Access/error request logging is disabled; failures expose allowlisted codes, never source exception messages.

This is loopback HTTP, not a public server or protection against malware/other code executing as the same OS user. No persistent launcher/control credential is implemented or exposed to the page. Provider credentials never enter URLs or browser storage. No generic OpenCode proxy, source mutation, shell-command or arbitrary path API exists.

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

The shell remains reachable with offline/loading sources. It is intentionally an early report/API surface: no live dashboard, native tray, detached restart, autostart or persistent instance discovery. Tests use synthetic read-only sources; local read-only source probes are separate from paid/live-model tests.
