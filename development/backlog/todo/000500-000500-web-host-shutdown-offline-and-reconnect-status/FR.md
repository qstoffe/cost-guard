# FR 000500 — Make stopped Web host/offline/stale state unmistakable

## Owner observation and goal

The owner intentionally stopped the Cost Guard tray-managed Web server while a browser page remained open. The old page can still look like an active/live dashboard, even though it is no longer connected to the host. The user needs a clear distinction between **server stopped**, **temporary connection loss**, **source disconnected** and **a stale frozen report**. A prior SSE terminal/status mechanism exists in `src/web/assets/live.js`, but its notification is not sufficiently obvious/reliable as a whole-page experience.

## Required behavior

- Surface an always-recognizable connection/host state in the common shell and global Watch: connected, starting, temporarily reconnecting, source unavailable, authentication expired, host intentionally stopped/source-changed and host unreachable. Never equate a working HTTP shell with healthy OpenCode/source/account acquisition.
- On intentional tray **Exit Cost Guard** or source-change shutdown, publish a terminal state where possible, freeze retained values with a prominent **STOPPED — NOT LIVE** banner and clear instruction to restart with the OS launcher. It must be impossible to confuse old numbers with live values; hide/disable misleading active controls safely. Browser storage must not retain secrets or spawn/restart hosts automatically.
- For abrupt termination, server crash or a tab loaded after shutdown (no SSE terminal event), transition promptly to **OFFLINE — last observation** based on bounded connection/health failures and last successful authenticated update; never permanently display `Live connected` from stale DOM. Distinguish recoverable outage from terminal host identity/authorization loss; do not repeatedly open tabs or leak control tokens.
- Preserve the last known report as marked stale when useful rather than silently clearing or replacing unknowns with zeros. Web UI can show time of last successful data update and server/observation state; reconnection must honor existing cookie/bootstrap identity and replay/resync logic, without assuming another local instance is the same host.
- Keep CLI/Watch independent and existing private stop/control credentials out of the browser. No unauthenticated sensitive status endpoints, port scanning or automatic broad-network availability checks.

## Acceptance

- Actual browser checks for tray Exit while viewing Overview/Watch, killed/crashed process, source loss with HTTP still up, network/SSE interruption, auth expiry, host restart/new identity and long-idle tab visibly show **distinct accurate states**.
- A stopped server never appears to be updating; stale contents are visibly time-stamped. Reconnect restores only authorized same-instance data and never silently trusts a different host.
- Focused browser/HTTP/lifecycle tests maintain bounded resource usage, security and diagnostics; coordinate with FR000420 startup and FR000460 Watch.

Relevant owners: `src/web/assets/index.html`, `app.js`, `live.js`, `app.css`, `src/web/host.py`, `events.py`, `http.py`, existing Web runtime/live/lifecycle tests.