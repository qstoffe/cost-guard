# Windows launcher verification

Source revision: 11fa96c2bea806c7a66341e407bc04eb1611d079
Checked revision: 11fa96c2bea806c7a66341e407bc04eb1611d079
Last checked: 2026-10-28
Status: current

## Responsibility and ownership

Windows batch entrypoints own shell selection and a separate-console handoff.
`src/windows_launcher.ps1` owns requirement feedback, Python discovery, mode dispatch,
native results and the surviving PowerShell prompt. No renderer owns terminal policy.

## Public contract

All three batch entrypoints use START without /B or /WAIT: an existing caller can
return, but never shares a console/input queue with the persistent child. Explorer
open remains supported; the transient batch console may close as the Cost Guard
console opens. The terminal host controls window/tab decoration. PowerShell uses
-NoProfile -NoExit and checkout-relative paths; execution policy changes are process-only.
Feedback is emitted only inside the child, before console initialization/Python checks.

Missing Python retains actionable Python 3.11+ guidance and child `$LASTEXITCODE = 9009`.
Other native results remain visible and available at that child's prompt. Batch
exit status acknowledges START only, not later Python completion. Direct Python is
the synchronous caller/exit-code route. Ctrl+C stops only the owned Watch console;
no waiting batch can ask the Windows batch-termination confirmation. Retain the explicit
SetConsoleCtrlHandler(NULL, FALSE) reset, including direct/legacy invocations.

## Allowed dependencies

In-box PowerShell 7 when available, Windows PowerShell 5.1 fallback, Win32 console
control and Python 3.11+ through available py.exe/python.exe. No installed dependencies,
prompt/profile changes, analysis changes or OpenCode service control.

## Entrypoints

- `windows/Cost Guard.cmd`: report.
- `windows/Cost Guard Watch.cmd`: Watch.
- `development/user-tools/diagnostics/windows/Cost Guard Diagnostics.cmd`: Diagnostics.
- `src/windows_launcher.ps1`: shared driver.

## Tests

Focused regressions: `development/tests/test_windows_launcher.py`,
`development/tests/test_launcher_feedback.py`, `development/tests/test_watch_lifecycle.py`,
`development/tests/test_watch_source_recovery.py`, `development/tests/test_rc2_public_diagnostics.py`.
These never open windows. They protect isolation, feedback ownership, persistent
shells, shell/Python fallback, mode arguments, native results and Ctrl+C reset.

Manual native evidence and commands: `development/architecture/governance/verification/windows-console-ownership.md`.
The manual harnesses `development/tests/evidence/windows-console/console_probe.py` and
`development/tests/evidence/windows-console/live_console_probe.py` require fresh explicit
bounded UI approval and a disposable clone. They use only owned consoles, synthetic
fixtures, aggregate buffer assertions and targeted input/Ctrl+C. They never stop OpenCode.
The real Diagnostics ZIP must be inspected for its validation result; collection exit
alone is not a full-local PASS. Never publish raw buffers/history/credentials.

The colleague's exact prompt setup and physical keyboard/focus appearance remain a
consumer follow-up, not proof supplied by textual tests or the bounded native probes.
