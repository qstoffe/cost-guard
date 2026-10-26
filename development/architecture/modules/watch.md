# Watch source contracts

Source revision: 282702930cb65362996a20ef4852c41b11c23bc0
Checked revision: 282702930cb65362996a20ef4852c41b11c23bc0
Last checked: 2026-10-26
Status: current

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Responsibility and ownership

The coordinator owns lifecycle, cadence/rendering and provider refreshes over abstract source/report contracts; lower layers never import Watch. Watch shares `ReportService` analysis/cache/context, never a second billing implementation or recurring subprocess. New Models shares the 12-hour first-sighting accent; existing seven-day eligibility is unchanged.

## Public contract

`WatchCoordinator.acquire_cycle` is the shared renderer-independent initialize/poll/history-slice seam. CLI keeps its terminal wait/render adapter; `src/watch/acquisition.py:LiveAcquisition` supplies headless cadence, hint buffering, selected-source recovery and source-free account wakes to one application-owned Web runtime. Both reuse the same tracker, valuation, retention, Today and account mechanisms. Web run origin is engine start, never tab open; live/account mutable state is not shared with finite report cleanup. The source hint pump bounds its queue to 1024, converting overflow to authoritative resync rather than blocking acquisition or inventing usage. Browser disconnect is independent of source state and never a terminal prompt event.

`watch/token_mix.py` owns run CCost and priced-only Token Mix keyed by source/session/message/step; completed pre-Watch requests stay excluded. `today_ccost.py` reconciles exact local-day requests with shared clone de-duplication, retaining deleted observations without a ledger. Interactive startup renders `Total today: Pending` (or the overnight date) before daily revision/history work. Once published, same-day CCost remains visible throughout subsequent enrichment/failure/recovery until atomic replacement; corrections may lower it. Midnight never relabels yesterday's publication. Main-thread slices acquire at most four necessary roots, reuse unchanged stable analysis and publish only after reconciliation. Midnight/DST resets the plan/day; native account publication reuses unchanged local totals. `Total YYYY-MM-DD` replaces `Total today` from 00:00–03:00, with idle redraws. [History acquisition](history-loading.md) owns scopes/evidence.

`WatchSessionSubtotal` sums selected rows' `PromptProjection.ccost` as Decimals, propagating unresolved provenance. Presentation formats `Σ`; native non-billable compactions contribute known zero. Amount/completeness enter change detection. Row subtotals need not partition run totals; no per-session run aggregate exists.

Global Watch selects rows before ordering whole session blocks: history first by latest supported end, active/recent last by latest event start, with ID ties. Tracker reuses its finite recent lifecycle for success, abort and terminal failure, not marker text, and uses all available block events rather than capped rows. Persistent failure evidence stays in analysis/projections; presentation derives critical row styling from the effective marker and preserves neutral `[ERROR]` labels after expiry. `PromptRowProjector` carries existing analysis terminal/compaction times; unavailable ends fall back to event starts, never observation time/duration. Scoped ordering is unchanged. Group/time changes enter both redraw signatures, including idle expiry. Presentation inserts one conditional table rule and adjusts activity placeholder offsets; [Watch lifecycle](../../../docs/watch-activity.md) owns the visible contract.

Global history cap membership uses the same supported-end/start fallback independently of the retained display key. Tracker restores prompt/compaction display sequence after selection, before grouping; running/recent protection, scoped selection and startup Earlier start ranking remain unchanged. No Watch-local terminal timestamp is introduced. `test_watch_terminal_recency.py` covers exact expiry, late native ends, unknown-end stability, native plugin-path interruption and selection/display separation. This is a correction inside existing ownership, not a new architecture boundary.

`watch/accounts.py` reconciles full keys and ages observations on every wake (stale after 60s, hard expiry after five minutes, including resume). `watch/account_refresh.py` owns main-thread publication and bounded reconnecting presentation over `AccountRefreshWork`; start signals are idempotent for autonomous acquisition, never a second polling clock. Auth/unavailability bypass retention. `ReportService.project_watch_accounts` projects cached local usage without source I/O. `accounts/quota_observations.py` records bounded run-local percentage/reset observations, success/change/publication times independently of scheduling. `cache/account_refresh_state.py` allowlists latest-writer evidence; Diagnostics separates it from independent report acquisition without identity/credential/response data. [Freshness semantics](../../../docs/account-support.md#watch-freshness-budget) keep upstream freshness unknown. Prompt success cannot regress to aborted; labels persist while red emphasis decays.

V1 batches payload-free revisions with bounded SQL parameters, never a root cap. V2 hints use a five-second cooldown; disconnect resyncs observed roots plus relevant changes. Startup covers 20 baseline roots plus all active/uncertain candidates regardless of age/row cap, skipping proven stable quiet roots; scoped Watch hydrates its tree and independently accounts for global Today. Changed unrelated old roots do not hydrate the dashboard. Quotas retain independent 30s healthy acquisition/60s freshness semantics. Shared local start epochs, lifecycle and cached source-free quota publication remain intact.

Source recovery retains the last projection and retries only the selected source every 5s (no reselection, subprocess or account refresh). The same coordinator owns unfinished initialization: staged hydration/local-usage acquisition precedes account work; partial state is discarded before fresh retry. V2 refreshes discovery/pools and resumes with authoritative snapshots/new events. Retired SSE readers are cancellable; no OpenCode process is stopped. Schema/auth errors are terminal; unreadable/concurrent data is bounded. Only `WatchedSessionEnded` intentionally ends scoped Watch; Ctrl+C includes initialization.

`sources/connectivity.py` observes complete operations, not harmless compatibility probes; `connectivity_events.py` owns the existing bounded source transition file (24 events/30 days, whitelist/no raw endpoints/auth/payloads). Watch and selection share it; Diagnostics archives without deleting live history. Metadata TLS certificate failures are distinct from other TLS; its existing cache/backoff owner is unchanged.

Watch tool observations use canonical prompt/task scope and one physical-call identity. `watch/tool_contracts.py` owns conservative persisted skill-input/metadata and bounded, known-script result evidence; no source reads, commands, secret discovery or accounting changes. `ToolObservation.skills` projects exact confirmed IDs and direct failure counts. Tracker attaches activity only to each session's latest prompt while it runs or retains its existing terminal marker, then removes rows on marker expiry or same-session supersession. Terminal snapshots retain final counts without live status; the final observation is reused for an unchanged source revision and may update on new authoritative evidence. Presentation adapts tool/skill rows to terminal width independently of fixed metric geometry; [activity contracts](../../../docs/watch-activity.md) define uncertainty and omissions.


Rolling account history extends the daily plan only to usable native/trailing-window starts, never a Watch calendar-month comparison. `src/reports/history.py` retains observed requests in that process-local scope and publishes after a finite plan completes. `src/analysis/period_ccost.py` indexes shared request valuation; source-free account queries advance on idle wakes/midnight without quota-driven history scans. Timestamp-only projection changes do not trigger redraws.

## Allowed dependencies

Watch depends on shared reports/analysis/domain and abstract source contracts; reports/analysis never import Watch. Presentation consumes projections without fetching history or native quotas.

## Entrypoints

`src/watch/coordinator.py`, `src/watch/acquisition.py`, `src/watch/today_ccost.py`, `src/reports/history.py`, `src/reports/accounts.py`, `src/presentation/token_mix.py`, `src/presentation/accounts.py`.

## Tests

`development/tests/test_watch_today_ccost.py`, `development/tests/test_account_period_ccost.py`, `development/tests/test_watch_idle_accounts.py`, `development/tests/test_history_loading.py`, `development/tests/test_watch_source_recovery.py`, `development/tests/test_quota_presentation.py`.
