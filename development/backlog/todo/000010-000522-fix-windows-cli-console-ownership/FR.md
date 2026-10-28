# FR 000522 — Fix Windows CLI launcher console ownership and prompt/output collisions

## Observed defect and strongest cause hypothesis

A colleague using Windows Terminal with PowerShell 7.6.9 and a decorated Git-aware PowerShell prompt launched Cost Guard from an existing PowerShell tab on 2026-10-28. Screenshots show the parent shell prompt becoming available before Cost Guard's requirement/progress/report output finishes. Typed characters appear in multiple positions, including across Cost Guard's progress indicator and report, making the normal CLI difficult to use. The owner uses vanilla PowerShell 7 without noticing this defect. The problem is not proof that a specific third-party prompt plugin is broken.

The current Windows report, Watch and Diagnostics .cmd launchers all invoke START /B with a second pwsh.exe or powershell.exe process, -NoProfile -NoExit, and src/windows_launcher.ps1. The batch wrapper then exits immediately; that script in turn runs Python. START /B shares a console without waiting. This creates a credible competing-prompt/console-writer and console-input-ownership defect. The source pattern and screenshots strongly support this hypothesis, but the exact failing process/input sequence and a correct replacement have NOT yet been reproduced and verified on the colleague's terminal.

The shared launcher deliberately restores Ctrl+C handling after START /B; it must not be removed casually. Passing existing text/launcher unit tests is not evidence that real Windows Terminal handoff works with a customized parent prompt.

## Required outcome

- **One effective foreground console owner** from launch through requirements feedback, Python startup/progress, running report or Watch, cancellation/completion and final usable prompt. When invoked from an existing PowerShell or cmd terminal, the caller MUST NOT regain an interactive prompt while Cost Guard still writes output or accepts input in the same terminal. No prompt duplication, random typed-character echoes, overlapping report/progress rows, or accidental keyboard input into two shells.
- Keep progress visibly advancing and the finished report readable. Avoid blank/hanging startup, misplaced ANSI/VT cursor positioning and stale progress rows. No workaround that merely hides output or asks users to disable prompt customization.
- Explorer double-click remains usable. After normal report/Diagnostics/error completion, the user gets a single usable prompt or an equally clear, intentionally owned terminal. Watch Ctrl+C stops Watch, returns to a usable prompt, does not stop OpenCode and does not produce the Windows 'Terminate batch job (Y/N)?' question. Preserve meaningful exit status and missing-Python/crash guidance.
- Support PowerShell 7, Windows PowerShell 5.1 fallback, cmd invocation, Windows Terminal and traditional Console Host. A custom PowerShell/PSReadLine/Git prompt must not cause competing readers/writers. A genuinely separate terminal, if technically necessary, is preferable to a corrupted shared terminal; clearly document the chosen handoff behavior.

## Investigation and implementation boundaries

1. Reproduce and instrument the real process/console ownership timeline: parent shell, .cmd, START /B, -NoExit child, src/windows_launcher.ps1, Python and interactive prompt return. Contrast vanilla and Git-aware PowerShell prompts (PSReadLine, oh-my-posh/posh-git-like test setup) and Explorer double-click. Confirm which process owns input and writes before choosing the fix.
2. Replace unsafe asynchronous same-console handoff with a deterministic foreground/console ownership model. Do not blindly remove START /B, -NoExit or the Ctrl+C handler without testing the batch-confirmation, lifetime and prompt-return regressions those choices previously addressed.
3. Apply the fix consistently to normal report, Watch and Diagnostics launchers, keeping Python 3.11+ discovery, checkout-relative paths, no global execution-policy modification, no new installed dependencies and CLI/OpenCode source isolation. Coordinate renamed filenames from FR000524, without requiring that rename to demonstrate this defect.
4. Do not change Cost Guard's analysis or render numerical semantics as a workaround.

## Acceptance evidence

- On an actual Windows interactive setup, repeat launch from an existing decorated PowerShell tab and vanilla PowerShell. During a deliberately long progress/report phase, attempt ordinary harmless typing: the caller must not expose a second active prompt or allow typed text to corrupt Cost Guard output. Confirm a single clean prompt after completion. If the original decoration cannot be installed, use a bounded instrumented competing-prompt reproduction and explicitly retain the real-user verification limitation.
- Exercise startup, mid-progress, completed report, failed/missing Python and Diagnostics; Watch running/refresh, Ctrl+C and subsequent commands; widths 80/120/160 and resize. Verify exit codes, keyboard focus, output placement, no batch termination question and no orphan owner.
- Include focused regressions for process/console sequencing and presentation, plus targeted existing tests. Real terminal interaction evidence is essential to close the reported user bug; mocked/subprocess-only tests are insufficient.
- No modification or interruption of the real OpenCode service, credentials, history or prompts. Any screenshots/logs used for evidence must exclude private terminal/history contents.

**Priority:** Critical / first new pending FR. This is a user-observed functional defect, not an optional CLI expansion. Documentation/source pointers: windows/Cost Guard.cmd, windows/Cost Guard Watch.cmd, development/user-tools/diagnostics/windows/Cost Guard Diagnostics.cmd, src/windows_launcher.ps1, development/architecture/modules/windows-launchers.md, development/tests/test_windows_launcher.py and test_launcher_feedback.py.
