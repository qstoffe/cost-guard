# Sources source contracts

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Session Sources

A Session Source normalizes agent history into provenance-bearing domain records. V1 is read-only SQLite; V2 is registered loopback HTTP with non-durable Watch hints. `openCode.source=auto|v1|v2` selects one healthy generation, preferring V2; histories are never unioned. Trusted CLI bootstrap or Web host startup may wake the shared service once through `src/opencode_service.py`'s bounded installed-CLI API info command before reselecting. No Desktop/TUI or recurring Watch subprocess; adapters/discovery remain process-free.

`sources/opencode_errors.py` maps explicit cancellation/limit IDs and bounded messages/JSON errors to `AbortedError` plus optional cause, never stack guesses. V2 idle errors carry `TerminalEvidence`; later success wins. `opencode_v2_interruptions.py` keeps bounded live user actors, matched to persisted idle session/ID/time only. Its revision signature invalidates pre-event cache; `observed_live` prevents persistence. Events never manufacture ends/usage. Labels outlast emphasis; tool-call success stays neutral.

### OpenCode V1 boundary

`src/sources/opencode_v1.py` alone knows the legacy V1 SQLite projection. Process-free discovery honors `OPENCODE_DB`, else the standard XDG data location. It validates the required `session`/`message`/`part` columns, opens SQLite `mode=ro` plus `PRAGMA query_only=ON`, and never starts the OpenCode CLI.

Hydration reads a root and its recursive descendants in one pinned read transaction, normalizing them into canonical sessions, messages, parts, events and invocations. `step-finish` parts, when present, replace cumulative assistant-message tokens/cost. Native message/part structure survives only through canonical types that compaction/tool/context analysis needs.

`get_session_tree_revision()` hashes membership/counts/timestamps/IDs without JSON. Catalog activity includes message/part row clocks; unchanged session clocks cannot hide descendants. A separate status-only latest-message/live-tool probe conservatively discovers old running candidates without declaring lifecycle truth. Revisions remain payload-free gates.

### OpenCode V2 boundary

`opencode_v2_transport.py` owns stdlib HTTP/SSE (pooled keep-alive JSON GETs, one retry on a service-closed idle socket, privacy-safe counters), `opencode_v2_wire.py` wire compatibility, `opencode_v2_normalization.py` pure message/part/request mapping with injected provenance, and `opencode_v2.py` acquisition/revision/snapshot assembly. Discovery reads standard registration, validates loopback, ignores proxies and probes `/api/info`. No auth logging, V2 SQLite or CLI/subprocess.

Global discovery uses cursor-paginated sessions, falling back to project enumeration/de-duplication. The current session-list limit500 is repeated on every opaque-cursor page; order is first-page-only. Omitting a continuation limit falls back to the service default50. Current and transitional message APIs share canonical V1/V2 session/message/part/event/invocation contracts; synthetic histories verify semantic parity.

Invocations are model requests, not assistant records. Current V2 can split one response's tool calls into explicit-zero, tool-only records; `normalize_request_invocations` drops only such a record's invocation (the message stays canonical history) when it directly follows a usage-bearing `tool-calls` record of the same session/prompt/model and either shares its provider response id or, without ids on both sides, began streaming within 500 ms of creation. Differing or one-sided ids, latency, own text/reasoning, absent counters, errors, model switches and user/compaction boundaries keep it a request.

The adapter caches a complete catalog and one shared child/tree index with memoized revisions. Discovery/resync replaces it; events invalidate it. Required snapshot batches share before/after catalogs, but every tree must match around its message reads; only unstable trees retry. A complete catalog at most 2s old may be the before bracket, followed by two fresh attempts on mismatch. Repeated instability fails; hints never become durable truth.

`load_session_snapshots_for_sampling()` is a strict, single-reader bounded-window
capability for report lookahead, not the four-reader observed-date or partial-Watch
path. It returns only fully bracketed batches or a typed failure. An internal
`SourceSnapshotMemberError` identifies a member fault for the consuming report;
the member locator is absent from exported error evidence. Shared catalog faults
remain unwrapped. Ordinary single/batch snapshot semantics are unchanged.

`opencode_v2_wire.py` binds qualified persisted `idle` outcomes to the preceding attempt as neutral `TerminalEvidence`. A failed/interrupted run with no assistant binds to its initiating user/synthetic message, never an earlier assistant; system notices are transparent, while compaction and ambiguous timestamps block attribution. Status/inactivity/transport failure alone proves no end. Native completion/usage/billing stays unchanged; Diagnostics counts terminal evidence separately. Path-free `location-switched`, `agent-switched`, and `model-switched` items become non-billable context boundaries. When supported, the documented session-context route contributes only path-free active message IDs; unsupported evidence stays absent. `opencode_v2_background.py` maps background jobs/completion notices to neutral `BackgroundActivity`/`BACKGROUND_COMPLETION`; a job without notice runs until its location's shell registry drops it.

FR000688 preserves the existing single lazy shell-registry observation per hydrated
session containing unfinished job starts. It now retains only command/cwd/shell and
ownership scalars as ephemeral `BackgroundActivity.invocation_input`; raw registry
objects/output/environment never cross the Watch boundary. Exact native shell/job
IDs and assistant/session links qualify recovery, not name/path/time similarity.
Duplicate/conflicting origins or supplied IDs withhold detail. Missing original
background input requires positive registry presence, never an inferred live job
from outage alone. Verified source 2.2.7 may make one optional exact-session
`kind=shell,status=running,descendants=false` experimental job read when ordinary
shell command ownership is absent; unsupported/404 stays normal no-detail evidence.
Each separately hydrated child has its own exact session filter. Unjoined session
records are not promoted into prompt activities. No new worker, persistent command
cache, expansion fetch or mandatory experimental dependency is added.

`/api/event` decodes current JSON-string and legacy object events. Hints invalidate snapshots; explicit live actors supplement only a matching persisted cancellation. End/disconnect/failure requires authoritative resync; older history and a fresh source never invent actors.

Web's isolated card-service factory may explicitly inherit a detached copy of the
coordinator's bounded actor evidence. `inherit_live_evidence()` checks the observed
registration/service epoch, not only the path-derived `source_instance`; an epoch
change clears old evidence and revision hints. Old streams retain their old registry,
so buffered retired events cannot contaminate a new epoch. Every returned snapshot
still requires its ordinary catalog brackets and matching persisted idle identity/time.
`test_watch_history_acquisition.py` covers this cross-reader proof contract.

Web cards alone may use `load_card_snapshots()` for one to three roots. Root-local
read failures remain typed outcomes while successful siblings still require their
after-catalog revision proof; auth/registration and shared catalog failures are
group-wide. An observed service-epoch change rejects the entire group, including
identical metadata. Ordinary strict and available-history report APIs retain their
existing failure semantics. Caller cancellation must reach transport and join all
owned hydration readers before replay; no partial bracket is publishable.

Exclusively borrowed Web-card readers additionally use `opencode_v2_tree.py`'s
`CardTreeBrackets`. One compact capability result per known observed epoch checks
the registered OpenAPI for session GET and parentID/limit/cursor. Valid absence or
explicitly unsupported specification routes use the original global path; auth,
transport and malformed specifications fail with their actual types. Scoped reads
recursively exhaust direct-child pages, including leaves, with identity/parent/
cycle checks and no tree-size or computation-duration limit. A qualified complete
global catalog may supply before only when all requested roots are present, using
a separate local index so its revision memo is untouched. After begins after all
group hydration and is always fresh. No partial tree renews or replaces global
membership, catalog time or revision hints. Active interpretation is shared with
global acquisition. Current-job tree locations feed skill lookup (including moved
sessions) without silently fetching a global catalog; the next borrow clears them.
Ordinary CLI, finite reports and the other Web lanes retain global brackets.
`test_v2_tree_brackets.py` covers this explicit local-index seam and typed failures.

Watch classifies V2 skill-call origin only from the location-scoped `/api/skill` registry: `/builtin` paths are built-in, other absolute source paths are custom, and unsupported/ambiguous paths remain unknown. Registry reads are cached per location and service connection; Cost Guard does not write OpenCode data.

### Source selection and migration-gap diagnostics

`src/sources/selection.py` selects process-free `auto|v1|v2`: healthy V2 first, otherwise healthy V1. Forced generations never silently fall back. Unhealthy V2 fallback warns; normal V1-only installations do not. `src/bootstrap.py` retains CLI recovery; `src/web/source_startup.py` coalesces one narrower host-only wake after eligible V2 failure. Unreadable registration/permissions/auth/schema never qualify. Healthy auto-V1 selection is unchanged. Both use the shared fixed command without importing CLI display/dispatch; Web uses five seconds, CLI retains twenty. Process exit is never source readiness.
Typed source errors/health carry stable registration/transport/HTTP/version/schema/data/concurrency categories. Only readiness failures permit the shared report read budget (`read_recovery.py`: three failed attempts, 0.5s spacing, 4s recovery deadline); one CLI wake stays separate. Watch selection waits every five seconds without runtime/provider reconstruction. Missing-installation wording requires absent CLI and filesystem evidence. Presentation receives scalar failure facts, never concrete adapters or raw errors. Healthy V1 auto-selection never switches later.

With V2 selected and readable V1 metadata, a best-effort metadata-only diagnostic finds V1 sessions missing from V2 or newer than their V2 copy, without merged hydration, source changes or OpenCode writes. It is evidence, not a source warning: each gap carries its V1 root and possibly unrepresented activity window; `reports/migration_notice.py` notes it only when that window meets the report scope (sample cutoff, dates, requested root, all history). Watch never shows it; Diagnostics keeps full counts.

