# Cost Guard development

Product code, executable tests, fixtures, developer tooling and machine-read
policies stay in this source repository. Building, testing and running Cost Guard
do not require access to the private backlog.

Project architecture, backlog, journal and the development guide are maintained
in [the private development repository](https://github.com/qstoffe/cost-guard-backlog):

- [Development guide](https://github.com/qstoffe/cost-guard-backlog/blob/main/development/README.md)
- [Architecture and module contracts](https://github.com/qstoffe/cost-guard-backlog/blob/main/development/architecture/OVERVIEW.md)
- [Code/test map](https://github.com/qstoffe/cost-guard-backlog/blob/main/development/architecture/modules/CODE_MAP.md)
- [Journal](https://github.com/qstoffe/cost-guard-backlog/blob/main/development/journal/INDEX.md)

Source-local areas:

- `tests/`: executable checks, deterministic fixtures and maintained integration probes.
- `tests/policies/`: machine-read validation policies; do not silently raise limits.
- `tools/`: development checks and diagnostics implementation.
- `user-tools/`: human-facing diagnostics launchers.
- `logs/`: ignored, on-demand runtime errors, crashes, recovery events and
  `diagnostics/cost-guard-diagnostics.zip`; never included in package copies.

Quiet maintenance starts 60 seconds after Web readiness or Legacy presentation,
then attempts retention once per day, independently of cache/source readiness.
Only recognized, unchanged regular files strictly older than 30 days are removed
from this tree and legacy root `logs/` / `diagnostics/`. Active recovery state,
unrecognized files, links and uncertain/in-flight ZIP staging survive. Bundling
does not prune recent logs or historic ZIPs. ZIP `logs/` members remain readable,
with distinct legacy prefixes and duplicate contents omitted. Custom Diagnostics
output stays caller-owned. Managed Web lock/auth/lifecycle/diagnostics and its
private error logs remain in per-user application data, outside this contract.

`repository.json` retains source release settings and the private backlog locator.
`applied-contract.json` identifies the adopted installed development contract.
Contract Sync changes no product behavior, release policy or backlog counters.

Executable boundaries live in `src/entrypoints/`: `desktop.py` routes ordinary
desktop startup, `web.py` owns managed/developer Web dispatch, and `cli.py` is the
explicit Legacy terminal entry. Each supports direct execution from any working
directory; `python -m src.entrypoints.<mode>` works from the installation root.
Keep user-facing Windows/macOS launchers at their existing paths. Launcher tests
use disposable installs and redirected/hosted-only harnesses, not workstation UI.

`src/version.py` owns the functional version and release date. Validate runtime
version output with `python development/tools/validate_package.py --working-tree`
and run all registered regressions with
`python development/tools/run_tests.py --suite full`. README is a tiny Web quick
start, not a version binding. Git retains release history; no prose history or
root documentation tree is shipped. The validator rejects retired root wrappers
and documentation while retaining package/privacy, import and size gates.
