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

`repository.json` retains source release settings and the private backlog locator.
`applied-contract.json` identifies the adopted installed development contract.
Contract Sync changes no product behavior, release policy or backlog counters.
