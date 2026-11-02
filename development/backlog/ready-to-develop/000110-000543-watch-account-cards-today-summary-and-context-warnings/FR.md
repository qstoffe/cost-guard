# FR 000543 — Refine Web Watch account cards, add all-day totals and move context price warnings into session cards

## Owner goal, dependency and scope

Finish the Watch page's account/cost presentation after **FR000542**: comparable subscription cards with aligned primary metrics; one full-width **Total Today** card summarizing all of today's activity; and contextual price-tier warnings at the bottom of the relevant active/historical session card.

The owner requested this complementary FR on 2026-11-02 while FR000542 was already being implemented (PR #118, branch `fr-000542`). **Implement on top of the delivered FR000542 result. Do not rewrite, replace or expand that in-progress task.** Permanent identity: **000543**. Queue priority: **000110**, immediately after FR000542's current 000100 priority.

This FR intentionally refines two decisions in FR000542: its minimal account cleanup becomes the structured account layout below, and its omission of Watch-wide daily summaries is replaced by exactly one deliberately scoped Total Today card above the accounts. It also specifies the location of context warnings that FR000542 required preserving but did not place. Preserve the unframed active/history cards, five-session/five-prompt policy, session totals, lifecycle, settings and progressive loading established there.

**Mini Watch / Document Picture-in-Picture is a separate brainstorming track and is not implemented by this FR.** No floating-window toggle, notification toasts, automatic minimize behavior or quota-notification feature is part of this request.

## Inspected baseline and reusable behavior

Inspected main at `7b67845199de32546823b9d253d596de44146934`. The implementation worker must reconcile these observations against FR000542's delivered code rather than restore the old renderer.

- `src/web/assets/render.js::overviewAccounts` renders `observation.label` as the heading and then `provider_label + plan` as a subtitle. The label already contains provider/plan, with account distinctions when necessary, explaining the duplicate text reported by the owner.
- Account quota order is provider-defined: for example Claude's 5-hour quota precedes weekly/model-specific windows. Raw status enums are not an appropriate summary: Claude can expose a known sub-100% utilization with status UNKNOWN, while account BLOCKED can also represent a provider restriction without a known exhausted percentage.
- Account `ccost_scopes` already contains `today` and supported rolling-window scopes. Account attribution can be unavailable or estimated, so the global daily total must not be obtained by adding displayed account amounts.
- `src/watch/today_ccost.py::WatchTodayCCost` already accumulates deduplicated current-local-day request usage, including history before Watch startup. It uses canonical request completion/attribution timestamps, retains known observations through transient omissions, and changes its CLI label to the explicit date before 03:00. The Web label below deliberately remains Total Today.
- Current Watch Token Mix uses Watch-observed, priceable sample data; the new all-day mix needs a different scope. `today_prompt_count` is not reliably populated in the current Watch path. These values need real data work, not relabeling.
- Canonical context helpers already expose approaching/exceeded severity, the configured approaching threshold, current Watch continuation state, and relative tier-price information. There is a current DTO gap for the Watch-specific cost multiplier; ordinary-report fields must not be substituted for it.

## 1. Subscription cards with a common aligned top section

Keep a responsive grid of subscription cards at the bottom of Watch. Cards can wrap onto a new row at sensible widths. Within each visual grid row, align the common header and primary metric tracks across all cards, regardless of provider, secondary quota count, long titles or missing data.

Use the following **same order and layout** in every card's top section:

| Track | Contents |
| --- | --- |
| 1 | Subscription/account title, once. |
| 2 | **CCost Today** and that account's current-day value in the effective Credits/USD unit. |
| 3 | Primary quota period label, such as **Monthly**, **5-hour** or **Weekly**, plus **N% used**. |
| 4 | Primary Used progress bar. |

Remove the redundant provider/plan subtitle under the title. Preserve any real account name/ordinal needed to distinguish two subscriptions with the same plan; do not collapse separate accounts because their titles otherwise match.

Use shared grid tracks, a consistent title region or another proportionate layout technique so CCost Today, the primary percentage and the primary progress bar line up horizontally when cards are side by side. Wrapping a title must not push that card's primary bar below its neighbors. Do not solve alignment by clipping distinguishing names or forcing cards to an unreadably small width. Whole cards should wrap at the responsive breakpoint; the common section stays consistent on the new row.

**CCost Today always means the same current-local-day scope in this top section.** It must not switch to five-hour, weekly, monthly or Watch-run cost depending on provider. Reuse canonical account attribution, source freshness and the saved display-unit preference. If a value cannot be assigned to that account reliably, show a truthful unavailable/estimated/partial value according to existing conventions rather than inventing a full amount or distributing a global total arbitrarily.

### Stable primary quota

Choose the provider's canonical primary quota window and keep that choice stable: normally monthly for Copilot, five-hour for Claude or an explicitly supplied primary window for other providers. Do not dynamically promote whichever quota is most depleted into the common top section.

If the expected primary window is temporarily unavailable, keep its slot and show an unavailable value. Do not silently substitute the weekly window and make the header's comparison period jump between refreshes.

## 2. Clear Used percentages and provider-specific details

### Remove raw status words

Remove visible **Blocked/BLOCKED**, **Available/available** and **Unknown/unknown** status suffixes from the Watch subscription-card presentation. A known exhausted window should simply show **100% used**, with the existing appropriate quota severity color and a full bar.

This is a presentation change, not a rewrite of source truth:

- A raw BLOCKED enum alone is not proof of 100% used; the provider may deny access or report a restriction without returning a utilization percentage. Do not fabricate 100%. Preserve a concise genuine restriction/acquisition diagnosis in the existing appropriate error/details presentation when needed, without reinstating the raw status suffix.
- A known utilization remains displayable even when its raw enum is UNKNOWN. A missing percentage is shown as **—** or an equivalent neutral unavailable value, never 0% and never an apparently healthy empty bar.
- Keep the numerical and graphical meaning **used**, not remaining; use existing canonical conversion and quota thresholds. Preserve a source-confirmed **Unlimited** quota as Unlimited, without inventing a percentage or determinate bar; distinguish it from unavailable data.
- Avoid rounding a genuinely sub-100% value up to an apparently exhausted **100% used**. Use sufficient precision or `<100% used` near the boundary; exact known exhaustion remains 100% used.
- If the weekly quota is 100% used while the primary five-hour quota is only 25% used, show those actual values in their respective places. Do not inflate the primary value or conceal the exhausted secondary window.

### Divider and lower detail section

Place the existing-style horizontal divider **after the aligned common section**. Below it, organize the information that varies by subscription:

- Reset information for the primary window, clearly associated with that window.
- Secondary quota windows, including their own period label, Used percentage/bar, and applicable reset information.
- Meaningful provider-specific period descriptions such as **Rolling 7-day window**, when that is the source's actual definition.
- Other useful existing provider-specific figures only where their scope is explicit and they do not repeat the common title/Today metric.

Use short label/value groups and consistent formatting. Keep reset text next to the quota window it describes; a generic Reset in value must not leave users guessing whether it refers to five hours or a week. Do not describe every weekly quota as rolling if the source uses a different reset model.

The lower section may vary in height and contents; it must not move the common section's aligned tracks. Keep secondary exhaustion visible in the normal card body. Do not introduce a new details disclosure merely to hide information the owner wants to compare.

Preserve FR000542's removals: no Watch accounts/independent-observation heading, repeated explanatory quote boxes, Observation details disclosure, or Copilot Unaccounted usage line. Genuine unavailable/stale/error data stays truthful. Scope this visual redesign to **Watch**; shared renderers must not accidentally remove information or change layout on the separate Accounts page.

## 3. One full-width Total Today card above the subscriptions

After the active/historical prompt-card content and **immediately above the subscription-card grid**, add one compact card spanning the same available main-content width as the prompt cards above.

On a wide desktop it should read as essentially one horizontal line, in this order:

**Total Today · <CCost/USD amount> · <N> prompts · Token Mix % · Input: <share> (<cost>) · Cached input: <share> (<cost>) · Cache write: <share> (<cost>) · Output: <share> (<cost>)**

This is a layout illustration; reuse the established category names/number formatting rather than hardcoding example amounts. At narrower widths wrap complete metric/category groups cleanly without clipping values, forcing tiny text, or creating an unnecessary page-wide horizontal scrollbar.

- The label is always **Total Today**. Do not switch it to an ISO date before 03:00 or expose a Watch-run start date.
- Use the existing Credits/USD preference for the total and all category cost amounts. Do not mix units within the card.
- Include usage across **all available providers/subscriptions and all of today's relevant prompts**, including activity before the browser or Watch started. This is not a sum of five visible prompts, five historical sessions, retained Watch rows or requests observed only during this Watch run.
- Do not restore a separate Watch CCost/run total, separate Watch token-mix summary, next-refresh banner or global price-warning footnote list.

## 4. A coherent full-day cost, prompt count and token mix

### One canonical accounting scope

Use the application's configured **local calendar day**, from local midnight to the current observation time, through the existing timezone/day-boundary helpers. All metrics in the new card must describe one coherent current-day acquisition/projection, including historical enrichment and newly observed activity.

Preserve the current canonical Today request-accounting rule: usage is assigned to the day by its request completion/attribution timestamp, not by when Watch first saw it or simply by the session's latest-update time. For a prompt spanning midnight, count **only its requests attributed to the current day** in today's cost and mix; do not charge its entire lifetime to both days or to its start day. Cover local timezone and daylight-saving day boundaries correctly.

Build on the same reconciled, deduplicated daily request set used by `WatchTodayCCost`/`PeriodCCostIndex` and canonical valuation. Preserve stable known daily observations during transient source omissions, and use that retained set for the count and mix too; otherwise a stable total and shrinking mix could contradict each other.

**Global Total Today is not the sum of the account-card values.** It includes known relevant usage even when the particular subscription cannot be assigned confidently. Deduplicate physical requests/steps and causally attributed child work before aggregation; never count the same usage again through another account, session, active card or history view.

### Count prompts, not model calls

Populate a real daily prompt count; do not expose the current unpopulated default zero. Count **distinct initiating user prompts contributing activity to the current-day dataset**, using canonical prompt identity/attribution. A prompt with many model calls or task children counts once. A continuing prompt that began before midnight but has current-day usage counts once for this day's activity.

Do not increment this counter for model calls, retries, physical trace entries, synthetic compaction events or repeated attribution of a child to its parent. Their legitimate token/cost usage still belongs in daily accounting. Preserve the same source-wide population as Total Today, not just visible/retained Watch prompts. Include today's already-known canonical usage from prompts that are still running; do not wait for the entire prompt to finish before its recorded requests contribute.

If complete prompt attribution is unavailable for some included usage, keep that usage in cost/token accounting and qualify the prompt count as partial/unavailable rather than fabricating a count or silently dropping the usage. Document the activity-day meaning concisely in existing help or a tooltip, without adding another explanatory panel to Watch.

### CLI-style token mix, calculated from today's records

Reuse the canonical category definitions, percentages and cost formatting:

| Category | Meaning |
| --- | --- |
| **Input** | Ordinary uncached input token volume and its CCost. |
| **Cached input** | Cache-read token volume and its CCost. |
| **Cache write** | Cache-write token volume and its CCost. |
| **Output** | Canonical output token volume and its CCost, with reasoning handled by the existing category definition. |

The percentage is the category's share of token volume. The amount in parentheses is that category's reference CCost, or its USD display equivalent, **not** a money-share percentage or a provider invoice claim.

Price each physical request using its own model, actual applicable input tier and canonical cache/output handling, then sum category amounts. Do not price a combined all-model token total as though it were one request or one model. With complete data, category costs must reconcile to Total Today before display rounding; complete token shares should follow the existing balanced rounding.

Use the full daily record set and the appropriate canonical helper such as `priced_token_mix`. Do not relabel `WatchTokenMix` or use the priceable-only `priced_sample_mix` to silently exclude unpriced/incomplete activity. Preserve existing partial, unknown-price and missing-telemetry semantics; distinguish a known zero-usage day from loading/unavailable data.

This new **Today** mix does not change the CLI Watch run-observed mix or the global latest-100-prompt comparison sample used by Models/relative CCost and context-tier multipliers.

### Loading, updates and rollover

Keep FR000542's active-first, progressive loading behavior. Daily historical enrichment and account details must not block active cards or prompt updates. Publish the daily total/count/mix as a coherent group, with clear loading/partial states while necessary; do not briefly present default zeros as a successfully acquired empty day.

Reuse bounded shared acquisition, cache/reconciliation and the existing live/account/history cadence. New live usage should update the daily view through that shared pipeline; do not rescan all full histories on each display tick or create a second acquisition engine per browser tab.

At local midnight, start a new day coherently for the global card and per-account Today values; retain the constant **Total Today** label. A delayed response for yesterday must not repopulate today's card. Preserve selected display units, theme, disclosure state, focus and scroll through updates.

## 5. Context price warnings belong to each session card

Add a conditional warning footer to the corresponding logical card:

- **Active card:** a fourth section, after its header, prompt table and tool/skill activity.
- **Historical Earlier Prompts card:** a third section, after its header and prompt table.

The footer is part of the existing unframed card layout. Show it only when the applicable current next-input context has an actual approaching or exceeded warning. If there is none, render no empty warning section/divider.

Remove context-price-warning asterisks, `*1`/`*2` references, warning icons/prose and threshold-specific cell coloring from the prompt table itself. Do not recreate a shared explanation list below all tables. Keep ordinary running/completion/abort row styling, normal prompt outcome markers, numeric context values and approximation markers; this change concerns the placement of **context price-tier guidance**.

### Warning source: valid latest continuation, not an old table row

Use the valid **current next incoming context** associated with the card's last/focal prompt, including subsequent compaction/context-epoch changes. The Context column is the Web name for this Next Incoming Context concept; an old prompt's historical incoming price tier is not the warning source.

- For a historical session, use its latest valid continuation/context state.
- For an active card, use the focal prompt's valid live Watch continuation state, even while it is still running. Ordinary-report estimates can be unavailable during execution and are not interchangeable with Watch fields.
- FR000542 displays up to five actual user prompts and does not give synthetic compaction events their own user-prompt slot. A later compaction must still update/invalidate the footer's context state. Do not search those five rows for the last non-empty warning and display it forever.
- If compaction reduces context below the warning threshold, remove the warning immediately on the authoritative context update, even when older high-context prompts remain in the table. If it only reduces the state from exceeded to approaching, downgrade the footer accordingly.
- A temporarily unknown post-compaction context must not revive an invalidated pre-compaction warning or be treated as a known safe zero. Preserve honest unavailable/loading context state through existing field-local handling.
- With several concurrent cards from the same session, keep guidance attributed to the correct focal/current continuation. Do not revive a superseded context on an older card or attach the newer prompt's model/multiplier to it. If an older card no longer owns valid continuation guidance, omit its footer while retaining its running prompt/activity.

### Same threshold rules and useful explanatory information

Reuse `next_context_warning_state`, `watch_context_state` and the canonical price-tier model. The current approaching setting is `thresholds.nextIctxPriceThresholdWarningPercent` (default **75%**); zero disables approaching warnings while retaining crossed-tier guidance. Do not invent a different Web trigger percentage.

Use exact unrounded token counts and canonical tier boundaries, including the difference between published `>` and `≥` limits. Current normalized tier membership is `tokens >= min_input_tokens`; displayed K/M rounding must never decide whether a threshold has been crossed.

- **Approaching:** warning icon plus text such as **Approaching price threshold …**, retaining the relevant boundary and established additional cost information.
- **Exceeded:** warning icon plus text such as **Price threshold … exceeded**, emphasized in the CLI-like **gold/orange** warning role, including the existing supported explanation of how much more expensive the tier is.

Use the same meaningful model/context pairing as the canonical continuation analysis, not the visible formatted Model/Effort text. Reuse the current highest-crossed/nearest-approaching tier choice; no separate multi-warning ladder or new prediction policy is required.

Where supported, show the canonical tier-price multiplier. It is a relative reference-price factor from the established comparison mix, not proof that this particular prompt's final bill rose by that factor. When a multiplier is unavailable, reuse the supported next-context cached/fresh cost range or existing truthful fallback; do not make up a factor.

Export the correct Watch/current-context fields or a canonical formatted explanation, including the Watch multiplier when necessary. Do not borrow the generic ordinary-report multiplier just because it already exists in the DTO, parse warning strings to recover severity, or compute valuation in JavaScript.

Keep warning icon/text understandable without color alone and readable in **Classic**, **Web light** and **Web dark**. Use the warning/gold-orange family for exceeded context tiers; abort/error red keeps its separate meaning.

## 6. Boundaries, affected areas and verification

This is a focused follow-up to the Watch layout. It does not change CLI layout/status wording/Today date labeling, provider quota truth, cost formulas, Models comparison scope, the Sessions-page design, FR000542's session-total definitions, or the number/order/lifecycle of its cards. Its new context footer is distinct from high-running-prompt-cost alerts and account-quota warnings; do not accidentally erase unrelated canonical information.

Likely owners after reconciling FR000542: Watch/account renderers and CSS; Web live projections; shared account daily scopes; `WatchTodayCCost` or a narrowly shared daily projection; canonical token-mix/prompt attribution helpers; current context-warning projection/formatting. Relevant existing paths include `src/web/assets/watch.js`, `render.js`, `app.css`; `src/application/live_projection.py`, `projection.py`; `src/reports/accounts.py`; `src/watch/today_ccost.py`, `token_mix.py`; `src/analysis/token_mix.py`, `period_ccost.py`, `context.py`; and `src/presentation/context_warnings.py`.

Add proportionate regression coverage in the existing Web/account/daily-accounting/context-warning tests and update `docs/web-beta.md`/relevant user help. These are implementation acceptance criteria, not new permanent repository gates.

## Acceptance criteria

1. **Aligned accounts:** with Copilot monthly, Claude five-hour/weekly, another primary/secondary provider, duplicate plans with distinct accounts, long titles and unavailable data, side-by-side cards align title regions, CCost Today, primary Used labels and bars. Titles appear once. Cards wrap cleanly on laptop/mobile; lower details never shift common top tracks.
2. **Used/status semantics:** no raw Blocked/Available/Unknown suffixes on Watch cards. Known 25%, 99.x% and 100% values remain accurate; sub-100% rounding does not imply exhaustion. A known percentage with UNKNOWN status is shown, missing usage remains unavailable, and provider restrictions do not fabricate 100%. An exhausted weekly window remains clearly visible while a non-exhausted five-hour primary keeps its actual value.
3. **Specific details and cleanup:** a divider separates the common area from primary/secondary reset information, secondary Used bars and real provider window descriptions. Each reset belongs clearly to a quota. No restored duplicate subtitle, Watch account heading, Observation details, explanatory quote boxes or Unaccounted usage. The separate Accounts page retains its intended presentation.
4. **Daily summary layout:** exactly one full-width Total Today card above the account grid, with total CCost/USD, actual prompt count and the four CLI-style token-share/category-cost cells. It is compact on wide desktop and wraps readably on narrow screens. Label remains Total Today at midnight/01:00/03:00; no Watch-run total is restored.
5. **Complete daily scope:** include pre-Watch history, more than five sessions/prompts, multiple providers, multiple accounts, unassigned-account usage and repeated observations. Deduplicate physical requests and causal child usage. Global cost stays correct even when some individual account costs cannot be allocated; it is not a sum of card values. Today metrics use the same canonical retained daily population.
6. **Count and mix correctness:** many model calls/children for one initiating prompt count once; synthetic compaction adds legitimate cost/tokens but not a user prompt. Exercise missing attribution and unpriceable/partial telemetry without silently dropping it. Token shares are volume shares; per-category prices use each request's model/tier and reconcile with Total Today when complete. Both Credits and USD formatting work; Models/CLI mix scopes remain unchanged.
7. **Midnight and progressive updates:** a prompt crossing local midnight contributes only current-day requests to today's cost/mix and one distinct prompt to the day's activity count. Test timezone/daylight-saving boundaries and stale previous-day results. Slow daily enrichment does not block active cards; loading, zero, partial and unavailable remain distinct; total/count/mix publish coherently.
8. **Threshold footer states:** no-warning, approaching, exact tier boundary, exceeded, configured warning-disabled, multi-tier and missing-multiplier cases use canonical logic. Both active and historical cards place the warning in the required footer with useful threshold/cost information and gold/orange exceeded styling; no context-warning stars/references/cell highlighting/global footnote list remain.
9. **Compaction and attribution:** reducing context removes or downgrades a previous warning while old high-context rows remain visible. A hidden synthetic compaction still affects the footer. Missing ordinary-report estimates do not suppress a valid live Watch warning. Unknown/replaced contexts and delayed responses cannot revive stale warnings; concurrent cards never borrow one another's warning model or multiplier.
10. **Visual and existing behavior:** verify Classic/Web light/Web dark, wide desktop and narrow layouts, long values, responsive wrapping, accessible severity/labels, and stable scroll/focus through live updates. Preserve FR000542's active/history behavior and independent account cadence. Record actual verification and any unverified platform/visual evidence honestly.

Publishing this FR is backlog-only; product implementation, release/version changes and Mini Watch creation are separate work.
