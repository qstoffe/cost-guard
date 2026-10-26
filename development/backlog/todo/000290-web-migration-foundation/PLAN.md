# Cost Guard Web migration — delivery map and shared decisions

Owner-approved direction, 2026-10-26. This is the design reference for executable Beta FR000290–FR000380, not a claim that the web application already exists. Future promotion and retirement are unnumbered suggestions requiring fresh owner decisions and later FR allocation. Each FR is independently deliverable after its stated prerequisites. Use the existing backlog workflow; do not create a second backlog or new permanent release gate.

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

After Beta stabilization, the separately retained unnumbered suggestions under `development/backlog/suggestions/` describe potential Web promotion and later Legacy retirement. They are **not executable**, impose no prerequisite on the Beta FRs and do not reserve future rollout dates. On explicit owner approval, create fresh numbered FRs from the then-current implementation and platform evidence. The formerly allocated identities 000390/000400 remain historical reservations; never reuse them or decrease the identity watermark.

A useful default implementation order is the numerical order. Prerequisites, rather than unfinished visual polish, govern readiness. Windows/macOS and static-report work may progress independently where the table permits. Reference FRs by identity: bundles can move from `todo` to `complete`. Shared decisions remain available in this FR000290 bundle when it moves. Normal priority; do not preempt or edit unrelated active work, including previously discussed FR000210.

## Runtime decisions

One web application instance per OS user and canonical Cost Guard checkout. Different checkouts must not kill one another. Double-clicking a Web launcher deliberately restarts that checkout's verified instance, waits for the new HTTP shell to be ready, opens the system default browser, then lets the launcher exit. Tray/menu-bar **Open Cost Guard** only opens the running instance; **Exit Cost Guard** stops it. Closing a browser tab does not stop it. No OS service, login autostart or watchdog restart is requested.

The old CLI remains an independent process using shared in-process Python services. It neither depends on the web server nor starts HTTP in a thread. Multiple browser tabs share one acquisition/scheduling owner, not one Watch process per tab. Treat mutable ReportService/source/cache state as owned, not automatically thread-safe.

A primitive code-change check is sufficient: periodically compare metadata for shipped runtime Python and web assets; a detected addition/change/deletion triggers bounded clean shutdown of this Web instance and its icon. No hot reload, automatic restart, updater, Git hooks, source snapshot deployment or promise to detect every change. Manual `git pull` remains the user's operation. Do not promise that this best-effort guard makes arbitrary concurrent updates atomic or prevents every OS file lock.

## Provisional technical defaults

These defaults may be refined with documented implementation evidence, without weakening the product contract:

- **Zero additional runtime or launcher packages is the product requirement.** Use the already-required installed Python 3.11+ standard library for the loopback HTTP host, JSON/SSE, scheduling primitives and browser opening, with deliberately small, auditable handlers, concurrency bounds and hardened security as required by FR000300. Do not automatically install or request consent to download Starlette, Uvicorn, pystray, Pillow, PyObjC, Node or other packages. Avoid a gratuitous general-purpose web framework. `http.server` is explicitly not production-hardened out of the box: add tests and protection for untrusted requests, resource limits and lifecycle, or stop and report a specific blocker rather than silently relaxing security. A future exception to zero installs requires separate explicit owner approval with comparative evidence; never add one merely for developer convenience.
- Ship locally tracked HTML/CSS/JavaScript (native browser APIs, modules and CSS); no frontend package installation, Node build, CDN or external analytics required to run or prepare the Beta. Optional developer-only asset tooling must not be required to clone, pull, launch or use it, and any generated asset has a reproducible source-controlled path. Prefer normal HTTP plus one multiplexed SSE connection per tab; do not introduce WebSockets solely for updates.
- Prefer **OS-native no-install tray integration**: Windows PowerShell 5.1 + in-box .NET `System.Windows.Forms.NotifyIcon`/menu (or focused Python `ctypes` Win32 API); macOS system `osascript`/JavaScript for Automation/AppleScriptObjC invoking AppKit `NSStatusItem` (or a small reviewed Python `ctypes` Cocoa bridge). These are implementation candidates, not claims of verified native behavior. Respect macOS UI-main-thread ownership and isolation from the HTTP worker; test on real supported OS installations. No binary executables checked into the repository and no PyObjC/pystray/Pillow downloads.
- Provide plain-text/script double-click launchers: Windows `.cmd`/PowerShell script, macOS `.command` and preferably a Finder-clickable `.app` bundle composed from source-controlled scripts/`Info.plist`/resources, **not a distributed precompiled per-OS executable**. Finder `.app` viability/Gatekeeper behavior must be proven on real macOS, not assumed from a folder name. `.command` may leave a Terminal window based on preferences; do not change preferences or close unrelated windows. A necessary compiled/helper binary or build-tool installation is a blocker to bring back to the owner, not an implicit exception.
- Use an OS-selected available loopback port recorded in protected local instance state. Launcher/tray discovery hides the port; do not kill a port occupant or hard-code a browser. URLs contain no OpenCode/provider credentials. Startup shell readiness is separate from source/account readiness, so source outages can be explained in the browser.

Primary design references: Python standard-library `http.server` security warning https://docs.python.org/3/library/http.server.html ; browser opening https://docs.python.org/3/library/webbrowser.html ; Apple's menu bar API https://developer.apple.com/documentation/appkit/nsstatusbar ; Windows in-box `NotifyIcon` API https://learn.microsoft.com/en-us/dotnet/api/system.windows.forms.notifyicon ; SSE protocol https://html.spec.whatwg.org/multipage/server-sent-events.html . References are documentation, never runtime downloads.

## Layout and owner checkpoints

Beta adds `windows/Beta/` and `macos/Beta/`; existing launchers keep their paths and semantics. The *unnumbered* promotion suggestion could later put Web at the ordinary OS-folder entry points and move old CLI launchers into `Legacy/`, with paths repaired. The separate retirement suggestion could eventually remove only terminal-specific code. Neither is authorized work, nor is a transition date implied. No completed Beta FR, version number or passing automated test substitutes for a new owner decision and newly allocated FR.

Source facts were checked against GitHub main `d602279b19356e20b08a5e0dc081bfdf3c758583`. Architecture owners include `src/reports/`, `src/analysis/`, `src/watch/coordinator.py`, `src/presentation/`, `src/runtime_errors.py`, and existing OS launchers. Re-read current source before implementation. The original publication allocated 000290–000400 while leaving 000210–000280 untouched. Owner subsequently moved the final two concepts out of todo into unnumbered suggestions; the high watermark stays 400 because allocated IDs are never reused. This changes only backlog specifications, not product code or versions.
