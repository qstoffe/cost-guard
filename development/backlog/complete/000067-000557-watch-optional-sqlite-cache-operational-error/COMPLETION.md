# FR 000557 completion — 2026-11-03

Implemented in v80.135: optional model-notice resource failures no longer stop
otherwise valid Watch polling. Known SQL/schema/programming/invariant/corruption
defects still propagate. General cache callers retain transaction failure and
5-second timeout semantics; WAL/NORMAL/foreign keys are unchanged.

Dirty in-memory notices and original first-sighting observations survive outages;
short-timeout attempts use bounded backoff, retry unread history before writes and
record sanitized degradation/change/recovery. Missing shared evidence never
manufactures a persisted first-sighting accent. Diagnostics exports explicit
optional-cache health without replacing source/pricing/account authority.

Verification: the exact normal-poll synchronous-PRAGMA regression was red before
the fix and green afterward, including a later prompt completion and unchanged
metrics. Setup/read/write/commit, read-only/directory denial, sustained outage,
recovery, concurrent WAL/busy access, rollback/close, redaction and defect
propagation are covered. Full suite: 127 files passed. Package validation: zero
failures, six existing advisory warnings. Real read-only V2 headless Watch startup
and poll succeeded; no model calls or shared-service changes.

Exact commands, results, setup decision, architectural updates and evidence limits:
[engineering journal](../../../journal/model-notice-cache.md).

The owner's masked SQLite error's OS cause is **unknown**. Deterministic containment
and real disposable lock/read-only evidence are not reproduction of that original
incident; the live smoke did not inject an outage or run six hours. No scoped
requirement/test exception was needed. No ZIP/tag/GitHub Release was produced.
