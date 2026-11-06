# FR 000598 — Mini Watch quota tooltips and Models price-list refresh

## Owner request and boundaries

**Owner-approved Ready Feature Request, 2026-11-05.** Two intentional Web Beta UX corrections in one FR:

1. **Mini Watch subscriptions:** their tooltips are far too verbose. Display just **Capacity** and **Next reset**, in that order. All the existing visible Used/Remaining percentage, CCost period amount and progress remain on the Mini line.
2. **Models:** remove the **More information** disclosure and its three explanation cards; move real explanations to column-header tooltips instead of generic sorting instructions. Add **Refresh price list** at the top left and the **actual last GitHub Copilot pricing fetch timestamp** immediately to its right. Clicking actively retrieves fresh prices and recomputes Models, not merely reopens cached report data.

Publish this as **FR000598**, priority **000200**, after the other Ready requests. Implement later, taking account of **FR000590** (shared value-based tooltips, no question-mark icons, hover delay), **FR000589** (text-only header hover) and ongoing Models/Mini changes. **This session is backlog authoring only:** create the Ready FR and advance the identity watermark, without implementing code, tests, documentation or a release.

## A. Mini Watch: exactly two facts in subscription help

In the separate Mini Watch Document Picture-in-Picture, each subscription/account row currently assembles a long `line.helpText` from `ReportView.quotaHelp(primary.quota, true)`, additional quota sections, CCost Used explanation and warning prose (`src/web/assets/mini.js::drawAccounts()`).

Replace its tooltip contents **entirely** with:

```text
Capacity: <value>
Next reset: <value or truthful state>
```

- Only these **two lines**, Capacity first, then Next reset; no heading, extra quota sections, CCost meaning, Used/Remaining duplication, native unit breakdown, status log, provider essay or generic disclaimers. The compact row already gives the important current usage.
- Both values must belong to **the actual primary quota/window shown in that Mini row**, not another quota or account. Capacity follows selected Credits/USD, the existing server-side capacity definition and **FR000590's `(guesstimate)` provenance** for an inferred numeric capacity. An exact capacity has no marker. Unknown or unavailable capacity stays `N/A`/unknown, not an invented zero or spurious guesstimate.
- Reset uses existing canonical local time/countdown/reset state (e.g. `watch_reset`) for that same quota. If its usage window has not started, use a truthful brief value such as **`Window not started`**, not a manufactured time. Unknown reset must not be represented as known.
- Preserve normal Mini row text, native progress, warning/exhaustion styling, important visible unavailable/blocked/stale indications, existing secondary-quota acquisition, account identity and screen-reader status. This request removes excessive **tooltip prose**, not needed application evidence.
- Attach the help to the **actual visible subscription label/value text**, not a standalone `?`, oversized row, progress track or PiP background; preserve focus/touch, hover delay, rapid window exit and tooltip cleanup from FR000590. Full Watch and Accounts account-card tooltips must keep their own richer useful facts; this minimalist rule is **Mini-only**.

**Mini acceptance:** single/multiple subscriptions, primary/secondary quotas, Used/Remaining, Credits/USD, exact/inferred/unknown Capacity and known/unstarted reset all reveal only the two scoped lines, without redundant description. Warnings remain visible elsewhere.

## B. Models: remove “More information” completely

In `src/web/assets/render.js::overviewModels()`, the `overviewConcepts()` helper currently adds a collapsed `More information` disclosure with **CCost**, **Token Mix %** and **Relative CCost** cards, paragraphs and model-pricing caveats.

- Remove that entire Models-specific disclosure and **all three cards**. Remove dead Web-only layout/helpers/style as appropriate; do not remove the separate Token Mix report or shared **CLI** definitions.
- The current card's static **`1 CCost = 1 Copilot AI credit`** is confusing when Settings shows reference prices in **USD**. The replacement header explanations must distinguish the **Copilot AI-credit-equivalent pricing basis** from the **selected display unit**: Credits or reference USD (`100 credits = $1.00`). Neither necessarily equals the actual subscription bill or native quota use.
- The healthy Models page should remain a clean table with existing filters, model discoveries, release/promotion information and the new price-list action, **without** an extra explanation card or static prose block underneath.

## C. Models: meaningful hover help on table headings

The four headings are **Publisher | Model | Relative CCost | Release date**. They currently show the same “Activate to sort; Hold Shift…” tooltip. **Replace that copy** with useful metric definitions. Retain sorting arrows, click/Enter/Space, Shift multi-sort, sorted state and accessible sort action names.

- **Publisher:** concise explanation that this is the developer/manufacturer of the model, **not** the user's subscription/account.
- **Model:** model name/identity as listed in the published catalog; relevant availability distinctions only if accurately sourced.
- **Release date:** actual published/verified date when known; no invented date for unknown.
- **Relative CCost:** one **high-signal, neatly separated tooltip**, with a few short paragraphs/bullets rather than legalistic text. It should explain **both** Relative CCost and the Token Mix used to calculate it. Required facts:
  - A **relative reference-price ratio** for one *identical token workload* across models and price tiers. **1.0x** is the cheapest comparable positive rate in the complete catalog; higher ratios mean proportionally more reference cost for that mix. It does **not** measure model capability or speed.
  - **Token Mix % = Input (new) / Cached input (reused) / Cache write (stored) / Output (generated, including reasoning)**, proportion of **tokens**, not proportion of CCost.
  - The **same shared token mix** from the latest **up to 100 qualifying completed, priceable prompts** is applied to **every** model and tier, including ones not previously used. Include the **actual sample size** where available, never a fictional 100. If there is no qualifying sample, accurately explain the **hidden fixed 2/96/1/1 ranking fallback**, and do not claim populated observed comparison ratios.
  - **Arrows** mean larger-input-context price tiers; **> / ≥** indicate the source's token threshold. Keep explanation correct even if multiple tiers are displayed.
  - Avoid the old universal “one displayed CCost equals one Copilot credit” line: ratios are **unitless** and unchanged between Credits/USD; if units are mentioned, reflect Settings correctly.
- These tooltips are attached to the **visible label text only**, use the shared `cursor: help` and open delay, and remain readable on focus/touch. The sortable button retains its click area/action, but empty header padding must not trigger help. No dotted underlines or separate `?`. Do not replace useful definitions with the previous generic sorting tutorial.

**Models help acceptance:** no More information block; four different semantic header explanations; Relative CCost accurately communicates ratio/sample/tokens/tiers across 0, 1 and many eligible prompts; existing sorts and filters work exactly as before.

## D. Models: explicit “Refresh price list” control and last successful fetch time

At the **top-left above the Models table**, present an aligned compact pair:

```text
[Refresh price list]   Prices last fetched: YYYY-MM-DD HH:mm
```

- Put the **button first**, time immediately to its right. Preserve the model filters on the right and existing New Models/promotion notices, wrapping predictably on narrow widths.
- The time means **when GitHub Copilot's published model price list was actually fetched successfully**. The report already exports `view.pricing_retrieved_at_ms` from the canonical `PricingCatalog.retrieved_at_ms`; use it, formatted in the configured timezone. Do **not** substitute page load time, cached-read time, button-click time, model availability poll or release-date enrichment time. If unknown, show `Unavailable`.
- Clicking must explicitly **bypass a fresh cache** and request a real upstream pricing fetch, reusing `src/pricing/github_copilot.py::GitHubCopilotPricingProvider.get_catalog(force=True)` or an equivalent safe forced-pricing operation. **A normal `acquire()`, Reload or `get_catalog()` alone is not enough** while the configured cache is fresh.
- **Crucial failure rule:** `_load_or_fetch(force=True)` currently **returns cached catalog on failed network fetch when it has one**. Therefore an object return is not evidence of fresh prices. Verify a successful *new upstream observation* (validated retrieval result / genuine advanced `retrieved_at_ms`) before claiming success or advancing the date. On failure **keep the old timestamp and table**, show a concise “Price list refresh failed; previous prices retained” message and allow retry. If the upstream document is unchanged but successfully fetched, the factual retrieved date may advance without asserting that rates changed.
- On success, recompute/re-render the **entire Models price-comparison table consistently against the newly retrieved catalog**: current models, tiers, model prices, Relative CCost, source revision, sample-based valuation, promotions and availability from the established canonical projection. A new timestamp with **old prices** is unacceptable. Don't locally recalculate raw token values/rates in JS.
- Preserve current **Show all Copilot-priced models**, **Latest versions only**, current sorts (including Shift priorities), selected Credits/USD unit, focus and table horizontal scroll where practicable. Show small inline **Refreshing…** progress, disable double-click/races, and keep unrelated views stable rather than blanking the page for the whole operation.
- Respect existing finite-job/report bounds and shared cache ownership. Models currently runs in an **isolated report job** (`src/web/jobs.py` and `src/web/composition.py`); Watch holds a separate **pinned catalog** and has `src/watch/model_discovery.py` for background pricing checks/notices. Use a bounded authenticated Web action/job to **force fetch then rebuild one coherent Models report**. Never fetch directly from the browser, never restart OpenCode or refresh accounts/subscriptions, and do not silently swap Watch's in-progress model valuations in the middle of a publication. Coordinate concurrent requests/tabs safely.
- The button is **optional explicit refresh**, not a permanent “Refresh snapshot” bar and not an automatic forced fetch on every navigation or SSE update. Normal Models first load/TTL caching remain functional.

**Price-refresh acceptance:** click with a warm cache really contacts the approved GitHub pricing source; changed prices cause a coherent new table/ratio and new fetched date, unchanged successful fetch only updates the date, and offline/invalid/failed upstream retrieval cannot masquerade as success. No duplicate worker storm, unintended Watch repricing or lost Models preferences.

## E. Implementation and verification

Likely code owners after earlier FRs land: `src/web/assets/mini.js::drawAccounts()`; `src/web/assets/render.js::overviewConcepts()/overviewModels()`, `app.css`, `app.js` and shared `help.js`; `src/pricing/github_copilot.py`, `src/web/jobs.py`, `src/web/http.py`, `src/web/composition.py`, `src/application/projection.py`, `src/application/display.py`, `src/reports/service.py`. Reuse actual Mini quota/reset display tokens, source-based CCost provenance, PricingCatalog timestamps/revisions and price-cache validity. Update active `docs/web-beta.md`, relevant current Mini/Models docs and Web architecture/help guidance when implementing, without rewriting historical completion evidence or CLI presentation.

Tests: deterministic Mini DOM and real Document PiP for **only the two facts**, units/unknowns/reset/source states and tooltip lifecycle; Models DOM/browser for four header explanations, missing/sample/fallback tiers, removal of three cards, sorting/accessibility and toolbar layout; Python/provider/API for **forced fresh fetch, unchanged upstream, failed fetch with cached fallback, true last-fetch provenance**, auth/job limits, concurrency and report/cached analysis invalidation. Cover responsive Classic/Web light/dark, navigation, controls and unit switching. No real model inference is necessary.

**Publication boundary:** create this Ready FR and update backlog identity watermark; product code, tests, docs and version remain unchanged now.
