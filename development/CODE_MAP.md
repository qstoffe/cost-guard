# Cost Guard code map

Navigation, not another architecture authority: [ARCHITECTURE.md](ARCHITECTURE.md) owns the contracts; [MAINTAINER.md](MAINTAINER.md) owns the workflow. This map helps a fresh human/AI session find the smallest relevant implementation and tests without importing the entire application or reading historical release material.

## Start here

1. Read root [AGENTS.md](../AGENTS.md) and the workflow it selects. The current filesystem, including uncommitted work, is authoritative.
2. Find the responsibility below, read its boundary types and focused tests, then the affected implementation. Do not put integration details into analysis or presentation.
3. Run a focused pattern/profile while iterating; finish with the environment-appropriate suite and validator (hosted: Quick, never a ZIP; local: Full, live checks and a ZIP). Remote publication remains a separate authorization.

Regenerate a whole-tree static inventory from the repository root:

```text
python development/tools/code_inventory.py
python development/tools/code_inventory.py --json
python development/tools/run_tests.py --profile structure
```

The inventory scans only Python under `src/`, `development/tools/`, `development/tests/` and `development/fixtures/`. It lists module purposes, sizes, longest functions, local imports, layer edges and test coupling. It never imports analyzed code, accesses credentials/runtime history, performs network requests or creates output files. JSON contains the complete per-module map. Lazy/type-only imports are included: these are navigation paths, **not measured test coverage or proof of runtime cycles**.

## Ownership and test routes

All paths in this table are relative to the repository root. Test names live under `development/tests/`; use `--pattern <name>` with the bounded runner.

| Change area | Read/edit first | Focused tests |
| --- | --- | --- |
| Entry/CLI/config/version | `cost-guard.py`, `src/bootstrap.py`, `src/cli.py`, `src/config.py`, `src/version.py` | `test_config.py`, `test_step7_reports_cli.py`, `test_zero_data_robustness.py`, `test_version_history.py` |
| Canonical values/account identity/CCost | `src/domain/models.py`, `accounts.py`, `ccost.py`, `capabilities.py` | `test_domain.py`, `test_accounts_ccost.py`, `test_ccost_migration.py` |
| Catalog ancestry and whole-tree metadata activity | `src/domain/session_tree.py`; call sites in `src/reports/service.py`, `src/watch/observers.py`, `coordinator.py` | `test_session_tree.py`, `test_compact_reports.py`, `test_watch_grouping.py` |
| V1 SQLite acquisition/change gates | `src/sources/opencode_v1.py`, `opencode_v1_revision.py` | `test_opencode_v1.py`, `test_source_selection.py`, `test_step9_parity_performance.py` (Full) |
| V2 discovery/HTTP/hydration | `src/sources/discovery.py`, `opencode_v2_transport.py`, `opencode_v2.py` | `test_opencode_v2.py`, `test_source_selection.py`, `test_watch_source_recovery.py` |
| V2 wire shapes vs canonical normalization | `src/sources/opencode_v2_wire.py` translates current/legacy wire shapes; `opencode_v2_normalization.py` maps bundles/parts/requests | `test_v2_normalization.py`, `test_effort_presentation.py`, `test_v2_synthetic_attribution.py` |
| Native termination/stop causes/background/move evidence | `src/sources/opencode_v2_events.py`, `opencode_v2_background.py`, `opencode_errors.py`, `opencode_v2_wire.py` | `test_opencode_terminal.py`, `test_opencode_aborts.py`, `test_watch_stop_reasons.py`, `test_session_move.py`, `test_watch_lifecycle.py` |
| Request attribution, child work, billing and valuation | `src/analysis/causal.py`, `billing.py`, `valuation.py`, `core.py`, `compaction.py` | `test_analysis_core.py`, `test_v2_synthetic_attribution.py`, `test_accounts_ccost.py`, `test_ccost_migration.py` |
| Context epochs, Ictx, effort, price thresholds | `src/analysis/context.py`, `effort.py`, `comparisons.py`; `src/reports/prompt_rows.py` projects rows, `prompts.py` assembles blocks | `test_step6_context_comparisons.py`, `test_prompt_projection.py`, `test_effort_presentation.py`, `test_threshold_multiplier.py`, `test_session_move.py` |
| Token telemetry/mix and quota Pace | `src/sources/opencode_tokens.py`, `src/analysis/token_mix.py`, `quota_pace.py` | `test_token_mix.py`, `test_token_mix_economics.py`, `test_quota_presentation.py` |
| Independent report eligibility/sample cutoffs | `src/reports/sampling.py`; `service.py` owns acquisition/cache and dispatch | `test_report_sampling.py`, `test_compact_reports.py`, `test_report_definitions.py`, `test_token_mix.py` |
| Report projections/detail/history/notices/account order | `src/reports/models.py`, `prompt_rows.py`, `prompts.py`, `accounts.py`, `token_mix_history.py`, `migration_notice.py`, `model_comparison.py`, `semantics.py` | `test_prompt_projection.py`, `test_account_ordering.py`, `test_step7_reports_cli.py`, `test_compact_reports.py`, `test_report_definitions.py`, `test_source_selection.py` |
| Account discovery/async acquisition | `src/accounts/credentials.py`, `discovery.py`, `acquisition.py`, `base.py` | `test_account_acquisition.py`, `test_accounts_ccost.py`, `test_claude_code_accounts.py` |
| Concrete quota providers/mapping | `src/accounts/github_copilot.py`, `openai_subscription.py`, `anthropic.py`, `claude_code.py`, `claude_transport.py`, `minimax.py`, `simple_http*.py`, `http_*.py` | `test_step6_pricing_accounts.py`, `test_http_account_providers.py`, `test_simple_http_engine.py`, `test_claude_transport.py` |
| Prices, tiers, aliases, promotions, release metadata | `src/pricing/catalog.py`, `tiers.py`, `identities.py`, `github_copilot.py`, `promotions.py`, `release_metadata.py`, `metadata_health.py` | `test_pricing_identities.py`, `test_model_comparison_tiers.py`, `test_model_pricing_presentation.py`, `test_release_metadata_recovery.py` |
| Disposable persistence/analysis reuse | `src/cache/database.py`, `repository.py`, `metadata_state.py`; `src/analysis/cache.py` | `test_cache.py`, `test_analysis_core.py`, `test_release_metadata_recovery.py`, `test_step9_parity_performance.py` (Full) |
| Watch lifecycle/change hints/recovery | `src/watch/coordinator.py`, `observers.py`, `account_refresh.py`, `accounts.py`, `model_discovery.py` | `test_watch_account_refresh.py`, `test_step8_watch.py`, `test_watch_source_recovery.py`, `test_account_acquisition.py`, `test_v7814_regressions.py` |
| Watch retained/grouped rows, tools and run totals | `src/watch/tracker.py`, `tools.py`, `token_mix.py`, `models.py` | `test_watch_grouping.py`, `test_watch_tool_activity.py`, `test_watch_subtotals.py`, `test_token_mix.py` |
| Terminal output only | `src/presentation/report.py`, `watch.py`, `accounts.py`, `model_comparison.py`, `model_supersession.py`, `terminal.py`, `context_warnings.py`, `definitions.py`, `token_mix.py` | `test_watch_rendering.py`, `test_quota_presentation.py`, `test_account_status_layout.py`, `test_report_polish.py`, `test_model_supersession.py` |
| Fatal/recoverable fault boundaries and launchers | `src/runtime_errors.py`, `src/windows_launcher.ps1`; `windows/`, `macos/` | `test_runtime_errors.py`, `test_watch_lifecycle.py`, `test_step10_release_hardening.py`; [runtime policy](runtime-failures.md) |
| Privacy-safe Diagnostics | `development/tools/collect_diagnostics.py`, `diagnostic_logs.py`, `diagnostic_metadata.py`, `diagnostic_screen.py`, `diagnostic_watch.py`, `macos_compatibility.py` | `test_rc2_public_diagnostics.py` (Full), `test_diagnostic_logs.py`, `test_diagnostics_ux.py` |
| Inventory/layer/growth gates/tests/package builder | `development/tools/code_inventory.py`, `structure_guard.py`, `validate_package.py`, `run_tests.py`, `build_release.py` | `test_structure_growth.py`, `test_structure_contracts.py`, `test_foundation_quick.py`, `test_foundation.py`, `test_release_builder.py` (Full), `test_version_history.py` |

## Shared synthetic fixtures

- `development/fixtures/session_snapshots.py`: canonical root/child/task/continuation/compaction/running snapshots and message/part/provenance builders.
- `development/fixtures/pricing_catalog.py`: the small deterministic two-model reference catalog.
- `development/fixtures/report_runtime.py`: in-memory source/pricing/quota boundaries and a stale-root/recent-child scenario.
- `development/fixtures/watch_runtime.py`: mutable/live synthetic sources, deterministic account scheduler and Watch service composition. It preserves the existing report/account seam without depending on test modules.
- `development/fixtures/opencode_v2_service.py`: fake loopback V2 services (transitional and current wire) that drop keep-alive sockets on stop like a real process.
- `development/fixtures/opencode_v1_database.py`: the synthetic V1 SQLite history used for generation parity.
- `development/fixtures/package_copy.py`: disposable distributable copies and tool subprocesses for validator/builder tests.
- `development/fixtures/synthetic_month.py`: scalable histories for bounded-sampling/cache/performance checks.
- `development/fixtures/opencode_v1/` and `opencode_v2/`: non-secret native wire/schema fixtures.

Import common setup from fixtures, not another test module. Fixture modules may import runtime contracts but never `development/tests/`. Some historical specialized test-to-test imports remain; the inventory shows exact remaining edges so they can be migrated when that responsibility is changed. Do not introduce a universal test `helpers.py` or a production dependency on fixtures.

## Protected distinctions

- Catalog metadata/revisions select candidates; hydrated snapshots establish actual usage. Domain tree traversal is not source hydration or causal request attribution.
- Reports retain archived history; Watch excludes archived root sessions. An orphan's metadata can remain observable without becoming a valid detail target.
- Comparison samples exclude running/aborted prompts; token samples include their observed telemetry. Both independent cutoffs must hold before skipping older roots; equal timestamps qualify.
- V2 wire compatibility, normalized messages/requests and source acquisition have separate owners. Per-step usage replaces cumulative message usage; mutable session selection never fills historical request attribution.
- Quota observations never establish history/account attribution or billing. Watch continues to share report analysis and owns its existing bounded workers/cadence/recovery.

## Feature placement and anti-degradation checklist

Before adding a feature, identify its **one semantic owner** and a protected neighboring behavior; do not append the implementation to bootstrap/coordinator just because they call everything.

| Feature | Smallest extension seam | Must not change |
| --- | --- | --- |
| New report mode | CLI/request mapping, focused `ReportService._build_*` method, projection and renderer | Other modes' source/account acquisition scopes; shared analysis truth |
| Prompt metric/context display | Analysis if new semantics are needed; `PromptRowProjector` for mapping; block totals only for aggregation; renderer for style | Usage/billing provenance, date cutoffs, compaction/subtask context epochs |
| Account/quota provider | Adapter/maintained mapping, normalized domain, bootstrap wiring | Current-login vs historical attribution, bounded acquisition, quota vs CCost |
| Account retry/liveness behavior | `WatchAccountRefresh` and its narrow `AccountRefreshWork` protocol | Source-event independence, successful-seen timestamps, deadline/late-result rules |
| Source generation/wire variant | Source adapter normalization and fake native fixtures | Reports/analysis must not branch on raw wire generation |
| Watch row/geometry behavior | Tracker/projection or presentation according to responsibility | Run totals vs visible-row subtotals; no renderer/provider calls |
| Shared test setup | Responsibility-owned `development/fixtures/` module | Never import another test module for a new fixture or import development into runtime |

1. Read the relevant table row and focused tests; characterize the behavior before moving code. Preserve the exact working tree, not an older Git/package version.
2. Use explicit typed inputs and named projection fields. Keep side-effect orchestration separate from normalized transformation; prefer cohesive functions/state owners, not mixins, dynamic forwarding or generic helpers.
3. Run the focused profile/pattern and validator while editing. `structure-policy.json` permits at most **55 body statements / 15 explicit control-flow branches** for ordinary runtime routines. Nested functions are measured independently; docstrings/field-per-line formatting do not inflate this metric.
4. Named legacy routine limits and the remaining 33 test-import edges are **bounded debt**, not a feature budget. Growth, new edges and stale declarations fail. Split the owner or extract a fixture and remove its resolved debt entry; never auto-generate/accept a replacement baseline to silence the gate. A genuine limit change requires an explicit architectural decision, not a passing-test justification.
5. Every runtime/fixture module describes its responsibility in a module docstring; local Markdown/table routes are regression-tested. Update this map and current contracts in place, not by accumulating version-specific copies. File caps remain unchanged.
6. On a workstation, finish with Full/local validation, privacy-safe live evidence and the version ZIP (its builder also gates a clean extraction); hosted sessions stop at Quick + validation. UI, commits and remote publishing still require their own authorization.

The metrics are guardrails, not a quality score or a substitute for reviewing semantics. Do not compress control flow into clever expressions or weaken tests to evade them. See [the current inventory/refactoring review](REFACTORING_REVIEW.md) for measured changes and proof limits.
