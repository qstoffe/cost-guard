# Cost Guard version history

## v80.39 — 2026-10-12

- Watch retains the latest prompt's tool/failure counts and confirmed distinct skill IDs after completion or abortion, replacing activity only when the same session begins a new prompt. Active tool/TODO/background indicators never survive completion; compaction, refresh and reconnect keep prompt ownership.
- A yellow Skills row shows exact persisted IDs, newest load first, with red per-skill tool call failure counts only for explicit metadata or direct skill-script execution. Generic reads, mentions and skill-load recency never imply attribution; unattributed failures remain in the total.
- Known Toolkit script contracts supplement native tool errors with bounded, schema-verified structured failures. Physical-call deduplication and cancellation handling prevent inflated totals; arbitrary output and nonzero exits alone remain neutral.
- Activity rows fit terminal width independently of the fixed metric table: total/failures outrank breakdowns, whole skill IDs/indicators precede an accurate +N more fallback. Stable completed frames reuse observations without new source reads or changes to usage, billing or token accounting.

## v80.38 — 2026-10-12

- Missing/unreachable Desktop V2 service now has actionable startup guidance, not crash wording or legacy table details. Reports retry structured readiness failures within a short shared budget; healthy reads stay immediate and CLI wake remains one-time.
- Watch recovers initial catalog/snapshot acquisition through its existing coordinator, discarding partial initialization before retry and deferring account work until source reads succeed. Established outages retain validated dashboards, source identity and quota cadence.
- Source errors distinguish registration, transport, HTTP/auth, version/schema, invalid data and concurrent changes. Restarted registration invalidates old catalogs/pools; idempotent stale-socket retry stays bounded and retired SSE readers are cancelled.
- Bounded source incident history retains sanitized phase/category/type/count/duration evidence for later Diagnostics, including after ZIP creation. External certificate-verification failures are distinct from other TLS failures; metadata cache fallback/backoff remains intact.
- Startup/troubleshooting documentation separates local loopback HTTP from external HTTPS and treats VPN/security/proxy/certificate causes as hypotheses, without weakening protections. Diagnostics summaries separate connectivity, metadata degradation, validation and ZIP creation.

## v80.37 — 2026-10-10

- Summarizes all changes since v80.36 (PRs #2-#5): removed dead definitions, unused imports and redundant integration/report/Watch code, retaining existing behavior and protected contracts.
- Causal analysis now derives trace entries, sorted prompt events and active compaction once per root/pass rather than per prompt. Recorded pre/post cleanup medians: 74 live roots 252 to 92 ms; a synthetic 500-prompt root 1.72 to 0.23 s. Analysis records remain identical.
- Analysis-cache serialization copies flat fields and serializes nested values once instead of deep-converting then discarding them (recorded 74-bundle median 90 to 31 ms; identical JSON). Metadata-only pricing changes use dataclass replacement; Watch identity/marker handling is consolidated without changing rows or accounting.
- Git delivery policy is tool-independent: explicit task/workflow authorization covers commits, push, PR and safe merge in an isolated clone without editing the ordinary working tree. Isolated Git delivery still builds no ZIP unless requested; existing quality gates and protection of maintainer rules remain.
- Every PR merged to main now requires a sequential product-version bump with release date, bounded net-change history, README current version and affected current docs in the same PR, including documentation-only and behavior-neutral work. Recheck against the latest base before merge; tags, GitHub Releases and packaging policy are unchanged.

## v80.36 — 2026-10-10

- Watch recognizes V2 live `session.execution.interrupted` events with explicit `reason: user`, including JSON-encoded event strings and current `data.sessionID` routing. `[ABORTED by user]` requires the same session, terminal identity and timestamp in authoritative interrupted history; an event alone never ends work.
- Live actor evidence survives refresh/resync in a bounded in-memory source-instance store, never in persisted analysis. A new process/source and older history without actor evidence still show `[ABORTED]`; inactivity/shutdown, other attempts and later success never inherit `by user`.

## v80.35 — 2026-10-10

- Watch shows `[ABORTED by user]`, `[ABORTED by quota limit]`, `[ABORTED by tool call limit]`, `[ABORTED by step limit]` or `[ABORTED by rate limit]` only for explicit native causes, including V2 idle errors and bounded structured API error responses. Unspecified cancellations remain `[ABORTED]`; later success clears an earlier abort.
- A source-reported successful end directly after tool calls shows neutral `[ENDED after tool calls]`, not a guessed limit failure. Full stop labels survive preview truncation; usage, billing and existing completion semantics are unchanged.
- Shared report/Watch account order is stable: credit/balance/budget accounts first, usage-limit accounts second, then name and proven identity. Remaining capacity, percentages, refresh completion and transient errors do not reorder established accounts; provider failures retain account labels/plan/capacity class.

## Earlier v80 history

- v80.34 pooled V2 reads/fresh snapshot brackets, memoized model identity, overlapped report acquisition and bounded Watch discovery/startup/resync. Recorded live timings with v80.33-identical output: normal report ~2.1→0.65 s, date report 7.5→2.1 s, Watch startup ~6.2→0.65 s, resync 13→1.4 s. Diagnostics gained all-account evidence and privacy-safe Watch geometry; concurrent Full and shared fixtures retired 10 test-import edges. Verification/packaging policy remains in maintainer rules.
- v80.32–v80.33 separated Watch account refresh, prompt projection/report orchestration and source normalization; shared catalog ancestry and bounded sampling; moved fixtures (67→43 test-import edges, 46 fewer test-import dependencies), enforced bounded routine/coupling debt without raising caps, standardized `Context:` warning explanations, and added code maps/inventory/layer guards. Source/cache/billing semantics stayed unchanged.
- v80.29–v80.31 fixed synthetic/background continuation and running-model attribution, restored move/unanchored Watch Δctx and N/A for unexplained shrinks, sanitized terminal text and deduplicated source scans. Priced Next-Ictx tiers show one-decimal sample/mix cost multipliers refreshed every 15 minutes; unpriced thresholds keep CCost ranges.
- v80.25–v80.28 kept BLOCKED on accounts, split wide Watch quotas, added privacy-safe observations, compared consecutive Next-Ictx anchors for Δctx and removed mutable session-model attribution; v80.30 corrected move/unanchored regressions.
- v80.21–v80.24 added conservative table-local model fading (plain GPT tiers, Claude families, numeric Grok; preview/variant exclusions), parallel bounded quota acquisition, shared credential discovery and nonblocking Watch account refresh. Current main became recommended; packaged GitHub Releases remain paused.
- v80.15–v80.20 introduced four-column Relative CCost comparison, `--all-models` exact USD/M tiers, shared tier-aware sorting and non-destructive metadata state under cache/state/. Release metadata acquired independent classified health/backoff/cache and Diagnostics evidence; hourly Copilot/15-minute V2 checks retained pinned CCost. Verified New Models/promotions, sleep/wake quota recovery, safe error/recovery logs and Diagnostics archival/cleanup gained regression coverage.
- v80.8–v80.14 unified persistent Windows launchers with usable Ctrl+C/completion/error prompts, added session row subtotals without changing run CCost, simulated macOS diagnostics, hardened Windows release paths and sanitized read-only V1 SQLite errors/cleanup.
- v80.0 established the 0BSD public Python baseline, cross-platform launchers and bounded test membership. v80.1–v80.7 added illustrated docs, token-expiry/sign-in guidance without credential writes, verified V2 background liveness, developer Diagnostics launchers, read-only scoped V1→V2 migration-gap notices, recoverable source outages without fallback, and Simple HTTP/OpenRouter/DeepSeek/MiniMax accounts without fabricated CCost.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
