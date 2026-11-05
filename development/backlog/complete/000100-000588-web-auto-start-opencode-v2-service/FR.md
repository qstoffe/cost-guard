# FR 000588 — Web Beta: automatically start an unavailable OpenCode V2 service

## Owner request

**Owner-approved Ready feature request, 2026-11-05.** When the user launches **Cost Guard Web Beta** and the local **OpenCode V2 background server is not running**, Cost Guard should first try to start/wake that service automatically instead of immediately leaving the user to start it manually. If the attempt succeeds, the Web app should connect and operate as usual. If it fails, the user should see the existing honest unavailable/waiting/retry/Refresh guidance rather than a false success or a stuck startup state.

This is **FR authoring only**. Do not implement product code, tests, documentation or version/release changes while publishing this request.

## Desired startup flow

1. When the **Web Beta host is launched** (not on every browser tab visit, page reload, route navigation or Refresh), check the selected source's actual availability. Leave healthy V2 sources untouched and preserve explicitly selected V1 behavior.
2. If the selected/eligible V2 service is unavailable for a **recoverable not-running/not-ready reason**, make **one bounded, safe server-side attempt** to start or wake the installed OpenCode service using a supported installed mechanism. Reuse the proven CLI wake/discovery path where appropriate; do not assume that a browser can start a local process. Avoid opening the full OpenCode Desktop UI if only its background service is needed.
3. While startup is in progress, show concise, visible, accessible status such as **“Starting OpenCode server…”**, distinct from the Web host/HTTP starting or reconnecting. Keep the Web shell responsive rather than blocking or freezing its browser handoff, navigation or unrelated data.
4. After a short bounded wait, **probe actual V2 service readiness again**, including the supported registration/loopback API health checks. A process spawn or successful CLI exit alone is not proof of readiness. On success, continue the ordinary source selection, initial reports and Live/Watch acquisition **automatically**, without requiring a manual Refresh.
5. On failure, unsupported launch environment, timeout or missing executable, end the attempt cleanly and fall back to existing **OpenCode unavailable / waiting for connection / Retry or Refresh** behavior and manual-start guidance, as applicable. Do not pretend the connection succeeded or leave an indefinite “Starting…” indicator. Ordinary later reconnect remains possible.

## Constraints / coordination

- The **existing CLI report recovery** in `src/bootstrap.py::_select_source()` can perform one `_wake_cli_service()` command (`opencode api get /api/info`); **Web** currently selects directly in `src/web/composition.py` (which explicitly says “no CLI wake”). Investigate how to share a safe bounded wake primitive without importing CLI display/dispatch side effects or duplicating repeated start logic.
- Perform startup only at the trusted Python/Web-host side, after normal configuration validation and source-mode checks. **Do not add a browser-callable arbitrary process-launch endpoint.** No shell-string injection, user-controlled executable arguments, credential exposure, new network listener or weakened local session/CSRF boundaries.
- Distinguish **service absent/unresponsive** from **invalid registration, access denied, incompatible API/schema, deliberate source mode V1, host authorization failure and other non-startup faults**. Do not attempt to “fix” the latter by repeatedly launching OpenCode, overwriting its service registration, silently switching an explicit source, changing config or editing OpenCode's data.
- Coalesce concurrent callers/startup paths into **at most one wake attempt per Web-host startup**. Bound command runtime and readiness probing. No duplicate lingering server processes, unbounded retries/polling or new launch on every tab/Live tick/reconnect. Never stop, restart or take ownership of an already-running shared OpenCode service; Web shutdown should continue to stop **only Cost Guard-owned work**.
- Preserve current host startup, source recovery, live subscriptions, frozen/retained evidence, CLI behavior, V1 fallback semantics for `auto`, Windows and macOS launchers, and user-friendly errors. If only one OS or OpenCode distribution supports a safe wake, fall back transparently on the others rather than inventing a command.
- Update relevant `docs/web-beta.md`, `docs/connectivity.md` and the Web/source module notes to describe the successful and unsuccessful paths accurately.

## Acceptance criteria

1. With a supported V2 installation and a stopped but startable service, **launching Web Beta once** shows a brief starting status, wakes OpenCode, confirms readiness and then loads the normal Web experience and Watch without manual intervention.
2. A healthy running OpenCode service is reused with **no new launch** and no observable startup delay.
3. With OpenCode absent/unstartable, incorrect registration, insufficient permissions or an unresponsive server, the attempt is **bounded**; the Web app displays the truthful existing connection/wait/Refresh guidance and remains usable where existing behavior permits. Later manually restored connectivity is recoverable.
4. Multiple tabs, browser refreshes, rapid opens and live acquisition do **not** spawn more services or repeat the startup attempt. Closing Web Beta never kills a pre-existing/shared OpenCode service.
5. Explicit `v1`, incompatible V2, authorization errors and unsupported schemes never trigger inappropriate autostart; no source auto-switch, privacy/security regression or loss of retained data.
6. Focused unit/integration and real browser/launcher coverage checks Windows and macOS paths where supported, short startup delay, timeout/failure, concurrency, status transitions and normal/failed recovery. No model inference or mutation of real OpenCode history is required for the tests.

**Publication boundary:** create this Ready FR and advance the backlog identity watermark; no product implementation or release change in this session.
