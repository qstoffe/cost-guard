# FR 000320 — Windows Web Beta launcher and tray

## Outcome

Implemented in Cost Guard v80.83 (2026-10-26). Opt-in `windows/Beta/Cost Guard Web.cmd` discovers Python 3.11+, resolves its own checkout, preflights configuration/native resources, uses the shared verified restart/detached lifecycle, waits for shell/icon readiness and opens the Windows registered browser association. The transient launcher exits; existing terminals return to their caller. Stable CLI/Watch/Diagnostics launchers are unchanged.

Same-process, main-thread Win32 notification icon has exactly **Open Cost Guard** and **Exit Cost Guard**, with an original bundled source-rendered shield/bar icon. Open hands off asynchronously without restart; Exit/source change/HTTP fault remove the icon and stop only the matching Web host. Explorer taskbar recreation re-adds its icon or fails closed. No packages, compilation, downloads, administrator access, services, startup registration, firewall exception or global execution-policy changes.

Native tray failure, startup timeout, unverifiable instance, configuration and browser failure have distinct allowlisted feedback. Failed browser handoff retains the tray; failed preflight leaves a healthy old host untouched. PowerShell supplies a private timestamp/code record even without Python when the diagnostic path is safe. Failures after an old host has stopped cannot restore it; no seamless-upgrade claim is made.

Candidate source: [1f2dee7](https://github.com/qstoffe/cost-guard/commit/1f2dee7603df95bbed6cb893126c65ed5a336799). Native ownership, test routes and reusable PowerShell findings are consolidated in the current [Web contract](../../../architecture/modules/web.md) and [user guide](../../../../docs/web-beta.md).

Delivery PR: [#62](https://github.com/qstoffe/cost-guard/pull/62); merge status is owned by the verified native delivery receipt, not a predicted SHA in this report.

## Verification

Observed on Windows 11 10.0.26300, Python 3.14.7, Windows PowerShell 5.1:

- `py -3 development/tools/run_tests.py --suite full`: 99 test files passed after repairing the intentional Beta-folder expectation and registering/testing the new browser execution root. No live-model calls or automatic PR self-review.
- `py -3 development/tools/validate_package.py --working-tree`: passed; four pre-existing design-budget warnings remain, no hard cap was raised. No release ZIP was built.
- `py -3 development/tests/integration/probe_web_lifecycle.py`: real read-only source acquired, finite session report completed, authenticated stop and owned-thread cleanup passed; zero model requests and no shared OpenCode stop.
- With explicit user UI approval, `py -3 development/tests/integration/probe_windows_web.py --allow-native-ui`: actual native menu labels/WM_COMMAND Open/Exit, browser-failure notification, HTTP-fault icon cleanup, detached survival after transient console exit, no inherited console, Open retaining identity, rapid overlap/coalescing, deliberate same-build restart, failed browser retaining host, injected native API failure preserving an old healthy instance, source-change exit, independent real CLI Watch across Web restart/exit and ShellExecute from a no-Git source ZIP copy with spaces/Unicode all passed. The native shell also passed with external socket connections denied by the probe; no machine network settings were changed.
- PowerShell regression tests cover missing/old/multiple candidates, actual py.exe `-3` argument preservation and private diagnostic DACL/log writes without UI. These caught and fixed scalar-splat command loss and Set-Acl's unexpected privilege requirement; no elevation was used.

## Decisions, exclusions and limits

ctypes was simpler than a separate PowerShell tray/helper lifecycle and keeps the GUI with its owning Python host. No third-party tray/image library or locally compiled C# helper is needed. Shared HTTP/security/control and CLI acquisition boundaries remain intact; macOS main-thread compatibility remains in the shared host contract.

Physical mouse double-click and visual light/dark readability were **NOT RUN**; ShellExecute tests the Windows file association, not physical mouse interaction. Other Windows/Python combinations and native macOS remain untested. The API-failure path is injected, not a claim that Explorer itself failed. No new permanent release gate or OS auto-launch is introduced. Browser tabs are not closed by Exit. No implementation agents, detached implementation workers, model switches or PR self-review were used.

Journal assessment: **no-update**; reusable findings were consolidated in the existing Web owner contract instead of duplicating a test/session log. Architecture assessment: updated current Web owners, execution-root policy, overview and code-map routes; no report/Watch/domain boundary change. Selected FR bytes are preserved; no attachments or new evidence files were added to the bundle beyond this report. Retention identity state is unchanged, with no pruning.
