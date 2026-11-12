# FR 000681 — Robust installed-Python discovery and readable startup errors on Windows/macOS

**Status:** Ready to Develop. **Primary objective:** reliably find an already-installed compatible Python. **Secondary objective:** make failure messages immediately understandable. Web launchers are the highest-impact user path; align supported Legacy and Diagnostics launchers as part of the same work.

## Observed problem and current implementation

A user on macOS reported that Cost Guard Web would not start even though Python was reportedly installed at a newer version than the **3.11+** minimum (approximately Python 3.13). The exact installation location and root cause were not verified. A Python installation can be valid but invisible to the environment of a Finder-launched Terminal or launcher; do not equate a missing PATH command with Python not being installed.

Source review on main:

- `macos/Cost-Guard-Web.command` and both `macos/Legacy/*.command` scripts test `python3`, `python` and only three fixed absolute locations. They can miss versioned Python.org framework binaries, versioned Homebrew formulas and common user-local installs. The macOS Diagnostics launcher duplicates similar lookup logic.
- `windows/Cost-Guard-Web.cmd` delegates to `src/web/windows_launch.ps1`, which currently probes `py.exe -3` and `python.exe` obtained through `Get-Command`/PATH. Windows Legacy report/Watch/Diagnostics use another copy in `src/windows_launcher.ps1`. Neither covers many registered/per-user Python installations when their commands are absent from PATH.
- Startup failure text is distributed across shell/PowerShell and `src/web/{windows_launch,macos_launch}.py`. Some paths print compacted consecutive guidance, while Windows also shows a modal dialog; the actual cause can be lost among generic launcher/Diagnostics/Legacy text. There is no consistent, readable root-cause-first format.

## 1. Required first: robust Python discovery (priority within this FR)

**Outcome:** a normal installed Python **3.11 or newer** launches Cost Guard without asking the user to edit PATH, reinstall Python or understand which of `py`, `python` or `python3` works.

- Keep PATH/launcher probing as a fast first pass, but also discover **normal non-PATH installations** from supported OS-native and standard installation metadata/locations. On Windows, consider the Python launcher/manager when available, PEP 514 registration under relevant user/machine and registry views, and bounded canonical per-user/system Python locations. Distinguish real Python from Microsoft Store execution aliases/stubs; do not trigger an installer prompt. On macOS, cover version-specific Python.org framework directories and Apple Silicon/Intel Homebrew versioned installations, plus reasonable user-local Python installations without an unbounded filesystem crawl. A discovered interpreter must work from a Finder/.command launch environment, not only the developer's interactive shell.
- Enumerate candidates deterministically, deduplicate by effective executable/invocation, probe each with a **bounded timeout** and validate the actual interpreter version, platform and executable behavior. If one candidate is old, broken, blocked or hangs, continue to another. Prefer a working eligible installation over an unsuitable first match; properly quote paths containing spaces/Unicode. Avoid shell-string injection and unintended execution of arbitrary unrelated files.
- Keep all discovery **before Python is available**: the resolver itself cannot depend on a working Python runtime or new third-party dependencies. Do not silently download/install Python, modify machine/user PATH, registry, shell profile, user configuration or security settings. No admin/developer tools should be required.
- Avoid independently drifting implementations: use a common, maintainable resolution policy within each OS and reuse it in **Web**, **Legacy CLI/Watch** and the **Diagnostics** launchers. Preserve their separate process, Ctrl+C, exit-code and output contracts. Do not start Web as a side effect of Legacy or Diagnostics.
- Ensure the optional generated macOS Finder `.app` uses the selected real interpreter and its existing secure fingerprint/invalidation path, so an outdated cached interpreter location does not silently break a later launch. Preserve the direct `.command` fallback.
- If no usable interpreter can be found, distinguish **no discovered Python**, **only unsupported versions**, and **discovered but not executable/broken** to the extent evidence supports; never claim that Python is uninstalled just because a search failed. Provide a straightforward manual fallback in guidance when automatic discovery cannot cover an unusual custom installation.

## 2. Required second: concise, visually separated startup failures

**Outcome:** at first glance the user sees that **Cost Guard did not start**, the **specific reason**, and **what to do next**, rather than one dense block of mixed status, technical detail and fallback commands.

- Standardize a short human-readable layout for interactive Windows and macOS launch failures, with a prominent first line and **blank lines/section spacing** between the outcome, one specific cause, the next action and optional Diagnostics. Example shape (illustrative, not mandatory literal copy):

```text
COST GUARD COULD NOT START

Reason: No usable Python 3.11+ installation could be located.

Next step: If Python is already installed, select or verify its location
using the documented fallback; otherwise install Python 3.11+.

Diagnostics: <platform-specific Cost Guard diagnostics launcher>
```

- Use equally clear but distinct reasons for an older-only Python installation, an unlaunchable candidate, invalid configuration, native tray/menu failure, Web startup timeout, ownership conflict, or browser-open failure. Do not label these all as "Python missing" or generic "requirements not met". If the Web host actually started but the browser did not open, say so and direct the user to the existing tray/menu **Open Cost Guard** action.
- Show one primary cause and at most a few actionable lines in the main view. Put optional details, tested locations or low-level data in safe Diagnostics rather than in a giant message. Preserve sanitized output: no raw stack traces, private paths/URLs, auth tokens or untrusted subprocess text in UI. A legitimate absolute executable path can be shown when necessary and safe for troubleshooting, but never dump environment variables.
- Make Windows console and native dialog consistent without duplicating a wall of text. On macOS, clear the spinner/progress row before displaying the error, maintain blank lines, and keep a useful interactive failure visible until acknowledgement. Redirected/non-interactive output must remain plain, deterministic, readable and non-blocking (no ANSI control characters or modal UI). Preserve meaningful nonzero exit statuses and existing bounded/private diagnostic records.

## Acceptance / regression scenarios

1. **macOS:** a usable Python 3.13 installed in a standard versioned Python.org framework path and not on launcher PATH starts Web; likewise a versioned Homebrew installation on both ARM and Intel layouts. Validate Finder/.command environment assumptions; a local generated `.app` must not use a stale interpreter. Clearly report what was checked on a real macOS system versus synthetic checks.
2. **Windows:** a usable Python 3.11+ registered/per-user installed but not on PATH launches Web; confirm Python launcher/manager and PEP 514 registry cases when applicable. Store alias-only, missing launcher and old-version candidates must not prevent trying the valid installation.
3. **Both:** multiple Python versions (including older first), broken/throwing/hanging executables, missing interpreter, and paths with spaces/Unicode behave deterministically within finite discovery time and never install anything or alter PATH.
4. **Messaging:** verify well-spaced, cause-specific messages for missing/old/unlaunchable Python and non-Python Web startup faults, including browser-only handoff failure. Interactive and redirected shells remain legible; Windows dialog is concise; macOS spinner is stopped and error retained; sensitive raw errors are never printed.
5. **No regressions:** successful cold/warm Web start, verified host restart, tray/menu Open/Exit and authenticated browser handoff retain existing ownership/security behavior; Legacy report/Watch and Diagnostics use the same robust discovery without changing what they run or their exit/Ctrl+C semantics.

## Delivery boundaries

Targeted surfaces: `macos/Cost-Guard-Web.command`, `windows/Cost-Guard-Web.cmd`/`src/web/windows_launch.ps1`, `macos/Legacy/`, `windows/Legacy/`/`src/windows_launcher.ps1`, OS Diagnostics scripts, `src/web/macos_app.py` when needed, and launcher message paths in `src/web/{macos_launch,windows_launch}.py`. Reuse focused launcher tests (`test_macos_web.py`, `test_windows_web.py`, `test_windows_web_activity.py`, `test_launcher_feedback.py`) and add appropriately scoped discovery and formatting cases. Update README/Web troubleshooting instructions.

No Python bundling, frozen executable, package-manager automation, service/host redesign or unrelated report/account functionality. The **automatic discovery fix is the main deliverable**; cosmetic polishing alone must not be treated as satisfying this FR.
