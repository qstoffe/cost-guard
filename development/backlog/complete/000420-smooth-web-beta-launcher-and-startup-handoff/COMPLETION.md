# FR 000420 completion — visible Web Beta startup

Implemented in v80.91, 2026-10-26, from default revision `ddb70b03f65e898cfe792a714fa3d5923d42d91e`.

## Delivered behavior and deliberate fallback

Windows PowerShell no longer captures all Python output before displaying anything. It shows Python discovery immediately, indeterminate native progress and flushed, allowlisted elapsed-time stages for config, tray preflight, existing-instance arbitration/restart, detached host/tray readiness and authenticated browser handoff. Success exits the transient console; failures retain the existing sanitized dialog/console recovery. CLI/Watch/Diagnostics launchers are untouched.

The FR's visible-launcher fallback is deliberate: a browser cannot receive this host's one-use bootstrap before the validated host/tray exists without changing the private ownership/publication protocol. No safety wait was removed, no unauthenticated data route or launch supervisor was added, and no universal subsecond/15-second promise is made. Account/history/source work already runs off the launcher in the existing host/jobs/acquisition owners; no second engine or synchronous report prefetch was introduced.

Static branded browser HTML now survives slow authorization, explains readiness and recovery even if JavaScript fails, and transitions to indeterminate report activity/actual job progress. Authorization failure ends activity and explains fresh tray Open/relaunch. Initial report outage offers Refresh; stale report evidence stays readable. HTTP shell, source, accounts and report readiness remain separate.

macOS command startup uses the same fixed progress sink, including an explicit optional first-launch Finder-helper preparation stage. Existing bounded compiler/preflight behavior is retained. This Windows delivery does not claim fresh native macOS acceptance or replace FR 000410's delivered hosted-CI remit.

## Measured Windows observations

Host: Windows 11 build 26300, Python 3.14.7, Windows PowerShell 5.1; one local observation per mode, not a distribution. The timing probe runs the actual batch/PowerShell/Python chain with redirected timing capture; separate native probes use transient consoles and ShellExecute. Cold means no managed Web host, not flushed OS/provider caches.

| Stage (seconds from batch invocation) | Cold host | Warm restart |
| --- | ---: | ---: |
| First PowerShell Python status | 0.227 | 0.273 |
| Python discovery finished | 0.300 | 0.353 |
| Configuration entered | 0.640 | 0.708 |
| Native preflight entered | 0.647 | 0.716 |
| Existing-instance arbitration | 0.661 | 0.730 |
| Verified old-host stop entered | n/a | 0.737 |
| Detached host/tray creation entered | 0.666 | 1.040 |
| Validated readiness / browser handoff entered | 1.083 | 1.458 |
| Browser API handoff returned | 1.124 | 1.519 |
| Transient launcher exited | 1.172 | 1.575 |

These measure browser API handoff, not browser paint/load completion. Batch requirements text precedes PowerShell. Configuration/preflight are entry timestamps; differences are approximate stage durations. Host/tray validation took about 0.42 seconds in both cases; stopping the previous host added about 0.30 seconds.

A separate read-only real-V2 probe measured HTTP shell at 0.009 seconds and first source-backed Live view at 1.808 seconds from host construction (0.25-second polling resolution; discovery plus first acquisition, not isolated provider latency). Subsequent finite normal report completed in 9.453 seconds, all-models 2.810, sessions 0.766, date 9.129. One acquisition owner, two streams and the run origin were preserved; deep history cancelled; all owned workers joined. These observations demonstrate why shell readiness must not imply report/account readiness. No shared OpenCode stop or model inference occurred.

## Verification and limitations

- Local Full: all 106 registered files passed; focused Windows/macOS/lifecycle/views tests also passed. Working-tree validator: zero failures, four existing design-budget warnings; no cap raised and no ZIP/release created.
- Deterministic regression checks cover flushed/timed allowlisted stages, config failure before native/restart work, missing/old/supported Python discovery through real PowerShell AST extraction, native GUI failure, bounded timeout/owned cleanup, restart progress ordering, no console/standard-handle inheritance, slow authorization/initial report, credential erasure before waiting, indeterminate (not fabricated numeric) activity, initial report outage/retry, stale evidence and failed authorization recovery.
- `probe_windows_web.py --allow-native-ui` passed real native menu/Open failure/Exit, HTTP-fault icon cleanup, detached host/console survival, overlapping-click coalescing, deliberate restart, browser failure without host loss, injected tray failure preserving an old host, source-change shutdown, independent CLI Watch, and ShellExecute source copy with spaces/Unicode. Cold/warm streamed timings above come from its added bounded timing case. No untrusted attachment or raw account/source/token evidence was published.
- `probe_web_live.py --reports` passed actual V2 source/report readiness, independent ownership and joined shutdown. Synthetic held promises exercise slow startup; native provider outages were not induced by stopping or reconfiguring the shared service.
- Physical Explorer mouse double-click, visual light/dark/layout/accessibility review, real missing-Python uninstall, OS-cold boot and fresh native macOS desktop acceptance were **not run**. DOM/HTTP checks and ShellExecute/native API execution are not visual acceptance. Existing hosted CI remains separate.

## Knowledge and retained dependencies

Updated the Web module owner route and current Web guide with the startup sink, streaming/fallback and readiness boundaries. No architecture boundary or dependency changed. Journal: **no-update**; the reusable owner facts are consolidated in those existing routes rather than duplicated in a session log. Exact selected FR bytes are preserved; only this root completion report is added. Remaining display/design/account/reconnect FRs stay pending and are not folded into startup. No unfinished cross-FR work, foreign changes or stashes were found in the isolated clone; all necessary evidence is retained here outside disposable scratch.
