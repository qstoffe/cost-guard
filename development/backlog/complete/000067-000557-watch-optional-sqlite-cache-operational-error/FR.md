# FR 000557 — Keep Watch running when optional model-discovery SQLite persistence fails

## Owner report, queue and outcome

**Owner-approved executable stability fix, 2026-11-03.** Permanent identity **000557**; **Ready priority 000040** (high because an otherwise functioning long-running Watch was terminated), ahead of the currently queued FR000555 at 000050 and FR000556 at 000060. An already selected/in-progress FR keeps its identity and work; this queue addition does not interrupt it.

**Required outcome:** a recoverable environmental SQLite failure while reading/writing **optional model-discovery notice history** must not terminate CLI Watch or an equivalent shared Watch consumer. Preserve the valid current report, source tracking, prices and CCost; identify the degraded auxiliary cache truthfully and recover persistence when available again. A genuine programming/invariant defect must not be hidden behind an indiscriminate SQLite exception handler.

## Observed incident and supported diagnosis

Owner-provided crash report `cost-guard-crash-20261103-145942-27656.txt` (sanitized summary; no unredacted exception payload is available):

- **Product:** Cost Guard **v80.134**, Windows 11 / Python 3.13.13, OpenCode V2, CLI **Watch**.
- **Watch start:** 2026-11-03 08:54:49 local; **fatal crash:** 2026-11-03 **14:59:42** local (approximately six hours into Watch).
- **Exception:** `OperationalError`, fingerprint `f07d6a3516a5957a`, `src/cache/database.py:79 in connect`. Report intentionally states `[message omitted for privacy]`.
- **Fatal route:** `WatchCoordinator.run_forever → _advance → acquire_cycle → poll_once → WatchModelDiscovery.refresh → _adopt_checks → _apply_check → _observe → _persist_known → CacheRepository.put → CacheDatabase.connect`; the application emits `COST GUARD FAILED` and exits with status 1.
- **Exact source line:** `src/cache/database.py:79` executes **`connection.execute("PRAGMA synchronous=NORMAL")`** after opening a SQLite connection and configuring its busy timeout. It is **not** evidence that the initial `sqlite3.connect(...)` call failed.
- **Escape path:** `src/watch/model_discovery.py::_persist_known` persists `known-catalog-ids` and `recent-discoveries`, calls `CacheRepository.put`, and catches only `(OSError, ValueError)`. Python SQLite `OperationalError` is not an `OSError`; it escapes and becomes a fatal main-thread incident. The initial optional `_initialize` reads likewise catch only `(OSError, ValueError)`.
- **Related precedent:** `src/reports/semantics.py::model_first_sighting_ms` already isolates SQLite failures for an optional first-sighting lookup using an explicit `sqlite3.Error` catch. Existing `development/architecture/governance/policies/runtime-failures.md` requires honest, narrow isolation—not generic catch-and-continue in cache, valuation or Watch orchestration.

**Known:** the fatal escalation path, failure location and missing optional-cache exception classification. **Not known:** the SQLite message/code, the OS-level reason for the `PRAGMA` failure, or whether the original trigger was a lock, file permission, disk I/O, concurrent CLI/Web processes, transient filesystem problem or something else. Do **not** label the original incident “database is locked” without separate evidence. Request or consult the owner's local sanitized error log/Diagnostics if necessary; never require an unredacted arbitrary error message in a public FR or log.

The cache is a disposable generation-named SQLite database (`cache/cost-guard-cache-v2.sqlite3`); the model-discovery notice-history writes are explicitly documented as **optional, non-authoritative**. This specific optional operation must not have authority to kill otherwise correct Watch acquisition/reporting.

## Requirements

### 1. Fix the owning optional boundary, not every SQLite error globally

1. Trace the actual `OperationalError` path, including connection setup and `_persist_known`, initial reads in `_initialize`, and related optional model-discovery notice/first-sighting reads. Handle **recoverable operational database unavailability** at those feature boundaries so a failed auxiliary read/write cannot escape to `run_forever` as a fatal error. Guard the operation itself, including connection/PRAGMA setup, execution and commit.
2. Preserve the general `CacheDatabase.connect` transaction/rollback/close guarantees and surface errors to callers that require them; **do not** globally swallow `sqlite3.Error`, silently return success from `CacheRepository.put`, or add blanket `except Exception: pass` to the Watch coordinator. Distinguish expected operational/resource SQLite conditions from SQL/schema/logic/programming defects as far as the available structured evidence permits. Genuine unrelated bugs still use the established fatal/reporting policy.
3. Review why configuring `PRAGMA synchronous=NORMAL` on every short-lived connection can fail in the affected environment; determine whether a safe, narrow setup change reduces contention or fragile setup without weakening WAL/durability semantics. Do not guess that a different timeout or deleting the DB is the root-cause fix. Keep existing concurrent-reader/writer and close behavior sound.
4. If failure prevents persistence, retain correct in-memory model/catalog state for the live Watch lifetime and treat persistent first-sighting/notice evidence as unavailable where necessary. Do not manufacture “new model” alerts, false persisted first-seen timestamps, successful-cache states, price changes, or altered CCost to conceal the outage. Re-attempt eligible persistence with bounded work/backoff on a later appropriate refresh, and automatically resume ordinary persistence after recovery **without requiring a Watch restart**.
5. Do not delete/rename/recreate an in-use SQLite database, touch users' OpenCode history, or launch/stop the user's OpenCode service. Do not introduce a second model-discovery acquisition owner or alter poll cadence or provider quotas. Any corruption remediation, if independently justified, must be safe, scoped to disposable cache data and non-destructive to other runtime state.

### 2. Visible diagnosis without log floods or privacy exposure

1. Record a **sanitized, bounded** optional-cache failure episode that distinguishes the **phase** (connect/PRAGMA, read, write, commit where known), affected component and a structured SQLite category/code when safely available; include failure start/change and eventual recovery. Do not log arbitrary SQLite exception text, full paths, private session/account data, prompts, credentials or unbounded stack repeats. Leverage the existing runtime error/recovery and Diagnostics policy rather than a new permanent telemetry service.
2. If the optional cache remains inaccessible, Watch must continue showing accurate available metrics while the auxiliary cache is honestly marked degraded/unavailable in appropriate diagnostics; lack of cache evidence is not equivalent to “zero new models” or a verified persisted cache. The user should not see `COST GUARD FAILED` for this specific recoverable incident.
3. Bounded retry and error reporting must not cause repeated multi-second stalls on every Watch poll, log storms, runaway threads, busy loops or continued stale “healthy” reporting. Recovery clears the degraded state only after a proven successful operation.

### 3. Deterministic regression evidence and verification

1. **Exact incident-path regression:** inject `sqlite3.OperationalError` at the **`PRAGMA synchronous=NORMAL`** step of `CacheDatabase.connect` while `WatchModelDiscovery._observe/_persist_known` runs from a normal Watch poll. Show baseline pre-fix fatal and post-fix Watch survival, with subsequent polls still updating normal report/prompt state. A test that only injects a failure into a different SQL statement is insufficient.
2. Also cover failure in optional `get` and `put` during discovery startup/refresh, failure during actual write/commit, read-only or temporarily unavailable cache directory, sustained outage across multiple polls, and success after recovery. Distinguish transient operational cases from intentional non-operational programming/schema faults so the latter are not silently ignored.
3. Test realistic bounded concurrent cache access (CLI Watch plus another reader/writer, and representative Web/Diagnostics access where supported), WAL/busy-timeout behavior and resource cleanup without using the owner's live service, private account data or real model calls. No forced deletion of a locked database and no leaked SQLite connection.
4. Assert invariants: no new fatal incident from the operational optional-cache failure; no fabricated model notice, first-sighting, pricing, tokens, CCost, quota or session lifecycle; correct eventual persistence and genuinely observed recovery; bounded diagnostics with safe redaction. Leave other fatal software-failure behavior intact.
5. Extend appropriate existing tests, particularly `development/tests/test_cache.py`, `test_watch_model_discovery.py`, `test_release_metadata_recovery.py` and affected Watch integration/unit fixtures; run targeted and relevant full product tests plus package validation. Include Windows-relevant behavior and portable deterministic fault injection where a real Windows lock cannot be recreated safely.
6. The completion/PR must report the actual established failure classification, tested baseline/post-fix behavior, exact commands and outcomes, any original-cause uncertainty, known residual risk and recovery evidence. **A green test proving containment does not by itself prove which real-world event caused the owner's masked SQLite `OperationalError`.** Never claim that the underlying file lock, access failure or database corruption was reproduced unless it truly was.

## Scope and related work

A focused **reliability correction** for optional model-discovery cache interaction and directly required connection setup/diagnostic/test support. Preserve current product release policy, existing RuntimeErrors boundary, CLI/Web analysis parity, new-model notice truth, pricing catalog cache semantics and generation-named cache compatibility. This is **not** authorization for a broad SQLite/cache redesign, a permanent new test gate or changes to user account/CCost calculations.

Relevant code: `src/cache/database.py`, `src/cache/repository.py`, `src/watch/model_discovery.py`, `src/reports/semantics.py`; runtime policy `development/architecture/governance/policies/runtime-failures.md`; diagnostics `docs/runtime-errors.md`.

**Publication only:** adding this FR and advancing the permanent identity counter makes it Ready. No application code, tests, version metadata, packaging or live service is changed by FR creation.
