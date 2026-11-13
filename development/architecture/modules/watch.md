# Watch source contracts

Source revision: 282702930cb65362996a20ef4852c41b11c23bc0
Checked revision: 282702930cb65362996a20ef4852c41b11c23bc0
Last checked: 2026-10-26
Status: current

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Responsibility and ownership

The coordinator owns lifecycle, cadence/rendering and provider refreshes over abstract source/report contracts; lower layers never import Watch. Watch shares `ReportService` analysis/cache/context, never a second billing implementation or recurring subprocess. New Models shares the 12-hour first-sighting accent; existing seven-day eligibility is unchanged.

Optional notice history uses `cache/model_notices.py` for resource-error classification, short lock waits and bounded retry/health evidence. Discovery retains dirty catalog/notice state, retries failed startup reads before writing, and never infers startup novelty from a delayed read. Shared first-sighting failures remain unavailable, preserving the original in-run observation for retry rather than fabricating a persisted timestamp. General cache transactions still propagate errors. Connection-local `synchronous=NORMAL`, WAL and ordinary callers' busy timeout remain unchanged.

## Public contract

FR000701 refines invocation lifetime: revision changes update bounded safe text,
not native disclosure openness. Browser per-call nodes survive single/multi
membership changes; new siblings do not inherit expansion. Logical nested spacing
indents activity without a second single-call gutter. `ToolFailure` carries ten
source-owned physical failed-call inputs at most, with fixed safe reason vocabulary.
One 4096-character ASCII-escaped input budget spans all three card lists, preserving
the 100-card event/replay bound. Counts remain complete; hidden/unrecoverable members
are explicit. Terminal failures follow existing activity grace; generation,
retained-source and verification gates clear their inputs independently of running
lifetime. No acquisition, accounting, persistence or CLI/Mini expansion changes.
[Diagnosis and evidence](../../journal/web/watch-invocation.md#stable-disclosures-and-physical-failures--fr-000701).

FR000697 adds `recent_finished.py`: at most five immutable, exact-root canonical
terminal cards qualified by engine-start/actual finish, complete snapshot, source
provenance and accepted root generation/revision. Partial observations retain old
evidence rather than replacing its finish; deletion/source identity and complete
reclassification invalidate it. `cards.py` promotes post-baseline new/changed roots
through the existing foreground permits, keeps the 3:1 historical fairness turn
and retains bounded visible captures beyond terminal grace. Global `HistoryPublication`
coverage/epoch is unchanged; an observed global publication atomically hides the
overlay. Independent cost/context enrichment remains nonblocking. Live hints
coalesce at a one-second minimum read interval, preserving source-error backoff;
poll-only sources keep their existing cadence. [Evidence](../../journal/web/recent-finished.md).

FR000647 is Full Watch presentation only: both prompt tables show the canonical
CCost total token, with independently source-verified Incoming Context CCost (I)
and Extra CCost (E) in the existing value help before unchanged grouped cost detail.
Displayed zero never invents component evidence. Projection, CLI, Mini, valuation,
acquisition and publication cadence are unchanged; `test_watch_prompt_cost.py`,
`web_live.cjs` and the existing Watch/help browser probes cover this scoped delta.

`WatchCoordinator.acquire_cycle` is the shared renderer-independent initialize/poll/history-slice seam. CLI keeps its terminal wait/render adapter; `src/watch/acquisition.py:LiveAcquisition` supplies headless cadence, hint buffering, selected-source recovery and source-free account wakes to one application-owned Web runtime. Both reuse the same tracker, valuation, retention, Today and account mechanisms. Web run origin is engine start, never tab open; live/account mutable state is not shared with finite report cleanup. The source hint pump bounds its queue to 1024, converting overflow to authoritative resync rather than blocking acquisition or inventing usage. Browser disconnect is independent of source state and never a terminal prompt event.

`watch/token_mix.py` owns run CCost and priced-only Token Mix keyed by source/session/message/step; completed pre-Watch requests stay excluded. `today_ccost.py` reconciles exact local-day requests with shared clone de-duplication, retaining deleted observations without a ledger. Interactive startup renders `Total today: Pending` (or the overnight date) before daily revision/history work. Once published, same-day CCost remains visible throughout subsequent enrichment/failure/recovery until atomic replacement; corrections may lower it. Midnight never relabels yesterday's publication. Main-thread slices acquire at most four necessary roots, reuse unchanged stable analysis and publish only after reconciliation. Midnight/DST resets the plan/day; native account publication reuses unchanged local totals. `Total YYYY-MM-DD` replaces `Total today` from 00:00–03:00, with idle redraws. [History acquisition](history-loading.md) owns scopes/evidence.

`WatchSessionSubtotal` sums selected rows' `PromptProjection.ccost` as Decimals, propagating unresolved provenance. Presentation formats `Σ`; native non-billable compactions contribute known zero. Amount/completeness enter change detection. Row subtotals need not partition run totals; no per-session run aggregate exists.

Global Watch selects rows before ordering whole session blocks: history first by latest supported end, active/recent last by latest event start, with ID ties. Tracker reuses its finite recent lifecycle for success, abort and terminal failure, not marker text, and uses all available block events rather than capped rows. Persistent failure evidence stays in analysis/projections; presentation derives critical row styling from the effective marker and preserves neutral `[ERROR]` labels after expiry. `PromptRowProjector` carries existing analysis terminal/compaction times; unavailable ends fall back to event starts, never observation time/duration. Scoped ordering is unchanged. Group/time changes enter both redraw signatures, including idle expiry. Presentation inserts one conditional table rule and adjusts activity placeholder offsets; [Watch lifecycle](../../../docs/watch-activity.md) owns the visible contract.

Global history cap membership uses the same supported-end/start fallback independently of the retained display key. Tracker restores prompt/compaction display sequence after selection, before grouping; running/recent protection, scoped selection and startup Earlier start ranking remain unchanged. No Watch-local terminal timestamp is introduced. `test_watch_terminal_recency.py` covers exact expiry, late native ends, unknown-end stability, native plugin-path interruption and selection/display separation. This is a correction inside existing ownership, not a new architecture boundary.

`watch/accounts.py` reconciles full keys and ages observations on every wake (stale after 60s, hard expiry after five minutes, including resume). `watch/account_refresh.py` owns main-thread publication and bounded reconnecting presentation over `AccountRefreshWork`; start signals are idempotent for autonomous acquisition, never a second polling clock. Auth/unavailability bypass retention. `ReportService.project_watch_accounts` projects cached local usage without source I/O. `accounts/quota_observations.py` records bounded run-local percentage/reset observations, success/change/publication times independently of scheduling. `cache/account_refresh_state.py` allowlists latest-writer evidence; Diagnostics separates it from independent report acquisition without identity/credential/response data. [Freshness semantics](../../../docs/account-support.md#watch-freshness-budget) keep upstream freshness unknown. Prompt success cannot regress to aborted; labels persist while red emphasis decays.

V1 batches payload-free revisions with bounded SQL parameters, never a root cap. V2 hints use a five-second cooldown; disconnect resyncs observed roots plus relevant changes. Startup covers 20 baseline roots plus all active/uncertain candidates regardless of age/row cap, skipping proven stable quiet roots; scoped Watch hydrates its tree and independently accounts for global Today. Changed unrelated old roots do not hydrate the dashboard. Quotas retain independent 30s healthy acquisition/60s freshness semantics. Shared local start epochs, lifecycle and cached source-free quota publication remain intact.

Source recovery retains the last projection and retries only the selected source every 5s (no reselection, subprocess or account refresh). The same coordinator owns unfinished initialization: staged hydration/local-usage acquisition precedes account work; partial state is discarded before fresh retry. V2 refreshes discovery/pools and resumes with authoritative snapshots/new events. Retired SSE readers are cancellable; no OpenCode process is stopped. Schema/auth errors are terminal; unreadable/concurrent data is bounded. Only `WatchedSessionEnded` intentionally ends scoped Watch; Ctrl+C includes initialization.

Web-only `source_status.py` confirms retryable read failures with retained evidence
after five monotonic seconds, without moving the first-failure origin on repeated
failure/partial capture. Existing publications advance retrying to unavailable;
successful relevant acquisition alone clears it. Initial failures remain immediate
except Earlier's explicit initial-confirmation option: retryable failures leave history
loading for the same five seconds, without publishing cards or claiming coverage.
Typed concurrent-change proof churn remains verifying, not an age-based unavailable
state; actual I/O confirmation keeps its five-second rule. Web Live also continues
automatic recovery from repeated concurrent-change observations without a failure-count
termination. Non-retryable failures remain immediate. Cards freeze observed duration while retrying; daily uses the existing
single history lane for a five-second retry. Browser HTTP/SSE health remains separate;
no CLI recovery/cadence or source-acquisition limits change. Web history first selects
the five sessions with the latest supported terminal times, then orders exact representative
finish/session/event IDs ascending. `WatchCapture.history_row` owns the representative;
capture retains its bounded context anchor even outside the six most recent starts.
Unknown-ended history fills spare slots before known finishes with deterministic identity,
never inventing a timestamp or displacing a known finish. Running start order, grace and CLI
history semantics remain unchanged. Context warnings retain canonical severity.

`sources/connectivity.py` observes complete operations, not harmless compatibility probes; `connectivity_events.py` owns the existing bounded source transition file (24 events/30 days, whitelist/no raw endpoints/auth/payloads). Watch and selection share it; Diagnostics archives without deleting live history. Metadata TLS certificate failures are distinct from other TLS; its existing cache/backoff owner is unchanged.

Watch tool observations use canonical prompt/task scope and one physical-call identity. `watch/tool_contracts.py` owns conservative persisted skill-input/metadata and bounded, known-script result evidence; no source reads, commands, secret discovery or accounting changes. `ToolObservation.skills` projects exact confirmed IDs and direct failure counts. Tracker attaches activity only to each session's latest prompt while it runs or retains its existing terminal marker, then removes rows on marker expiry or same-session supersession. Terminal snapshots retain final counts without live status; the final observation is reused for an unchanged source revision and may update on new authoritative evidence. Presentation adapts tool/skill rows to terminal width independently of fixed metric geometry; [activity contracts](../../../docs/watch-activity.md) define uncertainty and omissions.

`ToolObservation.tool_outcomes` aggregates distinct evidenced calls by tool name and failed/cancelled outcome inside the same observation pass; cancellation takes precedence. `failed_count` remains failure-only for CLI/skills, while derived cancellation/combined counts and explicit outcome DTOs serve Web. All-call groups stay inclusive, and terminal retention preserves the outcome tuples without extra acquisition. Full Watch renders those ordered subsets as red text; foreground and background Running lines both use `--watch-running`. Browser code never classifies source output.

FR000632 adds `watch/invocation.py`, a Web-card-only opt-in boundary over the same
canonical physical calls. FR000648 refines this allowlist: ordinary commands retain
their literal text, while `invocation_redaction.py` masks recognized credential value
spans or withholds ambiguous credential/header syntax. Structured/content-bearing,
unsupported, oversized and absent input have separate qualifications; safe commands
have no warning. Positive finite native shell/bash timeout numbers are presented in
milliseconds with a compact duration, never an inferred default/countdown. No raw output/metadata/environment crosses the
DTO. FR000688 adds bounded per-job lists to `ToolObservation` while retaining single
compatibility fields. `BackgroundActivity` carries source-proven original part/call
identities and ephemeral scalar registry input; each eligible job requires its own
exact session/assistant/native-job join. Kind/time/name never supplies identity.
`invocation.py` is the common privacy boundary (five running entries per mode,
honest total; FR000701's shared card budget above). Native input takes precedence; command-only mismatch shows original
input alone with executed-form uncertainty, while ownership/ID conflicts clear all
text. Unknown/aggregate jobs cannot borrow another command. Derived
details are retained with capture results, not recomputed on duration ticks or persisted.
Unverified/retained captures, catalog generations awaiting re-verification and terminal
prompts clear live detail. Opaque source-generation/physical-call identity and call-input
revision drive native disclosure reconciliation; body nodes remain stable on duration
and same-call revision updates; identity loss clears only affected entries. Missing/unverified
details show contextual Running facts and cause-specific prose, not a generic dead end.
Freeform screening remains bounded, not guaranteed secret detection.


Rolling account history extends the daily plan only to usable native/trailing-window starts, never a Watch calendar-month comparison. `src/reports/history.py` retains observed requests in that process-local scope and publishes after a finite plan completes. `src/analysis/period_ccost.py` indexes shared request valuation; source-free account queries advance on idle wakes/midnight without quota-driven history scans. Timestamp-only projection changes do not trigger redraws.

## Allowed dependencies

`watch/history_publication.py` owns Web Earlier membership proof and a bounded
five-card immutable publication, separate from active card readiness. `cards.py`
retains per-root scalar coverage keyed to the source-pinned coordinator lifetime and
catalog generation. Revision/status changes require re-verification even for evicted
nonwinners. Complete canonical evidence is mandatory; metadata prioritizes admission
only. `history_state`, opaque source scope, proof epoch/catalog revision, original
verification time, coverage counts and typed cause travel together through the Live
DTO. Unchanged ticks never renew evidence; refreshes retain one qualified epoch.
Removal/resumption invalidates affected entries; clients cannot restore independently
retained rows. Cold sources without a safe finish-bound certificate still need full
coverage; no new scanner, persistent raw ledger, worker lane or CLI change is added.

The in-progress foreground-recovery candidate admits small isolated history batches
within the same four logical card-root slots, reserving one from history for active
singles. Occupancy is per root, not per future; undersized groups do not wait to fill.
Only source hydration overlaps inside a batch; report/cache/pricing projection stays
on its owning thread. `capture_rows` accepts the already-certified snapshot without
rehydrating. A hydration-only watchdog cancels/joins an overrun before fair replay;
unfinished members subsequently run as singles. Replay is a scheduling event, not
a source outage or coverage. Epoch/generation/revision acceptance remains required.
Batching is enabled only when the selected source exposes the explicit outcome seam;
other sources retain independent single captures, not serial shared-future coupling.
Watch-card selection alone omits unused migration-gap inspection. The retained
candidate has matched three-way synthetic and independent real-global-oracle
evidence, not blanket whole-Web acceptance; see
[the active experiment ledger](../../journal/web/foreground-recovery.md).

The explicit Web V2 composition now injects `card_readers.py`: at most one
exclusively borrowed reader per existing card executor thread, four total.
Construction is registered before health validation; each job still probes the
selected source and builds fresh analysis/pricing/cache facades. Guidance and
other lanes retain fresh sources. Same observed epoch and equal detached actor
contents alone preserve the latest complete catalogue/index, without renewing its
two-second before-bracket eligibility. Every capture keeps its after-bracket;
singletons also reject an epoch change during hydration. Job metrics are replaced
before validation, transport counters reset in place, and per-session diagnostics/
skill lookups clear per borrow. Failures/replay retire readers; cancellation covers
idle and active readers, and final close runs after executor join even on a fatal
future. `test_watch_card_readers.py` covers reuse, invalidation and ownership. This
is a measured candidate; the independent final real-source oracle in the ledger
proves Earlier availability separately, not from reader reuse alone.

The completion-refill experiment signals one coalesced wake per unique completed
card/guidance future, after worker cleanup, with unchanged logical permit limits.
The application owner services one bounded acceptance/admission turn without full
projection/SSE, source/catalog polling, account refresh or population-wide numeric
guidance work. Regular publication retains its independent deadline and wins when
due. Result draining snapshots completed futures before reclaiming permits, so a
racing completion cannot lose its rows before replacement admission. Fault/churn/
replay-only bursts and failed roots wait for normal cadence; late empty wakes cannot
restart them. Capture eviction remains part of every servicing turn, not publication.
`test_watch_completion_service.py` covers the narrow seam, race and cleanup lifetime.
This seam does not itself certify an earlier publication. Separate authenticated
Full/Mini history leases promote the bounded completion-service demand, including
a visible Mini with hidden opener; history already runs at its measured safe maximum
from startup, so the recorded scoped no-acceleration exception remains explicit.

The same in-progress candidate's `card_guidance.py` owns one completed numeric
context-guidance observation and at most one sequential producer across scopes.
It is charged against the existing total/historical card permits until exit;
other cards never wait in occupied workers for the sample. Web captures explicitly
defer the multiplier, not tokens or actual warning text/severity. The scheduler
promotes existing active demand and preserves the historical ceiling/reserved
active slot. Dependencies, observed nonsecret source epoch, attempt generation and
calculation-start wall/monotonic freshness reject obsolete/rollback results. Expiry
alone never cancels healthy computation: a completed old same-scope sample may display
as `refreshing` with its original dated sample time while one fair replacement runs.
Freshness is never renewed at completion/access. Targeted source
cancellation keeps unrelated cards alive. Pure compact enrichment cannot advance
Earlier proof or trigger rehydration. `test_watch_guidance.py` covers occupancy,
admission, cancellation/setup, A→B→A, retry, TTL/rollback, empty success, pricing
requalification and superseded hidden-compaction anchors. Certified names, supported
finish/model/effort and context do not wait for independent session cost or numeric
guidance. `test_watch_history_acquisition.py` verifies this progression without a
new winner scan/proof epoch; Full/Mini staged DOM tests cover the shared display.
Real/global proof and measured performance remain separate entries in the ledger.

Web cards and Session detail share `reports/session_history.py::analyze_observed`:
retained objects preserve usage, while a source-certified complete snapshot owns
current lifecycle through ordinary causal analysis. Failed pre-response starts
join assistant work only within their canonical prompt window; a newer assistant
still wins. V1's read transaction and
V2's all-page/revision-bracket acquisition certify `SessionSnapshot.complete`;
partial/custom sources default to unproven. Durable ends stay assistant-attempt
scoped through omitted idle rows. A failed start retains its initiating boundary
if omitted, without restoring stale active children/tools; complete reclassification has no invented
outcome/end. Card generation and capture-time checks reject delayed rows
and failures. Terminal grace never contributes to running state or duration.

Web Watch's existing single background history lane retains one `WatchHistoryAcquisition`
across isolated services. Revision-proven roots skip hydration; known request telemetry
and causal initiating-prompt identities survive omissions. `analysis/daily_usage.py`
filters that population by canonical request timestamp/local-day boundary, clone-deduplicates,
and projects full-population cost/count/category mix together. The live thread publishes
only finished matching-day groups; rollover rejects late previous-day results. It never
scans history or prices browser-side. Native quota refresh remains independent.

`reports/watch_context.py` maps `session_watch_context` and canonical price thresholds
to one latest-prompt-owned continuation DTO, including hidden compaction rewrites and
the Watch multiplier/cost range. Full Watch shares this valid latest session continuation
across concurrent cards and suppresses it on source failure, independently of row Ictx.
There is no duplicate row-cell/footer warning DTO; CLI context semantics stay
unchanged. `application/watch_accounts.py` owns Watch-only stable primary slots and Used
display; native primary flags/order normalize into account-scoped labels, preserving an
absent primary on partial/error acquisition without inventing provider-wide windows.
Model limits never become account primary. Unavailable sign-in-method changes retain
their existing invalidation semantics. Canonical
account period projection explicitly marks provider-attributed estimated scopes.

Watch tables own themed body/header surfaces; first-request Ictx immediately precedes
Δ Ctx. One Session Context / CCost line follows the table before activity,
with canonical guidance once after both values. Approaching colors the triangle and
context figure amber; exceeded uses a red octagon/exclamation, context figure and
relative multiplier only. Session cost, labels, boundary wording and alternate price
ranges stay neutral. Sibling selectors separate cards, and outlined history has
natural document height. CCost Today presents the known integer without altering its
completeness metadata; routine refresh-state changes preserve its DOM and valid values.

`analysis/session_cost.py` owns a reconstructible `session-ccost-v1` namespace on the
existing generation-2 cache. Source instance/generation/root, analysis/aggregation version
and reference catalog identity isolate minimal hashed request fingerprints and unrounded
amounts. Revision changes trigger complete membership/fingerprint reconciliation, not
blind total reuse; unchanged contributions skip valuation. Authoritative omissions delete
contributions, partial source brackets never overwrite a complete checkpoint. Canonical
`trace_entries`, `unique_usage` and `comparison_cost` keep root-tree/report parity, including
children, compaction and provisional usage. No private prompt content is persisted.
`watch/session_costs.py` owns one independent background future plus scalar
`SessionCostState` and fair admission across visible roots. `WatchCards` hands off
canonical evidence and releases evicted heavy snapshots, retaining the baseline and
source key. Only source identity/revision/completeness or catalog identity changes
require reconciliation; row generations/timestamps/publication ticks do not. Completed
older same-source revisions can publish a checking baseline, never verified-current
status for the newer evidence. Replaced source identities cannot borrow that result.
Rows and account/daily work never wait for it.
Presentation ticks do no cache/source work; optional cache failures recompute from source
with honest persistence/coverage state. This is not a billing ledger or Sessions UI change.
Reference-catalog identity is checked once globally in the same bounded lane at
60-second admission intervals, without per-root reconciliation or history hydration.
Only a changed signature schedules root work. Failed validation stays unavailable
with a bounded retry; incomplete source results remain partial. Full/Mini consume
the same scalar/state; initial unknown is Loading, normal checking is quiet, and no
session-total presentation delay timer is used. Production composition
supplies isolated pricing/cache resources without source selection or schema writes.

Watch depends on shared reports/analysis/domain and abstract source contracts; reports/analysis never import Watch. Presentation consumes projections without fetching history or native quotas.

## Entrypoints

`src/watch/coordinator.py`, `src/watch/acquisition.py`, `src/watch/today_ccost.py`, `src/reports/history.py`, `src/reports/accounts.py`, `src/presentation/token_mix.py`, `src/presentation/accounts.py`.

## Tests

`development/tests/test_watch_today_ccost.py`, `development/tests/test_account_period_ccost.py`, `development/tests/test_watch_idle_accounts.py`, `development/tests/test_history_loading.py`, `development/tests/test_watch_source_recovery.py`, `development/tests/test_quota_presentation.py`.
