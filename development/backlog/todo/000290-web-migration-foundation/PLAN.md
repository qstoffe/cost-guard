# Cost Guard Web migration — delivery map and shared decisions

Owner-approved direction, 2026-10-26. This is the design reference for FR000290–FR000400, not a claim that the web application already exists. Each FR is independently deliverable after its stated prerequisites. Use the existing backlog workflow; do not create a second backlog or new permanent release gate.

## Product contract

Keep the existing CLI entry point and root `windows/` and `macos/` launchers working throughout Beta. Develop both presentations against the same Python analysis, source, account, pricing and report semantics. The web migration must not silently change CCost, billing, tokens, cache categories, causal attribution, duration, context, account periods, unknown/partial values or deduplication. Browser code presents server results; it does not become another valuation engine. FR000200 remains the separately approved change to static session snapshots with provisional running metrics.

Web Beta is an ordinary optional part of the same repository and updates, not a fork, separate beta checkout or permanent duplicated business-logic stack. Early incomplete web views are acceptable when clearly labeled; broken CLI is not. The implementation agent may choose sensible menus, spacing, colors, table components and small interaction details, then document them for owner testing. Preserve recognizable CLI concepts and measurements, not terminal ASCII geometry. Do not wait for a perfect visual design.

## Delivery sequence

| FR | Deliverable | Implementation prerequisites |
| --- | --- | --- |
| 000290 | Shared application boundary, immutable result contracts and CLI parity fixtures | Existing approved semantics; no prerequisite web FR |
| 000300 | Secure loopback HTTP runtime, report API and optional web environment | 000290 |
| 000310 | Verified single-instance restart, detached lifecycle, simple code-change shutdown | 000300 |
| 000320 | Windows Beta launcher, default browser and tray Open/Exit | 000310 |
| 000330 | macOS Beta launcher/app wrapper and menu-bar Open/Exit | 000310; reuse 000320's common host where delivered |
| 000340 | Navigable HTML shell, overview and static session reports | 000300; 000200 for running-metric parity |
| 000350 | Shared live acquisition and SSE/global live dashboard | 000310, 000340 |
| 000360 | Unlimited logical session history with live detail and stable scrolling | 000200, 000350 |
| 000370 | Complete models/accounts/date-range/Token Mix/report navigation | 000340; integrate 000350 live states when delivered |
| 000380 | Cross-platform Beta stabilization, parity, privacy-safe diagnostics | 000320–000370 |
| 000390 | Promote Web to standard launchers; move CLI launchers to Legacy | 000380 AND explicit owner promotion approval |
| 000400 | Retire Legacy presentation after real coexistence period | 000390 AND separate explicit owner retirement approval |

A useful default implementation order is the numerical order. Prerequisites, rather than unfinished visual polish, govern readiness. Windows/macOS and static-report work may progress independently where the table permits. Reference FRs by identity: bundles can move from `todo` to `complete`. Shared decisions remain available in this FR000290 bundle when it moves. Normal priority; do not preempt or edit unrelated active work, including previously discussed FR000210.

## Runtime decisions

One web application instance per OS user and canonical Cost Guard checkout. Different checkouts must not kill one another. Double-clicking a Web launcher deliberately restarts that checkout's verified instance, waits for the new HTTP shell to be ready, opens the system default browser, then lets the launcher exit. Tray/menu-bar **Open Cost Guard** only opens the running instance; **Exit Cost Guard** stops it. Closing a browser tab does not stop it. No OS service, login autostart or watchdog restart is requested.

The old CLI remains an independent process using shared in-process Python services. It neither depends on the web server nor starts HTTP in a thread. Multiple browser tabs share one acquisition/scheduling owner, not one Watch process per tab. Treat mutable ReportService/source/cache state as owned, not automatically thread-safe.

A primitive code-change check is sufficient: periodically compare metadata for shipped runtime Python and web assets; a detected addition/change/deletion triggers bounded clean shutdown of this Web instance and its icon. No hot reload, automatic restart, updater, Git hooks, source snapshot deployment or promise to detect every change. Manual `git pull` remains the user's operation. Do not promise that this best-effort guard makes arbitrary concurrent updates atomic or prevents every OS file lock.

## Provisional technical defaults

These defaults may be refined with documented implementation evidence, without weakening the product contract:

- Python remains the application/analysis runtime. Prefer a small maintained ASGI stack (Starlette/Uvicorn, single server worker, reload disabled) rather than extending a generic file server into an application framework. Web/tray packages are isolated from the dependency-free CLI in a per-user, per-checkout managed environment. Pin/test the actual supported versions during implementation. The first Beta setup may request explicit consent to download these packages; never install globally or require administrator access. Subsequent healthy starts must not require dependency downloads. No Node.js requirement for users.
- Initially use locally shipped HTML/CSS/JavaScript modules; a small UI dependency or build step is allowed when it genuinely simplifies tested behavior. Ship usable assets in Git/ZIP; no runtime CDN or external analytics. Prefer ordinary HTTP requests plus one multiplexed SSE connection per tab. Do not introduce WebSockets solely for receiving updates.
- Prefer a thin pystray/Pillow adapter, with the needed macOS bridge isolated in the optional environment. GUI event ownership must respect the platform main thread. Server work must not block the menu. Native alternatives are acceptable if installation/lifecycle behavior remains simpler and equally tested.
- On macOS provide the requested `.command` entry and a lightweight Finder `.app` entry for a genuinely terminal-free launch. A `.command` exiting does not establish that Terminal closed its window. Do not change global Terminal preferences or close unrelated windows. Windows keeps a `.cmd` Beta entry.
- Use an OS-selected available loopback port recorded in protected local instance state. Launcher/tray discovery hides the port; do not kill a port occupant or hard-code a browser. URLs contain no OpenCode/provider credentials. Startup shell readiness is separate from source/account readiness, so source outages can be explained in the browser.

Primary design references: Python browser control https://docs.python.org/3.11/library/webbrowser.html ; pystray main-loop/platform rules https://pystray.readthedocs.io/en/latest/usage.html ; ASGI response support https://starlette.dev/responses/ ; SSE protocol https://html.spec.whatwg.org/multipage/server-sent-events.html . These are design inputs, not runtime dependencies fetched from these pages.

## Layout and owner checkpoints

Beta adds `windows/Beta/` and `macos/Beta/`; existing launchers keep their paths and semantics. Promotion later places Web at the ordinary OS-folder entry points and moves both old CLI launchers into `Legacy/`, with relative paths repaired. Retirement removes only terminal-specific code after another owner decision. No elapsed date, completed FR, version number or successful automated test substitutes for either owner checkpoint.

Source facts were checked against GitHub main `d602279b19356e20b08a5e0dc081bfdf3c758583`. Architecture owners include `src/reports/`, `src/analysis/`, `src/watch/coordinator.py`, `src/presentation/`, `src/runtime_errors.py`, and existing OS launchers. Re-read current source before implementation. Publication allocates 000290–000400, leaving 000210–000280 untouched to avoid reusing previously discussed work even though this remote snapshot's identity-state is only 200. This publication changes specifications and identity allocation only, not runtime code or product versions.
