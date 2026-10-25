# Sources source contracts

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Session Sources

A Session Source normalizes agent history into provenance-bearing domain records. V1 is read-only SQLite; V2 is registered loopback HTTP with non-durable Watch hints. `openCode.source=auto|v1|v2` selects one healthy generation, preferring V2; histories are never unioned. Only bootstrap may wake the shared service once through the installed CLI's read-only API info command before reselecting; no Desktop/TUI or recurring Watch subprocess.

`sources/opencode_errors.py` maps explicit cancellation/limit IDs and bounded messages/JSON errors to `AbortedError` plus optional cause, never stack guesses. V2 idle errors carry `TerminalEvidence`; later success wins. `opencode_v2_interruptions.py` keeps bounded live user actors, matched to persisted idle session/ID/time only. Its revision signature invalidates pre-event cache; `observed_live` prevents persistence. Events never manufacture ends/usage. Labels outlast emphasis; tool-call success stays neutral.

### OpenCode V1 boundary

`src/sources/opencode_v1.py` alone knows the legacy V1 SQLite projection. Process-free discovery honors `OPENCODE_DB`, else the standard XDG data location. It validates the required `session`/`message`/`part` columns, opens SQLite `mode=ro` plus `PRAGMA query_only=ON`, and never starts the OpenCode CLI.

Hydration reads a root and its recursive descendants in one pinned read transaction, normalizing them into canonical sessions, messages, parts, events and invocations. `step-finish` parts, when present, replace cumulative assistant-message tokens/cost. Native message/part structure survives only through canonical types that compaction/tool/context analysis needs.

`get_session_tree_revision()` hashes membership/counts/timestamps/IDs without JSON. Catalog activity includes message/part row clocks; unchanged session clocks cannot hide descendants. A separate status-only latest-message/live-tool probe conservatively discovers old running candidates without declaring lifecycle truth. Revisions remain payload-free gates.

### OpenCode V2 boundary

`opencode_v2_transport.py` owns stdlib HTTP/SSE (pooled keep-alive JSON GETs, one retry on a service-closed idle socket, privacy-safe counters), `opencode_v2_wire.py` wire compatibility, `opencode_v2_normalization.py` pure message/part/request mapping with injected provenance, and `opencode_v2.py` acquisition/revision/snapshot assembly. Discovery reads standard registration, validates loopback, ignores proxies and probes `/api/info`. No auth logging, V2 SQLite or CLI/subprocess.

Global discovery uses cursor-paginated sessions, falling back to project enumeration/de-duplication. Current and transitional message APIs share canonical V1/V2 session/message/part/event/invocation contracts; synthetic histories verify semantic parity.

Invocations are model requests, not assistant records. Current V2 can split one response's tool calls into explicit-zero, tool-only records; `normalize_request_invocations` drops only such a record's invocation (the message stays canonical history) when it directly follows a usage-bearing `tool-calls` record of the same session/prompt/model and either shares its provider response id or, without ids on both sides, began streaming within 500 ms of creation. Differing or one-sided ids, latency, own text/reasoning, absent counters, errors, model switches and user/compaction boundaries keep it a request.

The adapter caches a complete catalog and one shared child/tree index with memoized revisions. Discovery/resync replaces it; events invalidate it. Required snapshot batches share before/after catalogs, but every tree must match around its message reads; only unstable trees retry. A complete catalog at most 2s old may be the before bracket, followed by two fresh attempts on mismatch. Repeated instability fails; hints never become durable truth.

`opencode_v2_wire.py` binds qualified persisted `idle` outcomes to the preceding assistant as neutral `TerminalEvidence`. Intervening boundaries, ambiguous timestamps or later tool work block attribution. Status/inactivity/transport failure alone proves no end. Native completion/usage/billing stays unchanged; Diagnostics counts terminal evidence separately. Path-free `location-switched`, `agent-switched`, and `model-switched` items become non-billable context boundaries. When supported, the documented session-context route contributes only path-free active message IDs; unsupported evidence stays absent. `opencode_v2_background.py` maps background jobs/completion notices to neutral `BackgroundActivity`/`BACKGROUND_COMPLETION`; a job without notice runs until its location's shell registry drops it.

`/api/event` decodes current JSON-string and legacy object events. Hints invalidate snapshots; explicit live actors supplement only a matching persisted cancellation. End/disconnect/failure requires authoritative resync; older history and a fresh source never invent actors.

Watch classifies V2 skill-call origin only from the location-scoped `/api/skill` registry: `/builtin` paths are built-in, other absolute source paths are custom, and unsupported/ambiguous paths remain unknown. Registry reads are cached per location and service connection; Cost Guard does not write OpenCode data.

### Source selection and migration-gap diagnostics

`src/sources/selection.py` selects process-free `auto|v1|v2`: healthy V2 first, otherwise healthy V1. Forced generations never silently fall back. Unhealthy V2 fallback warns; normal V1-only installations do not. Only `src/bootstrap.py` owns one-time CLI service wake after selection failure.
Typed source errors/health carry stable registration/transport/HTTP/version/schema/data/concurrency categories. Only readiness failures permit the shared report read budget (`read_recovery.py`: three failed attempts, 0.5s spacing, 4s recovery deadline); one CLI wake stays separate. Watch selection waits every five seconds without runtime/provider reconstruction. Missing-installation wording requires absent CLI and filesystem evidence. Presentation receives scalar failure facts, never concrete adapters or raw errors. Healthy V1 auto-selection never switches later.

With V2 selected and readable V1 metadata, a best-effort metadata-only diagnostic finds V1 sessions missing from V2 or newer than their V2 copy, without merged hydration, source changes or OpenCode writes. It is evidence, not a source warning: each gap carries its V1 root and possibly unrepresented activity window; `reports/migration_notice.py` notes it only when that window meets the report scope (sample cutoff, dates, requested root, all history). Watch never shows it; Diagnostics keeps full counts.

