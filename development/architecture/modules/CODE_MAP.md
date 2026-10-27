# Cost Guard code map

Navigation, not another architecture authority: [OVERVIEW.md](../OVERVIEW.md) owns the source contracts; installed OpenCode Toolkit skills own the workflow. This map routes implementation and tests without importing the application or loading historical releases.

## Start here

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
| Entry/CLI/config/version | `cost-guard.py`, `src/bootstrap.py`, `src/cli.py`, `src/config.py`, `src/version.py` | `test_config.py`, `test_step7_reports_cli.py`, `test_zero_data_robustness.py` |
| Canonical values/account identity/CCost | `src/domain/models.py`, `accounts.py`, `ccost.py`, `capabilities.py` | `test_domain.py`, `test_accounts_ccost.py`, `test_ccost_migration.py` |
| Catalog ancestry and whole-tree metadata activity | `src/domain/session_tree.py`; call sites in `src/reports/service.py`, `src/watch/observers.py`, `coordinator.py` | `test_session_tree.py`, `test_compact_reports.py`, `test_watch_grouping.py` |
| V1 SQLite acquisition/change gates | `src/sources/opencode_v1.py`, `opencode_v1_revision.py`, `opencode_v1_catalog.py` (row activity and separate liveness) | `test_opencode_v1.py`, `test_source_history_loading.py`, `test_source_selection.py`, `test_step9_parity_performance.py` (Full) |
| V2 discovery/HTTP/hydration and active-history evidence | `src/sources/discovery.py`, `errors.py`, `read_recovery.py`, `opencode_v2_transport.py`, `opencode_v2_wire.py`, `opencode_v2.py`; `opencode_v2_catalog.py`/`opencode_v2_snapshot.py` own shared indexes/consistency batches | `test_opencode_v2.py`, `test_source_history_loading.py`, `test_source_selection.py`, `test_connectivity_reliability.py`, `test_watch_startup_recovery.py`, `test_watch_source_recovery.py` |
| V2 wire shapes vs canonical normalization | `src/sources/opencode_v2_wire.py` translates current/legacy wire shapes; `opencode_v2_normalization.py` maps bundles/parts/requests and tool-continuation records | `test_v2_normalization.py`, `test_v2_tool_continuations.py`, `test_effort_presentation.py`, `test_v2_synthetic_attribution.py` |
| Native termination/stop causes/background/move evidence | `src/sources/opencode_v2_events.py`, `opencode_v2_background.py`, `opencode_errors.py`, `opencode_v2_wire.py`, `opencode_v2_interruptions.py` | `test_opencode_terminal.py`, `test_opencode_aborts.py`, `test_watch_stop_reasons.py`, `test_live_stop_reasons.py`, `test_session_move.py`, `test_watch_lifecycle.py` |
| Request attribution, child work, billing and valuation | `src/analysis/causal.py`, `billing.py`, `valuation.py`, `core.py`, `compaction.py` | `test_analysis_core.py`, `test_v2_synthetic_attribution.py`, `test_accounts_ccost.py`, `test_ccost_migration.py` |
| Historical execution timing and overlap-safe report/list totals | `src/analysis/duration.py`, `causal.py`, `compaction.py`; `src/reports/prompts.py`, `service.py`, `prompt_rows.py`; `src/presentation/duration.py` | `test_report_duration.py`, `test_opencode_terminal.py`, `test_watch_rendering.py` |
| Historical context vs current anchors, active history, deltas, effort, price thresholds | `src/analysis/context.py`, `context_history.py`, `effort.py`, `comparisons.py`; `src/reports/prompt_rows.py` projects rows, `prompts.py` assembles blocks | `test_context_history_projection.py`, `test_step6_context_comparisons.py`, `test_prompt_projection.py`, `test_effort_presentation.py`, `test_threshold_multiplier.py`, `test_session_move.py` |
| Token telemetry/mix and quota Pace | `src/sources/opencode_tokens.py`, `src/analysis/token_mix.py`, `quota_pace.py` | `test_token_mix.py`, `test_token_mix_economics.py`, `test_priced_token_mix.py`, `test_quota_presentation.py` |
| Independent report eligibility/sample cutoffs | `src/reports/sampling.py`; `service.py` owns acquisition/cache and dispatch | `test_report_sampling.py`, `test_compact_reports.py`, `test_report_definitions.py`, `test_token_mix.py` |
| Mode-specific root/day scopes, source batch/cache orchestration and numeric acquisition measurements | `src/reports/history.py`, `acquisition.py`, `accounts.py`; `src/domain/acquisition.py`; [history contracts/benchmarks](history-loading.md) | `test_history_loading.py`, `test_source_history_loading.py`, `test_watch_today_ccost.py`, `test_diagnostics_ux.py` |
| Report projections/detail/history/notices/account order | `src/reports/models.py`, `prompt_rows.py`, `prompts.py`, `accounts.py`, `token_mix_history.py`, `migration_notice.py`, `model_comparison.py`, `semantics.py` | `test_prompt_projection.py`, `test_account_ordering.py`, `test_step7_reports_cli.py`, `test_compact_reports.py`, `test_report_definitions.py`, `test_source_selection.py` |
| Optional transport-neutral report application | `src/application/service.py`, `contracts.py`, `projection.py`; [ownership and mode parity inventory](reports.md#transport-neutral-application-boundary-and-parity-inventory) | `test_application_reports.py`; existing report/Watch tests retain semantic ownership |
| CLI/Web numeric display contract | `src/display.py`, `src/numbers.py`, `src/application/display.py`, `src/web/assets/render.js`; [per-view baseline](../governance/verification/web-display-parity.md) | `test_web_display.py`, `development/tests/integration/web_display.cjs`; exact raw values remain numeric sort inputs |
| Overview / Normal rendered section and model-order parity | `src/web/assets/render.js`, `app.css`; existing application display tokens and CLI Normal projection | `test_web_overview.py`, `development/tests/integration/web_overview.cjs`; exact/default/fallback ranking, multiplier tiers, account groups and visible warnings |
| Models selectable/full-catalog comparison | `src/web/assets/render.js`, `reports.js`, `app.css`; canonical comparison DTOs from `src/application/projection.py` | `test_web_models.py`, `development/tests/integration/web_models.cjs`; CLI membership/rank, blank fallback, exact native rates, stable numeric sorting and catalog controls; explicit-browser `integration/probe_web_models.py` |
| Normal Accounts cards / quota display | `src/web/assets/render.js`, `app.css`, `src/display.py`, `src/application/display.py`; existing immutable account DTOs | `test_web_accounts.py`, `fixtures/account_views.py`, `integration/web_accounts.cjs`; explicit browser `integration/serve_web_accounts.py` + `probe_web_accounts.cjs` checks light/dark/360px and native disclosure keyboard behavior |
| Shared Web live engine / immutable Watch export / SSE | `src/application/live.py`, `live_projection.py`, `src/watch/acquisition.py`, `src/web/events.py`, `src/web/assets/live.js`; [live ownership](web.md) | `test_web_live.py`, `development/tests/integration/web_live.cjs`; read-only real-source `development/tests/integration/probe_web_live.py` |
| Complete session Snapshot/Live detail, observed retention and revision-aware pages | `src/application/session_detail.py`, `src/reports/session_history.py`, `src/analysis/prompt_index.py`, `src/web/assets/session.js`; [ownership and limits](web.md) | `test_web_session_detail.py`, `development/tests/integration/web_session.cjs`; read-only `development/tests/integration/probe_web_live.py --detail` |
| Remaining Date/Range and historical Token Mix presentation | `src/application/display.py`, `projection.py`, `src/web/assets/render.js`, `reports.js`; [review matrix](../governance/verification/remaining-web-parity.md) | `test_web_remaining.py`, `integration/web_remaining.cjs`; approval-only synthetic `integration/serve_web_remaining.py` |
| Optional Web security / private instance lifecycle / source-change stop | `src/web/http.py`, `security.py`, `host.py`, `lifecycle.py`, `instance_state.py`, `process_identity.py`, `change_guard.py`, `observations.py`; [Web contract](web.md) | `test_web_runtime.py`, `test_web_lifecycle.py`, `test_web_diagnostics.py`; opt-in read-only `development/tests/integration/probe_web_lifecycle.py`, synthetic `probe_web_bounds.py` |
| Windows Web Beta launcher / same-process tray | `windows/Beta/Cost Guard Web.cmd`, `src/web/windows_launch.ps1`, `windows_launch.py`, `native_windows.py`, `win32_tray.py`, `tray_icon.py`; [native ownership](web.md) | `test_windows_web.py`; approval-only `development/tests/integration/probe_windows_web.py` (native UI, no model inference) |
| Experimental macOS Web launcher / AppKit menu / local Finder app | `macos/Beta/Cost Guard Web.command`, `launcher.applescript`, `src/web/macos_launch.py`, `macos_app.py`, `native_macos.py`, `macos_status.py`, `objc_bridge.py`; [native-proof limits](web.md) | `test_macos_web.py`, `test_macos_app.py`; approval-only `development/tests/integration/probe_macos_web.py` (not run on Windows; Finder/Gatekeeper pending) |
| New Models first-sighting persistence/highlight | `src/cache/repository.py`, `src/reports/semantics.py`, `src/watch/model_discovery.py`, `src/presentation/pricing_notices.py` | `test_cache.py`, `test_model_pricing_presentation.py`, `test_release_metadata_recovery.py`, `test_watch_model_discovery.py` |
| Account discovery/async acquisition/freshness evidence | `src/accounts/credentials.py`, `discovery.py`, `acquisition.py`, `refresh_policy.py`, `refresh_loop.py`, `quota_observations.py`; `src/cache/account_refresh_state.py` | `test_account_acquisition.py`, `test_account_freshness.py`, `test_quota_observations.py`, `test_accounts_ccost.py`, `test_claude_code_accounts.py` |
| Concrete quota providers/mapping | `src/accounts/github_copilot.py`, `openai_subscription.py`, `anthropic.py`, `claude_code.py`, `claude_transport.py`, `minimax.py`, `simple_http*.py`, `http_*.py` | `test_step6_pricing_accounts.py`, `test_http_account_providers.py`, `test_simple_http_engine.py`, `test_claude_transport.py` |
| Prices, tiers, aliases, promotions, release metadata | `src/pricing/catalog.py`, `tiers.py`, `identities.py`, `github_copilot.py`, `promotions.py`, `release_metadata.py`, `metadata_health.py` | `test_pricing_identities.py`, `test_model_comparison_tiers.py`, `test_model_pricing_presentation.py`, `test_release_metadata_recovery.py`, `test_pricing_watch_startup.py` |
| Disposable persistence/analysis reuse | `src/cache/database.py`, `repository.py`, `metadata_state.py`; `src/analysis/cache.py` | `test_cache.py`, `test_analysis_core.py`, `test_release_metadata_recovery.py`, `test_step9_parity_performance.py` (Full) |
| Watch lifecycle/change hints/recovery/redraw decisions | `src/watch/coordinator.py`, `redraw.py`, `observers.py`, `account_refresh.py`, `accounts.py`, `model_discovery.py` | `test_watch_account_refresh.py`, `test_watch_idle_accounts.py`, `test_step8_watch.py`, `test_watch_source_recovery.py`, `test_account_acquisition.py`, `test_v7814_regressions.py` |
| Watch global prompt retention, startup Earlier sessions, session order, skills/tool failures, run totals and retained daily CCost | `src/watch/tracker.py`, `session_retention.py`, `skill_registry.py`, `tools.py`, `tool_contracts.py`, `token_mix.py`, `today_ccost.py`, `models.py`; `src/presentation/watch_activity.py` renders activity | `test_watch_grouping.py`, `test_watch_session_retention.py`, `test_watch_activity_lifecycle.py`, `test_watch_tool_activity.py`, `test_watch_skills.py`, `test_watch_subtotals.py`, `test_watch_today_ccost.py`, `test_token_mix.py` |
| Terminal output only | `src/presentation/report.py`, `source_errors.py`, `watch.py`, `accounts.py`, `model_comparison.py`, `model_supersession.py`, `terminal.py`, `context_warnings.py`, `definitions.py`, `token_mix.py` | `test_watch_rendering.py`, `test_quota_presentation.py`, `test_account_status_layout.py`, `test_report_polish.py`, `test_model_supersession.py` |
| Startup work/progress, buffered Watch rows/overflow scrollback and launcher handoff | `src/domain/progress.py`, `src/presentation/progress.py`, `startup_estimate.py`, `watch_screen.py`; `src/launcher_feedback.py`, `src/windows_launcher.ps1`, `windows/`, `macos/` | `test_startup_progress.py`, `test_watch_screen.py`, `test_launcher_feedback.py`, `test_windows_launcher.py`, `test_watch_startup_recovery.py`; `--profile startup` |
| Fatal/recoverable fault boundaries and launchers | `src/runtime_errors.py`, `src/windows_launcher.ps1`; `windows/`, `macos/` | `test_runtime_errors.py`, `test_watch_lifecycle.py`, `test_launcher_feedback.py`, `test_windows_launcher.py`; [runtime policy](../governance/policies/runtime-failures.md) |
| Privacy-safe Diagnostics | `development/tools/collect_diagnostics.py`, `diagnostic_accounts.py`, `diagnostic_logs.py`, `diagnostic_metadata.py`, `diagnostic_screen.py`, `diagnostic_watch.py`, `diagnostic_connectivity.py`, `diagnostic_web.py`; `src/sources/connectivity.py`, `connectivity_events.py` | `test_rc2_public_diagnostics.py` (Full), `test_diagnostic_logs.py`, `test_diagnostics_ux.py`, `test_quota_observations.py`, `test_web_diagnostics.py` |

## Shared synthetic fixtures

- `development/tests/fixtures/session_snapshots.py`: canonical root/child/task/continuation/compaction/running snapshots (also without the /compact work, or after a location move) and message/part/provenance builders.
- `development/tests/fixtures/pricing_catalog.py`: the small deterministic two-model reference catalog and a two-tier 100K-threshold catalog.
- `development/tests/fixtures/warning_projections.py`: single-prompt report/Watch projections carrying one Next-Ictx warning severity.
- `development/tests/fixtures/report_runtime.py`: in-memory source/pricing/quota boundaries and a stale-root/recent-child scenario.
- `development/tests/fixtures/compact_reports.py`: cache-backed `report_service(test, ...)` factory, fixed model `Availability`, plain `rendered` reports and their `START`/`NOW` clock.
- `development/tests/fixtures/accounts.py` and `quota_rendering.py`: normalized account snapshots/fixed providers; fixed-time rolling quota projections with report/Watch account-section text.
- `development/tests/fixtures/watch_runtime.py`: mutable/live synthetic sources, deterministic account scheduler and Watch service composition. It preserves the existing report/account seam without depending on test modules.
- `development/tests/fixtures/terminal_buffer.py`: in-memory VT cursor/erase/wrap and scrollback replay for Watch overflow redraws; no terminal process or UI automation.
- `development/tests/fixtures/account_workers.py`: finite gated provider calls, virtual-latency quota observations and bounded worker synchronization.
- `development/tests/fixtures/watch_rows.py`: synthetic neutral prompt blocks/canonical snapshots for global grouping, chronological lifecycle order and divider regression tests (`test_watch_session_groups.py`).
- `development/tests/fixtures/opencode_v2_service.py`: fake loopback V2 services (transitional and current wire) that drop keep-alive sockets on stop like a real process.
- `development/tests/fixtures/opencode_v1_database.py`: the synthetic V1 SQLite history used for generation parity.
- `development/tests/fixtures/package_copy.py`: disposable distributable and config-only package copies and tool subprocesses for validator/config tests.
- `development/tests/fixtures/synthetic_month.py`: scalable histories for bounded-sampling/cache/performance checks.
- `development/tests/fixtures/opencode_v1/` and `opencode_v2/`: non-secret native wire/schema fixtures.

Import common setup from fixtures, not another test module. Fixture modules may import runtime contracts but never `development/tests/`. Some historical specialized test-to-test imports remain; the inventory shows exact remaining edges so they can be migrated when that responsibility is changed. Do not introduce a universal test `helpers.py` or a production dependency on fixtures.

## Protected distinctions

- Catalog metadata/revisions select candidates; hydrated snapshots establish actual usage. Domain tree traversal is not source hydration or causal request attribution.
- Reports retain archived history; Watch excludes archived root sessions. An orphan's metadata can remain observable without becoming a valid detail target.
- Comparison samples exclude running/aborted prompts; token samples include them. Both admit only prompts with a reference-priceable request and use only such requests; aggregate CCost scopes and `--token-mix` keep all usage. Both independent cutoffs must hold before skipping older roots; equal timestamps qualify.
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
4. Named legacy routine limits and the remaining 10 test-import edges are **bounded debt**, not a feature budget. Growth, new edges and stale declarations fail. Split the owner or extract a fixture and remove its resolved debt entry; never auto-generate/accept a replacement baseline to silence the gate. A genuine limit change requires an explicit architectural decision, not a passing-test justification.
5. Every runtime/fixture module describes its responsibility in a module docstring; local Markdown/table routes are regression-tested. Update this map and current contracts in place, not by accumulating version-specific copies. File caps remain unchanged.
6. Routine product-release ZIP generation is not supported. UI, commits and remote publishing retain independent authorization; development-only verification comes from installed Toolkit.

The metrics are guardrails, not a quality score or a substitute for reviewing semantics. Do not compress control flow into clever expressions or weaken tests to evade them. See [the current inventory/refactoring review](../../journal/PERFORMANCE.md) for measured changes and proof limits.
