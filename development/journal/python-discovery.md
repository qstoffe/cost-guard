# Installed Python discovery and startup failures — FR000681

## Cause and ownership

The previous launchers duplicated PATH checks plus a few fixed macOS paths.
macOS/Legacy probes could wait forever; a reported Python 3.13 installation's
actual location/root cause was never established. Missing PATH evidence is not
evidence that Python is uninstalled.

`src/python_discovery.ps1` and `src/python_discovery.sh` now own each OS's
pre-Python policy for Web, independent CLI report/Watch and Diagnostics. They
use installed metadata/finite standard layouts, deduplicate candidates and
validate real interpreter version/platform/standard-library behavior with
isolated, bounded probes. Windows only asks launchers/managers for installed
paths (`-0p`); it never invokes a Store Python alias or an install command.
Discovery changes no PATH, registry, config, shell profile or security setting.
An unusual custom install has a documented direct-executable fallback.

Windows probes use exact owned hidden process handles and fixed output buffers;
macOS probes use exact children, limited temporary output and cleanup. Each
probe gets at most about two seconds within an approximately twenty-second
overall budget. Budget exhaustion/broken evidence is not reported as absence.
Python's `-I -S` keeps user site hooks/PYTHONPATH from influencing discovery.
Windows PowerShell 5.1 and PowerShell 7 differ in JSON-array enumeration; the
resolver deliberately assigns the decoded array directly, covered in both shells.

`src/web/launch_messages.json` supplies fixed post-Python reasons to Python
and the Windows console/dialog. Only known failure codes cross the child-output
boundary; arbitrary prefixed text/tracebacks never become a dialog. Outcome,
reason, action and optional Diagnostics have blank-line separation. Browser-only
failure says Web is running. macOS clears its spinner before Python output and
only retains an interactive acknowledgement when both input/output are terminals.

Generated Finder apps invoke the quoted `.command` through `/bin/zsh` rather
than pinning the build interpreter forever. Every launch resolves an interpreter;
the existing private fingerprint/inventory/atomic compiler path then includes
the resolver source and selected Python. Moving the checkout still needs a new
app. Host lifetime, exact-process restart, one-use browser handoff and native
menu/tray responsibilities are unchanged. SourceGuard includes the new shell file.

## Verification ledger

- Windows native-focused profile: all 16 groups passed locally, including both
  installed PowerShell shells, timeouts/owned-process joins, candidate fallback,
  Unicode/space path, plain redirected failure and message sanitization.
- Real workstation, read-only: resolver fed only actual PEP 514 registrations
  selected the installed Python and successfully ran `cost-guard-web.py --help`.
  This proves non-PATH registered lookup/invocation, not a visible native launch.
- Full local suite, final validator, headless real-installation probe and protected
  PR CI results will be recorded before completion. No pending check is a PASS.
- macOS tests use real zsh/process/glob behavior on CI with representative disposable
  framework/Homebrew/user-install trees; those installations are synthetic. No
  local macOS desktop is available. Physical Finder/Gatekeeper, visual dialog/menu,
  consumer-installation and browser-paint acceptance are not inferred from CI.
- No model calls, downloads, package installation or shared OpenCode stop is part
  of verification. Runtime caches/logs and private raw evidence stay outside Git.
