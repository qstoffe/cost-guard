# Windows launcher verification

## Contract and boundary

The three `.cmd` files start the same `src/windows_launcher.ps1` driver with a mode.
`start /b` reuses the launcher's console; cmd exits immediately, before Python detection/work.
PowerShell uses `-NoExit`, sets the package root as its working directory and remains interactive.
The per-process execution-policy option runs the bundled driver without modifying saved policies.
Missing Python retains the actionable Python 3.11+ message and `$LASTEXITCODE = 9009`.
Other native command results remain in `$LASTEXITCODE`, with a visible non-zero result.

**Do not remove the Ctrl+C reset.** Windows `start /b` inherits ignored Ctrl+C into its child.
The driver calls `SetConsoleCtrlHandler(NULL, FALSE)` before Python starts. Omitting it can leave
Watch uninterruptible. Calling PowerShell synchronously from batch instead can restore the unwanted
`Terminate batch job (Y/N)?` interaction. No renderer owns this terminal policy.

## Bounded workstation smoke

Run only with explicit approval for these launcher/UI actions. Deterministic suites never open
windows, inject keys or depend on the user's OpenCode installation. Do not stop the shared service.

1. Open `windows/Cost Guard.cmd` using Explorer's open/double-click action. After the report, run
   `Get-Location` and inspect `$LASTEXITCODE` at the ordinary package-root PowerShell prompt.
2. Open `windows/Cost Guard Watch.cmd`, wait for the steady dashboard, press Ctrl+C and verify
   `Watch stopped.` followed by a usable prompt in the same console, without batch confirmation.
3. Open `development/windows/Cost Guard Diagnostics.cmd`, let it finish, verify its bundle and
   execute a harmless command at the surviving prompt. Validation failure must still be inspected
   in the bundle; successful ZIP collection alone does not establish a passing validation gate.
4. In a disposable package copy only, inject `ValueError('launcher smoke failure')` into
   `WatchCoordinator._advance` from an entry-point wrapper. Open that copy's Watch launcher and
   verify bootstrap's runtime error, native result 1 and a usable prompt; repeat with RuntimeError
   or OSError as needed. Never modify the real OpenCode service/history or add a production test knob.
5. Confirm the handoff creates no second console for PowerShell, the original outer cmd process
   is gone before interruption, and each shell accepts a new command. Close only smoke-owned shells
   after verification. Host-specific initial window decoration is not a claim of zero cmd processes.

Automation may use ShellExecute's `open` verb (the Explorer double-click action), console buffer
inspection, `GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)` and targeted console input in only the
consoles it created. Record aggregate pass/fail/window/process observations, never prompt text,
session titles, auth data or raw console buffers. Console-host/delegation differences require fresh
live evidence on another Windows setup; textual launcher tests do not prove them.
