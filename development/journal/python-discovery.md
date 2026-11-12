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
Python's `-I -B -S` keeps user site hooks/PYTHONPATH from influencing discovery
and prevents probe imports from writing bytecode into the installation.
Windows PowerShell 5.1 and PowerShell 7 differ in JSON-array enumeration; the
resolver deliberately assigns the decoded array directly, covered in both shells.

`src/web/launch_messages.json` supplies fixed post-Python reasons to Python
and the Windows console/dialog. Only known failure codes cross the child-output
boundary; arbitrary prefixed text/tracebacks never become a dialog. Outcome,
reason, action and optional Diagnostics have blank-line separation. Browser-only
failure says Web is running. macOS clears its spinner before Python output and
only retains an interactive acknowledgement when both input/output are terminals.
Its spinner requires all three streams to be terminals; redirected input or output
never enables display controls. Legacy status rows also require terminal input/output.

Generated Finder apps invoke the quoted `.command` through `/bin/zsh` rather
than pinning the build interpreter forever. Every launch resolves an interpreter;
the existing private fingerprint/inventory/atomic compiler path then includes
the resolver source and selected Python. Moving the checkout still needs a new
app. Host lifetime, exact-process restart, one-use browser handoff and native
menu/tray responsibilities are unchanged. SourceGuard includes the new shell file.

## Verification ledger

- Windows native-focused profile: all 16 groups passed locally, including both
  installed PowerShell shells, timeouts/owned-process joins, candidate fallback,
  Unicode/space path, plain redirected failure and message sanitization. Rechecked
  after the final terminal-input gating change: 67 tests, zero skips (19.0s).
- Real workstation, read-only: resolver fed only actual PEP 514 registrations
  selected the installed Python and successfully ran `cost-guard-web.py --help`.
  This proves non-PATH registered lookup/invocation, not a visible native launch.
- Full local suite: all 184 groups PASS (150.1s). Initial failures were obsolete
  duplicated-source assertions and native-profile inventory expectations; they
  were updated to assert shared ownership and retain behavioral coverage.
- Validator: 11 checks PASS, zero failures, seven existing advisory warnings.
  Rechecked on the final terminal-feedback/completion tree with the same result.
  Portable macOS cases passed locally (31 tests, 4 unavailable native-shell skips);
  this Windows run is not macOS shell execution evidence.
- The initial generic Live probe FAILED an immediate post-close worker assertion
  (two provider workers). Its failure is retained, not relabeled PASS. Following
  Decision Delegate guidance, `probe_source_generation.py` ran using the exact
  PEP 514-selected interpreter with normal providers retained: authenticated V2,
  one owner, two verified streams, instance/source identity and advancing sequence
  PASS; zero initial/final owned workers/processes, retirement wait 0.0s. This is
  bounded observation, not a universal provider-cleanup reliability claim.
- Protected [PR #286](https://github.com/qstoffe/cost-guard/pull/286) CI at
  `8d06cef` passed all four checks: [common Quick/validator/rendered smoke](https://github.com/qstoffe/cost-guard/actions/runs/43271456577)
  and [Windows/macOS ARM/macOS Intel native](https://github.com/qstoffe/cost-guard/actions/runs/43271456638).
  Windows reported 16 groups / 67 passed tests; each macOS architecture reported
  5 groups / 41 passed tests / 2 Windows-only skips. Native menu/tray actions,
  HTTP-fault cleanup, cold/warm lifecycle, identity and cache invalidation passed.
  Browser handoff was ACCEPTED once per platform; browser paint is not verified.
- On both real macOS runner architectures, actual Python **3.11** ran through
  disposable non-PATH user-framework and pyenv layouts. Removing only the primary
  fixture symlink then running the actual generated Finder command selected the
  fallback and passed native startup/preferences/ownership checks. Other global
  roots were relocated only in the disposable source copy; installed runtimes
  were not changed. This proves real-runtime behavior, not a consumer Python 3.13
  installation. Separate synthetic metadata cases cover versioned 3.13 layouts.
- Initial macOS CI failures were repaired, not waived: the fake-secret assertion
  accidentally matched `/private/`, and the fixture incorrectly assumed other
  installed global candidates were absent. The latter resolved successfully to
  a different valid interpreter; isolating the fixture made the fallback oracle
  deterministic. Final terminal-feedback refinements additionally exercise hidden
  PTYs with fully interactive and separately redirected input/output. The final
  protected PR head must pass the same four checks before merge; PR #286 retains
  its exact head and results rather than attributing older CI to a newer commit.
- GitHub's job-log endpoint returned HTTP 401. Canonical check-run annotations
  remain accessible and provide the scoped failure/native evidence; no identity
  change, credential recovery or alternate login was attempted.
- macOS tests use real zsh/process/glob behavior on CI with representative disposable
  framework/Homebrew/user-install trees; those installations are synthetic. No
  local macOS desktop is available. Physical Finder/Gatekeeper, visual dialog/menu,
  consumer-installation and browser-paint acceptance are not inferred from CI.
- No model calls, downloads, package installation or shared OpenCode stop is part
  of verification. Runtime caches/logs and private raw evidence stay outside Git.

## Scoped verification decision

Decision Delegate authorized a conditional, journal-only verification exception:
after successful core non-PATH real-runtime startup, stale-command recovery and
native lifecycle checks, unavailable physical Finder/Gatekeeper/Explorer, visual
dialog/tray/browser and actual consumer-distribution observations remain NOT RUN /
UNVERIFIED. Real-runtime and native CI establish separable behavior without
disruptive workstation UI; they do not reproduce the reported user's incident.
This decision does not waive causal failures, unresolved host lifetime defects or
core automatic discovery. No Suggestion is required solely for those physical
observations. The first generic live-probe failure remains disclosed above.
