# Windows CLI console ownership — FR 000522

Observed 2026-10-28 on the user's Windows workstation, Python 3.14.7.
Implementation candidate: `11fa96c2bea806c7a66341e407bc04eb1611d079`.
Original comparator: `a8be7f0253ecc4007a2d03d7fc01cd03c2027c87`.
This is a bounded native reproduction, not confirmation on the colleague's machine.

## Reproduction and decision

With explicit user approval, disposable copies retained the real batch/shared
PowerShell driver and substituted a synthetic slow Python worker. The parent used
PSReadLine and a synthetic Git-style prompt; prompt return and worker startup were
recorded as PIDs in private scratch. A helper attached only to the test-owned console,
queried GetConsoleProcessList, injected harmless console input and sent Ctrl+C.
No raw buffer, history, title, screenshot, credentials or Diagnostics ZIP is published.

The original START /B wrapper returned the parent prompt while Python was working.
The caller PID was present in the worker's console process list (five attached
processes including the observation helper). Ctrl+C reached the worker. This proves
concurrent interactive-prompt/worker ownership in one console, not a specific
third-party plugin defect or every observed physical character collision.

The chosen START without /B gives the persistent child a separate console. The
same test found the caller absent from the worker console (four attached processes
including the helper). Parent typing and child progress use distinct input/output
queues. The child accepts commands after completion/cancellation, with no batch
termination question. /WAIT was rejected because it leaves a waiting batch in the
interruption path; hiding progress would not repair ownership. -NoExit and the
explicit Ctrl+C reset remain. Requirement feedback moved out of the caller's batch.

## Native observations

| Exercise | Verified observation |
| --- | --- |
| Synthetic decorated PowerShell + PSReadLine | Old caller prompt/worker share a console; fixed caller prompt/worker do not. |
| Vanilla PowerShell, explicit Console Host caller | Separate console; width 80; progress advanced; Ctrl+C received; child command succeeded; native result 0. |
| Decorated PowerShell, explicit Windows Terminal caller | Separate console; width 160; progress advanced; Ctrl+C received; child command succeeded; result 0. |
| Windows PowerShell 5.1 fallback, Windows Terminal caller | Copied batch's pwsh discovery deliberately failed; fallback child stayed isolated; width 160; progress advanced; Ctrl+C and child command/result 0 passed. |
| cmd parent | Separate console; width 120; progress advanced; Ctrl+C and child command/result 0 passed. |
| Explorer-style open | ShellExecute open of the real copied report batch; completed report fixture remained readable; child command/result 0 passed. |
| Diagnostics batch | Copied real relative entrypoint/driver selected the synthetic Diagnostics target; completed output and child command/result 0 passed. |
| Missing Python | In the disposable driver only, discovery returned no candidates. Visible Python guidance, usable prompt and result 9009 passed. Unit tests also cover both shells. |
| Crash | Disposable worker raised ValueError; visible nonzero command result and child command/result 1 passed. |
| Real report | Unmodified production driver/application against the real read-only installation; product heading present; completed result 0 and subsequent child command passed. |
| Real Watch | Unmodified production driver/application; after 12 seconds sent Ctrl+C only to its console. Watch stopped message, no batch question, no remaining Python member, and child command/result 0 passed. |
| Real Diagnostics | Unmodified production driver/collector with normal service-start check; completed result 0 and child command passed. Its private bundle reports full-local validation ok, Full 113/113 files in 50.6 seconds, package validator ok (four design warnings). Bundle creation alone was not treated as validation proof. |

Console widths are measured buffer widths, not screenshot-based font/layout claims.
Width changes were exercised inside the owned child; one early requested width 80
remained 120 because its window was wider than the requested buffer. The probe was
repaired to shrink the window before the buffer, and the explicit Console Host
rerun measured 80. Final native report/Watch/Diagnostics smoke preceded only the
version metadata change to v80.102 and documentation/accounting changes.

## Re-run, only after fresh bounded UI approval

Use a disposable clone. The manual harnesses are not automatically discovered tests:

```powershell
py -3 development/tests/evidence/windows-console/console_probe.py unique-decorated pwsh.exe watch 160 terminal
py -3 development/tests/evidence/windows-console/console_probe.py unique-vanilla pwsh.exe watch 80 conhost
py -3 development/tests/evidence/windows-console/console_probe.py unique-fallback powershell.exe watch 120 terminal
py -3 development/tests/evidence/windows-console/console_probe.py unique-cmd pwsh.exe watch 120 cmd
py -3 development/tests/evidence/windows-console/console_probe.py unique-explorer pwsh.exe report 120 explorer
py -3 development/tests/evidence/windows-console/console_probe.py unique-error pwsh.exe crash 120
py -3 development/tests/evidence/windows-console/console_probe.py unique-missing pwsh.exe missing 120
py -3 development/tests/evidence/windows-console/live_console_probe.py report
py -3 development/tests/evidence/windows-console/live_console_probe.py watch
py -3 development/tests/evidence/windows-console/live_console_probe.py diagnostics
```

Use a new unique case name; each synthetic case exclusively creates its directory.
Private artifacts remain under the disposable clone's `.console-probe/`; generated
Diagnostics/cache are not source artifacts. The harness closes only its recorded
PowerShell/caller trees. Native observation must identify the PowerShell PID, not
Python's immediate parent (py.exe can be an intermediate launcher). Earlier probe
failures were repaired and rerun, never counted as PASS.

## Limits and follow-up

The colleague's exact Windows Terminal/PowerShell 7.6.9, prompt plugin and physical
keyboard/focus appearance were not available. The FR-authorized bounded synthetic
prompt reproduction was used instead. No physical screenshot/visual cursor audit is
claimed. Synthetic progress asserts actual advancing rows; deterministic progress,
Watch-screen and rendering tests cover presentation without changing its semantics.
The native evidence does not cover every terminal delegation setting or user profile.
No existing user terminal/profile or shared OpenCode service was changed/stopped.

The first Full run found three files pinning the unsafe /B behavior; their focused
contracts now require isolation while retaining cancellation/results. A later README
expansion exceeded its hard cap; the explanation was condensed, not the cap raised.
No Toolkit defect publication or new permanent test gate was needed.
