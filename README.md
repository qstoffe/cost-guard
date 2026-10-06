# Cost Guard

**Monitor AI model usage, cost and quotas in OpenCode.**

Cost Guard is a local monitoring and analysis tool for [OpenCode](https://opencode.ai/). It shows how OpenCode prompts and sessions use AI models, compares relative model costs, tracks account quotas, and can monitor active OpenCode sessions in real time.

![Cost Guard Watch: OpenCode sessions and quotas](docs/images/cost-guard-watch.png)

Live OpenCode prompts/sessions: model/effort, CCost, calls, context development and account quotas.

## At a glance

- Monitor active OpenCode prompts and sessions in real time.
- Compare AI model costs; see CCost per prompt/session.
- Analyze Token Mix across input, cache read, cache write and output.
- Track context growth and causal usage, including subagents.
- Monitor account/subscription quotas across supported providers.
- Inspect available historical OpenCode sessions and prompts.
- Compare available AI models using your observed workload mix.

## Why Cost Guard?

Multiple OpenCode models, providers and subscriptions make relative cost, token mix, context growth and independent quotas hard to follow together. Cost Guard combines these signals locally.

## Quick start

Extract the [release ZIP](https://github.com/qstoffe/cost-guard/releases/latest), keeping its folder structure. Install **Python 3.11+**. Standard supported OpenCode installations need no Cost Guard configuration.

### Windows

Double-click the ready-to-use `.cmd` launchers under `windows/`; no manual Python commands needed:

| Launcher | Mode |
| --- | --- |
| `Cost Guard.cmd` | Normal model comparison/account quota report. |
| `Cost Guard Watch.cmd` | Live/global Watch; Ctrl+C exits. |
| `Cost Guard Diagnostics.cmd` | Privacy-safe diagnostics ZIP; shows its path. |

The report console stays open. See [download trust](#open-source-license-and-windows-download-trust) for warnings.

### macOS

Equivalent `.command` launchers are under `macos/`:

| Launcher | Mode |
| --- | --- |
| `Cost Guard.command` | Normal report. |
| `Cost Guard Watch.command` | Live/global Watch; Ctrl+C exits. |
| `Cost Guard Diagnostics.command` | Privacy-safe diagnostics ZIP. |

Files ship executable. Use Finder's **Open** for quarantine prompts; never bypass Gatekeeper.

### Python CLI

From the extracted package root:

```text
python cost-guard.py                # Normal report
python cost-guard.py --watch        # Live/global Watch; Ctrl+C exits
python cost-guard.py --token-mix    # Usage by model/token category
python cost-guard.py --sessions 10  # Latest 10 root sessions
python cost-guard.py --help
```

Use `python3` on macOS if needed, or `py -3` on Windows. See [all commands](#setup-and-usage).

## Core concepts

### What Cost Guard counts

Distinct signals:

- **Usage:** observed model requests and input/cache/output/reasoning tokens.
- **CCost:** reference token valuation, not verified billing or credits deducted.
- **Billed:** actual monetary spend with reported or explicit subscription/zero-billing evidence; otherwise `N/A`.
- **Quotas / limits:** independent account-native windows, credits, budgets and availability.

CCost uses GitHub reference rates in Copilot AI-credit-equivalent units. Included subscription work can have positive CCost and Billed $0.00. Unknown prices stay partial/unknown, never replaced with billed cost. A quota credential does **not** prove historical request-account attribution.

### Symbols and token categories

Token Mix uses **I/C/W/O** for uncached input/cache read/cache write/output (including reasoning). See the [usage and cost reference](docs/usage-and-cost.md) for exact counting, rounding, symbols and attribution caveats. Session detail is opt-in, not a billing ledger.

## Reports and usage analysis

### Model comparison and account overview

This cropped normal-report example shows model pricing/comparison and account quotas, not every report section. Comparisons use your observed workload mix.

![Cost Guard: model comparison and account quotas](docs/images/cost-guard-report.png)

Details: [normal report](#normal-report), [model comparison](#model-comparison), [account quotas](#account-quota-blocks).

### Token Mix

`--token-mix` breaks available historical usage down by model and input/cache-read/cache-write/output token category, together with CCost.

![Cost Guard Token Mix: model/category usage and CCost](docs/images/cost-guard-token-mix.png)

See [Token Mix reference](#token-mix--by-model---token-mix). Screenshots are illustrative and may show an earlier Cost Guard release.

## Requirements

- Python **3.11 or newer**.
- A supported OpenCode installation/history:
  - **V1:** Cost Guard reads the local legacy OpenCode SQLite database directly in read-only/query-only mode.
  - **V2:** Read-only registered-service loopback HTTP. If unavailable, `auto`/`v2` may call `opencode api get /api/info` once (no Desktop/TUI); Watch retries process-free every five seconds. Diagnostics `--test-service-start --no-network --snapshots 0` tests cold startup; never stop a shared active service.
- Internet access when GitHub Copilot pricing/model metadata needs its first fetch or refresh.
- Optional Copilot quota reuses OpenCode OAuth in memory, without login, credential writes or GitHub CLI.
- Optional OpenAI subscription quota is fail-soft. Read-only V2 accounts take priority; legacy `auth.json` applies only without V2 rows. Credentials are never refreshed, rotated or written.
- Configured OpenAI/Anthropic API accounts are distinct from **Claude Code subscriptions**, discovered through the optional installed `claude` CLI. Cost Guard never reads/copies Claude credentials or attributes current login to history.
- Claude Code quotas use optional experimental SDK-control metadata (no prompts, transcript scans or new dependencies); accounts stay visible when quotas fail. See [Claude integration and limitations](development/claude-code.md).
- No third-party Python packages are required.

## Setup and usage

Check `python --version` is 3.11+. Full commands, from the extracted folder:

```text
python cost-guard.py                            # Available models + account quotas
python cost-guard.py --all-models               # Full pricing/model catalog only
python cost-guard.py --token-mix                # Total and per-model Token Mix %/CCost, all available history
python cost-guard.py --sessions 10              # Latest 10 available root sessions
python cost-guard.py --sessions all             # All available root sessions
python cost-guard.py --watch                    # Global Watch; Ctrl+C exits
python cost-guard.py <session-id>               # One session
python cost-guard.py <session-id> --watch       # Watch one session/root tree
python cost-guard.py 2026-08-24                 # One local calendar day
python cost-guard.py 2026-08-01:2026-08-31      # Inclusive local date range
python cost-guard.py --version
python cost-guard.py --help
```

See [Quick start](#quick-start) for launchers. Diagnostics ZIPs go under `diagnostics/`.

Cost Guard uses `config/default-config.jsonc`. Create optional `config/user-config.jsonc` beside it only for overrides.

## Open-source license and Windows download trust

Cost Guard uses **0BSD**: use, modify and redistribute, including commercially, without attribution. See `LICENSE`.

Windows may show SmartScreen warnings for unsigned Internet-downloaded launchers. Cost Guard does not bypass this. After verifying the ZIP's source, you may optionally remove its download mark:

```powershell
Get-ChildItem -Recurse | Unblock-File
```

No signing certificate ships.

## OpenCode V1/V2 source selection

The shipped default is:

```jsonc
{
  "openCode": {
    "source": "auto"
  }
}
```

`auto` selects **one** healthy source: V2 first, otherwise V1; histories are never merged. Force `v1`/`v2` only for troubleshooting or a legacy workflow.

With V2 selected, a metadata-only V1 check may warn of missing/newer legacy sessions. Cost Guard never combines, repairs or writes OpenCode history/migration state.

Reports show `OpenCode not found` only after source selection fails and neither a PATH executable nor standard installation/data evidence exists. Usable V1/V2 sources work without the CLI; offline installations keep source errors. Watch still waits/retries.

## Normal report

`python cost-guard.py` shows `CCost:`, `Token Mix %:` and `Rel CCost:` definitions, models/notices, then `Accounts Overview`. Token Mix % covers up to 100 latest visible prompts with telemetry, including running/interrupted/child work: prompt count, volume (`137.1M`), shares and CCost. No monthly usage, prompt detail or graph is built.

### Model comparison

**Rel CCost applies your Token Mix %** from up to 100 latest completed visible prompts to each model's CCost/M rates; the cheapest is `1.0x`. Running/aborted prompts are excluded. Without a sample, Rel CCost stays blank: a hidden synthetic I/C/W/O 2/96/1/1 mix sorts rows through the same pricing path, never shown as observed usage. Real samples replace it automatically. Multipliers are relative CCost, not predictions of model behavior.

Availability uses V2's settled `/api/model` selectable IDs (V1: `opencode models`). Exact/verified aliases match reference prices; explicit variant rates win and unknown/ambiguous prices stay unknown. Lookup failures warn and show the **pricing catalog, not proven availability**. Unpriced models have no row.

`--all-models` uses the full downloaded catalog and the same sample/table/highlights, without availability lookup or account discovery/quota fetches.

| Column | Meaning |
| --- | --- |
| `Publisher` | Model creator/group when identifiable from metadata. |
| `Model` | Model display name. |
| `Rel CCost` | Token Mix % CCost relative to the least expensive comparable model; promotion markers align left, multipliers right. |
| `Copilot CCost/M tokens I/C/W/O` | Reference CCost per million input/cache-read/cache-write/output tokens; exact rates, `→` separates tiers. |
| `Release date` | Public model release date when confidently available. Recently released models are highlighted/notified. |

New Models lasts seven UTC days after release; report promotion markers/highlights last through validity. Watch promotion notices require a proven start within seven days and never survive expiry; unknown starts are not guessed from release/first fetch. Only notice labels are colored.

## Token Mix % by model: `--token-mix`

Scans all available OpenCode history; the first uncached run can be slow. `Total Token Mix % · <volume> tokens` comes first, recomputed from shown requests. Each historically used, currently selectable model has `Prompts`, `Calls`, aligned Input/Cache/Write/Output shares and CCost, and total `CCost`.

- `Prompts`: unique user prompts where the model contributed usage. One prompt can count on several model rows, so rows do not sum to a prompt total.
- `Calls`: model requests attributed to the model, including tool-loop continuations, subagent and compaction requests. Compare both to judge sample size.
- Deleted or pruned history is not reconstructed; no private ledger exists. Rows never imply which account or subscription served a model.
- If current model availability cannot be established, all historically used models are shown with a warning (fail open).

Interactive progress is transient; redirected output uses stage lines.

## Available sessions: `--sessions N|all`

Shows only a session table and its legend, newest causal-tree activity first, not cost order. `N` is a positive maximum; an oversized limit or `all` shows all available root sessions, including available archived sessions. Descendants belong to their root rather than appearing as duplicate detail targets. No aggregate Total row is shown.

| Column | Meaning |
| --- | --- |
| `Session id` | OpenCode root-session ID. |
| `Name` | Session title. |
| `Model` | Primary model by attributed CCost; trailing `*` means another model also contributed. |
| `CCost` | Reference valuation for the entire available session, across day/month boundaries; not billing. |
| `#` | Relevant visible prompts across the entire session; compactions remain distinct detail events, not user prompts. |

## Session and date detail reports

Passing a session ID shows only that session/root's prompt analysis and explanations. Explicit date/date-range modes use the same table against their selected scope, limited to data still available from OpenCode. Neither fetches model availability or account quotas.

| Column | Meaning |
| --- | --- |
| `Prompt` | Local time, prompt number and preview. Separate `Model:` and `[ABORTED]` timeline rows provide history context. `/compact` is shown as its own event. |
| `CCost` | Reference token valuation of the prompt/event, independent of billing; `?` marks a partial subtotal. |
| `Calls` | Completed causal model requests belonging to the prompt/event. |
| `~Ictx` | Incoming context or `Δctx -> Next Ictx` when the chronological context state is available. |
| `~Ictx CCost` | Incoming-context reference valuation, not billing. |
| `~Extra CCost` | Additional causal usage reference valuation beyond incoming context, not billing. |
| `I/C/W/O %` | Token-category mix, or running-state text while a prompt is still active. |

Known causal splits show **Main / Subagents / Total**; running prompts may show `running - consider ABORT`. `(Next Ictx CCost 0.3–3)` is the next input context's cached–fresh CCost range, not a cache-hit prediction. Threshold markers/indicators share amber `nextIctxWarning`: approaching highlights the marker; exceeded the full explanation.

Moving a session (e.g. to a worktree) keeps its ID and never re-counts history; V2 reads messages by session ID. The non-billable move starts a new context epoch: Next Ictx is N/A until the first request after it sets the new baseline.

A one-shot session report automatically follows an already-running latest prompt until that prompt completes or aborts.

Persisted V2 terminal evidence ends the matching attempt (duration freezes) and keeps failure/cancellation/success distinct; inactivity or disconnection alone proves no end, and usage/cost is unchanged.

## Account quota blocks

Only detected/configured accounts appear. Same-provider accounts retain source-aware identities. Upstream labels distinguish identical provider/plan rows; unknown labels use neutral ordinals, never invented Personal/Work labels.

Aligned 10-cell remaining bars and matching native amounts share a row. Reports align every quota bar and Remaining using one report-wide label column; Watch globally aligns only primary bars, with individual narrow fallback. Native money/units remain in reports; warnings indent and zero/unknown balances hide unless significant.

Copilot `Usage Today` is absent: GitHub's billing usage API requires a classic PAT, not Copilot OAuth, so no substitute is added.

`Remaining: X/day · Y/workday` (formerly Pace) spreads reported included credits over days/workdays until the reported reset, rounded down. Today counts as a day and, when applicable, a `workdayCalendar` workday. No history is needed; extra credits are excluded. Missing balance/reset hides it; organization pools are not personal allocations. Reports use a separate Remaining line and retain units/money/reset.

Positive reported Copilot overage allowances show separately as `Extra credit limit N` (report: `N AI credits`), never an inferred purchased/remaining balance or included Remaining. Paused states and independent billing/balances remain. No extra polling.

Report/vertical Watch resets: <24h → `Reset in Nmin, HH:MM`; 24h–<7d → `Reset in Nh, Weekday HH:MM`; ≥7d → `Reset at YYYY-MM-DD HH:MM`. Elapsed-time tiers, whole units, configured timezone/English weekdays; no negative countdowns.

Copilot Business/Enterprise plan, usage and `hasQuota=false` survive zero, pooled or unusable entitlement; known blocked state shows `⚠  COPILOT PAUSED`, while errors alone never imply blocked.

## Watch

Watch shares report analysis and groups sessions by latest activity (oldest first; session-ID ties). `watchDashboardMaxRows` defaults to 14, is user-configurable, and limits retained/displayed prompts only; active/recent rows remain protected, so it is not a hard maximum. Prompt/compaction order is preserved.

| Column | Meaning |
| --- | --- |
| `Session / prompt` | Session grouping plus prompt/event rows. Running prompts show tool counts (`8× read · 3× other · 2 failed`) and, for a ≥10 s tool/open TODO, `running: bash 34s · TODO 2/4 done · text`. Both subordinate arrows align with `#`; failures stay red. |
| `Model / effort` | Same as report: explicit/request-proven effort, otherwise `(Default)` for a known normal request. No model-family default guesses or `Default -> X`. Compaction shows only its own explicit effort. |
| `CCost` | Current observed prompt/event reference valuation, not billing. |
| `Calls` | Completed causal model requests. |
| `Duration` | Wall-clock prompt duration; running durations continue between source refreshes. |
| `Δctx -> Next Ictx` | Context-state change and next context when available. |

`Token Mix % · N prompts` shows unique prompts, shares and CCost this run, without volume/bar. Startup-running requests, between-poll completions, child work and compactions count; pre-Watch completed history does not. Row eviction/resync/disappearance never removes qualifying run usage. `Watch total CCost` below it sums that run usage: 0 at start, never re-added by rescans or moves.

Any account count uses compact rows when they fit, otherwise individual wrapped blocks. Resets use `Reset@...`; fixed quotas with Remaining omit duplicate compact reset text, retained in reports/narrow fallback:

```text
GitHub Copilot Pro+   Month  ██████████ 100% · 7000/7000 · Remaining: 259/day · 350/workday
OpenAI Plus          5h     ████████░░  82% · Reset@22:49 | Week ██████████  98% · Reset@Sunday 07:59
```

`Watch:` stays last. Interactive startup uses `Cost Guard vX.Y (YYYY-MM-DD) — <Mode>` with progress immediately below, no blank row. Modes include Report, Watch, Diagnostics, Token Mix, All Models, Sessions, Session, Date and Date Range. Transient UI disappears before final reports/Watch dashboards; redirected output remains plain, without animation.

Aborted labels persist after red emphasis expires. Quota errors retain values for five minutes; scheduling gaps/first startup errors allow 60s `STALE / RECONNECTING` recovery with 5/10/20s retries. Auth rejection remains visible.

Interactive full redraws clear screen/scrollback and erase below the status row; countdowns replace only the status line.

V1 Watch uses process-free SQLite gating; V2 events are hints with a five-second cooldown and authoritative resync. `sessionWatchIntervalSeconds: "auto"` adapts refreshes within 5–30 seconds. Quota refresh is independently rate-limited.

## Pricing, quota and network behavior

Pricing/model metadata refreshes by `pricingMaxAgeHours` (default six hours). Expired promotions revert to verified standard rates or are withheld. Failed refresh can reuse a prior successful snapshot.

GitHub Copilot quota uses OpenCode's existing OAuth credential by default. `copilotQuota.authJsonPath` may override the path when a non-standard OpenCode setup requires it. Cost Guard reads credentials only for the request and never stores them in its own cache.

Read-only V2 inventory takes priority over legacy auth; inactive accounts do not change login. Explicit paths stay file-only; invalid credentials are never replaced or sought in other installations. OpenAI/Claude quotas are version-sensitive/fail-soft.

## Configuration

`config/default-config.jsonc` owns defaults, thresholds and colors. Optional `config/user-config.jsonc` recursively overrides defaults and never ships.

Useful settings include:

- `runningPromptWarningCCost`: warn for a running prompt at 1800 CCost by default (0 disables). **Breaking in v78.36:** remove `runningPromptWarningUsd` and `thresholds.watchCostDeltaDisplayUsd` from saved configs; the latter is dead and has no replacement. Obsolete keys fail as unrecognized properties before source/provider/cache work. No aliases, silent migration or automatic config rewrite.

- `openCode.source`: `auto`, `v1` or `v2`.
- `timezone`: local day/timestamp zone. The shipped `Europe/Stockholm` default works without an external tzdata package; other custom IANA zones require host/Python zoneinfo data.
- `workdayCalendar`: `SE` for Swedish weekends/public holidays, or empty for weekends only.
- `copilotQuota.enabled` / `authJsonPath`: optional account lookup controls.
- `openAiQuota.enabled` / `authJsonPath`: fail-soft OpenAI ChatGPT/Codex usage lookup controls.
- `anthropicQuota.enabled`: Anthropic API and Claude CLI account lookup; `authJsonPath` overrides only the API-account inventory.
- `sessionWatchIntervalSeconds`: `"auto"` (default, adaptive 5–30 seconds) or an explicit compatible integer.
- `pricingMaxAgeHours`: pricing/model metadata cache age.
- `thresholds`: running-cost, context, percentile and quota warning thresholds.
- `colorScheme`, `colorSchemes`, `colors`: terminal palette selection and per-role overrides.

`modelComparisonNew`: lime (classic 118) for new names/dates/notice labels. `modelComparisonPromotion`: gold (214) for active rates/Rel CCost/notice labels. `reportDefinitionLabel`/`reportDefinitionValue`: plain Yellow for report definition labels/live values. Light scheme: green 28/ochre 130. Other text is normal; release date stays last.

Invalid configuration fails at startup.

Legacy `monthlyAiCredits` is tolerated but ignored; it is not shipped or displayed.

## Cache and concurrent Cost Guard processes

Runtime acceleration state is created under:

```text
cache/
  cost-guard-cache-v2.sqlite3
```

The cache is disposable, not authoritative history. Stop Cost Guard before deleting `cache/`; the next run rebuilds it. Breaking schemas use a new generation filename, never migration/deletion of an in-use database.

SQLite WAL, short transactions and bounded waits support concurrent report/global/session Watch.

## Diagnostics for environment-specific problems

Use the Diagnostics launcher or run from the package root:

```text
python development/tools/collect_diagnostics.py
```

Creates `diagnostics/cost-guard-diagnostics-YYYYMMDD-HHMMSS.zip`: **Full/local** tests, package validation (including failures), environment/version, source/wire statistics, timings and provider health. `--no-network` skips pricing/quotas; `--skip-validation` is emergency/recursive-only.

Bundles omit prompt text, titles, raw payloads/auth, tokens and account labels/IDs; session IDs are hashed. Account evidence is limited to plan/status, numeric quota shape, parser classification and HTTP status.

## Release status

**v80.1** refreshes documentation and static images; runtime behavior is unchanged. v80.0 is the Python 3.11+ public baseline; V1/V2 share one analysis core. Claude quotas remain experimental; physical restart/sleep and visual terminal behavior need separate live evidence.

Quick is the hosted-AI gate; Full adds package/release/performance checks; Diagnostics covers the affected workstation.

## Development

`AGENTS.md` routes maintainers to self-contained architecture, FR, test and release guidance under `development/`.

From the package root:

```text
python development/tools/run_tests.py --suite quick      # default; bounded hosted-AI gate
python development/tools/run_tests.py --profile runtime   # focused example
python development/tools/validate_package.py --working-tree
python development/tools/run_tests.py --suite full       # unrestricted/local tier
python development/tools/collect_diagnostics.py         # Full + validator + environment bundle
python development/tools/build_release.py               # Quick-gated package build by default
python development/tools/build_release.py --quick-already-run  # after same-tree Quick in a tight harness
python development/tools/build_release.py --full-verification  # unrestricted local build
```

The builder validates inventory/architecture and source/archive bytes, then repeats its test tier and validation from a clean extraction. Quick is default; final releases require Full/local evidence. ZIPs live under git-ignored `releases/`; runtime/cache/diagnostic/user-config/checkpoint/credential/bytecode/Git debris never ships.
