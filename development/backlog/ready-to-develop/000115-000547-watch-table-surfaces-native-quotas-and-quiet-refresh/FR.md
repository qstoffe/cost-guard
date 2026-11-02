# FR 000547 — Refine Watch tables, history flow, native primary quotas and quiet Today updates

## Owner goal, priority and preceding work

Complete another focused Web Beta Watch cleanup: make each prompt table visually distinct like the Models table, attach context-price guidance directly to its table without a divider, separate adjacent session cards, let expanded history use normal page scrolling, tighten the daily-summary/account spacing, and remove distracting count/refresh wording. Correct the subscription cards so an account with only a native weekly quota uses Weekly as its primary metric rather than a fabricated unavailable five-hour quota.

The owner requested and approved this follow-up on **2026-11-02**. Permanent identity: **000547**. Ready priority: **000115**, after **FR000545** (compact one-row cards, 000110) and before **FR000544** (Mini Watch, 000120). **FR000546** (terminal-lifecycle correctness, 000100) remains ahead of both.

Implement on top of delivered FR000542/FR000543 and **FR000545's compact-card result**. This FR deliberately supersedes these earlier presentation choices:

| Earlier decision | New final requirement |
| --- | --- |
| Active context warning is a fourth section after activity, with a dividing line | Warning is immediately below its table, before active tool/skill activity, without its own divider. |
| Earlier Prompts has a viewport-height cap and internal vertical scrollbar | Expansion adds its complete height to normal document flow; the page scrolls. |
| OpenAI generally defaults to a five-hour primary quota | The actual account's native primary/capability evidence determines its primary; a weekly-only account has no five-hour placeholder. |
| Incomplete prompt attribution adds a lower-bound sign and explanatory text | Total Today always displays the known integer as **N prompts**, without count-completeness qualifiers. |
| Routine background refresh is labelled Refreshing even with existing values | Keep the existing values visible silently until replacement values arrive. |

Preserve FR000545's one prompt per active card, one latest prompt from each of five eligible historical sessions, Started formats, ellipsis/one-line table behavior, removal of Watch session totals and CLI color roles. Preserve FR000543's daily accounting and aligned subscription-card structure. No redesign of Sessions, CLI layout or Mini Watch's window interaction is requested. Do not rewrite the completed or already queued FRs to carry these amendments.

## 1. Visible table surfaces matching Models

Give both active and Earlier Prompts tables a clearly visible theme-aware surface, following the Models overview table's background, header and line treatment. The user should immediately see the table's extent rather than have its header/body blend into the page background.

Reuse the existing Models `--panel`, `--surface` and `--line` family or equivalent shared theme roles. Keep an identifiable body surface, an appropriate header surface and a restrained edge/border where needed to distinguish the complete one-row table. Cover **Classic**, **Web light** and **Web dark**. Exact colors should follow the established theme, not introduce an unrelated palette.

The surface belongs to the **table**. Do not add a framed parent card around every active session, revive filters/paging, or import unrelated Models sorting and wrapping behavior. Keep all FR000545 table constraints: compact complete non-Prompt columns, a flexible Prompt column with a sensible minimum, ellipsis on overflow, and no wrapped table rows. Per-table horizontal overflow remains available on narrow screens.

Preserve yellow running rows/titles, neutral historical titles, gold/brown activity, red failure fragments and gold/orange context warnings. The new backgrounds must not obscure those distinctions or reduce text contrast.

## 2. Warnings next to tables; dividers between cards

Use this logical content order:

- **Active card:** linked session title → one-row table → conditional context warning → tool/skill/current running activity.
- **Historical card:** linked session title → one-row table → conditional context warning.

Move the warning as necessary to achieve actual adjacency. Removing its border while leaving tool/skill activity between it and the table does not satisfy the request.

Remove the warning block's horizontal separator and separator-sized padding/margins. The guidance should follow its table with only a small readable gap, without a separate framed panel. Keep it outside the table cells and outside any horizontally clipped table-content area so longer guidance can wrap normally. When there is no warning, render no empty warning space.

This changes **placement and decoration only**. Keep canonical approaching/exceeded severity, exact threshold boundaries, the current continuation/model pairing, supported price explanation/multiplier, and compaction-driven invalidation/downgrade. Do not restore stars, footnote numbers, threshold prose or warning-specific coloring inside Prompt/Context cells.

Add restrained horizontal dividers **between adjacent active cards** and **between adjacent historical cards**. There should be one separator between siblings, with compact spacing, rather than an extra leading line before the first card or trailing line after the last. Reordering, removal and active-to-history transitions must leave the separators correct.

Keep the separate divider inside subscription cards between their aligned common metrics and provider-specific details. That divider is still wanted; it is not the context-warning divider being removed here.

## 3. Earlier Prompts expands the page naturally

Remove the historical container's fixed/max-height, viewport-dependent vertical cap and internal vertical scrolling. Expanded Earlier Prompts displays all of its selected cards at their natural combined height and pushes subsequent page content down. The document/page owns vertical scrolling, just as it does for active cards.

Do not merely hide the scrollbar while retaining clipping or a scrollable fixed-height region. Remove obsolete history-only scroll-position handling where appropriate, while preserving normal keyed updates, the user's page scroll/focus and the disclosure's open/closed state.

Retain FR000545's subtle outline around the **expanded history container**, the dividers between its cards, and any necessary horizontal overflow for individual tables. The request removes nested **vertical** scrolling, not the visible distinction between history and active work.

The earlier requirement to preserve some active content in view at 1080p by capping history height, and the older estimate based on 3.5 five-row cards, are explicitly retired. With five historical sessions and one prompt each, full expansion takes its natural space. Do not add a responsive height cap that restores the discarded behavior on smaller windows.

History continues to be maintained while collapsed through the existing bounded shared acquisition. This change does not introduce lazy loading, paging, filtering or a new session limit.

## 4. Tighten Total Today-to-subscription spacing

Reduce the visible vertical gap between the bottom of the full-width **Total Today** card and the top of the subscription-card grid to only a few pixels, targeting roughly **4 CSS pixels** or the equivalent small spacing token.

Use a Watch-scoped layout/margin adjustment. Preserve the daily card's readable internal padding, the spacing between subscription cards, their responsive wrapping and the alignment of their common title/CCost Today/primary Used tracks. Do not globally shrink section margins on other pages or remove the subscription details divider.

## 5. Resolve the real native primary quota per account

The owner reports an **OpenAI Pro Lite** account for which CLI shows only weekly usage. Web currently renders a five-hour primary with a dash/Usage unavailable and relegates the actual weekly quota to the lower detail area. The required result is **Weekly usage and its progress bar in the common top section**, with no nonexistent five-hour row, label, bar or unavailable placeholder anywhere in that card.

Base the selection on the account's real native primary declaration, supported-window evidence and canonical adapter ordering, consistent with the quota population that drives CLI. Do not hardcode behavior from the visible plan name or infer that every OpenAI account has a five-hour limit.

Preserve these distinctions:

| Actual evidence | Required behavior |
| --- | --- |
| Successful native data identifies Weekly as the account's primary/only supported quota | Weekly is primary; do not manufacture a five-hour component. |
| Native primary is five-hour and weekly is a real secondary | Keep five-hour in the common top section and weekly below the divider. |
| A real expected primary is explicitly established but its usage is missing/unavailable | Keep that primary's slot with truthful missing/stale/recovery treatment. |
| A previously established expected primary is temporarily omitted by partial/error acquisition | Preserve the existing appropriate recovery semantics; do not opportunistically promote a secondary just because it has a percentage. |
| Only provider identity suggests a possible five-hour window | Provider identity alone is insufficient to invent that window for this account. |
| A model-specific additional limit exists | Do not silently promote it to an account-wide primary. |

Use a proportionate canonical resolver or preserve/normalize appropriate native primary metadata; a new large account-model redesign is not required. Primary choice should remain stable for the same account/window contract. It must not switch to the most depleted quota or whichever metric happens to finish loading first.

Show every real secondary window once in the lower provider-specific section. If Weekly becomes primary, do not duplicate it below as secondary. Keep its reset/window information associated with that same real quota in the appropriate lower details area. Preserve genuine unlimited, exhausted, unavailable and restriction semantics and FR000543's aligned common top section.

The corrected canonical result must also be the input for **FR000544 Mini Watch** and its same-primary-period CCost. Do not add a second Mini-only five-hour default that recreates this error. This FR does not itself create the floating window or change its cost-period policy.

### Inspected cause and useful existing support

At the inspected baseline, `src/application/watch_accounts.py::primary_quota` honors explicit primary metadata first, but then assumes an account-scoped 18,000-second quota for every OpenAI/Anthropic/Claude account and fabricates `QuotaComponent("5-hour")` if none is found.

CLI `src/presentation/accounts.py::account_capacity_parts` instead iterates the native quota tuple without inventing an absent five-hour row. `src/accounts/openai_subscription.py::convert_usage_payload` already reads native `primary_window` before `secondary_window`, derives labels from duration, skips absent windows and puts model-specific additions afterward. `src/accounts/base.py::normalize_quota` retains tuple order but does not currently populate the existing primary metadata fields, allowing Web to fall through to its provider-wide assumption.

This explains the reported weekly-only presentation at the source level; no private payload from the owner's account was inspected. Verify with representative native fixtures, including a weekly `primary_window`, rather than assuming the user's visible plan string proves the exact payload shape.

## 6. Total Today shows a plain prompt count

Display the canonical known integer as **N prompts**, regardless of the prompt-attribution completeness flag. For the owner's example, the visible result is simply **181 prompts**.

Remove **≥**, **>=**, **Partial Attribution/partial attribution**, and any equivalent lower-bound/approximation qualification from this count's Watch presentation. Do not replace them with an asterisk, “at least”, an attribution badge/icon or a tooltip containing the same rejected qualification. The neutral existing tooltip explaining what a daily initiating prompt means can remain.

This is an explicit owner-selected simplification of the visible count. Preserve the internal canonical count and its completeness metadata accurately. Do not set completeness to true to suppress the text, invent additional prompt identities, count model calls instead, or discard unattributed request usage from cost/token accounting.

Keep FR000543's current-local-day scope, pre-Watch history, initiating-prompt deduplication, causal child attribution and compaction semantics. Unattributed usage still contributes its real CCost/tokens. This count-wording change does not remove unrelated pricing/telemetry information or change valuation.

## 7. Quiet refresh after the first value

When Total Today has no valid observation yet, a concise **Loading…** state is appropriate. Do not fabricate zero prompts or zero cost during first acquisition.

Once a valid current observation exists, keep its cost, count and token mix visible during routine background refresh. Show no **Refreshing**, **Loading**, routine refresh badge or spinner alongside already available values. Replace the old values when the next coherent observation is ready. A repeated background refresh must not flash placeholders or make the card jump between numbers and status text.

Continue acquisition at its normal cadence. The change removes routine visual chatter; it does not stop refresh, reduce freshness, or clear the retained data to force a different rendering path. Preserve the coherent cost/count/mix publication and the broader stable-value behavior required by FR000545. Avoid unnecessary DOM replacement when only an internal routine-refresh flag changes; keep selection, focus and page layout stable.

Genuine acquisition failures remain distinct from routine refresh and may use the established truthful source/freshness treatment with retained data. The removed prompt-count qualifiers must not reappear as a workaround in that treatment. At a real day/account/source/host identity change, obsolete values must not be presented as current: preserve the existing new-day reset and rejection of delayed prior-day results. Loading is allowed when no valid value exists for the newly selected/current scope.

## Baseline, affected areas and focused verification

Inspected main: **`f6ed34fd327e91b414ed1ae18f2cf6ed604e889c`**. At this point FR000542/543 are delivered and FR000544–546 are queued. Reconcile these source pointers against their implementation rather than restoring old five-row cards or session totals:

- `src/web/assets/watch.js`: active card currently places activity before the warning; `daily` directly adds the lower-bound sign, partial-attribution text and routine Refreshing text; history update code retains an internal scroll position.
- `src/web/assets/app.css`: Watch cells currently use transparent backgrounds; `.watch-context-warning` has a top border and separator spacing; `.watch-history` has max-height/vertical overflow; `.watch-daily` inherits broad section margins.
- `src/web/assets/render.js::overviewModels` and Models CSS: reference table surface/header/line treatment, not a source of new Watch filters/wrapping behavior.
- `src/application/watch_accounts.py`, `src/accounts/openai_subscription.py`, `src/accounts/base.py`, `src/domain/accounts.py`, `src/presentation/accounts.py`: native window identity/order, primary metadata and the Web fallback defect.
- `src/analysis/daily_usage.py`, `src/application/live_projection.py`, `src/watch/web_coordinator.py`: preserve canonical count/completeness and already-retained coherent daily observations during background work.

### Acceptance criteria

1. **Table distinction:** active and historical one-row tables have visible Models-like surfaces and boundaries in Classic/Web light/Web dark. Their compact widths, ellipsis, complete metrics, horizontal overflow and semantic text colors remain correct.
2. **Warning adjacency:** in both sections, the warning appears directly below its table without a warning-specific separator/frame. Active activity follows the warning. No-warning cards reserve no empty space; canonical threshold/compaction behavior and outside-cell warning placement remain intact.
3. **Card separation:** two or more active/historical cards have understated horizontal lines only between siblings. Insertion, reordering, grace expiry and history transitions do not leave stray leading/trailing rules. Subscription common/detail dividers remain.
4. **Natural history height:** all five one-row historical session cards expand the document at desktop and narrow viewport sizes; subsequent content moves down. No nested vertical scrollbar, clipping, fixed/max-height or viewport cap remains. The history outline, per-table horizontal panning, disclosure, page scroll/focus and background updates remain correct.
5. **Compact account adjacency:** Total Today and the subscription grid are only a few pixels apart without changing their internal readability, responsive card gaps, shared metric alignment or other routes' section spacing.
6. **Weekly-only native account:** a native weekly-only OpenAI fixture, including the reported plan label as a display example, yields Weekly in the common top section and no five-hour placeholder anywhere. CLI/Web agree on the actual window population; Weekly is not duplicated below. Five-hour-plus-weekly, explicit primary ordering and model-specific additional quotas also behave correctly.
7. **Real missing primary:** an explicitly established five-hour primary with unavailable or temporarily omitted data retains honest stability/recovery behavior. Make existing missing-primary fixtures explicit about that evidence so they are distinguishable from genuinely weekly-only accounts. Do not keep a provider-wide invented five-hour default just to satisfy an old test.
8. **Plain count:** both complete and incomplete attribution with `prompt_count=181` render exactly the plain count **181 prompts**. No rejected sign/attribution qualification is displayed. Internal incomplete metadata and unattributed cost/token usage remain accurate; first acquisition still does not fabricate a zero count.
9. **Silent routine refresh:** a valid observation followed by repeated refreshing states retains its figures without Loading/Refreshing indicators, then switches to the next coherent observation. Genuine failure and new-day/identity invalidation remain correctly handled; delayed old-day work cannot repopulate today's card.
10. **Integration:** preserve FR000545's final one-row/five-session design and FR000546 lifecycle correctness. FR000544 consumes the corrected shared primary selection. Verify actual affected themes/layouts and record checks honestly.

Use proportionate existing tests, notably `development/tests/integration/web_watch_summary.cjs`, `test_watch_daily.py`, `fixtures/watch_summary.py`, `test_step6_pricing_accounts.py` and the relevant Watch visual/card coverage. The Web integration currently expects `≥37 prompts · partial attribution`; update that presentation assertion while preserving the underlying completeness test. Existing temporarily-missing-primary fixtures need explicit capability/primary evidence, not deletion of the useful stability case. Update relevant Web Beta help to match the new history/primary/count behavior.

These are this FR's acceptance cases, not new permanent release gates. Creating the FR is backlog-only; implementation and product version/release work remain separate.
