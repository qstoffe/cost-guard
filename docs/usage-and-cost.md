# Usage and cost reference

Detailed counting and display contracts for Cost Guard. Start with the [README](../README.md#core-concepts) for the product introduction and core concepts.

## What Cost Guard counts

Usage includes all canonical provider IDs. **CCost** values observed tokens using replaceable GitHub reference rates, independent of subscription/billing. Unknown prices yield partial/unknown CCost, never billed-cost substitution. **Billed** needs reported spend or explicit subscription/zero-billing evidence; otherwise `N/A`. Legacy monetary fallback is not actual billing. A quota credential does **not** prove historical request-account attribution.

**CCost scale:** 1 CCost = 1 GitHub Copilot AI-credit-equivalent of reference value; currently $1 of Copilot reference value = 100 CCost. It is not verified billing or credits deducted from a Copilot account. OpenAI/Anthropic subscription usage can have positive CCost with Billed $0.00. Actual billing, balances, budgets and native quota-to-money information remain monetary.

**Numeric display:** CCost is naked (`437`, `?437`), including Token Mix % parentheses. Exact zero is `0`; positive amounts below 0.1 show `<0.1`; 0.1–<1 use one upward-rounded decimal; amounts ≥1 round upward to whole CCost. Internal Decimal analysis is never display-rounded. Rates/limits preserve source precision without unnecessary zeros. Used AI credits round upward; Remaining and Remaining/day/workday round downward, retaining tenths below 1 (`<0.1` for smaller positives). No quantity uses thousands separators; intentional K/M/B abbreviations remain.

Successful reference/current-price fallback is Diagnostics-only. Missing reference pricing still warns of incomplete CCost, even when actual billing is known.

Date totals de-duplicate exact fork-cloned requests; session views retain available history. Child/subagent work and eligible synthetic continuations belong to their initiating prompt. Model work that OpenCode resumes after a background job (for example a backgrounded shell) ends stays on the prompt that was running; waiting adds Duration only, never Calls or CCost, and native job IDs are never shown. Only explicit completion/failure/cancellation notices or the service no longer listing the job end that wait. Completed `/compact` remains separate, including native V2 checkpoints without billable summaries.

Deleted OpenCode sessions leave reports and Relative CCost samples; caches keep no ledger.

## Model comparison

Normal reports show Publisher, Model, Relative CCost and Release date. `--all-models` retains the full GitHub catalog and adds `GitHub USD/M I/C/W/O`: original USD per million input/cache-read/cache-write/output tokens, with exact numeric precision, all tiers and current promotions. `→` separates exact tiers; context boundaries remain visible even without an observed comparison mix. `-` means a category has no published rate. This reference column does not change CCost, Watch or quotas.

Relative CCost applies the existing latest-100 completed-prompt I/C/W/O token mix separately to every published tier. All tiers divide by the same cheapest positive comparable **base-tier** price, never a separate long-context reference. Cache-write fallback remains the existing input-rate rule only when the write rate is missing; published zero is zero. No input-only shortcut or arbitrary doubling is used.

For example, `8.0x → 16.0x (>200K)` (illustrative) means eight times the reference at base context and sixteen times above 200000 input tokens. `≥` is inclusive; exact K/M boundaries are never rounded. Additional levels extend the chain. Promotion markers, each multiplier, arrows and boundaries occupy dynamically aligned internal fields; colors are applied after width measurement. Numeric cells remain intact on narrow terminals (the table can exceed terminal width rather than lose prices).

Both modes use one deterministic sorter: descending full-precision base price; for exact ties, descending next-tier price then ascending actual price-increase boundary, repeating for later tiers; alphabetical name last. A missing extra tier means unchanged price, an unknown rate stays unknown, and equal-price tiers introduce no artificial boundary ordering. Multipliers show exactly one decimal; only presentation rounds.

Without eligible token data, Relative CCost stays blank and the existing hidden synthetic 2/96/1/1 mix drives the same sorter. It is never reported as observed Token Mix %. Completed-prompt eligibility, availability filtering in normal reports, full-catalog selection in `--all-models`, promotions, release dates and New Models notices remain unchanged.

Recognized stable GPT/Claude/Gemini/Grok versions are faded when a numerically newer version of the same manufacturer, family and meaningful variant appears in the current table. Named tiers/families are matched generically, so GPT-6 Luna fades GPT-5.6 Luna and Claude Fable 5.1 fades Claude Fable 5, while GPT-5.6 Terra stays normal without a newer Terra. For xAI's standard Grok names, showing Grok 4.7 fades Grok 4.5 and 4.6, not 4.7. This means only **superseded in this comparison**, not officially deprecated or better. Unknown, preview, experimental and fast-mode names remain untouched. Availability-filtered normal reports and full-catalog reports can intentionally classify the same model differently.

The presentation modifier attenuates each cell's original color independently (including gold promotions and green recent-release segments), adapting to the built-in dark/light themes and resolved custom colors. Borders/headers are unchanged. No rows, rates, multipliers, token mix, ordering, promotion/New Models semantics or CCost are changed; plain output is byte-for-byte equivalent in information and geometry.

## Account acquisition

Local read-only credential discovery shares OpenCode auth/SQLite reads, preserves per-integration V2 priority, legacy fallback and explicit file-only paths, and never copies credentials into Cost Guard storage. Other supported identities such as Claude CLI remain separate. Presence is a candidate, never proof of a plan or entitlement.

At most four provider jobs run concurrently, including multiple-account work within a provider, and overlap normal-report analysis. The report's final remaining wait is at most 15 seconds; a provider attempt expires after 45 seconds in Watch. Existing transport deadlines remain. Failures/timeouts keep unknown/partial/error semantics, not false zero capacity; unexpected provider defects use sanitized RuntimeErrors logging.

Watch's first local view does not wait for HTTPS. Its main-thread one-second status wake applies individual completions; workers never render. Normal one-minute refresh rechecks inventory only as needed from source revisions (including SQLite WAL); additions/removals are reflected without restart. Identity-aware stale retention, bounded resume retries and refresh cadence remain. Expired/old-generation results are ignored; a timed-out request keeps its bounded worker slot until it actually returns, preventing retry/thread growth. Shutdown discards pending output without waiting for in-flight HTTP. Diagnostics contains only allowlisted acquisition timings/counts, not credentials.

Three independent concepts:

- **Usage:** observed input/cache/output/reasoning token activity and requests.
- **CCost / Billed:** independent reference valuation and actual monetary spend. Included subscription work can have positive CCost and zero Billed.
- **Quota / limits:** account-native windows, credits, budgets and availability; provider identity is not account identity.

Reports retain Copilot's native $0.01/AI-credit conversion; Watch omits that conversion/unit. Percentage-only quotas never imply dollar capacity.

## Symbols and token categories

- `I` = **uncached input**, `C` = **cache read**, `W` = **cache write**, `O` = **output** (including separately reported reasoning).
- Token Mix % divides raw counts (`Input`/`Cache`/`Write`/`Output` = I/C/W/O). Largest-remainder rounding selects tenths summing to exactly 100%; trailing `.0` is omitted. Tiny shares may round to `0%`. Incomplete telemetry or zero totals show `--`; no samples show `no token data yet`. Absent fields are not zero.
- Category CCost uses each request's model/tier; the four unrounded amounts reconcile with the same requests' CCost. Rounded cells need not sum exactly; `0.4% (24)` is a small but expensive share.
- `~` marks approximate diagnostics (`~Ictx`, `~Ictx CCost`, `~Extra CCost`), never pricing provenance or Relative CCost.
- `?` before a CCost cell means only the priced subset is shown. Completely unpriced workloads show `N/A`.
- `N/A` means unavailable.
- A trailing `*` on a model means linked child/subagent work used an additional model.
- Numbered `*1`, `*2`, ... markers on a session header point to matching context-warning footnotes.
- `Δctx -> Next Ictx` describes change in the session's effective next-input context state, not a billed-token total.
