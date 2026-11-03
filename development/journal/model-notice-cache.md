# Optional model-notice SQLite reliability

2026-11-03 · FR 000557 · v80.135 · starting default `d6c52fff96ca2afea55a920b8146dcba3815f690`.

## Established diagnosis and boundary

The deterministic baseline reproduced the reported escape from a normal
`WatchCoordinator.poll_once` through `_observe`/`_persist_known`, `CacheRepository.put`
and the exact `PRAGMA synchronous=NORMAL` statement. An injected unstructured
`sqlite3.OperationalError` escaped before the fix. This establishes the containment
defect, not the original environmental cause: the owner's exception message/code
is unavailable. No claim of reproducing that original lock, permission failure,
disk fault or corruption is made.

`cache/model_notices.py` now owns only optional notice-history/first-sighting
resource classification, health and backoff. Known SQLite BUSY, LOCKED, READONLY,
IOERR, FULL, CANTOPEN, PERM and NOMEM primary codes (including extended variants)
are eligible. Unknown-code OperationalError is contained without text parsing;
known SQLITE_ERROR, programming, invariant and corruption errors propagate.
General repository operations do not suppress failures. The database annotates
connect/PRAGMA/operation/commit phases without replacing the original exception;
rollback/close remain unconditional for opened connections.

`synchronous` is connection-local. Moving its setup only into initialization would
not configure subsequent connections; changing its setting or repeatedly querying
it offers no established root-cause repair. NORMAL, foreign keys and persistent WAL
are retained. Optional operations alone use 50 ms instead of the ordinary 5000 ms
lock budget; retry intervals are 1/5/15 minutes then hourly, independent of provider
acquisition. Each optional component stops further attempts inside backoff.

Dirty in-run catalog/notice state survives. Failed startup reads are retried before
overwriting history; a delayed read never asserts startup novelty. First-sighting
timestamps are evidence only after successful persistence/readback, and retries
retain the original in-run observation time. Local catalog-diff eligibility does
not become a fabricated shared accent. State is bounded to 512 pending/observed
first-sighting entries per repository. No DB deletion/replacement, OpenCode history
mutation, model acquisition owner, poll cadence, quota or CCost change was added.

Watch discovery diagnostics expose unavailable/unknown/ok separately for history
and first sightings. Diagnostics' headless smoke exports those sanitized states as
an independent observation, not proof of another Watch process's health. Existing
RuntimeErrors episodes record phase/numeric SQLite code, changed failure, bounded
repetition and proven operation recovery. Error text/paths are never serialized.

## Verification and limits

- Expected-red baseline command:
  `py -3 development/tools/run_tests.py --pattern test_watch_model_discovery.OptionalCachePollTests --verbosity 2`.
  It failed at the exact synchronous PRAGMA through the incident path; post-fix the
  test survives the outage, keeps CCost/call/context/token-mix values and observes
  a later authoritative prompt completion.
- Focused `run_tests.py --pattern` invocations passed for `test_cache.py`,
  `test_watch_model_discovery.py`, `test_release_metadata_recovery.py`,
  `test_runtime_errors.py`, `test_model_pricing_presentation.py` and
  `test_diagnostics_ux.py`. Real disposable connections cover setup/read/write/
  commit failures, rollback/close, WAL readers during a held writer, short busy
  timeout and recovery, real read-only URI access, injected directory denial,
  sustained outage/backoff, unknown-code errors, code/phase changes, redaction and
  non-operational defect propagation. Existing concurrent writer/reader and atomic
  first-sighting tests also pass. These are CLI/Web/Diagnostics-style connection
  patterns, not an assertion of reproducing the owner's multi-process incident.
- `py -3 development/tools/run_tests.py --suite full`: 127 files passed (initial
  complete run: 68.4 s); final delivery also verifies the later Diagnostics export.
- `py -3 development/tools/validate_package.py --working-tree`: zero failures;
  six existing advisory prose/module-size warnings, no cap/baseline changes.
- Task-local `py -3 -B ../live-notice-probe.py`: real V2 selected and healthy,
  scoped headless Watch initialized in 1026.8 ms and polled in 1132.5 ms; one row
  remained available, notice history status `ok`. Shared first-sighting status was
  honestly `unknown` because none was needed. No account providers/model calls,
  desktop UI or service restart/stop; full-day history enrichment was deferred.
  The script/evidence were disposable `scratch:/live-notice-probe.py` and
  `scratch:/live-notice-evidence.json`, not distributed product files.

The real smoke did not inject faults into the live installation or prove a
six-hour outage, Python 3.13-specific behavior, disk failure or native PRAGMA lock.
Fault injection and SQLite lock/read-only tests ran on this Windows workstation
with Python 3.14.7 / SQLite 3.50.4;
the masked original cause remains unknown. No requirement/test exception was
requested or approved. No release ZIP, tag or GitHub Release is produced.
