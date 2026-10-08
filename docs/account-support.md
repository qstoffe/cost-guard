# Account support and native capacity

Cost Guard shows only detected/configured accounts. Same-provider accounts retain full source-aware identities; provider ID alone is not an account. Upstream labels distinguish identical provider/plan rows; unknown labels use neutral ordinals, never invented Personal/Work labels. A failing credential does not hide a healthy account for the same provider.

## Shared presentation

Aligned 10-cell remaining bars and matching native amounts share a row. Reports align every quota bar and Remaining using one report-wide label column; Watch globally aligns only primary bars, with individual narrow fallback. Variable 5h/Day/Week/Month/Limit labels use the same formatter. Native money/units remain in reports; warnings indent and zero/unknown balances hide unless significant.

Bars represent genuine provider-reported capacity: a real denominator or an explicitly reported percentage, never a fabricated allocation. Balance/informational spend without capacity stays textual. Native currencies are not added or converted; balances/spend are not CCost or historical usage. A current credential never establishes historical request-account attribution. There are no provider-specific Report/Watch renderer branches.

Report/vertical Watch resets: <24h → `Reset in Nmin, HH:MM`; 24h–<7d → `Reset in Nh, Weekday HH:MM`; ≥7d → `Reset at YYYY-MM-DD HH:MM`. Elapsed-time tiers use whole units, configured timezone/English weekdays and no negative countdowns. Compact Watch uses `Reset@...` and the same underlying components.

Watch keeps an account's label beside its compact quotas whenever possible. If the whole row is too wide, whole `|` components move to continuation lines indented beneath the first quota with aligned bars; only a component that still cannot fit wraps by itself. Genuinely narrow terminals keep the verbose block.

Account-level `BLOCKED` belongs to the account, not to every window. When a current account-scoped window is known to be exactly 0% remaining, its bar and reset already explain the restriction, so no `BLOCKED` text appears. Otherwise, for example when the remaining quota is positive, merely rounds to 0%, is unknown, expired or not started, exactly one account-level `BLOCKED` remains. A window-specific block on an otherwise available account keeps its own indicator.

## GitHub Copilot

Copilot preserves provider plan/status/usage when entitlement is zero, pooled or unusable. Business/Enterprise `hasQuota=false` survives degraded denominators; a known blocked state shows `⚠  COPILOT PAUSED`, while errors alone never imply blocked. Only explicit native unlimited state establishes unlimited capacity.

`Remaining: X/day · Y/workday` (formerly Pace) spreads reported included credits over days/workdays until the reported reset, rounded down. Today counts as a day and, when applicable, a `workdayCalendar` workday. No history is needed; extra credits are excluded. Missing balance/reset hides it; organization pools are not personal allocations. Reports use a separate Remaining line and retain units/money/reset.

Positive reported overage allowances show separately as `Extra credit limit N` (report: `N AI credits`), never an inferred purchased/remaining balance or included Remaining. Paused states and independent billing/balances remain, without extra polling. Copilot `Usage Today` is absent: GitHub's billing usage API requires a classic PAT, not Copilot OAuth, so no substitute is added.

## OpenAI and Anthropic / Claude Code

OpenAI's fail-soft subscription reader normalizes native rolling/model quota windows and extra credits independently of configured API accounts. Anthropic API accounts are separate from optional Claude Code CLI-owned subscriptions. No current login attributes history; credentials are never refreshed/written by Cost Guard. See [Claude integration and limits](../development/claude-code.md).

## OpenRouter

The authenticated key's current UTC Day/Week/Month spend is shown in native USD. A reported key limit and authoritative remaining limit produce a normal remaining-capacity bar labelled Day, Week, Month or non-resetting Limit. The limit's period is not a reset timestamp, so no reset instant is invented.

No limit means textual spend only. No organization-wide usage, management credential, paid plan or BYOK aggregation is inferred. All-time/monthly spend is not substituted for key-limit capacity.

## DeepSeek

Provider-reported total, granted and topped-up remaining balances retain their native USD/CNY currencies separately. There is no original allocation/budget denominator, so no percentage/bar, FX conversion or inferred deposit history. Provider availability/status is retained without treating balance parts as historical deposits.

## MiniMax Token Plan

`minimax-coding-plan` / `minimax-cn-coding-plan` subscription credentials can expose native 5h/Week windows, resets and count/percentage variants. Generic `minimax` / `minimax-cn` accounts do not prove subscription entitlement. Shared/general buckets avoid equivalent repeated rows; independent limits stay separate and bucket labels do not invent request-model IDs.

Native counts/percentages and absolute/relative resets are normalized by a dedicated first-class adapter. Unknown/conflicting response forms remain partial/unavailable instead of guessed quota; authentication rejections and transient backend failures retain existing Watch semantics. API-key presence alone does not establish a plan/tier.

## Credentials, refresh and troubleshooting

Read-only V2 credential inventory wins per integration; inactive configured accounts can remain visible. Legacy auth fallback follows existing rules; explicit `authJsonPath` stays file-only. OpenRouter/DeepSeek/MiniMax use maintained fixed read-only Bearer HTTPS GET endpoints, not arbitrary user-configurable URLs, headers, cookies, scripts or OAuth refresh.

Account discovery shares each local credential source across providers, caching only an in-memory revision view; missing providers trigger no network/progress check. Multiple accounts and Claude CLI-owned identities remain supported, without inferring subscription entitlement from credentials or model visibility.

Four bounded provider workers overlap normal-report analysis (at most 15 seconds of final remaining wait). Watch's first view never waits for quotas: results appear independently on its main thread. Attempts expire after 45 seconds, with existing transport deadlines and identity-aware stale/recovery rules; late generations cannot overwrite current state. The normal refresh cadence checks local source revisions to discover added/removed accounts without restart or reparsing unchanged files. Workers never render, persist credentials or keep the process alive on exit.

`openrouterQuota`, `deepseekQuota` and `minimaxQuota` expose only `enabled` / `authJsonPath`. Existing Copilot/OpenAI/Anthropic controls are unchanged. Account refresh is independent of source activity; redraws do not trigger provider requests. Existing stale retention, bounded recovery retries and isolated auth failures apply per account.

Diagnostics reports sanitized discovery/category, request/HTTP/schema classification, component categories and ignored/malformed data, never keys, headers, raw responses or account labels/locators. New providers can be tested with synthetic documented responses without personal accounts; a passing fixture is not authenticated live-account evidence. See [maintained HTTP account developer contracts](../development/simple-http-accounts.md) for endpoints, response evidence, security limits and adding providers.
