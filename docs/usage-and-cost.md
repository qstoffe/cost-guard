# Usage and cost reference

Detailed counting and display contracts for Cost Guard. Start with the [README](../README.md#core-concepts) for the product introduction and core concepts.

## What Cost Guard counts

Usage includes all canonical provider IDs. **CCost** values observed tokens using replaceable GitHub reference rates, independent of subscription/billing. Unknown prices yield partial/unknown CCost, never billed-cost substitution. **Billed** needs reported spend or explicit subscription/zero-billing evidence; otherwise `N/A`. Legacy monetary fallback is not actual billing. A quota credential does **not** prove historical request-account attribution.

**CCost scale:** 1 CCost = 1 GitHub Copilot AI-credit-equivalent of reference value; currently $1 of Copilot reference value = 100 CCost. It is not verified billing or credits deducted from a Copilot account. OpenAI/Anthropic subscription usage can have positive CCost with Billed $0.00. Actual billing, balances, budgets and native quota-to-money information remain monetary.

**Numeric display:** CCost is naked (`437`, `?437`), including Token Mix % parentheses. Exact zero is `0`; positive amounts below 0.1 show `<0.1`; 0.1–<1 use one upward-rounded decimal; amounts ≥1 round upward to whole CCost. Internal Decimal analysis is never display-rounded. Rates/limits preserve source precision without unnecessary zeros. Used AI credits round upward; Remaining and Remaining/day/workday round downward, retaining tenths below 1 (`<0.1` for smaller positives). No quantity uses thousands separators; intentional K/M/B abbreviations remain.

Successful reference/current-price fallback is Diagnostics-only. Missing reference pricing still warns of incomplete CCost, even when actual billing is known.

Date totals de-duplicate exact fork-cloned requests; session views retain available history. Child/subagent work and eligible synthetic continuations belong to their initiating prompt. Model work that OpenCode resumes after a background job (for example a backgrounded shell) ends stays on the prompt that was running; waiting adds Duration only, never Calls or CCost, and native job IDs are never shown. Only explicit completion/failure/cancellation notices or the service no longer listing the job end that wait. Completed `/compact` remains separate, including native V2 checkpoints without billable summaries.

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
