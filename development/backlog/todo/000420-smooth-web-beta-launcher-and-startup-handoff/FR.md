# FR 000420 — Smooth Web Beta startup and visible handoff

## Problem and objective

Owner feedback (Windows desktop Beta, 2026-10-26): double-clicking `windows/Beta/Cost Guard Web.cmd` leaves a largely blank console visible for roughly 10–20 seconds, then closes when the browser finishes loading. This feels stalled even when the detached server/tray eventually work. The current Windows chain (`.cmd` → `windows_launch.ps1` → Python preflight → `lifecycle.launch`) waits for validated tray/HTTP readiness and browser opening before returning; `START_SECONDS = 15` is a bounded readiness wait, not a user-facing progress indicator. Confirm timings on the actual path instead of treating the reported duration as proven for every machine.

**Top-priority UX outcome:** ideally double-click flashes the transient console only briefly, starts a detached managed host/tray and immediately hands the person to a branded browser startup/loading view that visibly progresses into Overview/Watch as the underlying source becomes ready. Do not confuse HTTP-shell readiness with source/account/report readiness.

## Required behavior

- Measure and document startup stages (Python discovery, safe preflight/config, existing-instance arbitration/restart, host+tray creation, authenticated browser handoff, source discovery, initial report). Make expensive/unnecessary synchronous launcher work asynchronous where safe; do not silently remove bounded safety checks.
- Prefer fast launcher exit and an **actual branded loading screen in the browser** with progress/status and useful failure/retry directions. If authenticated early browser bootstrap is technically unsafe/unavailable, the explicitly acceptable fallback is a **visible, immediately updating launcher status** (e.g. "Checking Python", "Starting Cost Guard Web Server", "Opening browser") with meaningful progress/indeterminate activity; never a blank black console for multiple seconds. No invented numeric percentages or fake completion.
- Keep Windows tray separate from the transient console. On a successful launch, no orphan console, no CLI Watch subprocess, no need for further button clicks, no duplicate server on repeated clicks. If startup fails, give actionable, sanitized error status that stays observable rather than instantaneously vanishing.
- Reuse the existing managed-instance control/auth/one-use bootstrap safely: never expose startup tokens, bind broad interfaces, open an unauthenticated data page, mark an unavailable source as ready, create a second acquisition engine or weaken stop/identity checks merely to open the browser faster.
- Maintain existing CLI/Watch/Diagnostics launchers and independent runtime. Assess analogous macOS behavior without claiming native macOS completion on Windows. For first-launch macOS local helper compilation, retain meaningful visible preparation feedback if needed; FR000410 separately owns cross-platform hosted CI.

## Acceptance

- Actual double-click Windows experience is responsive: immediate status/handoff, prompt dismissal of the transient console in the preferred path, recognizable loading state until the app can render data, and clear failure recovery. Record measured stages/host OS and remaining limits; don't hardcode a universal startup-duration promise.
- Test warm/cold startup, slow source, unavailable source, Python missing, bad config, GUI/tray failure, browser failure, repeated launch and existing-host restart, Unicode/spaces and shutdown. Assert no hang, hidden indefinite wait, insecure bootstrap, duplicate host or console inheritance.
- A fresh browser tab never looks like an unexplained blank or indefinitely black window. Deferred account/history work continues with visible application progress after handoff.
- Add focused lifecycle/launcher and browser UI checks; coordinate with existing pending FR000410 CI instead of replacing its remit. Document differences between automated/native/owner-visual evidence.

Relevant owners: `windows/Beta/Cost Guard Web.cmd`, `src/web/windows_launch.ps1`, `windows_launch.py`, `lifecycle.py`, `host.py`, `security.py`, `assets/index.html`, `assets/app.js`.

Publishing this FR does not implement it.