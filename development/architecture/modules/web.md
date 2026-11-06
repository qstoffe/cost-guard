# Optional Web runtime

Source revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Checked revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Last checked: 2026-11-06
Status: current

## Responsibility and ownership

`assets/report-loading.js` owns the four finite pages' shared
determinate loader, monotonic stage bands and bounded admission retries.
AI Stats alone has a resumable logical attempt; every child retains its finite watchdog.
`app.js` starts only eligible visible routes, preserves quiet-refresh DOM and applies
validated results atomically. Historical cache/load/projection observations are
allowlisted by `application/service.py`; batch counts cannot consume global bands.
The existing `source_startup.py` owner supplies detached typed `report_status()`
proof to HTTP admission and status without a second selection or wake path. Real
transient failures/429 use bounded backoff; terminal failures do not. Live stream
reconnect is not source failure. No shared report Cancel markup/handler remains.
Navigation/hiding preserves the original bounded page-memory admission intent and
in-flight acquisition, never starting new inactive periodic checks. Hidden documents
read settled server outcomes before applying the client deadline and cannot strand completion on a
suspended animation frame. Existing process, result, priority, source, valuation,
freshness and CLI/Live ownership boundaries remain unchanged. Current evidence and
limits: [finite report loading](../../journal/web/report-loading.md).

`assets/help.js` owns one text-only contextual-help controller per document,
including Mini PiP. Shared passive buttons/adjacent cues preserve selection and
action cursors; manual Popover, pointer transfer, focus/tap, Escape/light-dismiss and
current-token refresh replace native-title/duplicate help. No acquisition or layer
boundary changes. [Writing conventions and surface inventory](web-help.md) are the
current reference; older per-cell/native-tooltip descriptions below are historical.

`src/web/http.py` owns bounded loopback HTTP, fixed assets and routing; `src/web/security.py` owns one-use bootstrap/HttpOnly sessions/CSRF; `src/web/jobs.py` owns finite admission, process isolation, progress, cancellation and retention; at most 64 progress messages drain per host turn to prevent scan backpressure without starving control/Live. `src/web/composition.py` creates fresh canonical ReportApplication integrations.

Only validated terminal IPC grants up to one second for natural child teardown,
including a completed Stats slice whose logical job requeues. Cancellation,
watchdog, malformed/abandoned IPC and shutdown force termination promptly, retaining
the existing one-second terminate and kill joins. Exit must be confirmed before
closing handles or releasing the active slot. An unconfirmed exit latches
`report_worker_stop_timeout`, blocks all result reuse/admission/polling and retains
the exact owner for bounded cleanup retries. HTTP cancellation propagates this fault
to the host rather than hiding it in a request future. Serving cleanup still closes
Live/events/HTTP; main-owner close retries the retained child, without clearing the
host failure or double-counting worker time. This is a safety repair, not proof of
the rare Windows shutdown delay's cause; see the report-loading journal.

Models' explicit `POST /api/models/refresh` accepts only authenticated/CSRF-protected
`{}` and submits the Web-only `ModelsPriceRefresh` request marker. Existing job equality
coalesces concurrent actions separately from normal TTL captures; all finite-process,
result, deadline and parent-loss bounds remain. Composition calls the concrete provider's
strict `refresh_catalog()` and pins that validated catalog on a fresh ReportService
before canonical acquisition/projection. Unlike legacy fail-soft `get_catalog(force=True)`,
strict refresh raises on upstream failure, never labeling cached prices/date as fresh.
No account providers are constructed and Live's pinned catalog remains unchanged.
Browser replacement consumes one coherent report, retaining filters/sorts/unit/focus/pan;
failure retains the prior DOM/date. Mini help selects exactly primary-window Capacity
and `watch_reset` tokens; richer Full Watch/Accounts help and visible warnings remain.
Evidence and the scoped split-verification decision: [Models pricing](../../journal/web/models-pricing.md).

`src/web/assets/app.js` owns finite refresh/stale state and memory-only observations; Models keeps its frozen normal report. `reports.js` owns route resolution; eligible visible finite pages acquire automatically through `app.js`, without hidden-page preloading. Accounts bypasses finite jobs/report shell and consumes app-level retained Live, even without a Watch DOM. `account-cards.js` is the single Watch/Accounts subscription renderer: account-keyed membership, bound metric/reset/help updates, per-card signatures excluding the publication clock, shared physical-width cap and existing subgrid styles. Empty success clears membership; missing/failed empty publications retain usable cards with truthful warnings. Settings synchronize visible/detached roots without acquisition. `render.js` presents DTOs with exact Decimal/vector sorting; generic reports retain presentation search/50-row paging, while Models has independent catalog/version filters and complete document-scrolling rows. Totals never come from cells. Sessions bypasses finite jobs and the report shell: `sessions.js` renders six-column live catalog pages; `session.js` renders one ten-column complete chronological history. Both use intrinsic metric tracks, elastic title/preview and document vertical scrolling. Shared Watch `ContextLine` and contextual-help components consume canonical report context, not a browser estimator.

Token Mix, AI Stats and Comparisons are cached historical finite views, not Live owners.
`token-mix.js` owns a retained compact summary and exactly two 13-column
tables, exact integer/Decimal/rational sort keys, prepared unit tokens and text-only
ContextHelp. Keyed reconciliation preserves rows, focus and panning; it never values
or acquires usage. `ai-stats.js` renders ten equal server-prepared emoji cards, five
periods, safe record links and shared title help. AI Stats automatically acquires
selected 30-day scope through shared bounded slices; period changes immediately
reprioritize missing work, while valid compact evidence is shared across scopes.
Unknown old roots cannot be excluded by metadata, so earlier Today/7-day completion
is conditional on validated coverage. `cached-reports.js`
and `app.js` share 5-minute Token Mix / 15-minute AI Stats active-visible scheduling
and last-success re-entry bands: fresh immediate, overdue through 60m quiet, >60m
withheld with bounded progress/recovery. Active pages never blank at minute 61.
AI Stats logical work is host-owned, independent of polling interest. Its one job
retains at most five validated requested scopes: the latest selection prioritizes
the next slice, then earlier missing goals resume from the same observation/scan.
Coherent narrow results can remain usable while wider goals finish. Internal cancel,
shutdown and finite-child/no-progress/resource bounds remain. Other running
finite reports keep their original lifecycle. Whole-result
validation and synchronous retained-node updates preserve focus/scroll. Both
historical kinds coalesce without relabeling observations. AI Stats shares one active
job across all scopes/tabs; latest explicit selection owns the next finite slice.
`stats_jobs.py` pins observation/scan identity, accepts coherent milestones, bounds
no-progress retries and shrinks timed-out batches. `jobs.py` retains one fresh child,
parent-loss termination, fair low-priority requeue and bounded IPC. Only its logical
AI Stats acquisition may exceed 120 seconds; other report deadlines are unchanged.
Compact report evidence belongs to reports, not Live. Scoped update:
FR000614 delta on `d381d399f401c24302fa559eb62ec68e33aba4e7`; other
contracts retain their original checks. [AI Stats findings](../../journal/web/ai-stats.md)
and [Token Mix findings](../../journal/web/token-mix.md) separate proof/limits.

Comparisons' semantic identity owner is `analysis/input_identity.py`: ordered exact
normalized text/verified inline content, versioned fingerprint, fail-closed references.
`analysis/matched_runs.py` owns individual-run grouping, qualified gaps and the optional
period fact. `reports/matched_inputs.py` acquires all roots in bounded source batches;
`reports/matched_runs.py` maps canonical prompt attribution/timing/historical context
to compact metrics. Only fingerprint/scalars enter its disposable revision-keyed index;
existing derived bundles may be read, never newly persisted with raw prompts by this
scan. Fresh previews are ephemeral; warm scans batch at most ten displayed representatives.
`application/comparisons.py` exports allowlisted run/group/page facts and unit tokens,
never fingerprints. `assets/comparisons.js` keeps keyed sections/rows, all repetitions,
ten-group paging, shared Watch table/help and coherent source-revision resets.
Identical low-priority jobs coalesce; five-minute checks require active visible online
route state. AI Stats reuses its own period acquisitions to add an optional eleventh
fact, preserving its ten baseline metrics, period/cadence and independent ownership.
Source change, incomplete pricing/timing, zero baselines and unsupported attachments
never turn into an exact no-match/benchmark claim. [Evidence](../../journal/web/comparisons.md).

The Web Reports menu, date form and date-only renderer are retired. `reports.js`
resolves old `#/reports` hashes to a scope-free Sessions redirect; `app.js` replaces
the history entry before constructing view state or acquiring anything. Queries are
discarded, including invalid dates and unrelated sort/page parameters. No hidden
date job or Sessions date filter remains. CLI date/range engines, canonical DTOs,
shared `/api/reports` validation/jobs and date-history progress labels used by
surviving captures are unchanged. Current routes: Models, Watch, Sessions/detail,
Accounts, Token Mix, AI Stats, Comparisons and Settings (`docs/web-beta.md`). The old
`#/cost-per-hour` hash aliases AI Stats; reusable rate APIs/session-detail help remain.
Actual checks and explicit proof limits: [Reports retirement verification](../governance/verification/web-reports-retired.md).

`application/session_catalog.py` owns full observed membership, six exact server comparators and stable older-page epochs. Seven latest-visible-page admissions alternate with one oldest-attempt background turn, within four-root/two-second admission slices; unchanged validated scalars are reused. Per-root failures expose unavailable/retained states with bounded backoff, terminal failures wait for changed evidence, and lane-wide failure never masquerades as pending. Running requires current successful evidence. `reports/session_summary.py` caches source/dependency/algorithm-checked scalars; active/running roots bypass reuse. Every metric key must validate before global sorting, otherwise activity order is explicit. `watch/web_coordinator.py` shares catalog observations and isolates this lane from detail, account history and four card workers. HTTP never acquires history; transport/cancellation still bounds individual reads.

`assets/app.css` shares the Watch-derived compact header/cell/divider/rounded-shell contract across semantic Sessions, Models and both Token Mix tables, preserving their individual tracks/sorts. Sessions uses browser-local numeric date fields (not locale-string parsing), accessible pending cells and URL-backed pager buttons. Detail's adaptive preview keeps intrinsic numeric columns; a separate prepared first-request context token preserves raw values and richer CLI/Watch transitions. Indeterminate progress belongs only to initial/pinned acquisition, not complete-history background checks. No new acquisition owner, timer, source or pricing boundary is introduced.

`application/session_detail.py` round-robins captures on the isolated detail lane. `begin` pins a capture and `chunk` reads rich 25-row slices from that same revision while acquisition may advance; full totals remain canonical. Compatibility 50-row `page`/`freeze` remain API-only. `reports/session_history.py` retains canonical evidence outside durable caches; omissions freeze lifecycle/time rather than falsely complete rows. Unchanged running evidence reuses attribution/valuation. The browser batches new DOM suffixes, retains keyed rows/selection/focus/document anchors, closes obsolete leases and has one five-second polling timer through navigation races. Web→application→reports is unchanged; missing/archive/outage is not empty success. Scope/cache/route inventory: `docs/web-beta.md`; measured evidence and the scoped cold-index exception: [Sessions findings](../../journal/web/sessions-live.md).

`src/web/host.py` owns shutdown of HTTP/jobs and one `src/application/live.py` thread; GUI run/close stays on main. `source_startup.py` runs once on that Live worker after config validation, reuses healthy source selection, and optionally calls `src/opencode_service.py`'s fixed hidden wake (5s). Narrow V2 absent/transport categories qualify, never unreadable/invalid registration, permission/auth/schema or selected V1. Fresh registration/API selection with the existing short read budget proves readiness; even CLI failure/timeout can only succeed through that proof. A lock/event coalesces entry paths and holds finite jobs queued until the attempt ends, not HTTP/navigation. `starting_opencode` is a detached SSE/HTTP state mapped to visible/accessibly announced feedback, cleared before ordinary acquisition/wait/failure. Later Live factories, tabs and finite report workers cannot wake. Composition transfers the Watch service to `src/watch/acquisition.py`; tabs only read detached values. Live persists without tabs, preserving engine-start origin and independent account cadence. Finite reports never borrow/close that context. Unexpected faults reach main RuntimeErrors (managed logs outside checkout); children monitor their exact parent sentinel. OpenCode is never stopped.

LiveRuntime requests optional driver cancellation before joining. Web's
`watch/source_reads.py` tracks only its isolated in-flight sources; cancellation
retires their V2 transports before pool joins, including late service admission.
V2 buffered reads use a cancellation-aware raw socket wait because cross-thread
socket shutdown alone did not wake a timed Windows read in the causal fixture.
Original per-read timeouts remain intact; idle connections and response bodies
remain owner-closed, without a daemon escape or shared-service stop. Daily history
uses the existing four-root slices and authoritative shared V2 brackets, rather
than one complete catalog fetch per root. Finished-plan publication, retained
history, native periods, revision proof and CLI cadence are unchanged. Probe-only
phase observations and primary-plus-cleanup exceptions are development evidence,
not a production telemetry or timeout/retry system. See
[lifecycle findings](../../journal/web/live-lifecycle.md).
Account close additionally reaps idle quota workers within one shared 200ms budget;
it does not extend or wait out external-provider HTTP. The real probe rejects any
remaining owned worker, not just a live serving/publisher thread.

`src/web/events.py` publishes immutable full live/progress/terminal state with instance-bound IDs, 32-event/8 MiB replay and 2 MiB publications. `src/application/live_projection.py` allowlists Watch/tool/skill/context, subtotals and run/Today (not normal month/billing). `src/web/assets/live.js` owns one cookie-authenticated EventSource per tab. Gaps require HTTP resync; duplicates/older events cannot reset values; old instances require authorization. Terminal notices stop retry across gaps; offline retains evidence, never invents completion or launches servers.

Full Watch's prompt **CCost (I + E)** cell concatenates the existing immutable
`ccost`, `incoming_context_ccost` and `extra_ccost` display tokens. Both card types
reuse `PromptRowProjector`'s first-attributed-request incoming valuation and remaining
usage, including supported provisional/child observations. No acquisition, valuation
or lifecycle owner changes. Additive report-owned `incoming_context_ccost_known` and
`extra_ccost_known` distinguish first-request input-category coverage from all-request
I/C/W/O coverage. Only cards export those flags to the immutable display adapter, which
withholds unsupported component tokens without altering raw/CLI/other-report values.
Unknown components stay independent, partial totals retain
coverage. Mini Watch pairs that prompt total with its independent whole-session total, without the I/E split. Header help and intrinsic
metric widths remain shared. `test_watch_prompt_cost.py`, `integration/web_watch_prompt_cost.cjs`
and `fixtures/watch_cost_browser.cjs` pin parity, units, unknowns and actual hidden layout.

Shared Watch/Accounts `watch_accounts.py` quota slots bind identity-matched period cost to
`projection.quota_record`; legacy report account DTOs retain their original scopes.
`application/quota_ccost.py` calculates reference Capacity/Remaining using Decimal:
verified Copilot included credits use the native allowance/remainder; other current
valid windows use observed cost / raw used fraction. Partial pricing, unknown or
ambiguous scopes, invalid/expired evidence and zero-used ratios withhold estimates.
`display.py` publishes both Credits/USD tokens; JavaScript only selects tokens.
Full Watch and Accounts show Today, native percentage with bare reference parentheses, Capacity,
bar, reset and pace using seven subgrid rows. Only secondary regions have a divider.
Native ratios/money/source/attribution stay in accessible help.
Mini keeps a single primary line and exposes Capacity in help. Known Used zero remains
numeric; unknown reference amounts use ?. Unlimited Capacity is N/A with Used fallback.
`application/quota_display.py` adds pure Web-only Used/Remaining variants from each
quota's normalized native facts. A trustworthy native remainder wins; a finite
usage complement is safe fallback. Unlimited, zero/missing limits or unknown usage
never invent Remaining. `render.js` selects variants and updates bound text/bars in
place, including detached Watch views; `mini.js` redraws its retained keyed rows.
Provider-confirmed idle rolling zero keeps native 100% Remaining/full healthy fill
independently of unknown reference Capacity, without fabricating a reset. Native
exhaustion is independent of fill orientation/rounding. Acquisition, period
accounting, CLI and remaining pace semantics are unchanged.

`watch/running.py` aggregates distinct canonical in-progress focal prompts once per
Web publication, excluding compaction/history/placeholders/terminal grace. Count,
prompt-only CCost and maximum canonical duration travel together with completeness
and pricing state. Empty success differs from missing/partial acquisition; source
capture failure freezes retained card duration. `assets/mini.js` owns one explicit
Document PiP session per owning document, independent DOM and route lifetime. It
consumes app-level Live/health/settings directly, without another connection, auth
or acquisition owner. Window-identity checks reject stale callbacks/replacements;
main pagehide ends the session. The PiP document's timer only detects stale
publications, never extrapolates duration; repeated progress/snapshots cannot
refresh its epoch. External `mini.css` reuses `app.css` theme tokens under unchanged
CSP. Primary subscription costs reuse the indexed native-period history lane and
stable server primary selection, with estimated/partial attribution retained.

Mini's controller installs the effective theme before adding PiP styles/content.
Web copies the owner's computed custom properties and resolves native content
`color-scheme` from the owner's media query: Chromium PiP can independently prefer
dark while the main page is light. Confirmed Settings changes and an owner media-query
change listener resynchronize the palette without data/render timers or new acquisition.
Closing/replacing PiP removes that listener; Classic removes all inherited Web overrides
and retains its original shared CSS. Mini-only Web canvas/quota-surface/scrollbar rules
never restyle the owner, Classic or browser-native chrome. No layer boundary changes.

Mini renders canonical active/focal card identities, not the running aggregate: one
keyed row per prompt with prompt-local cost/duration/context and shared terminal grace.
Both tables have four columns: active `Session | CCost (Total) | Duration | Ctx`,
historical `Activity | Session | CCost (Total) | Ctx`. Session contains only the flexible,
ellipsized title; the cost cell pairs `prompt.ccost (session_summary.cost)` at its
intrinsic nonwrapping width, using independent shared display/state handling.
Active Session help preserves the canonical prompt ordinal and full title;
historical cost help reads the canonical singleton representative's model/effort,
duration, known calls and relevant linked/mixed/partial/outcome evidence, not another
prompt or browser aggregation. Stable value nodes use shared ContextHelp without
native titles, row-wide help or dedicated cues. Its header's neutral
Earlier Sessions disclosure starts collapsed per new PiP document and survives publications.
It takes the last three of the shared eligible, oldest-to-newest `history_cards`, excludes
active/grace session IDs, and uses `session_summary.context`, never historical prompt Ctx.
Both keyed tables retain intrinsic heading/metric widths and horizontal panning.
Session totals/context retain their canonical source/cache states and display tokens;
there is no added acquisition, valuation, SSE or history scan. The session and subscription
regions use natural height without premature vertical caps; the document scrolls when needed;
primary Used bars stay thin and cyan until authoritative exhaustion. Estimated costs
have accessible provenance without a visible approximation glyph. Native close and
the filled Watch toggle own closing; the title still returns to the existing tab.
Intrinsic metric/header minima leave all spare width to Session; only titles ellipsize,
and narrow prompt regions scroll horizontally. Healthy/transient operational text is
omitted. Independent usable-observation clocks for prompts, Daily and each quota
produce one muted notice after ten minutes; definitive host/auth/identity failures
remain immediately actionable. Partial reads retain unmatched rows but accept valid
per-card corrections; observed empty publications still evict. Earlier exports canonical
`completed_at_ms` and local finished display tokens; the Windows Stockholm fallback
preserves repeated-hour fold/offset identity. No source, accounting or lifecycle owner moves.

The separate, non-navigating right header reuses `daily_usage.total`/`prompt_count`,
the full Watch display tokens and daily pricing/source state. Observation times and
retained/partial provenance are accessible, not prominent warning suffixes. Additive
`daily_usage.day_end_ms` uses configured timezone/DST so disconnected Mini clears the
previous day without calculating any usage. Loading is not zero. The left title alone returns
to Watch. Mini-only header alignment never changes full Watch tables. `OpeningMeasure`
loads the shipped styles inside an inert, invisible shadow layout, then renders current
presentation synchronously before the opening gesture calls native PiP. Natural layout
includes all accounts/statuses and a height-only two-running-row reserve. Fit width
comes from the maximum max-content header clone across both disclosure states and
real/reference `CCost Today 90 000 · 999 prompts` text, plus body padding, eight CSS
pixels of focus/rounding tolerance and an actual measured scrollbar gutter. The
Fit-only stable document gutter and equal-width marker prevent disclosure layout
shifts; no authentic totals/disclosure are mutated, table minima or fixed width used.
The conservative 16×48-DIP frame estimate separates the opener's side frame from its
outer/inner zoom estimate; height is measured at the resulting content width. Remember
mode retains its prior first-open size intention, not the minimal Fit width. PiP content
mounts after stylesheet load to prevent an unstyled scrollbar/wrapping feedback loop;
close/cancellation/style-failure races retain ownership checks. Actual native dimensions
and header fit are inspected after stylesheet load, never repaired
without a new gesture. Outer height is capped at min(1000, known screen available height).
Browser clamps remain authoritative and preserve document scrolling. No iframe/CSP
relaxation, acquisition, dependency, persisted geometry or polling owner is introduced.
Fit on open requests initial sizing on every opening, which can reset remembered position;
Standard position can reset remembered size. Only both Remember choices permit browser
cached bounds after the first opening within the same opener/host nonce. Preferences
never reposition an open PiP; reload/new openers start fresh.
`DisclosureSize` alone measures expansion and compact two-row targets within pointer or
native keyboard activation. Fit collapse shrinks to current content; remembered mode
restores achieved pre-expansion bounds unless manually resized. One native call preserves
current width where unclamped. Vertical-only `resizeBy` is preferred, with `resizeTo`
fallback; an observed one-DIP zoom-rounding bias is compensated on subsequent eligible
clicks, never by an extra/passive call. Native events/two-frame confirmation record achieved
bounds and cancel stale work. Missing activation/refusal/clamps retain disclosure/scroll.
No rendering/data event invokes native sizing. Full Watch's card/source presentation waits
30 continuous seconds before component/retry/refresh delay guidance, keeps retained prompt,
session, daily and account metric DOM quiet and exposes provenance in cost help.
Neither app startup without a frame nor independent history/accounts/daily loading
creates an elapsed-time global Watch warning. Only observed prompt membership on a
healthy running source/connection establishes “No running prompts”; partial, missing
and retained observations do not. Initial placeholders never claim observed empty/zero; unavailable/partial and host/auth guidance
remain explicit. Source states, timings and lifecycle are unchanged. Historical Windows150%
standard-frame measurements do not prove fresh physical Remember-last behavior;
the Mini journal records hidden API proof and the scoped physical-verification exception.

Full Watch's cost-cell boundary replaces I/E with the selected unit's zero only when
its formatted total displays zero (preserving `?`); raw values, unavailable totals,
positive-total component availability, CLI and Mini are unchanged. Focal row/title
ink shares confirmed `completed_successfully`, with errors/aborts taking precedence
and no success inferred from idleness. Historical titles stay neutral. Deterministic
cost/Live/summary tests and `integration/probe_watch_presentation.cjs` cover these
presentation rules without new acquisition, timers or lifecycle/grace changes.

`src/web/lifecycle.py` owns deliberate launcher restart, overlap coalescing, bounded readiness/stop and detached spawn. `src/web/instance_state.py` owns canonical checkout/user identity, transition and lifetime OS locks, private atomic records and bounded allowlisted lifecycle diagnostics. `src/web/process_identity.py` owns native birth/image proof and safe termination handles. `src/web/change_guard.py` owns the allowlisted five-second runtime metadata baseline and terminal source_changed state; it never reloads/restarts code.

`src/web/native_windows.py` owns same-process main-thread GUI integration and one asynchronous registered-browser handoff. `src/web/win32_tray.py` owns typed Win32 resources/message dispatch and Explorer taskbar recovery. It scopes PMv2 to the UI thread before creating any HWND/menu, restores on cleanup/failure, selects physical small-icon metrics and positions the hidden owner on the relevant icon/popup monitor. Process defaults and other threads are unchanged. `src/web/tray_icon.py` is the sole canonical CG pixel artwork; `development/tools/generate_web_icon.py` regenerates the tested multi-resolution ICO. HTTP exposes only two fixed favicon paths and limits image CSP to them. Native/browser checks and unverified physical acceptance: [branding findings](../../journal/web/branding.md).

Windows-only Copy is a third native event between Open/Exit, not an HTTP/browser
capability. `host.copy_browser_link` mints the same owner-side URL and revokes only
its own credential on copy failure. `security.BrowserSession` serializes up to 16
independent in-memory pending links, expiring each after 120 seconds, refusing
overflow instead of invalidating another link; redemption never rotates an active
session/CSRF. `win32_clipboard.py` owns typed movable-memory/Unicode transfer and
history/cloud exclusion formats. A separate coalesced worker bounds clipboard
contention retries to four 20ms waits, with result feedback on the native pump and
no credential-bearing logs. An explicit bootstrap hashchange in an already-loaded
page erases the fragment before using the existing exchange endpoint, then reloads
the clean Models URL; terminal authorization-error pages can accept pasted handoffs
without bypassing HTTP guards. No new process, dependency, macOS menu, route, acquisition
or trust boundary is added. Tests and explicit desktop limits:
[browser handoff evidence](../../journal/web/browser-links.md).

FR 000573 replaces the shared eight-hour deadline with per-browser stable bearer
records and seven days since a successful protected API reply. `http.reply` alone
records ordinary successful activity; validation, failures, assets and SSE do not.
`security.activity` coalesces each browser's cookie headers hourly; browser storage
is seven days plus one hour, while server authorization rejects at exactly seven
inactive days. The storage/equality exception is explicitly Decision Delegate-approved;
see [session findings](../../journal/web/browser-sessions.md). Session wall time includes
host sleep. Bootstrap remains monotonic/120-second/one-use; an existing valid
browser credential is reused on redemption, without rotating peers or instance CSRF.
SSE validates its opening bearer; an obsolete stream triggers current-cookie sync
and guarded replacement, not immediate terminal sign-out. Existing ten-second
Live sync renews cookies without new requests or acquisition. No layer, process,
port, dependency, source or accounting owner changes.

`src/web/windows_launch.py` and `src/web/windows_launch.ps1` own Beta-only Python/configuration/native preflight and sanitized failure feedback; stable terminal launchers do not import them. The Windows Beta batch waits synchronously for PowerShell's launch status; indeterminate activity spans bounded Python discovery and streamed startup stages until validated ready plus the OS browser-open result. The managed pythonw host remains detached/tray-owned, never console-owned; exit does not prove browser first paint. No compiler/cache/daemon is added. [Earlier hidden-delegation evidence](../governance/verification/windows-handoff.md) is historical, superseded by FR 000537.

`src/web/startup.py` owns fixed, flushed, elapsed-time launcher stage text shared by Windows/macOS. Lifecycle's optional progress sink reports arbitration/restart/host/browser boundaries without receiving secrets. PowerShell drains stages privately and prints one `Starting CostGuard web...` label, updating only a spinner cell at 120ms intervals through discovery and handoff. Progress panels are suppressed; redirected/noninteractive output stays plain. A finally block clears the cell before errors or exit. Browser startup is static branded HTML until authorization; initial report activity remains separate from HTTP/source/account readiness. No new supervisor, auth route, acquisition owner or dependency boundary is introduced.

`src/web/native_macos.py`, `macos_status.py` and `objc_bridge.py` own the experimental main-thread NSStatusItem, typed 64-bit callbacks/default-tracking pump, host-loss dismissal and asynchronous `/usr/bin/open`. `macos_launch.py` preflights in a bounded child; `macos_app.py` uses in-box osacompile for the optional fingerprinted/cache-verified Finder app. No new dependency/server owner. Native acceptance remains pending; exact limitations are in `docs/web-beta.md`.

## Public contract

`src/web/settings.py` is the sole write exception: `webSettings.theme` (`classic|web`),
`ccostDisplayUnit` (`credits|usd`), `miniWatchPlacement` (`remember-last|standard`),
`miniWatchSize` (`fit-on-open|remember-last`)
and `quotaDisplayMode` (`used|remaining`)
in this checkout's `config/user-config.jsonc`, each also accepting symbolic `default`.
Shipped defaults must be actual enum values. `config.validated_values`
shares startup validation, normalization and color resolution; neither merged
defaults nor CLI colors are serialized. Bounded JSONC token offsets preserve every
unrelated byte; duplicate keys and malformed/unsupported settings fail safely.
Owned/non-reparse paths, 1 MiB bounds, private same-directory temporaries, in-host
serialization and last-moment file identity/byte comparison precede atomic replace.
This is ordinary editor-conflict detection, not a hostile same-user race guarantee.

`GET /api/settings` and fixed `POST /api/settings/theme`, `/api/settings/ccost`,
`/api/settings/mini-placement`, `/api/settings/mini-size` and `/api/settings/quota-display` expose effective `webSettings`, symbolic/explicit
`webSettingsChoices`, current `webSettingsDefaults` and allowlisted error codes,
behind existing Host/Origin/session/CSRF/body/stopping guards. Early HTML selects
the effective theme before CSS paint. `assets/settings.js` owns the five native
dropdowns (Default first with a canonical-default-derived label) in the unframed
compact Settings grid. Feature-detected base-select/selectedcontent enhances native
options with a bounded adjacent description column; narrow/touch presentation
shows inline descriptions, while unsupported browsers keep native selects plus
a Choice help disclosure. Shared ContextHelp covers separate intrinsic labels and
current values; save locking dismisses their pending/open help. Native focus,
typeahead, preview/commit and cancellation are not reimplemented. Confirmed-only CSS/display-token switching, rollback and
keyboard focus recovery. `#/settings` reads on entry, never submits report jobs,
restarts the host or polls. Other tabs converge on their next read, not a broadcast.
Explicit nested theme, including inheriting `default`, overrides legacy user `webTheme`; normalization happens before
shipped nested defaults merge. Web CCost never follows CLI `ccostDisplayUnit` after
promotion. Only separately approved promotions get independent Web fields; other
settings remain shared. CLI/Watch settings and acquisition stay unchanged. Tests: `test_web_theme.py`,
`integration/web_theme.cjs`, `integration/web_views.cjs` and real hidden Chrome/Edge
`integration/probe_web_settings.cjs`; evidence/limits: [compact Settings](../governance/verification/web-settings-597.json),
[Web settings verification](../governance/verification/web-settings.md); historical
[theme verification](../governance/verification/web-theme.md).

`cost-guard-web.py --foreground` is explicit icon-free developer mode, independent of managed discovery and CLI. Only 127.0.0.1 with an assigned port is supported; exact Host/Origin and authenticated sensitive reads are mandatory. Standard-library only, no installation, updater, generic proxy/shell/filesystem routes or browser-side calculator. Accounts/source/analysis readiness remain independent of HTTP-shell readiness.

`windows/Beta/Cost-Guard-Web.cmd` and experimental `macos/Beta/Cost-Guard-Web.command` accept only approved adapters. Readiness requires a usable icon/event loop; GUI failure cannot advertise an unmanaged host. Native preflight precedes restart. Open uses the registered browser; Exit stops only its matching host. Detached handles/private cwd, no packages/downloaded compiler/service/autostart. macOS/Finder/Gatekeeper remains unverified; in-box osacompile is optional, never an SDK install. Mocks are not native proof.

Overlapping clicks coalesce; deliberate later launches restart. Private lifetime locks and nonce/PID/birth/image/port/build/schema/control records prevent duplicate or foreign ownership. Corrupt state is conflict; reused PIDs are never kill authority. Windows stale retirement (including inaccessible reused PIDs) requires the existing lifetime lock to be free under transition serialization, plus an unchanged full record. Every legacy schema-1 managed host already holds lifetime before publication through cleanup; an open Windows lock file cannot be replaced/deleted. No boot metadata, clock inference or schema extension is needed. Busy/unavailable/unsafe proof preserves state; no old control secret is sent on recovery. Lifetime releases for child admission, while transition stays held through readiness; the exclusive lifetime lock also prevents delayed children from creating a duplicate host. Non-Windows identity/termination policy is unchanged. Graceful stop allows ten seconds; forced stop requires a revalidated Windows handle/Linux pidfd (macOS refuses). Other checkouts, CLI, browser, unknown port occupants and OpenCode are never stopped.

Private /control/status, /control/stop and /control/open require a separate secret header, exact Host, empty body and no Origin/Cookie. No control secret reaches browser storage or normal logs. Open issues a fresh one-use fragment without invalidating same-instance browser sessions; old-instance cookies/control fail against replacements. Browser-open failure is distinct from server failure and retryable via native Open.

Twelve HTTP slots admit four streams; ordinary requests have five-second absolute deadlines. Healthy authenticated streams have no rotation timer; two-second writes, ten-second heartbeats, per-turn authorization and three-second native reconnect remain. HTTP health cannot mask an interrupted stream. Connected status is compact; actionable non-sticky notices retain expandable observation details. [FR 000532 evidence](../governance/verification/web-live-stability.md) records real-source soak and fault checks. Finite work: four outstanding jobs, one process, sixteen results, 8 MiB/result, 120 seconds per child. Only AI Stats resumes across finite children without a total logical deadline; bounded stalls/checkpoint faults/revision churn remain terminal. Detail admission: sixteen observed trees, thirty-two handles; abandoned handles expire after five minutes, never rows/history. Stop publishes terminal state and joins owned work; retained `/api/live` stays readable while stopping. DTOs retain decimal strings/null/provisional values, not raw errors. No same-user-malware boundary.

Guard membership/mtime_ns/size covers shipped Python/assets/Beta launchers/root entries/manifests, excluding development/docs/user config/cache/log/bytecode/environment. No links are followed; stat errors retry the original baseline. Proven change triggers terminal source_changed/shutdown without browser acknowledgement. Identical metadata can be missed; no atomic-update/file-lock guarantee. Changed code needs manual launch.

Wire/adapter/resource details: `docs/web-beta.md`. No new permanent gate.

v80.89 stabilization: `security.py` names cookies by canonical checkout (not port); opaque session/CSRF values remain instance-specific. `observations.py` owns bounded numeric API/source/lifecycle facts, persisted through InstanceStore's private atomic `diagnostics.json` at most every five seconds plus shutdown. `development/tools/diagnostic_web.py` reads this checkout's snapshot and allowlisted lifecycle codes without importing/starting Web or reading the control record; bad/missing/stale facts are not readiness proof. Shutdown retains diagnostic facts after instance removal. No account/cache schema or analysis boundary changes. Full parity/native/privacy inventory and explicit platform limits: [stabilization evidence](../governance/verification/web-beta-stabilization.md).

`development/tests/test_web_views.py` / `development/tests/integration/web_views.cjs` exercise served assets/facade: navigation, exact sorting, filters, tiers, independent accounts, deferred history, long lists and frozen/stale/empty/missing/hostile-text states. Node is optional VM tooling, not visual/assistive-technology proof.

The shared numeric display seam is `src/display.py` / `src/numbers.py` → terminal and `src/application/display.py` → immutable DTO `display` / `display_roles` → `render.js`. Raw exact values remain separate sort keys. Application never imports terminal presentation; formatting never acquires or values usage. `development/tests/test_web_display.py` and `development/tests/integration/web_display.cjs` pin CLI-derived goldens. The [per-view display baseline](../governance/verification/web-display-parity.md) distinguishes formatting coverage, browser-only interactions and page-specific remaining work; it is not visual acceptance.

FR 000528 adds sparse `display_units.credits/usd` tokens only where CCost text differs.
`render.js` owns weak DOM text bindings; file-backed Web Settings selects the unit before
report/Live startup and synchronizes visible and detached detail roots. Switching changes
text nodes, not tables, sort keys, report identities or acquisition. Session/Watch presenters
bind summaries, subtotals and context amounts too. Report projections retain structured
date-range and provider-only note costs rather than parsing formatted prose in JavaScript.
Reload/fresh tabs read the saved Web-only unit; CLI/native quotas/billing stay independent.
Architecture boundaries are unchanged; journal assessment: no-update. Evidence and explicit
browser/platform limits: [historical selector verification](../governance/verification/web-ccost-toggle.md)
and [current Settings verification](../governance/verification/web-settings.md).

FR 000537 unifies the former Overview and Models at `#/models`; `#/overview` and `#/models/all` replace legacy history entries, preserving bootstrap erasure and Models keyboard focus. Exactly Publisher/Model/Relative CCost/Release date fill main-content width with intrinsic subgrid tracks. All matching rows scroll with the document; narrow screens alone use horizontal overflow. Models has no account cards, search, pager, catalog links, native-rate column or superseded fading. The explicit price action/time, New Models and two accessible checkboxes precede the table; matching Price Promotion follows. FR 000598 replaces More information/cards with semantic header help. CCost selection belongs only to Settings. Accounts retains full shared acquisition/data. Other routes retain their controls and scroll contracts.

One opt-in `ModelCatalogProjection` freezes full catalog, selectable publisher/name membership, notices and candidate-local supersession from the same acquired sample, without new availability/history/account calls. Every filter combination uses the same full-catalog cheapest-positive base; CLI ranking/denominator remain unchanged. Defaults: all-priced off, latest-only on, exact Relative CCost descending. Candidate scope precedes conservative supersession and stable exact tier-vector sorting; missing ratios/dates stay last. Shift mouse/keyboard supports ordered multi-sort with primary-only aria-sort; ordinary click/touch replaces keys, with no persistent additive mode or extra sort control. Unknown prices remain rows; unverified fail-open and verified-empty remain distinct, never subscription entitlement proof. Prepared tokens align tiers without browser valuation.

`report-loading.js` retains bounded observed initial progress without an approximation glyph; `app.js` keeps heartbeat-stable frozen DOM. `test_web_models.py`, `test_web_overview.py`, `test_web_loading.py`, `integration/web_models.cjs` and `integration/web_views.cjs` cover filters, uncapped rows, exact tiers, warnings, route/focus and shared acquisition. `integration/serve_web_models.py` is a bounded loopback fixture for the integrated browser; hidden `integration/probe_report_loading.cjs` checks the four finite loaders. Historical [Overview](../governance/verification/web-minimal-overview.md) and [Models](../governance/verification/models-display-parity.md) results are not current UI acceptance; [current evidence](../../journal/web/report-loading.md) distinguishes actual checks from physical/native limits. No security/lifecycle/CLI valuation boundary changes.

## Allowed dependencies

Normal loading observations additionally allowlist a `stage`: sampling, availability,
comparison/catalog, quotas, account cache/load/analysis/projection, then application
packaging. They retain source-neutral phases/counts for CLI compatibility. Sampling
reports completed roots without inventing a denominator; counted cache/analysis/model
units report after completion. `jobs.ProgressRelay` bounds child publications to one
latest observation per 100ms plus final flush; host-assigned per-job sequences reject
stale polling/SSE labels. Each consuming stage owns its own estimated band, without
serializing the existing availability/account prefetch. Blocked source batches,
provider waits and projection calls without internal observations can pause honestly.
Only an applied usable result paints 100%; a usable partial result finishes the
attempt without claiming full coverage. Errors/lifecycle interruptions do not reach
100%, and frozen-navigation acquisition remains unchanged. Focused tests and headless real
Normal-workflow browser fixture: `integration/web_minimal_overview.py`.

The former Normal-only Accounts report is no longer a route consumer of `overviewAccounts`; report DTO/helper compatibility remains separately tested by `test_web_accounts.py`, `fixtures/account_views.py` and `integration/web_accounts.cjs`. Current shared live coverage is `integration/web_watch_summary.cjs`, `web_views.cjs`, hidden `probe_accounts_live.cjs` and read-only `probe_web_live.py --accounts --watch-cards`. [Current evidence](../../journal/web/accounts-live.md) supersedes historical [frozen Accounts parity](../governance/verification/accounts-display-parity.md). No acquisition, formula, source/privacy or application/presentation boundary changes.

FR 000542 replaces Web's retained-row table with `watch.js` keyed prompt cards;
`watch/cards.py` owns uncapped active membership, observed grace and top-five
actual-prompt history. `reports/watch_capture.py` preserves canonical row anchors/context
evidence while `cards.py` selects exactly one focal/latest actual prompt per card.
No dedicated complete-session totals phase/state is acquired. `watch/card_workers.py` admits four isolated services,
sources and caches, no queued futures or per-card detail leases. One session's
capture/analysis is shared across its concurrent cards. Revision refresh retains
visible history membership and coherent metrics until replacement; collapsed history
uses the same scheduling. Canonical prompt background fields feed activity DTOs.
Only active/top-five snapshots are retained; catalog revisions/generations reject
stale results. Source capture/analysis is necessary per session, not streaming.
Capture fairness uses successful admission order, not result time or a revision-reset
timestamp. Invalidated/delayed captures retain their turn; changing early session IDs
cannot repeatedly overtake a retained running card waiting to observe retirement.
The active/history rotation, four-worker bound and canonical lifecycle are unchanged.

`watch/web_coordinator.py` adapts the existing coordinator, leaving CLI hydration
and retention unchanged. It isolates account-history aggregation and Sessions
detail in separate single-worker lanes; native account acquisition retains its
existing scheduler. Live owns publication/lifecycle and the shared EMA, measured
from actual capture work, not just catalog admission. `application/live.py` calls
the optional detail adapter without importing Watch. `live_projection.py` exports
minimal detached card DTOs so 100 one-row cards fit the existing SSE bound.
`/api/status` exports the process-loaded `DISPLAY_VERSION`; the persistent header
uses it only after authorization, without a new poll or source-file reread.
Watch account DTOs carry each actual quota's associated period cost and canonical
pace from `QuotaPeriodProjection`, not label-based browser joins. Native monthly
history shares the existing single-worker account lane and revision reuse. The
subscription subgrid aligns title/Today/primary label/bar tracks; complete primary
reset/pace precedes any secondary-only divider. Title bands use theme tokens while
body values stay left aligned; Accounts now shares this exact subscription component.
`watch.js` shares ten columns across active/history cards: local HH:mm Started/Finished,
Duration, canonical #N Prompt, Model, Effort, CCost (I + E), Calls, Token Mix %, Ictx, Δ Ctx.
The number does not ellipsize; only the preview flexes. Intrinsic non-Prompt subgrid
tracks pan horizontally. All headers provide native top-layer explanations on
hover/focus/click, outside table clipping; time cells retain accessible full dates.
Running and Earlier sessions share individual rounded frames. History remains an
unframed/uncapped section with one expanded/nonempty-only section divider;
keyed disclosures retain focus/scroll. Running yellow,
activity gold/brown, red failures and context gold/orange have separate theme roles.
`render.js` scopes account-detail cleanup through its Watch-only flag; Accounts,
Models, settings, navigation and security are unchanged. User-visible scope and
failure semantics: `docs/web-beta.md`. Current evidence and explicit native/pixel
limits: [Watch cards](../../journal/web/watch-cards.md). The older
`probe_web_watch.py`/`web_watch_browser.js` table probe is historical, not current
acceptance; use approval-only `probe_watch_cards.cjs` and the integrated-browser
`serve_web_watch.py` fixture, plus read-only `probe_web_live.py --watch-cards --detail`.

Full Watch's retained View gives subscription tracks/cards a scoped CSS width of
floor(448 / (devicePixelRatio × visualViewport.scale)) pixels. DPR includes desktop
page zoom; only pinch adds the visual-viewport factor. Resolution media changes and
window/visual-viewport resize update the cap without replacing focused cards or
changing text size or acquisition. Accounts uses the same width owner; Mini is unchanged. Both grid/card selectors share
the cap, and narrow tracks shrink. Headless raster proof and the scoped unverified
native-desktop exception are in [physical-width findings](../../journal/web/watch-account-pixels.md).
Slim .83rem teal bars use 2px track/fill corners
in Chromium/WebKit and Gecko selectors. Canonical per-quota exhaustion alone colors that summary/fill red and
tints only its subscription header; stale/restriction warnings remain independent.
Application display prepares Watch-only reset tokens using shared `duration_text`
and canonical deadline/local-clock timestamps. Live's existing publication time
advances these tokens without provider polling or browser timers. The nested generic
reset token remains unchanged for CLI; Accounts and Mini's Next reset share Watch's tokens. Focused formatting,
DOM and rendered responsive evidence: [Watch polish](../../journal/web/watch-polish.md).
`live_projection.card` exports the canonical session continuation and entire root-tree
cost as `session_summary`, shared across concurrent/earlier cards, independently of row
Ictx. Unknown/compacted continuation never falls back to obsolete row tokens. Existing
`live_context` stays unchanged for Mini. `watch.js` owns one neutral Session Context / CCost
line with stable context/cost/warning spans. Canonical warning wording and display-cost
tokens lose only their outer display delimiters, joining once after both values; raw
multiplier presence selects the narrow emphasis role, never severity parsed from prose.
One retained SVG changes from amber triangle to red octagon/exclamation in place.
Only context and (for exceeded) relative multiplier inherit severity; labels, session
cost, threshold wording and alternate range remain neutral. Accessible severity names
do not repeat the adjacent explanation. In-place updates invalidate guidance even while
focus/selection protects surrounding rows. No thresholds, valuation, acquisition, cache,
Mini or lifecycle rules change. `fixtures/watch_context_browser.cjs` checks themes,
contrast, responsive wrapping and transitions using the actual shipped assets.

Watch capture already opts into canonical observed running metrics. Its minimal card
export now retains `token_mix_percent`; no client attribution, rounding or acquisition
is added. A Watch-only `MIX_FIELDS` coverage guard suppresses incomplete categories,
including completed/child usage, without changing CLI/Reports. Known values retain
the session report's rounding (not aggregate TokenMix's different rounding). Accepted
source corrections replace the mix; stale captures/SSE cannot roll it back. See
[prompt table evidence and scoped parity exception](../../journal/web/watch-prompt-tables.md).

HTTP/security/assets and lifecycle/process/state/guard depend on standard library and their Web owners. Jobs consume shared application/report contracts. Composition wires concrete source/config/cache/pricing/providers and the Watch acquisition driver; the separate host-startup owner alone may wake, never CLI dispatch. LiveRuntime consumes that supplied driver and exports immutable values; application/reports never import Web. CLI and Diagnostics do not import Web.

## Entrypoints

Runtime: `cost-guard-web.py`, `src/web/main.py`, `src/web/host.py`, `src/web/composition.py`, `src/web/http.py`, `src/web/assets/index.html`, `src/web/assets/app.js`, `src/web/assets/session.js`. Supporting lifecycle/security/process/asset owners are named above.

Native entries: `windows/Beta/Cost-Guard-Web.cmd`, `src/web/windows_launch.ps1`, `macos/Beta/Cost-Guard-Web.command`, `macos/Beta/launcher.applescript`. Generated applets stay outside Git, source/product/OS/architecture/Python-fingerprinted and hash-checked; failures preserve the command fallback.

## Tests

`development/tests/test_web_live.py` covers shared CLI/global projections, terminal transitions, partial pricing, midnight/DST, source recovery and hint resync, account-only publication, detached exports, replay/overflow/old instances, actual HTTP stream bounds/terminal delivery and stop beside a slow finite report. `development/tests/integration/web_live.cjs` exercises client ordering/offline/terminal/safe rendering in an optional Node VM, not a browser. Read-only `development/tests/integration/probe_web_live.py` observed V2, one owner/two streams, preserved run origin and joined shutdown on Windows/Python 3.14 on 2026-10-26. No inference, shared-service stop or native/visual/macOS acceptance is implied.

`development/tests/test_web_lifecycle.py` covers metadata changes/exclusions/faults, private state/locks/process identity, concurrent launches/restart, control/browser separation, main-thread/cleanup and force-stopped parent/blocked child. It uses an idle acquisition fixture, never live providers. `development/tests/test_runtime_errors.py` retains execution-root inventory. Windows process handles/locks are exercised; GUI assertions are not native tray/macOS proof.

`development/tests/test_web_runtime.py` / `development/tests/fixtures/web_reports.py` own wire/security/DTO/bounds/cancellation; `development/tests/test_application_reports.py` owns calculator parity. Read-only `development/tests/integration/probe_web_lifecycle.py` starts/stops only its own host. `development/tests/test_windows_web.py` covers adapter failure/readiness/Open/Exit, PowerShell discovery/arguments and private logs without UI. Approval-only `development/tests/integration/probe_windows_web.py` covers native menu/WM_COMMAND, browser failure, shutdown, transient consoles, overlap/restart, old-host preservation, source-change, independent Watch and spaces/Unicode ZIP launches. Windows 11/Python 3.14 observations date to 2026-10-26; physical mouse/visual/macOS acceptance remains untested. No inference or new gate.

`test_web_diagnostics.py` checks real two-checkout HTTP cookie-jar coexistence, bounded/allowlisted diagnostic export, missing/corrupt/oversize facts, write failure and retained shutdown evidence; replacement credential rejection is in `test_web_runtime.py`. `integration/probe_web_bounds.py` measures 5,000 synthetic replay publications/three simulated tabs and virtual authentication expiry, not physical suspend or hours-long soak. Native source-change probes must not overlap real-source probes of the same checkout.

`development/tests/test_macos_web.py` / `development/tests/test_macos_app.py` cover typed callbacks/faults, main-thread/tracking timers, preflight/readiness/cleanup, asynchronous actions and cache/quoting/rebuild failures without AppKit/UI. Approval-only `development/tests/integration/probe_macos_web.py` was not run here. Finder/Gatekeeper/clone/ZIP/executable-bit/no-Terminal/browser/tracking/source-change/orphan/CPU-architecture checks remain pending as documented in `docs/web-beta.md`.

`test_web_session_catalog.py` covers full-catalog six-key order, cold readiness/invalidation, persistent scalar reuse/corruption, archived membership, live versus frozen epochs, bounded/fair warming and blocked-index/detail isolation. `test_web_session_detail.py` / `integration/web_session.cjs` retain legacy first/middle/latest API coverage and add complete client history, revision-pinned rich chunks, whole-session totals, keyed selection and navigation/lease races. `integration/probe_web_sessions.cjs` uses a fresh hidden Chromium and actual HTTP/assets over synthetic 120-root/1,001-prompt evidence; `probe_web_live.py --sessions` separately observes the real V2 source. Historical --detail/--reports results remain API evidence, not current UI acceptance. Actual timings, cold coverage and physical/macOS/assistive limits: [Sessions findings](../../journal/web/sessions-live.md).

Remaining report presentation shares `display.history_tokens` for configured prompt clocks,
Next Ictx guidance and CLI historical mix category cells. `projection.token_mix` exports the
exact aggregate cost separately for sorting; JavaScript never totals displayed cells.
Session footer uses canonical block tokens and stable row IDs; internal pinned chunks
do not create a user-facing frozen mode. `test_web_remaining.py` /
`integration/web_remaining.cjs` compare shared session and historical Token Mix tokens
against CLI fixtures, including partial/unknown coverage. The older
[owner matrix](../governance/verification/remaining-web-parity.md) retains historical
Date UI evidence, not a current route inventory. `integration/probe_web_sessions.cjs`
also checks retired bookmarks, actual navigation, reload and browser Back/Forward.

Session detail now captures the visible document row immediately before DOM mutation,
preserving its pixel anchor without forcing follow-latest. There is no inner vertical
scroll owner. Frozen finite reports retain their actual DOM during host-health checks
unless report/search/view/output changes: health is not a new snapshot. Detail attach
is idempotent for its current parent, avoiding focus/scroll loss during health updates.
The older [table-scroll investigation](../governance/verification/web-table-scroll.md)
describes the superseded paged Sessions layout; its finite-report retention findings remain.

## Native launcher maintenance notes

Windows startup maps native access denied separately from unavailable identity and preserves allowlisted state/coordination/control/readiness causes through console, existing dialog and lifecycle log. Diagnostics exports the latest bounded lifecycle event independently of historical host snapshots. `stale_instance_recovered` is retirement evidence, not an active ownership conflict. Regression tests cover legacy recovery, busy/unavailable proof, overlapping replacement, concurrent record changes, native API error/handle mapping and privacy-safe feedback/export. Non-UI Windows observation and isolated fixture evidence: [stale recovery](../governance/verification/windows-stale-recovery.md). Journal assessment: no-update; protocol ownership remains here, with no new coordinator or layer boundary.

PowerShell 5.1: preserve `[array]$pythonArgs` (scalar `-3` splatting lost the command in a real probe). Use DirectoryInfo.SetAccessControl/private DACL, not Set-Acl requiring SeSecurityPrivilege. AST-extracted production functions/assignments test real py.exe handoff/private logs. Never elevate or change global policy. These owner facts replace a redundant journal log; historical evidence is unchanged.
