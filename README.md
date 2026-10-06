# Cost Guard CLI

Cost Guard compares model prices, account quotas and token mix, with session/context analysis and reference valuation (**CCost**). **v80.0 is the Python 3.11+ public baseline**; V1/V2 share one analysis core.

Session detail is opt-in, not a billing ledger.

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

1. Extract the ZIP to a folder.
2. Make sure `python --version` (or the Windows `py` launcher) resolves to Python 3.11+.
3. Run Cost Guard from the extracted folder:

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

Launchers live under `windows/` (`.cmd`) and under `macos/` (`.command`):

- `Cost Guard`: normal report, leaving the console open.
- `Cost Guard Watch.cmd` / `Cost Guard Watch.command`: global Watch; Ctrl+C exits through Python.
- `Cost Guard Diagnostics.cmd` / `Cost Guard Diagnostics.command`: privacy-safe ZIP under `diagnostics/`, keeping its path visible.

The `.command` files ship executable. Use Finder's **Open** for quarantine; Gatekeeper is never bypassed.

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

## What Cost Guard counts

Usage includes all canonical provider IDs. **CCost** values observed tokens using replaceable GitHub reference rates, independent of subscription/billing. Unknown prices yield partial/unknown CCost, never billed-cost substitution. **Billed** needs reported spend or explicit subscription/zero-billing evidence; otherwise `N/A`. Legacy monetary fallback is not actual billing. A quota credential does **not** prove historical request-account attribution.

**CCost scale:** 1 CCost = 1 GitHub Copilot AI-credit-equivalent of reference value; currently $1 of Copilot reference value = 100 CCost. It is not verified billing or credits deducted from a Copilot account. OpenAI/Anthropic subscription usage can have positive CCost with Billed $0.00. Actual billing, balances, budgets and native quota-to-money information remain monetary.

**Numeric display:** CCost is naked (`437`, `?437`), including Token Mix % parentheses. Exact zero is `0`; positive amounts below 0.1 show `<0.1`; 0.1–<1 use one upward-rounded decimal; amounts ≥1 round upward to whole CCost. Internal Decimal analysis is never display-rounded. Rates/limits preserve source precision without unnecessary zeros. Used AI credits round upward; Remaining and Remaining/day/workday round downward, retaining tenths below 1 (`<0.1` for smaller positives). No quantity uses thousands separators; intentional K/M/B abbreviations remain.

Successful reference/current-price fallback is Diagnostics-only. Missing reference pricing still warns of incomplete CCost, even when actual billing is known.

Date totals de-duplicate exact fork-cloned requests; session views retain available history. Child/subagent work and eligible synthetic continuations belong to their initiating prompt. Completed `/compact` remains separate, including native V2 checkpoints without billable summaries.

Deleted OpenCode sessions leave reports and Rel CCost samples; caches keep no ledger.

Three independent concepts:

- **Usage:** observed input/cache/output/reasoning token activity and requests.
- **CCost / Billed:** independent reference valuation and actual monetary spend. Included subscription work can have positive CCost and zero Billed.
- **Quota / limits:** account-native windows, credits, budgets and availability; provider identity is not account identity.

Reports retain Copilot's native $0.01/AI-credit conversion; Watch omits that conversion/unit. Percentage-only quotas never imply dollar capacity.

## Symbols and token categories

- `I` = **uncached input**, `C` = **cache read**, `W` = **cache write**, `O` = **output** (including separately reported reasoning).
- Token Mix % divides raw counts (`Input`/`Cache`/`Write`/`Output` = I/C/W/O). Largest-remainder rounding selects tenths summing to exactly 100%; trailing `.0` is omitted. Tiny shares may round to `0%`. Incomplete telemetry or zero totals show `--`; no samples show `no token data yet`. Absent fields are not zero.
- Category CCost uses each request's model/tier; the four unrounded amounts reconcile with the same requests' CCost. Rounded cells need not sum exactly; `0.4% (24)` is a small but expensive share.
- `~` marks approximate diagnostics (`~Ictx`, `~Ictx CCost`, `~Extra CCost`), never pricing provenance or Rel CCost.
- `?` before a CCost cell means only the priced subset is shown. Completely unpriced workloads show `N/A`.
- `N/A` means unavailable.
- A trailing `*` on a model means linked child/subagent work used an additional model.
- Numbered `*1`, `*2`, ... markers on a session header point to matching context-warning footnotes.
- `Δctx -> Next Ictx` describes change in the session's effective next-input context state, not a billed-token total.

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

## Release status

v80.0 establishes the clean public-repository baseline, retaining current CCost, quotas, Token Mix and Watch behavior. Claude quotas remain experimental; physical restart/sleep and visual terminal behavior need separate live evidence.

Quick is the hosted-AI gate; Full adds package/release/performance checks; Diagnostics covers the affected workstation.

## Diagnostics for environment-specific problems

Use the Diagnostics launcher or run from the package root:

```text
python development/tools/collect_diagnostics.py
```

Creates `diagnostics/cost-guard-diagnostics-YYYYMMDD-HHMMSS.zip`: **Full/local** tests, package validation (including failures), environment/version, source/wire statistics, timings and provider health. `--no-network` skips pricing/quotas; `--skip-validation` is emergency/recursive-only.

Bundles omit prompt text, titles, raw payloads/auth, tokens and account labels/IDs; session IDs are hashed. Account evidence is limited to plan/status, numeric quota shape, parser classification and HTTP status.

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
