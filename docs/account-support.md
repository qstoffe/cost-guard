# Account support and native capacity

Cost Guard shows only detected/configured accounts. Same-provider accounts retain full source-aware identities; provider ID alone is not an account. Upstream labels distinguish identical provider/plan rows; unknown labels use neutral ordinals, never invented Personal/Work labels. A failing credential does not hide a healthy account for the same provider.

## Shared presentation

Reports and Watch sort credit/balance/budget accounts before usage-limit accounts, then by provider/plan/account name and stable source-aware identity. Adapters supply the capacity class even when quotas are unavailable; remaining capacity, percentages, status and refresh timing never decide the order.

Aligned 10-cell **Used** bars, percentages and Used/Total native amounts share a row. 100% used means exhausted; 0% used means unused. Native money equivalents use the same orientation. Provider-confirmed Unlimited shows native Used when known, without a percentage, finite denominator or Remaining pace. Reports align every quota bar and Remaining using one report-wide label column; Watch globally aligns only primary bars, with individual narrow fallback. Native money/units, reset, status and warnings remain.

Bars represent genuine provider-reported capacity: a real denominator or an explicitly reported percentage, never a fabricated allocation. Balance/informational spend without capacity stays textual. Native currencies are not added or converted; balances/spend are not CCost or historical usage. A current credential never establishes historical request-account attribution. There are no provider-specific Report/Watch renderer branches.

Report/vertical Watch resets: <24h → `Reset in Nmin, HH:MM`; 24h–<7d → `Reset in Nh, Weekday HH:MM`; ≥7d → `Reset at YYYY-MM-DD HH:MM`. Elapsed-time tiers use whole units, configured timezone/English weekdays and no negative countdowns. Compact Watch uses `Reset@...` and the same underlying components.

Watch keeps an account's label beside its compact quotas whenever possible. If the whole row is too wide, whole `|` components move to continuation lines indented beneath the first quota with aligned bars; only a component that still cannot fit wraps by itself. Genuinely narrow terminals keep the verbose block.

Account-level `BLOCKED` belongs to the account, not to every window. When a current account-scoped window is known to be exactly 0% remaining, its bar and reset already explain the restriction, so no `BLOCKED` text appears. Otherwise, for example when the remaining quota is positive, merely rounds to 0%, is unknown, expired or not started, exactly one account-level `BLOCKED` remains. A window-specific block on an otherwise available account keeps its own indicator.

## GitHub Copilot

Copilot preserves provider plan/status/usage when entitlement is zero, pooled or unusable. Business/Enterprise `hasQuota=false` survives degraded denominators; a known blocked state shows `⚠  COPILOT PAUSED`, while errors alone never imply blocked. Only explicit native unlimited state establishes unlimited capacity.

`Remaining: X/day · Y/workday` (formerly Pace) spreads reported included credits over days/workdays until the reported reset, rounded down. Today counts as a day and, when applicable, a `workdayCalendar` workday. No history is needed; extra credits are excluded. Missing balance/reset hides it; organization pools are not personal allocations. Reports use a separate Remaining line and retain units/money/reset.

Positive reported overage allowances show separately as `Extra credit limit N` (report: `N AI credits`), never an inferred purchased/remaining balance or included Remaining. Paused states and independent billing/balances remain, without extra polling. Copilot `Usage Today` is absent: GitHub's billing usage API requires a classic PAT, not Copilot OAuth, so no substitute is added.

## OpenAI and Anthropic / Claude Code

OpenAI's fail-soft subscription reader normalizes native rolling/model quota windows and extra credits independently of configured API accounts. Anthropic API accounts are separate from optional Claude Code CLI-owned subscriptions. No current login attributes history; credentials are never refreshed/written by Cost Guard. See [Claude integration and limits](../development/architecture/modules/claude-code.md).

OpenAI replacement uses the current authoritative inventory: removed identities disappear, old in-flight results cannot restore them, and proven OAuth aliases prefer canonical V2 records. A canonical V2 OpenAI record suppresses legacy `codex`/`openai-codex` fallback, even when unusable; distinct configured identities stay separate. Failed lookups clear old OpenAI capacity; unknown plans do not inherit a prior tier. Safe returned plan identifiers, including new names, retain native windows without inferring a price or entitlement. HTTP 401 means the quota request was rejected, not that model sign-in failed; 403 means quota-endpoint access was denied, and 429 means lookup throttling. None establishes tier support. Cost Guard never refreshes auth or retries another identity to make quota succeed.

`chatgpt-browser` / `chatgpt-headless` and historical methodless Codex OAuth storage use the maintained read-only WHAM quota surface, with an account header only when the credential supplies an identity. `chatgpt-token-sharing` instead authorizes the OpenAI API resource. Its method or token-sharing scopes (including migrated browser metadata) prevent WHAM requests. Unknown OAuth methods also fail closed. These accounts remain configured, but show **quota unavailable for this sign-in method**, not a reconnect instruction or invented quota/plan. This does not diagnose or change model authentication.

For identified token sharing, report and Watch name **Codex browser (legacy)** (`chatgpt-browser`) and **Codex device code (legacy)** (`chatgpt-headless`) as currently compatible options to try in OpenCode for quota lookup. Availability is not guaranteed. **Sign in with ChatGPT** (token sharing) and API-key sign-in do not currently provide Cost Guard with Codex subscription quota; this says nothing about API billing/usage APIs or successful model requests. Cost Guard does not switch accounts, refresh tokens or initiate sign-in. Unknown methods and actual legacy rejection/expiry/access errors retain their separate messages.

On the affected Windows OpenCode 2.1.4 installation (2026-10-25), safe local inspection matched the active connection to the current unexpired token-sharing record and API provider route. The installed OpenAPI schema exposed no usage/limits route; no compatible supported read-only quota source was established. Real token-sharing quota values therefore remain unavailable. Headless report and Watch acquisition/rendering agreed without making an incompatible network request. This is not a successful authenticated quota retrieval or proof of the upstream server's precise 401 cause.

## OpenRouter

The authenticated key's current UTC Day/Week/Month spend is shown in native USD. A reported key limit and authoritative consumption produce a Used-oriented bar labelled Day, Week, Month or non-resetting Limit. The limit's period is not a reset timestamp, so no reset instant is invented.

No limit means textual spend only. No organization-wide usage, management credential, paid plan or BYOK aggregation is inferred. All-time/monthly spend is not substituted for key-limit capacity.

## DeepSeek

Provider-reported total, granted and topped-up remaining balances retain their native USD/CNY currencies separately. There is no original allocation/budget denominator, so no percentage/bar, FX conversion or inferred deposit history. Provider availability/status is retained without treating balance parts as historical deposits.

## MiniMax Token Plan

`minimax-coding-plan` / `minimax-cn-coding-plan` subscription credentials can expose native 5h/Week windows, resets and count/percentage variants. Generic `minimax` / `minimax-cn` accounts do not prove subscription entitlement. Shared/general buckets avoid equivalent repeated rows; independent limits stay separate and bucket labels do not invent request-model IDs.

Native counts/percentages and absolute/relative resets are normalized by a dedicated first-class adapter. Unknown/conflicting response forms remain partial/unavailable instead of guessed quota; authentication rejections and transient backend failures retain existing Watch semantics. API-key presence alone does not establish a plan/tier.

## Credentials, refresh and troubleshooting

Read-only V2 credential inventory wins per integration; inactive configured accounts can remain visible. Legacy auth fallback follows existing rules; explicit `authJsonPath` stays file-only. OpenRouter/DeepSeek/MiniMax use maintained fixed read-only Bearer HTTPS GET endpoints, not arbitrary user-configurable URLs, headers, cookies, scripts or OAuth refresh.

Account discovery shares each local credential source across providers, caching only an in-memory revision view; missing providers trigger no network/progress check. Multiple accounts and Claude CLI-owned identities remain supported, without inferring subscription entitlement from credentials or model visibility.

Four bounded provider workers overlap normal-report analysis (45-second attempt deadline; at most 15 seconds of final remaining wait). Watch instead reserves at most one worker per configured adapter (seven in the standard composition), plus one account scheduler. A timed-out call keeps its lane until it really returns: no overflow/replacement threads or overlapping calls for an adapter. Other providers keep their capacity. Removed/changed credentials invalidate old work before publication. Shutdown signals the scheduler and discards pending results; in-flight HTTP retains its native deadline and existing Claude private-helper cleanup, never a shared-service stop.

`openrouterQuota`, `deepseekQuota` and `minimaxQuota` expose only `enabled` / `authJsonPath`. Existing Copilot/OpenAI/Anthropic controls are unchanged. Account refresh is independent of source activity; redraws do not trigger provider requests. Existing stale retention, bounded recovery retries and isolated auth failures apply per account.

Diagnostics reports sanitized discovery/category, request/HTTP/schema classification, component categories and ignored/malformed data, never keys, headers, raw responses or account labels/locators. New providers can be tested with synthetic documented responses without personal accounts; a passing fixture is not authenticated live-account evidence. See [maintained HTTP account developer contracts](../development/architecture/modules/simple-http-accounts.md) for endpoints, response evidence, security limits and adding providers.

## Watch freshness budget

The shared scheduler uses monotonic, start-anchored 30-second healthy deadlines, not batch completion plus a minute. It runs independently of source hydration, redraws and session events, checks cached local credential revisions every five seconds, and never catches up with request bursts. Scheduling is per adapter, not a provider-specific workaround; adapters serialize their native multi-account acquisition. Credential-backed recovery pins only failed records; healthy neighbors still receive periodic full refreshes.

**Healthy objective: newly available upstream values appear within 60 seconds.** Defined normal conditions are total adapter acquisition (including probe and all its accounts) ≤20 seconds, scheduler dispatch overhead ≤1 second and main-thread publication plus terminal rendering ≤2 seconds. The conservative budget is 30 + 20 + 1 + 2 = 53 seconds, including a value changing immediately after a request sampled the old value. Tests simulate 0/1/10/20-second providers and actual idle/active Watch rendering. This is not an upstream update SLA: a successful response may contain unchanged or delayed upstream values, whose actual upstream freshness is unknown unless the provider supplies it. Long source operations or a suspended/blocked terminal can delay rendering, but cannot pause ongoing account acquisition; publication delay is measured rather than misreported as a new observation.

Watch attempts expire after 20 seconds. Network/transport/timeouts and retryable HTTP failures receive at most three recovery attempts after 5/10/20 seconds from completion, including after previous success; sustained failure then checks every 60 seconds. Authentication, unsupported capability, changed formats, provenance rejection and software failures receive no fast retries. A successful recovery restores normal cadence. A stuck lane is never retried concurrently. No new endpoints, credentials, token renewal or synthetic usage are involved.

Only actual successful responses advance observation time, even when percentages are unchanged. Publication and local cached reprojection do not. Retained values are marked stale immediately on transient failure or when the observation is over 60 seconds old; capacity is removed after five minutes, without waiting for another result and without extending retention on resume. Existing compact stale/reconnecting presentation remains; normal fresh rows gain no clutter.

`cache/state/watch-account-refresh.json` contains the latest bounded, numeric/allowlisted evidence, updated at most every five seconds and read into Diagnostics as `watch_account_refresh`. Concurrent Watches are last-writer-wins, not merged history; `recorded_at_ms` identifies the snapshot's age and a random `quota_observations.run_id` identifies its writer. Provider ordinals carry attempt/completion/successful observation/publication ages, acquisition and worker wait, effective intervals, scheduling delay, retry/timeout/failure counts and outcome. Display age/state and observation age distinguish stale rendering from failed acquisition; upstream freshness remains `unknown`. No identities, credentials, endpoints, raw responses or account labels are recorded. The file is disposable and excluded from source distribution.

`quota_observations` retains 64 observations for each of at most 64 run-local account/window series: 31.5 minutes at healthy 30-second polling. Each history entry carries acquisition-completion UTC milliseconds, remaining percentage (null when unknown), reset UTC milliseconds, acquisition duration/outcome, `value_changed` (percentage) and `reset_changed` (metadata). Provider IDs are allowlisted; account/window identifiers are run-local ordinals, with window duration for interpretation. Identity/credential revisions and window definitions partition series without exporting them. Oldest series are evicted under exceptional identity/window churn; extra error retries can shorten the covered time. Restart starts a new baseline, not reconstructed continuity.

`last_successful_retrieval_ms` advances on unchanged success. `last_value_change_ms` and its age advance only on a comparable remaining-percentage transition; initial observations and failed/unknown values have no change flag. `observed_unchanged_seconds` starts at the first known baseline and is not proof the upstream value stayed unchanged between polls. Ages are evaluated at `captured_at_ms`, not at a later ZIP read; an old file never proves Watch is still running. Reset changes are recorded separately, even with identical percentages: millisecond reset jitter must not reset the unchanged-percentage clock. A reset-associated percentage refill is still a value change. `last_watch_publication_ms` records consumption of that successful observation by Watch, not rendering. Missing samples/failures remain explicit; no value-change age triggers retries or stale state. Independent Diagnostics acquisition is under `report.account_acquisition.quota_observations` with a different run ID and no Watch-publication timestamp. The ZIP's text summary explains the distinction; normal Watch gains no extra labels.
