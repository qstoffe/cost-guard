# Cost Guard code map

Source revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Checked revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Last checked: 2026-11-07
Status: current

Scoped v80.200 update: canonical subagent prompt counts and shared subscription capacity/
responsive alignment; earlier dispatcher/evidence/partial-history and Sessions restoration
owners and tests. Baseline revisions above retain the other module checks.

Test Health 105 on `70462006910b0507c7f21412ef87330c3f675e2f` (2026-11-09):
Quick 52 unit groups; Full retains all 181. Ordinary CI uses Quick; manual Full
and platform-triggered native checks retain deeper coverage. Fixture ownership
and two sibling-test edges remain; runtime boundaries are unchanged.

Navigation, not another architecture authority: [OVERVIEW.md](../OVERVIEW.md) owns the source contracts; installed OpenCode Toolkit skills own the workflow. This map routes implementation and tests without importing the application or loading historical releases.

FR000633 navigation-only delta on `9b9fdf389d93d90a09bfa13e9b075b564d026961`,
checked 2026-11-08: AI Stats fun-first owners/tests below; no whole-map revalidation.

## Start here

FR000694: `domain/effort.py` owns independent tooltip evidence;
`sources/opencode_v2_effort.py` / the shared Desktop catalog own bounded current
options, and `analysis/effort_defaults.py` owns exact reviewed vendor fallback.
`application/effort_help.py` separates ordinary versus dedicated Effort-value copy.
Prompt parts, matched runs and sampled Stats carry evidence without changing
accounting/group identity. Coverage: `test_default_effort_help.py`, existing
effort/cost/alias/cache groups, `probe_web_help.cjs --effort-defaults` and read-only
`probe_effort_live.py`. [Evidence and limits](../../journal/default-effort-help.md).

FR000688: `sources/opencode_v2_background.py` owns exact native-job registry recovery;
`watch/invocation.py` owns bounded multi-job identity, canonical-first mismatch
handling and the common privacy filter. `cards.py`/`live_projection.py` retain live
verification gates; `watch.js` reconciles affected job entries only. Coverage:
invocation/card/Live/V1 parity tests, Watch VM and hidden `probe_watch_invocation.cjs`
plus authenticated `probe_web_help.cjs ... --watch-shells` / `probe_watch_jobs.cjs`.
[Source evidence and acceptance clarification](../../journal/web/watch-invocation.md#multi-job-command-recovery--fr-000688).

FR000686: `domain/progress.py::DetailProgress` owns the explicit source milestone
budget; `watch/detail_capture.py::WorkMeter` transports it separately from scalar
liveness work, qualified by `application/session_detail.py` attempt identity.
`reports/session_history.py` owns phase entry/known publication rows; V2 snapshot
hydration owns measured discovered-tree units. `assets/session.js` consumes source
percent and remaps pinned transfer to 70–95%, completing only after applied DOM.
Coverage: detail liveness/status, `web_session.cjs`, first-load/layout/native-zoom
and liveness browser probes; [evidence](../../journal/web/session-loading.md#source-driven-whole-operation-progress-fr000686).

FR000689: `assets/ai-stats.js` owns the permanent Loading-only card invariant;
`app.js` owns separate cold-error feedback and attempt-qualified application.
`stats_jobs.py` and `dispatch.py` distinguish unready exhaustion from success,
retain busy-checkpoint scans and regenerate old projection policies. Coverage:
Stats resume/dispatch tests, loading/lifetime VM, rendered Stats matrix and real
read-only installation probe. [Current evidence and limits](../../journal/web/ai-stats.md#loading-only-and-supervised-recovery--fr000689).

FR000687 scoped P2: `application/model_help.py` owns recorded-selector copy;
prompt parts, scalar Sessions and compact matched runs retain raw identities separately
from effective prices. `test_recorded_model_help.py`, existing alias/cache/cost tests,
`replay_owned_models.py` and `probe_web_help.cjs --raw-models` cover provenance.
[Delivery limits](../../journal/recorded-model-help.md) exclude historical repair and full-catalog proof.

FR000685: `analysis/ai_stats_responses.py` owns bounded deterministic response sampling
and weighted per-model TPS; `reports/ai_stats_responses.py` extracts already-acquired
request-level intervals. `ai_stats_evidence.py` owns revision/time-valid summaries;
application/JS own prepared medal rows, never browser math. The permanent
[best-effort / never Unavailable contract](reports.md#ai-stats--best-effort--never-unavailable)
applies to every Stats card. Coverage: token/Stats/recovery/resume tests, canonical
podium/states/loading browser probes and read-only cold/warm installation probe.
[Current evidence](../../journal/web/ai-stats.md#sampled-response-podium--fr000685).

FR000683: `assets/help.js::watchHover` owns the open-only 1000ms exact-target check
and thirty-second trusted-pointer idle lease, shared by Full Watch and Mini PiP.
Opening tickets and owner/lifetime cleanup stay in the same controller. Coverage:
`integration/web_help.cjs` virtual hover/clock and `probe_web_help.cjs --hover-watchdog`
with `probe_help_watchdog.cjs` deliberately suppressing native exits in actual PiP.
[Tradeoff and verification](../../journal/web/contextual-help.md#fr-000683-bounded-hover-watchdog-2026-11-12).

FR000682: `analysis/ai_stats.py::_token_metrics` derives observed integer traffic,
sharing `ai_stats_rates.py` denominators without cost/time fillers. Application Stats
prepares exact-total help and unit-independent rates. `assets/ai-stats.js` owns twelve
stable shells and authoritative scope-ready retention (`fun-2-tokens`); compact
usage stays reusable, coverage v3 rejects undated-request exclusion proofs. Coverage: Stats/token/rates/resume tests,
`probe_ai_stats_loading.cjs`, production slices/two-tab/browser probes and read-only
`probe_ai_stats.py`; [current evidence and TPS exclusion](../../journal/web/ai-stats.md#observed-token-traffic-and-ready-card-shells--fr000682).

FR000681: `src/python_discovery.ps1` / `.sh` own bounded pre-Python installed-runtime
resolution shared by each OS's Web, Legacy and Diagnostics launchers. Fixed Web
failure reasons live in `web/launch_messages.json`, rendered by Python and the
Windows status boundary. Finder apps re-enter the `.command` resolver; private
cache fingerprints/inventory and existing lifecycle/security owners are retained.
Coverage: Windows launcher/activity, macOS Web/app and launcher-feedback tests;
[policy, reproduction and proof limits](../../journal/python-discovery.md).

FR000679: `assets/sessions.js::update` completes lease recovery silently and retires
incompatible protected rows before publishing a replacement page. Existing catalog,
index, sorting, source and cache owners are unchanged. Coverage: `web_session.cjs`,
`probe_web_help.cjs --sessions-quiet-refresh`, navigation/live Sessions probes and
`probe_web_sessions.cjs --catalog-real-recovery` through `sessions_source_browser.cjs`.
[Reproduction and limits](../../journal/web/sessions-expiry.md).

FR000677: `application/quota_ccost.py` accepts qualified priced same-window subtotals
for provisional Capacity/30-day estimates and prepares fact-specific unknown help.
`render.js::quotaCapacityHelp` preserves those server reasons on shared cards. History,
attribution, scope joins and native accounting retain their owners. Coverage: quota-CCost,
account-period and pace tests, `fixtures/account_capacity.cjs`, hidden
`probe_accounts_live.cjs ... --secondary-capacity` and `probe_web_live.py --accounts --quota-capacity`.
[Causes and evidence](../../journal/web/secondary-capacity.md).

FR000678: `reports/token_mix_cache.py` emits the same identity semantics its
decoder admits; `application/service.py` types cache failures, `history_work.py`
distinguishes checkpoint contention, and `web/dispatch.py` owns recovery/backoff.
`ai_stats.py` types fresh catalog turnover as revision churn. `assets/app.js` /
`ai-stats.js` retain valid period results, preserve lookup deadlines through Live
health events and remove manual historical Retry/false zero fallback. Coverage: alias-cache, dispatch, Stats resume,
loading/lifetime tests, Token Mix/Stats browser probes and opt-in
`probe_ai_stats.cjs ... --live-history` through `serve_historical_reports.py`.
[Reproduction and limits](../../journal/web/historical-recovery.md).

FR000675: `render.js::accountHeading` adds one decorative SVG within the existing
trusted link; `account-cards.js` retains that heading through track redraws and retains
only native slots (not daily accounting) when quotas fail. No acquisition or pricing
boundary changes. Coverage: `fixtures/account_links.cjs`, `account_today.cjs`,
`test_ccost_midnight.py`, hidden `probe_account_links.cjs` and `probe_account_today.cjs`
through the Accounts driver; read-only `probe_web_live.py --accounts --daily`.
[Causes and limits](../../journal/web/account-today.md).

FR000673: exact Claude Agent catalog identity lives in `domain/model_identity.py`
and `sources/opencode_v2_model_identity.py`; `pricing/identities.py` owns scoped
derived-cache semantics. Reference account compatibility lives in
`analysis/period_ccost.py`, combined by `reports/accounts.py` for all shared views.
Coverage: alias identity/cache and account-period tests, `fixtures/claude_account.py`,
`probe_accounts_live.cjs --claude-agent` and `probe_web_sessions.cjs --detail-first-load`.
The latter measures existing FR000674 runtime behavior, not another acquisition
owner. [Independent causes and excluded live proof](../../journal/claude-agent-ccost.md).

FR000674: `application/session_detail.py` owns fair attempt budgets, safe Retry and
typed detached acquisition state; `watch/detail_capture.py` owns one supervised
capture child and bounded private file IPC. `web/detail_worker.py` composes that
child without reversing Watch→Web dependencies. Domain work checkpoints observe
source normalization/analysis/projection, never timer-generated progress. Coverage:
`test_session_detail_liveness.py`, detail/Live regressions and authenticated
`probe_web_sessions.cjs --detail-liveness`; [causality and limits](../../journal/web/session-loading.md#finite-source-acquisition-fr000674).

FR000672: `mini.js::activityLabel` formats the selected absolute start/finish using
the prepared local date and configured-zone `ReportView.timestamp` current day.
The existing Controller render clock owns age transitions; selection, source access,
help and native sizing retain their owners. Coverage: `fixtures/mini_activity.cjs`
through the Mini Controller VM, plus `probe_mini_activity.cjs` via the real PiP driver.

FR000671: `assets/mini.js::View.sessionRow` / `drawSessions` render the decorative
running Activity triangle from canonical prompt flags; `mini.css` keeps it compact
inside the existing metric width. Selection, lifecycle, time help and native sizing
owners are unchanged. Coverage: Mini session/Controller VM fixtures and the existing
PiP theme/lifecycle/Activity probes. [Evidence](../../journal/web/mini-watch.md#running-activity-indicator-fr000671).

FR000670: `application/live.py::_publish_frame`, `assets/live.js`, `app.js`,
`index.html` and `app.css` own the source-qualified global notice, not selection.
`test_v1_web_watch.py` / `fixtures/v1_watch.py` compare actual SQLite through separate
CLI and Web owners; `serve_v1_watch.py` / `probe_v1_watch.cjs` exercise genuine host/
HTTP/SSE/Full/Mini and synthetic failure/reconnect/layout states.
[Source matrix and investigation limits](../../journal/web/v1-compatibility.md).

FR000669: `sessions.js` composes stable task/count/work slots around the unchanged
shared loader. `session_summary.py` reports actual bounded cache/read/projection
boundaries through `session_catalog.py`, without source-content export or another
lane. Coverage: extended catalog/VM/navigation fixtures and opt-in read-only
`probe_web_sessions.cjs ... --catalog-real-churn`; ordinary synthetic navigation uses
`--catalog-navigation-only`. [Cause and limits](../../journal/web/sessions-navigation.md#three-tier-progress-and-apparent-rollback-fr000669).

FR000668: `assets/app.js::focusReport`, `app.css` and the named `index.html` main
target separate automatic Models focus from intentional keyboard transfers. Existing
route top/scroll and centered loader lifetimes are unchanged. Coverage: loading VM,
`probe_models_startup.cjs` / `probe_models_focus.cjs`, Models-only report-loading,
pricing/layout and hosted `ci_browser_web.py` focus assertions.
[Diagnosis and verification limits](../../journal/web/models-focus.md).

FR000667: `reports/session_summary.py::context_fields` prepares root-scoped CTX
using canonical `analysis/context.py::session_watch_context`; scalar algorithm 3
qualifies source/revision/epoch facts. `application/session_catalog.py` extends its
existing global index/comparator; `sessions.js`/`app.css` render seven intrinsic
columns and shared help without a new acquisition owner. Coverage: catalog tests,
Sessions VM/navigation/live/detail browser fixtures and read-only V2 Sessions probe.
[Evidence and limits](../../journal/web/sessions-context.md).

FR000690: `analysis/session_context.py` resolves source-qualified session-last-good
observations; `reports/watch_context.py`, `watch/cards.py` and `session_summary.py`
own pending retention/shared catalog projection. Mini's observation cache is not
prompt/DOM/history-scope keyed. Full Watch consumes the same continuation contract.
Coverage: `test_session_context_continuity.py`, Mini/footer/catalog tests,
`fixtures/mini_context.py` / `.cjs` and real headless `probe_mini_fit.cjs ... context-only`.
No context arithmetic/acquisition change. [Evidence](../../journal/web/mini-watch.md#persistent-session-ctx-fr000690).

FR000665: `mini.js` keeps Total noninteractive, reuses the existing server-prepared
`account_ccost` subtotal token after its no-priced-work guard, and shortens Session
help without changing CCost help or canonical costs. Coverage: `test_mini_watch.py`,
`fixtures/mini_sessions.cjs`, `mini_help.cjs`, `probe_mini_help.cjs`,
`probe_mini_duration.cjs` and `probe_mini_width.cjs` through the real PiP fit probe.
[Evidence and limits](../../journal/web/mini-watch.md#quiet-total-and-direct-session-help-fr000665).

FR000663: `application/quota_ccost.py` prepares distinct raw period/30-day Capacity
help from accepted Decimal inputs; `quota_estimates.py` owns the inclusive 5%
estimate-only tolerance and USD precision caveat. `render.js` separates native
usage help from Capacity help; shared `account-cards.js` retains intrinsic targets.
Coverage: quota-estimate/CCost/pace tests, `fixtures/account_capacity.cjs`, shared
Watch DOM, `probe_quota_estimates.cjs` and `probe_subscription_capacity.cjs` through
the Accounts driver. No acquisition, accounting or layer-boundary change.

FR000661: `application/display.py` exports the existing source-backed
`monthly_applicable` presentation fact without changing Decimal calculations.
`account-cards.js` retains unknown Capacity rows and stable bound tracks; `app.css`
shares subgrid slots for every quota ordinal through presentation-only wrappers.
Coverage: `fixtures/account_capacity.cjs`, existing daily/quota tests,
`probe_subscription_capacity.cjs` and `probe_quota_display.cjs` through the full
Accounts driver. Mini and legacy report formatting are unchanged.
[Layout evidence](../../journal/web/quota-layout.md).

FR000660: `mini.css` leaves `.mini-prompts` at automatic scrollbar-gutter sizing;
real overflow and the measured JavaScript opening/Fit helpers are unchanged.
`probe_mini_gutter.cjs` runs through `probe_mini_fit.cjs` for paired original/fixed
Classic/Web light/dark geometry, 0–10-row transitions and classic/overlay scrollbars.

FR000659: `render.js::modelHeading` shares the two Models heading/source structures;
`app.css` supplies shared semantic table shells/cells, responsive toolbars and the
compact one-column effort picker. `benchmark.js` orders source options without
changing keys or filter math. Coverage: existing Models/overview/views tests,
`probe_models_parity.cjs` through authenticated `probe_models_refresh.cjs`, frozen
Models browser layouts and real `probe_web_live.py --models --benchmark`.
No backend or architecture-boundary change. [Evidence](../../journal/web/models-parity.md).

FR000658: Comparisons pin qualification/stages remain in `reports/matched_inputs.py`;
`application/service.py` marks rejected pinned requests terminal. Browser retry/rebase
and new-route Models top policy are in `assets/app.js`; page-only recovery budgets in
`report-loading.js`; shared pager rules in `app.css`, `comparisons.js`, `sessions.js`;
benchmark initial key in `benchmark.js`. Coverage: matched-inputs/dispatch/loading/
views/Models/Session tests, `web_report_lifetime.cjs`, hosted `ci_browser_web.py` and
`ci_paging_navigation.py` using `serve_comparisons_paging.py`; read-only real
`probe_comparisons.py --paging`. [Evidence](../../journal/web/paging-navigation.md).

FR000657: Web-only `render.js::timestamp` owns explicit-zone browser instants;
`settings.py` exports the configured timezone and application display prepares numeric
`web_reset` alongside unchanged CLI reset tokens. `token-mix.js` quiets only its own
display values and retains partial-pricing/telemetry title help. Models' final
More Coding Benchmarks link is static. Coverage: Web display/remaining/models/theme/
loading/session tests; `probe_token_mix_help.cjs`, Mini Activity locale/DST probes
and Models browser layout. [Evidence](../../journal/web/presentation-dates.md).

FR000653: `analysis/context.py` owns guarded prompt-local input/next fallback and
running invalidation; `reports/prompts.py` retains richer adjacent baselines.
`live_projection.py` exports the short canonical context detail; `mini.js` separates
Next/Δ/guidance paragraphs without changing scope or columns. Source-shaped fixtures:
`fixtures/context_deltas.py`, context-history/comparison/move/V1/V2/Mini tests;
`probe_mini_help.cjs` through the real PiP fit probe checks source→SSE→Full/Mini.
`probe_web_live.py --context-deltas --detail` checks real export/formatting, not the
owner's private incident or an independent reconstruction of every baseline.

FR000652/FR000656: `src/benchmarks.py` validates fixed public Harbor Terminal-Bench 4.0
aggregates; `cache/benchmark.py` owns its separate versioned last-good file.
`web/benchmark.py` reuses an independent `ReportJobs` instance under the existing
host tick/close owner, without source/price-job dependency. `application/benchmark.py`
prepares raw Decimal keys, per-attempt values, exact unique catalog eligibility and
reference-release-only New. `web/assets/benchmark.js` owns the retained five-column
table, independent Copilot/effort filters and value help. The existing lane also
coalesces authenticated forced manual refresh, retaining the 24-hour automatic path.
`reports/model_comparison.py` freezes exact labeled native USD tier help;
`service.py` exports the actual comparison shares/count, `application/display.py`
balances their help percentages without changing ratio math or broader Token Mix.
Coverage: `test_web_benchmark.py`, existing Models/tiers/price-refresh/overview tests,
`web_models.cjs`, hidden Chrome/Edge Models and toolbar/help probes, and read-only
`probe_web_live.py --benchmark --benchmark-cold`, `probe_models_values.cjs` through
the authenticated refresh probe. [Original](../../journal/web/models-benchmark.md)
and [FR000656 evidence](../../journal/web/models-controls.md).

FR000650: `cost-guard.py` / `src/product_entry.py` route default desktop intent to
existing managed Web; `cost-guard-cli.py` preserves independent report/Watch.
Public Web launchers are `windows/Cost-Guard-Web.cmd` / `macos/Cost-Guard-Web.command`;
CLI pairs live under each platform's `Legacy/`. `macos/launcher.applescript` feeds
the owned `Cost Guard.app` cache/version metadata. SourceGuard covers actual trees.
Coverage: foundation, launcher, native Web/app and rendered CI tests; actual native
and unavailable physical acceptance are separated in the promotion journal.

FR000648: `watch/invocation.py` owns bounded scalar eligibility and native shell/bash
timeout presentation; `invocation_redaction.py` owns literal credential value spans
and ambiguous-syntax withholding. `watch.js` keeps stable native disclosures with
command-first text and no safe-input warning. Coverage: `test_watch_invocation.py`,
`test_watch_cards.py`, `test_web_live.py`, `probe_watch_invocation.cjs`; the real Live
probe compares already-acquired native commands in memory and exports counts only.

FR000644/FR000655: `analysis/ai_stats_rates.py` owns nominal configured-local date/workday
normalization and raw active-hour intensity over existing period totals/durations.
`ai_stats.py` retains the original active-hour value; reports thread the configured
calendar; projection keeps raw compatibility shifts while application prepares three
per-hour values and compact formula help. The retained first Web card alone gets
Calendar/Workday/Active AI average rows. Coverage: `test_ai_stats_rates.py`, existing
Stats/recovery tests, `probe_ai_stats.cjs`, layout/state probes and real read-only
`probe_ai_stats.py`. No new history acquisition or valuation boundary.

FR000643: `mini.js::View.drawSessions` gates terminal foreground on the existing
historical category, matching Full Watch without a second grace clock. Coverage:
`mini_sessions.cjs`, `mini_watch.cjs`, synthetic `fixtures/mini_lifecycle.py` and
`probe_mini_theme.cjs` through `probe_mini_fit.cjs` / `probe_mini_watch.cjs`.
See [foreground evidence](../../journal/web/mini-watch.md#historical-foreground-correction-fr000643).

FR000642: `mini.js::sessions` selects one canonical session representative and
chronological five-slot finished fillers without changing Full Watch or the verified
server history population. `boundTable` measures a five-row internal viewport;
`tableWidth` / `OpeningMeasure` measure table/header opening needs; `FitSize` owns only
explicit height requests. `app.js` leases history automatically below five active
sessions; `display.py` prepares start-offset help. Tests: `mini_sessions.cjs`,
`mini_opening.cjs`, `mini_fit.cjs`, `mini_watch.cjs`, `test_mini_watch.py`,
`test_watch_cards.py`, `test_web_display.py`; current headless `probe_mini_fit.cjs`
(width/activity/AX) and `probe_mini_watch.cjs --history-demand-only` (authenticated
leases). Obsolete two-table/disclosure probe branches are retired, not acceptance
for current Mini. [Current evidence](../../journal/web/mini-watch.md).

FR000641: `application/quota_estimates.py` owns pure Decimal estimate-only display
rounding/help. `quota_ccost.py` retains raw `ccost_reference` and pace provenance;
`display.py` prepares both units. Shared cards, legacy Accounts and Mini consume those
tokens without browser arithmetic. Coverage: `test_web_quota_estimates.py`, existing
quota/pace tests, both Watch/Mini VM suites and `probe_quota_estimates.cjs` through
`probe_quota_display.cjs`. [Decision/evidence](../../journal/web/quota-estimates.md).

FR000651: `sources/opencode_v2_model_identity.py` observes read-only location-scoped
provider/model catalogs and materializes Desktop-parity estimates separately from
the recorded alias in `domain/model_identity.py`. `analysis/model_identity.py`
owns compact codecs/admission; each derived-cache owner validates only relevant
dependencies, including negative mappings, without changing native history brackets
or global pricing signatures. Existing alias/cache/browser tests include turnover,
exact location/provider matching, preserved clone identity and process restarts.

FR000629: `pricing/identities.py` and `catalog.py` share conservative alias labels
and valuation gates. `analysis/cache.py`, `session_cost.py`, `reports/session_summary.py`,
`token_mix_cache.py` and `matched_runs.py` repair affected historical projections lazily;
`application/comparisons.py` retains raw identity separately from `model_label`.
`test_claude_alias_identity.py`, `test_claude_alias_cache.py` and
`fixtures/claude_alias.py` cover current V2 shape, pinned rates, cross-projection
repair, unaffected hits and real subprocess restarts. [Evidence](../../journal/claude-alias-identity.md).

FR000636: `render.js::accountHeading` owns the reviewed static provider destinations
and bound external heading links for shared `account-cards.js` and legacy
cards. `fixtures/account_links.cjs` (via `web_watch_summary.cjs`) covers every supported
ID, API/subscription distinctions, hostile labels/IDs and stable refresh/redraws;
`probe_account_links.cjs` runs through the shipped Accounts/Watch browser probe.
No projection, acquisition, authentication or accounting boundary changes.

FR000637's explicit ↕ Fit action survives FR000642 in `FitSize`; its obsolete
disclosure/delta tests are replaced by the unified viewport probes above. No acquisition
boundary changes; earlier [Fit evidence](../../journal/web/mini-fit-height.md) is historical.

FR000638: Web-only reference-CCost remaining pace is owned by
`application/quota_ccost.py`, `display.py`, identity-bound `projection.py` /
`watch_accounts.py`, `account-cards.js` and legacy `render.js`. Focused coverage:
`test_web_quota_pace.py`, `test_quota_period_lifecycle.py`, Accounts/quota VM tests
and `probe_quota_pace.cjs` through `probe_accounts_live.cjs`. Native/CLI pace is unchanged.

FR000640: that same `quota_ccost.py` owner converts coherent verified finite native
allowances into matching reference Used/Remaining/Capacity; percentage-only ratio
estimates and independent observed costs remain separate. `test_web_quota_ccost.py`,
`test_web_watch_quota.py`, `test_web_quota_pace.py` and `probe_quota_display.cjs` cover
the shared Accounts/Watch/open-Mini tokens and independent native mappings.
`probe_web_live.py --accounts` adds a count-only real native-fact oracle.
[Evidence and limitations](../../journal/web/quota-reference-amounts.md).

FR000635 scoped navigation: `mini.js`/`mini.css` retain the grouped measured header
(disclosure removed by FR000642); `settings.js`/`app.css` own native sibling help panes and
wheel delegation. `fixtures/settings_wheel.cjs` covers units/guards/preview;
`integration/probe_settings_wheel.cjs` covers trusted native wheel/scrollbar input;
Current Mini probes above replace the old pressed/disclosure matrix. Settings tests
remain independent. [Historical evidence and exceptions](../../journal/web/header-picker.md).

1. Use the installed OpenCode Toolkit `/repo-backlog` command and currently loaded skills for development workflow; the current filesystem, including unrelated uncommitted work, remains authoritative.
2. Find the responsibility below, read its boundary types and focused tests, then the affected implementation. Do not put integration details into analysis or presentation.
3. The runner exposes focused patterns/profiles and Quick/Full suites. Installed Toolkit determines which verification is applicable; remote publication and UI retain independent authorization.

Regenerate a whole-tree static inventory from the repository root:

```text
python development/tools/code_inventory.py
python development/tools/code_inventory.py --json
```

The inventory scans only Python under `src/`, `development/tools/`, `development/tests/` and `development/tests/fixtures/`. It lists module purposes, sizes, longest functions, local imports, layer edges and test coupling. It never imports analyzed code, accesses credentials/runtime history, performs network requests or creates output files. JSON contains the complete per-module map. Lazy/type-only imports are included: these are navigation paths, **not measured test coverage or proof of runtime cycles**.

## Ownership and test routes

All paths in this table are relative to the repository root. Test names live under `development/tests/`; use `--pattern <name>` with the bounded runner.

| Change area | Read/edit first | Focused tests |
| --- | --- | --- |
| Host-owned Web dispatcher / shared compact evidence / warm Sessions restoration | `src/web/dispatch.py`, `dispatch_http.py`, `dispatch_dependencies.py`, `report_control.py`, `history_jobs.py`, `jobs.py`, `assets/data-demand.js`; `src/reports/shared_evidence.py`, `history_work.py`, `history_snapshots.py`; [boundaries](data-dispatch.md) | `test_web_dispatch.py`, `test_web_runtime.py` (`JobBoundaryTests`: publish-before-exit retirement, resident bound, escalation), `test_historical_reports.py`, `test_web_live.py`, `test_web_session_catalog.py`, `test_web_session_detail.py`, `test_web_views.py`; hidden `integration/probe_data_dispatch.cjs`, gated first-Live `probe_models_startup.cjs` / `serve_models_startup.py`, read-only `probe_data_dispatch.py`, synthetic `benchmark_data_dispatch.py`; [measurements/limits](../../journal/web/data-dispatch.md) |
| Entry/CLI/config/version | `cost-guard.py`, `src/product_entry.py`, `cost-guard-cli.py`, `src/bootstrap.py`, `src/cli.py`, `src/config.py`, `src/version.py` | `test_foundation_quick.py`, `test_config.py`, `test_step7_reports_cli.py`, `test_zero_data_robustness.py` |
| Canonical values/account identity/CCost | `src/domain/models.py`, `accounts.py`, `ccost.py`, `capabilities.py` | `test_domain.py`, `test_accounts_ccost.py`, `test_ccost_migration.py` |
| Catalog ancestry and whole-tree metadata activity | `src/domain/session_tree.py`; call sites in `src/reports/service.py`, `src/watch/observers.py`, `coordinator.py` | `test_session_tree.py`, `test_compact_reports.py`, `test_watch_grouping.py` |
| V1 SQLite acquisition/change gates | `src/sources/opencode_v1.py`, `opencode_v1_revision.py`, `opencode_v1_catalog.py` (row activity and separate liveness) | `test_opencode_v1.py`, `test_source_history_loading.py`, `test_source_selection.py`, `test_step9_parity_performance.py` (Full) |
| V2 discovery/HTTP/hydration and active-history evidence | `src/sources/discovery.py`, `errors.py`, `read_recovery.py`, `opencode_v2_transport.py`, `opencode_v2_wire.py`, `opencode_v2.py`; `opencode_v2_catalog.py`/`opencode_v2_snapshot.py` own shared indexes/consistency batches | `test_opencode_v2.py`, `test_source_history_loading.py`, `test_source_selection.py`, `test_connectivity_reliability.py`, `test_watch_startup_recovery.py`, `test_watch_source_recovery.py` |
| V2 wire shapes vs canonical normalization | `src/sources/opencode_v2_wire.py` translates current/legacy wire shapes; `opencode_v2_normalization.py` maps bundles/parts/requests and tool-continuation records | `test_v2_normalization.py`, `test_v2_tool_continuations.py`, `test_effort_presentation.py`, `test_v2_synthetic_attribution.py` |
| Native termination/stop causes/background/move evidence | `src/sources/opencode_v2_events.py`, `opencode_v2_background.py`, `opencode_errors.py`, `opencode_v2_wire.py`, `opencode_v2_interruptions.py`; `src/analysis/prompt_index.py` scopes pre-response ends | `test_opencode_terminal.py`, `test_pre_response_terminal.py`, `test_opencode_aborts.py`, `test_watch_stop_reasons.py`, `test_live_stop_reasons.py`, `test_session_move.py`, `test_watch_lifecycle.py`; `integration/export_pre_response_watch.py` + `probe_pre_response_watch.cjs` check actual headless DOM/SSE/reload/reconnect |
| Request attribution, child work, billing and valuation | `src/analysis/causal.py`, shared task/subagent windows in `child_links.py`, `billing.py`, `valuation.py`, `core.py`, `compaction.py`; Watch reuses the windows | `test_analysis_core.py`, `test_child_links.py`, `test_subagent_attribution.py`, `test_v2_synthetic_attribution.py`, `test_accounts_ccost.py`, `test_ccost_migration.py` |
| Reason-specific unavailable reference CCost | `src/domain/reference_cost.py`, `src/pricing/reference_diagnostics.py`, `catalog.py`; `src/analysis/valuation.py`, `session_cost.py`; `src/application/reference_cost.py`, `display.py`; shared Web value targets | `test_ccost_unavailable.py`, `test_web_price_refresh.py`, `fixtures/ccost_unavailable.py`; hidden `probe_web_help.cjs --ccost-unavailable` / `probe_ccost_unavailable.cjs`; [classification/evidence](../../journal/web/ccost-unavailable.md). Diagnostic signature is separate from rate semantics; no hover acquisition or persisted request ledger. |
| Canonical request category costs / distinct child prompts / role-model-effort-tier tooltip groups and linked-model evidence | `src/analysis/prompt_index.py`, `causal.py`, `models.py`, `cache.py`; `src/reports/prompt_costs.py`, `prompt_rows.py`; bounded `src/application/prompt_costs.py`, `display.py`, `live_projection.py` | `test_prompt_cost_detail.py`, `integration/probe_help_values.cjs`, `probe_cost_groups.cjs`; no browser pricing, hover acquisition or CLI total changes |
| Historical execution timing and overlap-safe report/list totals | `src/analysis/duration.py`, `causal.py`, `compaction.py`; `src/reports/prompts.py`, `service.py`, `prompt_rows.py`; `src/presentation/duration.py` | `test_report_duration.py`, `test_opencode_terminal.py`, `test_watch_rendering.py` |
| Process-local inactive/unfinished execution uncertainty | `src/sources/opencode_v2_wire.py`, `src/analysis/causal.py`, `models.py`; `src/reports/session_history.py`, `sampling.py`, `prompt_rows.py`; `src/watch/cards.py`, `running.py`, `tracker.py`; shared application/CLI/Web/Mini projections | `test_execution_unverified.py`, `fixtures/execution_lifecycle.py`; `integration/export_unverified_watch.py` + `probe_pre_response_watch.cjs` cover source-derived detail/Full/Mini DOM, SSE, reload/reconnect; real `probe_web_live.py --watch-cards --detail`; [limits/decision](../../journal/web/watch-terminal-lifecycle.md) |
| Web AI Stats / fun-first numbers, early snapshots and retained period results | `src/analysis/ai_stats.py`; `src/reports/ai_stats.py`, `ai_stats_evidence.py`; `src/application/ai_stats.py`, `projection.py`; `src/web/jobs.py`, `stats_jobs.py`, `assets/ai-stats.js`, `cached-reports.js`, `app.js` | `test_ai_stats.py`, `test_ai_stats_recovery.py`, `test_ai_stats_resume.py`, `test_web_dispatch.py`, `test_active_hour.py`, `test_web_loading.py`; `integration/ai_stats_progress.cjs`, `cached_reports.cjs`; hidden `integration/probe_ai_stats.cjs`, `probe_ai_stats_states.cjs`, `probe_ai_stats_slices.cjs` (production processes); read-only `integration/probe_ai_stats.py --cold-and-warm`; fixed-history `integration/benchmark_ai_stats.py --baseline <exact-git-hash> --sliced`; [heuristics, evidence and scoped exception](../../journal/web/ai-stats.md) |
| Exact first-input Web Comparisons / optional period matched-run fact | `src/analysis/input_identity.py`, `matched_runs.py`; `src/reports/matched_inputs.py`, `matched_runs.py`; `src/application/comparisons.py`; `src/web/assets/comparisons.js` and shared cached-report lifecycle | `test_matched_inputs.py`, `test_ai_stats.py`, `integration/cached_reports.cjs`; hidden `integration/probe_comparisons.cjs`, read-only `integration/probe_comparisons.py`; [evidence/limits](../../journal/web/comparisons.md) |
| Historical context vs current anchors, active history, deltas, effort, price thresholds | `src/analysis/context.py`, `context_history.py`, `effort.py`, `comparisons.py`; `src/reports/prompt_rows.py` projects rows, `prompts.py` assembles blocks | `test_context_history_projection.py`, `test_step6_context_comparisons.py`, `test_prompt_projection.py`, `test_effort_presentation.py`, `test_threshold_multiplier.py`, `test_session_move.py` |
| Token telemetry/mix and quota Pace | `src/sources/opencode_tokens.py`, `src/analysis/token_mix.py`, `quota_pace.py` | `test_token_mix.py`, `test_token_mix_economics.py`, `test_priced_token_mix.py`, `test_quota_presentation.py` |
| Independent report eligibility/sample cutoffs | `src/reports/sampling.py`; `acquisition.py` stages bounded strict snapshots without consuming them; `service.py` owns dispatch | `test_report_sampling.py`, `test_report_sample_acquisition.py`, `test_source_history_loading.py`, `test_compact_reports.py`, `test_report_definitions.py`, `test_token_mix.py` |
| Global comparison mix / retained wire evidence | `src/analysis/comparisons.py`, `models.py`; `src/reports/service.py:_relative_usage/_threshold_multiplier`; no model/publisher profile cache engine | `test_workload_mix.py` (global counts/ratios, evidence export, historical publisher parity), `test_report_sampling.py` (eligibility/cutoffs) |
| Bounded canonical context-guidance input | `src/reports/context_sample.py`, `acquisition.py::release`; `service.py::_threshold_multiplier` preserves the fifteen-minute observation | `test_context_sample.py`, `test_threshold_multiplier.py`; compact ordering/token volumes, both sample cutoffs, sampler-only heavyweight release and clock rollback; no Earlier membership proof |
| Mode-specific root/day scopes, source batch/cache orchestration and numeric acquisition measurements | `src/reports/history.py`, `acquisition.py`, `accounts.py`; `src/domain/acquisition.py`; date-only observed V2 batches in `src/sources/opencode_v2_snapshot.py`; [history contracts/benchmarks](history-loading.md) | `test_history_loading.py`, `test_source_history_loading.py`, `test_historical_reports.py` (872-root scale cases in Full), `test_watch_today_ccost.py`, `test_diagnostics_ux.py` |
| Report projections/detail/history/notices/account order | `src/reports/models.py`, `prompt_rows.py`, `prompts.py`, `accounts.py`, `token_mix_history.py`, `migration_notice.py`, `model_comparison.py`, `semantics.py` | `test_prompt_projection.py`, `test_account_ordering.py`, `test_step7_reports_cli.py`, `test_compact_reports.py`, `test_report_definitions.py`, `test_source_selection.py` |
| Optional transport-neutral report application | `src/application/service.py`, `contracts.py`, `projection.py`; [ownership and mode parity inventory](reports.md#transport-neutral-application-boundary-and-parity-inventory) | `test_application_reports.py`; existing report/Watch tests retain semantic ownership |
| CLI/Web numeric display contract | `src/display.py`, `src/numbers.py`, `src/application/display.py`, `src/web/assets/render.js`; [per-view baseline](../governance/verification/web-display-parity.md) | `test_web_display.py`, `test_ccost_display_unit.py`, `development/tests/integration/web_display.cjs`; exact raw values remain numeric sort inputs; projection-local clock reuse preserves both units, token precedence, DST and advancing resets |
| Unified Models / retained Normal presentation | `src/web/assets/render.js`, `app.js`, `reports.js`, `app.css`; `src/reports/model_comparison.py` freezes supplemental catalog, `src/application/projection.py` exports candidate-local supersession | `test_web_models.py`, `test_web_overview.py`, `integration/web_models.cjs`, `integration/web_overview.cjs`, `integration/web_views.cjs`; four-column uncapped document scrolling, independent filters, exact tier multi-sort, unknowns/notices, legacy routes, focus and heartbeat-stable DOM; integrated fixture `integration/serve_web_models.py`, explicit-browser `integration/probe_web_models.py` |
| Shared finite-report auto-loading / retained request lifetime, observed progress and bounded waiting | `src/web/assets/report-loading.js`, `app.js`, `app.css`; `src/web/source_startup.py`, `http.py` expose existing typed readiness; `src/application/service.py` allowlists report-owned history stages | `test_web_loading.py`, `test_web_views.py`, `test_web_runtime.py`, `test_web_source_startup.py`; `integration/web_report_loading.cjs`, `web_report_lifetime.cjs`, hidden `integration/probe_report_loading.cjs` with `fixtures/report_loading.py`; [actual evidence and scoped exceptions](../../journal/web/report-loading.md) |
| Explicit Models price refresh / true upstream observation | `src/pricing/github_copilot.py::refresh_catalog`, `src/web/jobs.py::ModelsPriceRefresh`, `composition.py`, `http.py`, `assets/app.js` / `render.js`; toolbar-only `app.css` styles; no account refresh or Watch catalog replacement | `test_web_price_refresh.py`, `test_web_runtime.py`; `integration/probe_models_refresh.cjs` uses canonical in-memory reports for UI and invokes `probe_models_toolbar.cjs` for computed fonts/responsive geometry, separate `probe_web_live.py --refresh-prices` proves real HTTP/spawn/provider flow; [proof limits](../../journal/web/models-pricing.md) |
| Shared live Accounts / Watch subscription cards | `src/web/assets/account-cards.js`, `app.js`, `watch.js`, `reports.js`, `app.css`; existing `live_projection.py` / `watch_accounts.py` DTOs | `test_watch_daily.py` / `integration/web_watch_summary.cjs`, `test_web_views.py` / `integration/web_views.cjs`; hidden `integration/probe_accounts_live.cjs` checks route/DOM/geometry/settings/freshness, read-only `probe_web_live.py --accounts --watch-cards` checks the real shared owner. `test_web_accounts.py` retains legacy report DTO/helper parity, not the current route. |
| Shared full-size period/30-day Capacity, responsive parity, Used/Remaining and idle zero | `src/application/quota_ccost.py`, `quota_display.py`, `projection.py`, `watch_accounts.py`; `src/reports/accounts.py` binds existing period cost by quota identity; `src/web/assets/account-cards.js` | `test_web_quota_ccost.py`, `test_web_watch_quota.py`, `integration/web_watch_summary.cjs`; hidden `probe_accounts_live.cjs` runs `probe_subscription_capacity.cjs` and `probe_quota_display.cjs` for shared-route and compact compatibility; no new scan or native accounting change |
| Shared Web live engine / immutable Watch export / SSE | `src/application/live.py`, `live_projection.py`, `src/watch/acquisition.py`, `source_status.py`, `src/web/events.py`, `src/web/assets/live.js`; [live ownership](web.md) | `test_web_live.py`, `test_web_connection.py`, `development/tests/integration/web_live.cjs`; read-only real-source `development/tests/integration/probe_web_live.py` |
| Once-per-Web-host service wake / queued initial reports | `src/web/source_startup.py`, `host.py`, `composition.py`; shared trusted wake `src/opencode_service.py`, called also by CLI bootstrap | `test_web_source_startup.py`, `test_connectivity_reliability.py`, `test_v7814_regressions.py`; synthetic hidden browser `integration/probe_web_source_startup.cjs` / `serve_web_source_startup.py` |
| Web one-prompt cards, live per-prompt token mix/canonical CCost split, terminal lifecycle, compact layout and replenished session history | `src/watch/web_coordinator.py`, `card_workers.py`, `cards.py`, `src/reports/watch_capture.py`, `session_history.py`, `src/application/live_projection.py`, `src/web/assets/watch.js` | `test_watch_cards.py`, `test_watch_token_mix.py`, `test_watch_prompt_cost.py`, `test_watch_card_lifecycle.py`, `test_web_live.py`; headless `integration/probe_watch_cards.cjs`, read-only `integration/probe_web_live.py --watch-cards --prompt-token-mix --prompt-cost` |
| Web Watch full-day summary, native monthly/period CCost, quota pace, aligned subscriptions and current-context footers | `src/analysis/daily_usage.py`, `period_ccost.py`, `src/reports/history.py`, `accounts.py`, `watch_context.py`, `src/application/watch_accounts.py`, `live_projection.py`, `src/watch/web_coordinator.py`, `src/web/assets/watch.js` | `test_watch_daily.py`, `test_web_daily_lifecycle.py` (modeled budget/fresh batch sharing), `test_quota_period_lifecycle.py`, `test_watch_context_footer.py`, `integration/web_watch_summary.cjs`; integrated-browser `integration/serve_watch_summary.py`, read-only `integration/probe_web_live.py --watch-cards --daily` |
| Mini Watch / session-keyed Activity table, five-row viewport, measured opening and explicit Fit | `src/watch/cards.py`, `src/application/display.py`, `src/web/assets/mini.js`, `mini.css`, `app.js` | `test_mini_watch.py`, `test_watch_cards.py`, `test_web_display.py`; `integration/mini_watch.cjs` ownership/health/daily parity; `probe_mini_fit.cjs` + `serve_mini_watch.py` real headless PiP/CSP/SSE, width/activity/help/AX, zoom/DPR, bounded scroll and preferences. `probe_mini_watch.cjs --history-demand-only` tests authenticated automatic filler leases. Physical/native helpers require separate authority; [limits](../../journal/web/mini-watch.md). |
| Live Sessions catalog, exact global sort keys, measured cancellable navigation and stable older pages | `src/application/session_catalog.py`, `src/reports/session_summary.py`, `src/web/session_catalog.py`, `src/web/assets/sessions.js`, `src/watch/web_coordinator.py`; [ownership and limits](web.md) | `test_web_session_catalog.py` (including 3,217 scalar keys, typed failures and pinned arrivals), `fixtures/sessions_navigation_vm.cjs` through `test_web_session_detail.py`, `integration/probe_web_sessions.cjs --catalog-navigation-only` / `--catalog-detail-only`; read-only `integration/probe_web_live.py --sessions` |
| Complete live session history, observed retention and revision-pinned chunks | `src/application/session_detail.py`, `src/reports/session_history.py`, `src/analysis/prompt_index.py`, `src/web/assets/session.js`; [ownership and limits](web.md) | `test_web_session_detail.py`, `development/tests/integration/web_session.cjs`; read-only `development/tests/integration/probe_web_live.py --sessions` |
| Selected full native sanitized session JSON / Save As and browser fallback | `src/sources/opencode_v2_export.py`, `opencode_v2_transport.py`, `src/application/session_detail.py`, `src/web/session_export.py`, `http.py`, `assets/session-export.js`, `app.js`; [ownership](web.md#native-session-export-fr-000631) | `test_session_export.py`, `fixtures/session_export.py`, `integration/web_session_export.cjs`; hidden `integration/probe_session_export.cjs` / `serve_session_export.py`; [compatibility, measurements and native-save exception](../../journal/web/session-export.md) |
| Historical Token Mix / shared session presentation; retired Reports bookmarks | `src/reports/token_mix_cache.py`, `token_mix_history.py`, `src/application/display.py`, `projection.py`, `src/web/assets/token-mix.js`, `render.js`, `reports.js`, `app.js`; [Web route contract](web.md) | `test_web_token_mix.py`, `test_web_remaining.py`, `integration/web_remaining.cjs`, `test_web_views.py`, `integration/probe_token_mix.cjs`, read-only `integration/probe_token_mix_baseline.py`; CLI date/shared API tests remain independent |
| Optional Web security / private instance lifecycle / source-change stop | `src/web/http.py`, `security.py`, `host.py`, `lifecycle.py`, `instance_state.py`, `process_identity.py`, `change_guard.py`, `observations.py`; [Web contract](web.md) | `test_web_runtime.py`, `test_web_shutdown.py`, `test_web_lifecycle.py`, `test_web_diagnostics.py`; opt-in read-only `development/tests/integration/probe_web_lifecycle.py`, synthetic `probe_web_bounds.py` |
| Shared Web/Mini value-first help, 600ms hover and intrinsic targets | `src/web/assets/help.js`, `app.css`; integrations in `watch.js`, `mini.js`, `render.js`; [writing/interaction guideline](web-help.md) | `test_web_help.py`, `integration/web_help.cjs`, `fixtures/web_help_vm.cjs`; hidden `integration/probe_web_help.cjs` with `probe_help_headers.cjs`, `probe_help_values.cjs` and lifecycle assertions, plus Mini/theme/quota browser probes |
| Web-wide silent loaded refresh, row-bound promotions and safe Sessions recovery | `assets/app.js`, `cached-reports.js`, `render.js`, `watch.js`, `mini.js`, `account-cards.js`, `sessions.js`, `session.js`, `token-mix.js`, `comparisons.js`; `reports/semantics.py`, `application/projection.py` | `test_web_models.py`, `test_watch_daily.py`, `test_mini_watch.py`, `test_web_watch_quota.py`, `test_web_views.py`, `integration/web_report_lifetime.cjs`, `web_session.cjs`; hidden `probe_web_help.cjs --quiet-refresh` + `probe_quiet_refresh.cjs` / `probe_promotion_help.cjs`, Watch/Accounts/Mini probes; [matrix and limits](../../journal/web/quiet-refresh.md) |
| Web Settings / compact native option help, inherited-vs-explicit Theme, CCost, Mini position/size and quota orientation | `src/web/settings.py`, `assets/settings.js`, `help.js`, `app.css`, `mini.js`, `http.py`; canonical `src/config.py` enum/default resolution; pure `src/application/quota_display.py` native variants | `test_web_theme.py`, `test_web_watch_quota.py`, `integration/web_theme.cjs`, `integration/web_views.cjs`, `integration/web_accounts.cjs`, `integration/mini_watch.cjs`; hidden `integration/probe_web_settings.cjs` covers native picker/fallback and `integration/probe_mini_fit.cjs` covers Mini; pre-fit bounds/process-restart evidence stays historical in the Mini journal |
| Windows Web status console / same-process tray / shared CG favicon | `windows/Cost-Guard-Web.cmd`, `src/web/windows_launch.ps1`, `windows_launch.py`, `native_windows.py`, `win32_tray.py`, `tray_icon.py`, `http.py`, `assets/favicon.ico`; generator `development/tools/generate_web_icon.py`; [native ownership](web.md) | `test_windows_web.py` checks DPI scope/resources/rollback, icon-source equality and synchronous batch exit without visible UI; `test_web_runtime.py` pins favicon routes/CSP; approval-only `integration/probe_windows_web.py` checks native handoff, not browser paint |
| macOS Web launcher / AppKit menu / local Finder app | `macos/Cost-Guard-Web.command`, `macos/launcher.applescript`, `src/web/macos_launch.py`, `macos_app.py`, `native_macos.py`, `macos_status.py`, `objc_bridge.py`; [native-proof limits](web.md) | `test_macos_web.py`, `test_macos_app.py`; approval-only `development/tests/integration/probe_macos_web.py` (not run on Windows; Finder/Gatekeeper pending) |
| New Models first-sighting persistence/highlight and optional-cache recovery | `src/cache/model_notices.py`, `repository.py`, `src/reports/semantics.py`, `src/watch/model_discovery.py`, `src/presentation/pricing_notices.py` | `test_cache.py`, `test_model_pricing_presentation.py`, `test_release_metadata_recovery.py`, `test_watch_model_discovery.py`; deterministic real-connection faults in `fixtures/sqlite_faults.py` |
| Account discovery/async acquisition/freshness evidence | `src/accounts/credentials.py`, `discovery.py`, `acquisition.py`, `refresh_policy.py`, `refresh_loop.py`, `quota_observations.py`; `src/cache/account_refresh_state.py` | `test_account_acquisition.py`, `test_account_freshness.py`, `test_quota_observations.py`, `test_accounts_ccost.py`, `test_claude_code_accounts.py` |
| Native quota-period CCost / empty, reset and delayed-history lifecycle | `src/analysis/period_ccost.py`, `src/reports/accounts.py`, `src/watch/accounts.py`, `web_coordinator.py`; immutable `AccountPeriodHistory` | `test_account_period_ccost.py`, `test_quota_period_lifecycle.py`, `fixtures/account_periods.py`, `integration/web_period_ccost.cjs`, `test_watch_daily.py`, `test_copilot_unaccounted_usage.py`; daily/local month/native UTC month remain distinct |
| Concrete quota providers/mapping | `src/accounts/github_copilot.py`, `openai_subscription.py`, `anthropic.py`, `claude_code.py`, `claude_transport.py`, `minimax.py`, `simple_http*.py`, `http_*.py` | `test_step6_pricing_accounts.py`, `test_http_account_providers.py`, `test_simple_http_engine.py`, `test_claude_transport.py` |
| OpenAI identity, verified TLS and safe transport failures | `src/accounts/openai_subscription.py`, `openai_tls.py`, `diagnostics.py`, `refresh_policy.py`; shared failure text in `src/presentation/accounts.py` | `test_openai_account_switch.py`, `test_openai_transport.py`; synthetic chain fixture `development/tests/fixtures/openai-tls/` |
| Prices, tiers, aliases, promotions, release metadata | `src/pricing/catalog.py`, `tiers.py`, `identities.py`, `github_copilot.py`, `promotions.py`, `release_metadata.py`, `metadata_health.py` | `test_pricing_identities.py`, `test_model_comparison_tiers.py`, `test_model_pricing_presentation.py`, `test_release_metadata_recovery.py`, `test_pricing_watch_startup.py` |
| Disposable persistence/analysis reuse | `src/cache/database.py`, `repository.py`, `metadata_state.py`; `src/analysis/cache.py` | `test_cache.py`, `test_analysis_core.py`, `test_release_metadata_recovery.py`, `test_step9_parity_performance.py` (Full) |
| Two-clock session-cache retention / meaningful demand / idle pruning | `src/cache/session_scope.py`, `lifecycle.py`, `repository.py`; `src/web/cache_housekeeping.py`, `http.py`, `dispatch_http.py`; explicit CLI presentation in `bootstrap.py` | `test_cache_lifecycle.py`, `test_web_cache_housekeeping.py`, `test_web_runtime.py`; executable shipped-API `integration/cache_demand.cjs`; [evidence](../../journal/cache-lifecycle.md) |
| Full/Mini Watch session summary / evidence-gated fair incremental root-tree CCost | `src/analysis/session_cost.py`, `src/watch/session_costs.py`, `cards.py`, `src/application/live_projection.py`, `src/web/assets/watch.js` | `test_session_cost_cache.py`, `test_session_cost_scheduler.py`, `test_watch_context_footer.py`, `integration/web_watch_summary.cjs`, `probe_cost_groups.cjs`, headless `integration/probe_watch_cards.cjs`; read-only `integration/probe_web_live.py --watch-cards --session-cost` |
| Watch lifecycle/change hints/recovery/redraw decisions | `src/watch/coordinator.py`, `redraw.py`, `observers.py`, `account_refresh.py`, `accounts.py`, `model_discovery.py` | `test_watch_account_refresh.py`, `test_watch_idle_accounts.py`, `test_step8_watch.py`, `test_watch_source_recovery.py`, `test_account_acquisition.py`, `test_v7814_regressions.py` |
| Watch global prompt retention, startup Earlier sessions, session order, skills/tool failures, run totals and retained daily CCost | `src/watch/tracker.py`, `session_retention.py`, `skill_registry.py`, `tools.py`, `tool_contracts.py`, `token_mix.py`, `today_ccost.py`, `models.py`; `src/presentation/watch_activity.py` renders activity | `test_watch_grouping.py`, `test_watch_session_retention.py`, `test_watch_activity_lifecycle.py`, `test_watch_tool_activity.py`, `test_watch_skills.py`, `test_watch_subtotals.py`, `test_watch_today_ccost.py`, `test_token_mix.py` |
| Full Watch invocation disclosure, uniform Running ink and failed/cancelled subsets | `src/watch/tools.py`, `invocation.py`, `models.py`, `src/sources/opencode_v2_background.py`, `src/application/live_projection.py`, `src/web/assets/watch.js`, `app.css` | `test_watch_invocation.py`, `test_watch_cards.py`, `test_watch_tool_activity.py`, `test_watch_skills.py`, `test_watch_activity_lifecycle.py`, `test_web_live.py`, `fixtures/watch_tool_outcomes.py`/`.cjs`; hidden `integration/probe_watch_tool_outcomes.cjs` + `probe_watch_invocation.cjs` with `serve_watch_summary.py --tool-outcomes`; read-only `probe_web_live.py --tool-invocations` (active DTO), separate `--watch-cards --tool-outcomes` (whole Earlier proof/outcomes) |
| Terminal output only | `src/presentation/report.py`, `source_errors.py`, `watch.py`, `accounts.py`, `model_comparison.py`, `model_supersession.py`, `terminal.py`, `context_warnings.py`, `definitions.py`, `token_mix.py` | `test_watch_rendering.py`, `test_quota_presentation.py`, `test_account_status_layout.py`, `test_report_polish.py`, `test_model_supersession.py` |
| Startup work/progress, buffered Watch rows/overflow scrollback and launcher handoff | `src/domain/progress.py`, `src/presentation/progress.py`, `startup_estimate.py`, `watch_screen.py`; `src/launcher_feedback.py`, `src/windows_launcher.ps1`, `windows/`, `macos/` | `test_startup_progress.py`, `test_watch_screen.py`, `test_launcher_feedback.py`, `test_windows_launcher.py`, `test_watch_startup_recovery.py`; `--profile startup` |
| Fatal/recoverable fault boundaries and launchers | `src/runtime_errors.py`, `src/windows_launcher.ps1`; `windows/`, `macos/` | `test_runtime_errors.py`, `test_watch_lifecycle.py`, `test_launcher_feedback.py`, `test_windows_launcher.py`; [runtime policy](../governance/policies/runtime-failures.md) |
| Privacy-safe Diagnostics | `development/tools/collect_diagnostics.py`, `diagnostic_accounts.py`, `diagnostic_logs.py`, `diagnostic_metadata.py`, `diagnostic_screen.py`, `diagnostic_watch.py`, `diagnostic_connectivity.py`, `diagnostic_web.py`; `src/sources/connectivity.py`, `connectivity_events.py` | `test_rc2_public_diagnostics.py` (Full), `test_diagnostic_logs.py`, `test_diagnostics_ux.py`, `test_quota_observations.py`, `test_web_diagnostics.py` |

## Shared synthetic fixtures

Web Earlier proof is owned by `src/watch/history_publication.py` and revision/status
coverage in `cards.py`. `test_watch_cards.py` and `test_web_live.py` cover delayed
capture, atomic refresh, source failures, removal/resumption and independent active
publication; `integration/benchmark_history_readiness.py` asserts fixed 2700-root
winners/coverage and cold/warm/changed reads. Current Mini Fit invokes
`integration/probe_history_readiness.cjs` for actual Full/Mini DOM and AX state parity.
[Measurements and the real-source exception](../../journal/web/history-readiness.md)
separate correctness from unproven private cold-start speed.
`test_watch_history_acquisition.py` adds isolated-reader live-evidence/epoch parity,
initial retry confirmation and independent 2700-root automatic recovery using
`fixtures/history_acquisition.py`. Its six-root deferred-enrichment case pins exact
winner certification before session CCost/numeric guidance, available context/model/
finish fields, and unchanged rows/proof/time/read counts after enrichment.
`fixtures/mini_sessions.cjs` exercises Full-five/Mini-five-slot session selection and staged
fields; `fixtures/watch_context_browser.cjs` checks initial pending-to-ready summary
fields over actual Full DOM without mistaking retained-price refresh for first load.
`integration/benchmark_v2_acquisition.py` compares
reader lifetime and bracket sizes with numeric-only wire/source measurements;
its `--capture` mode separates fresh whole-card selection/migration and projection
from acquisition using pinned pricing/disposable caches. `test_watch_card_batches.py`
covers Watch-only member outcomes, epoch rejection, reserved active capacity and
transport-cancel/join/replay with independent winner recovery;
`test_watch_card_readers.py` covers exclusive per-worker reader lifetime,
before/after brackets, actor/epoch/expiry invalidation, per-job metrics and
cancel/retire/fatal-close ownership in `src/watch/card_readers.py` and Web composition;
`test_v2_tree_brackets.py` owns Web-card-only recursive scoped brackets in
`src/sources/opencode_v2_tree.py`, per-epoch capability checks, complete-global
isolation, active/location parity and mutation/failure/cancel cases.
[FR000624's in-progress ledger](../../journal/web/foreground-recovery.md) retains
the failed real baseline and outstanding whole-Web acceptance gates.
`integration/benchmark_web_runtime.py` pins each complete historical default Web
backend to `fixtures/historical_web_source.py` (raw current V2 HTTP) and
`historical_web_inputs.py` (isolated discovery/config/cache and raw pricing/account
inputs). Its optional explicit `--browser` invokes `probe_historical_web.cjs` for
the selected tree's shipped reports, Sessions, Accounts and headless Document PiP
Earlier DOM against the independent synthetic oracle. Single small smokes are not
matched performance/large-real-source/native-desktop acceptance.
The raw synthetic quota window is pinned to the source timestamp across versions
and spawned observations while fetched timestamps remain real. Parent pre/post
input checks censor quota expiry or a relevant local calendar boundary, not product
computation. Historical-runtime tests cover stable raw periods, child-bootstrap
propagation and input-invalid classification; older moving-window timings remain
a distinct workload. Diagnostic-only `--report-timeline` adds the original Token Mix
entrypoint/continuation observer (`historical_web_inputs.observe_build`) and scalar
job/dispatcher transitions (`dispatch_probe_resources.FiniteTimeline`); its overhead is
not a performance comparator. Managed Token Mix bulk derived-cache observation is owned
by `src/reports/acquisition.py::RootAcquisition.observe` and covered in
`test_web_token_mix.py`.
`test_historical_web_runtime.py` checks the independent finish oracle, cross-model
input groups, raw pagination past500, original HTTP202 admission and positive
period/paged-membership requirements. `recent-metadata` is exhaustive-cutoff stress;
`cutoff-effective` fixes ten percent recently touched old roots and otherwise
canonical activity. This contrasting fixture is not an inferred real distribution.
`integration/benchmark_retained_web_runtime.py` keeps one synthetic registration
identity across normal preparation and two fresh-host/browser arms, restoring one
WAL-consistent seed at the same cache path through `fixtures/historical_web_retention.py`.
It separates preparation traffic from arm counters; optional `--sparse-stale` changes
exactly three dispersed roots once before both arms, not concurrent update freshness.
The same focused test file covers seed restoration, registration non-rewrite,
counter deltas and preservation of ordering/finish through that fixed mutation.
Optional `--card-timeline` uses `fixtures/card_service_timeline.py` to observe
unique owned futures, cleanup completion, owner reap and conservative ready-backlog
permit waiting, without source IDs or scheduling changes. `test_card_service_timeline.py`
pins group counting, detached per-capture factory/acquisition/allowlisted transport
observations and noninterference; diagnostic timings include observer overhead.
The real read-only `probe_data_dispatch.py --card-timeline <owned-output>` reuses
that opt-in observer and exports numeric history coverage without winner identities.
The full-runtime harness's `--card-brackets global` changes only the new bracket
seam, retaining reader lifetime and all normal source/host work. Optional
`--live-updates 1|3` enables owned synthetic running prompts and serial source
changes during normal browser/finite warming, then requires actual accepted active
content and server publication, not heartbeats. `fixtures/live_update_timeline.py`
records numeric owner stages and the actual loop-local publication deadline;
account-history spans include actual calling-thread CPU (nested wall spans are
not additive CPU), allowing the known-update comparison without a function,
card or broad owner profiler.
`test_live_update_timeline.py` pins rejection/active-marker handling, noninterference
and source mutation/oracle semantics. Static trials and update diagnostics are
different workloads; neither proves native geometry or the private source oracle.
`--history-switch` exercises an unfinished Models/history switch with actual native
Full disclosure keyboard input, certified paint and visible headless Document PiP
while its opener is hidden; `--history-switch mini` instead switches at once to a
visible Mini Earlier over a hidden opener while Models and proof are unfinished,
recording first usable finite results. `--history-pacing off`
(`historical_web_inputs.withhold_history_pacing`) is a historical-replay control
for the rejected history-pending demotion; current production fails it explicitly.
`--warm-idle SECONDS [--warm-settle SECONDS]` (browser only, not with
`--live-updates`) appends two browser-owned Watch idle windows (Earlier expanded,
then collapsed) measured by `integration/warm_idle_economy.py` (host CPU/IO/RAM,
Live publications, busy jobs, unfinished Sessions scalar warming rows, fixture
source requests, report starts), then same-tab and fresh-page warm re-entry
of the four finite routes; `test_historical_web_runtime.py` pins its window summary.
The rejected prospective2↔3 admission control and
observer were removed after whole-host comparisons; evidence remains in the ledger.
`history_demand.cjs`/`test_web_dispatch.py` cover capability/legacy shape, strict
Watch-only demand, independent Full/Mini leases, PiP timers, expiry and late-close
guards. `test_watch_completion_service.py` covers ordinary three-history admission,
guidance and demand handling. Visible Earlier demand never demotes hidden
requested reports (visible finite0, hidden requested1, background2); the rejected
history-pending pacing was removed after paired runs. Real background park/resume
completion on the same stack is covered by `test_web_dispatch.py`.
`prepare_watch_account_history` requirements-only
setup/final-projection equivalence is covered by `test_watch_daily.py`.
`probe_web_live.py --history-oracle <new-owned-output> --browser <explicit-Chromium>`
uses `integration/history_reference.py` and `real_history_oracle.py`: a separate
normal global-bracketed reader, complete membership/revision reconciliation and
canonical lifecycle scalar reduction without product cache/pricing or Watch ranking.
The Live-owner observer supplies actual proof bindings only, never expectations.
Changed roots/time-sensitive tool-continuation boundaries invalidate scalars;
incomplete/churning roots are not exclusion evidence. Heavy preparation precedes
the default host; reconciliation still contaminates timing, so this is correctness
evidence, not a cold-performance arm. Private-mode shipped-browser Full/Mini checks
include prompt/finish/order and actual hidden opener. After each browser check a fresh
exact re-match must still have the rendered winners; changed live winners re-render
(at most three cycles) or remain INCONCLUSIVE. Only numeric/equality/run-local
opaque-digest evidence is exported. `test_history_reference.py` covers these
reference contracts and verifies the global rather than optimized scoped path.
`fixtures/owner_cost_timeline.py` adds opt-in nested inclusive/exclusive wall and
thread-CPU aggregates by fixed host-thread role, plus a short owner function
profile (turns starting5..8s), constructed/finalized on that owner thread with
stdlib `profile.Profile`. `test_owner_cost_timeline.py` pins nesting,
exception unwinding, foreign-thread exclusion, plausible timings, return/privacy
and wrapper restoration. Coarse publication substages separate projection,
top-level display, outer DTO conversion and EventHub JSON/copy work.
Both harnesses support `--owner-profile` (real probe takes an owned output path).
Use `--owner-functions off` for coarse-only comparisons. The full-host harness's
explicit `--timezone UTC|Europe/Stockholm` changes only owned fixture configuration;
UTC remains the default. Observer overhead and Windows CPU timer quantization
remain limitations, not evidence that short-stage CPU exceeds possible work.
Only the real probe's explicit `--extend-history-observation` can extend the same
normal90s Watch observation in advancing30s slices, at most300s total. This is
observation policy, never a product computation timeout or independent oracle.
Unwrapped CPU remains unknown; nested/cross-thread inclusive spans are not additive.

Mini's session totals/history presentation, canonical Finished clock and unknown-finish help are covered by `test_mini_watch.py`,
`fixtures/mini_sessions.cjs`; `integration/probe_mini_help.cjs`, invoked
by current `probe_mini_fit.cjs`, pins the five-column layout, name-only Session,
independent prompt / whole-session cost cells and symmetric Session/cost help for each
focal or canonical historical representative (including unknown ordinals). Stable
focus/live help, Escape suppression, pointer/keyboard/touch and intrinsic cost widths
are checked across widths, font/CSS zoom, themes and units. `probe_mini_duration.cjs`
checks the safe running-only Duration span, ticking/selection and open-help outcome changes.
`fixtures/account_capacity.cjs` and `probe_subscription_capacity.cjs` cover shared-card
numeric availability, unknown/known transitions, first-letter labels and native help/ARIA.
Older
`integration/probe_mini_sessions.cjs` belongs to the pre-fit/pre-paired-cost probe.
`integration/probe_mini_activity.cjs`, invoked by the current `probe_mini_fit.cjs`,
checks historical-only column indices, midnight/DST tokens, live tooltip/focus identity,
pointer/touch help and nominal/narrow geometry in Classic/Web light/dark and both units.
`fixtures/mini_opening.cjs` pins inert real/reference measurement in both states,
larger-real precedence and cleanup on failed layout. `integration/probe_mini_width.cjs`
checks achieved text/control geometry, bounded tolerance, stable gutter/markers,
light/dark fonts/units and pointer/keyboard reference toggles through the native fit probe.
`fixtures/mini_disclosure.cjs` covers bounded sizing state and failures;
`integration/probe_mini_disclosure.cjs` measures native pointer/keyboard outer/inner
bounds and safe fallbacks. `integration/probe_watch_quiet.cjs` checks actual card
heights/retained figures across transient and virtual sustained refresh failures.
`fixtures/live_status.cjs`, run by `web_watch_summary.cjs`, pins the shared presentation-only
indefinitely quiet retained refresh, nonfresh/cost-only replay, real partial quotas and actionable
auth failures. `web_report_lifetime.cjs` covers quiet host retry/ownership and immediate
offline/auth/source errors; Mini's independent clocks and configured-day expiry stay in `mini_watch.cjs`.
`integration/probe_watch_presentation.cjs` runs that proof plus total-only CCost and independent I/E value help,
confirmed focal title/row colors, focus/selection and contrast in Classic/Web light/dark
at wide/narrow widths. `test_watch_prompt_cost.py`, `test_watch_daily.py` and
`integration/web_live.cjs` own the matching total-token/paired-help, initial/delayed status and
SSE/lifecycle regressions; no backend pricing/acquisition change is implied.
`integration/probe_watch_loading.cjs` adds three virtual minutes per independent
history/accounts/daily/partial lane to that theme/width matrix.
`integration/probe_watch_loading_app.cjs` uses the shipped app/HTTP/SSE and synthetic
`serve_mini_watch.py` publications for three wall-clock minutes, initial missing-frame
feedback, new cards, route retention and host/source/offline recovery. It never
starts model work or accesses a personal browser; the real-installation probe is separate.
The shared `session_summary` projection
and cache/lifecycle tests retain valuation and history eligibility ownership.

Quota Used display is shared by `src/display.py`, `src/presentation/accounts.py` and `src/application/display.py`; `test_quota_used.py` covers parity and the temporary `src/presentation/quota_migration.py` visible-Watch state owner. Web Watch's native Used/Total versus independent inline period CCost is covered by `test_web_watch_quota.py`, `integration/web_watch_summary.cjs` and the headless `integration/probe_watch_cards.cjs` layout/currency matrix. `test_watch_context_footer.py` and `fixtures/watch_context_browser.cjs` pin Full Watch's two-row Context/Total CCost summary, one Context warning, targeted severity colors/SVG shapes, theme contrast, compaction, stale captures and focus-safe invalidation; Mini keeps the original live-context fields. Remove only the temporary notice per the [cleanup note](../../backlog/quota-used-warning-cleanup.md), never the permanent Used conversion.

- `development/tests/fixtures/session_snapshots.py`: canonical root/child/task/continuation/compaction/running snapshots (also without the /compact work, or after a location move), shared single `one_request`, explicit start/end `history` snapshots and message/part/provenance builders.
- `development/tests/fixtures/active_hour.py`: finite hourly-cost service/capture setup shared by rate tests and the synthetic browser probe, without importing test modules.
- `development/tests/fixtures/pricing_catalog.py`: the small deterministic two-model reference catalog, two-tier 100K-threshold catalog and synthetic provider pricing Markdown, imported directly by provider/presentation tests.
- `development/tests/fixtures/warning_projections.py`: single-prompt report/Watch projections carrying one Next-Ictx warning severity.
- `development/tests/fixtures/report_runtime.py`: in-memory source/pricing/quota boundaries and a stale-root/recent-child scenario.
- `development/tests/fixtures/compact_reports.py`: cache-backed `report_service(test, ...)` factory, fixed model `Availability`, plain `rendered` reports and their `START`/`NOW` clock.
- `development/tests/fixtures/accounts.py` and `quota_rendering.py`: normalized account snapshots/fixed providers; fixed-time rolling quota projections with report/Watch account-section text.
- `development/tests/fixtures/watch_runtime.py`: mutable/live synthetic sources, deterministic account scheduler, finite lifecycle Watch composition and render/status/finish recorder. Runtime-fault, lifecycle and source-recovery tests import this owner directly, not each other; the report/account seam is unchanged.
- `development/tests/fixtures/watch_rendering.py`: two-session full Watch frame, quota, warnings and activity shared directly by rendering and tool-activity tests; no test-module imports or runtime changes.
- `development/tests/fixtures/terminal_buffer.py`: in-memory VT cursor/erase/wrap and scrollback replay for Watch overflow redraws; no terminal process or UI automation.
- `development/tests/fixtures/windows_shell.py`: hidden synthetic shell readiness/release, bounded owned-child cleanup and the terminal console stub; no native tray/browser/desktop proof.
- `development/tests/fixtures/report_process.py`: controlled process exit and IPC for deterministic natural/forced termination, retained ownership and host/HTTP cleanup-failure propagation; no OS child or timing assumptions.
- `development/tests/fixtures/account_workers.py`: finite gated provider calls, virtual-latency quota observations and bounded worker synchronization.
- `development/tests/fixtures/openai-tls/`: disposable localhost chain/key reproducing expired cached-intermediate shadowing and rejecting expired leaves, untrusted chains and hostname mismatch; no workstation/provider certificates or credentials.
- `development/tests/fixtures/watch_rows.py`: synthetic neutral prompt blocks/canonical snapshots shared directly by grouping, visible-row subtotal, chronological lifecycle and divider tests (`test_watch_session_groups.py`).
- `development/tests/fixtures/opencode_v2_service.py`: fake loopback V2 services (transitional and current wire) that drop keep-alive sockets on stop like a real process.
- `development/tests/fixtures/opencode_v1_database.py`: the synthetic V1 SQLite history used for generation parity.
- `development/tests/fixtures/package_copy.py`: disposable distributable and config-only package copies and tool subprocesses for validator/config tests.
- `development/tests/fixtures/synthetic_month.py`: scalable histories for bounded-sampling/cache/performance checks.
- `development/tests/fixtures/models_progress.py`: bounded real Normal workflow with separate sample/account history, batch/non-batch paths, cache reuse and optional slowed completed units; `integration/web_minimal_overview.py` exercises its production process/HTTP/event/browser path.
- `development/tests/fixtures/web_help_reports.py`: immediate in-memory report jobs for the shared-help browser audit, using canonical synthetic report services; not report-process/lifecycle evidence. `serve_mini_watch.py --help-audit` selects this owner without changing the existing cancellation fixture.
- `development/tests/fixtures/opencode_v1/` and `opencode_v2/`: non-secret native wire/schema fixtures.

Import common setup from fixtures, not another test module. Fixture modules may import runtime contracts but never `development/tests/`. Some historical specialized test-to-test imports remain; the inventory shows exact remaining edges so they can be migrated when that responsibility is changed. Do not introduce a universal test `helpers.py` or a production dependency on fixtures.

## Protected distinctions

- Catalog metadata/revisions select candidates; hydrated snapshots establish actual usage. Domain tree traversal is not source hydration or causal request attribution.
- Reports retain archived history; Watch excludes archived root sessions. An orphan's metadata can remain observable without becoming a valid detail target.
- Comparison samples exclude running/aborted/execution-unverified prompts; token samples include them. Both admit only prompts with a reference-priceable request and use only such requests; aggregate CCost scopes and `--token-mix` keep all usage. Both independent cutoffs must hold before skipping older roots; equal timestamps qualify.
- V2 wire compatibility, normalized messages/requests and source acquisition have separate owners. Per-step usage replaces cumulative message usage; mutable session selection never fills historical request attribution.
- Quota observations never establish history/account attribution or billing. Watch continues to share report analysis and owns its existing bounded workers/cadence/recovery.

## Feature placement and anti-degradation checklist

Before adding a feature, identify its **one semantic owner** and a protected neighboring behavior; do not append the implementation to bootstrap/coordinator just because they call everything.

| Feature | Smallest extension seam | Must not change |
| --- | --- | --- |
| New report mode | CLI/request mapping, focused `ReportService._build_*` method, projection and renderer | Other modes' source/account acquisition scopes; shared analysis truth |
| Prompt metric/context display | Analysis if new semantics are needed; `PromptRowProjector` for mapping; block totals only for aggregation; renderer for style | Usage/billing provenance, date cutoffs, compaction/subtask context epochs |
| Account/quota provider | Adapter/maintained mapping, normalized domain, bootstrap wiring | Current-login vs historical attribution, bounded acquisition, quota vs CCost |
| Account retry/liveness behavior | Acquisition `ProviderRefresh` / `AccountRefreshLoop`; `WatchAccountRefresh` publishes/ages full account keys | Source-event independence, successful-seen timestamps, bounded lanes, deadline/late-result rules |
| Source generation/wire variant | Source adapter normalization and fake native fixtures | Reports/analysis must not branch on raw wire generation |
| Watch row/geometry behavior | Tracker/projection or presentation according to responsibility | Run totals vs visible-row subtotals; no renderer/provider calls |
| Shared test setup | Responsibility-owned `development/tests/fixtures/` module | Never import another test module for a new fixture or import development into runtime |

1. Read the relevant table row and focused tests; characterize the behavior before moving code. Preserve the exact working tree, not an older Git/package version.
2. Use explicit typed inputs and named projection fields. Keep side-effect orchestration separate from normalized transformation; prefer cohesive functions/state owners, not mixins, dynamic forwarding or generic helpers.
3. Run focused product tests and applicable source validation only for product-code changes; development-only workflow comes from installed Toolkit skills.
4. Named legacy routine limits and the remaining 3 test-import edges are **bounded debt**, not a feature budget. Growth, new edges and stale declarations fail. Split the owner or extract a fixture and remove its resolved debt entry; never auto-generate/accept a replacement baseline to silence the gate. A genuine limit change requires an explicit architectural decision, not a passing-test justification.
5. Every runtime/fixture module describes its responsibility in a module docstring; local Markdown/table routes are regression-tested. Update this map and current contracts in place, not by accumulating version-specific copies. File caps remain unchanged.
6. Routine product-release ZIP generation is not supported. UI, commits and remote publishing retain independent authorization; development-only verification comes from installed Toolkit.

The metrics are guardrails, not a quality score or a substitute for reviewing semantics. Do not compress control flow into clever expressions or weaken tests to evade them. See [the current inventory/refactoring review](../../journal/PERFORMANCE.md) for measured changes and proof limits.
