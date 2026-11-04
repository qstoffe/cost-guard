# FR 000571 — Remove Mini Watch CTX tilde and clarify daily CCost labels

## Owner request

**Owner-approved executable FR, 2026-11-04.** Permanent identity **000571**, Ready priority **000110**, following the existing Ready FR000570.

In **CostGuard Web Beta → Mini Watch**, the **CTX** column currently displays a leading `~` before numeric context-token values to indicate an estimate. **Remove that visible `~` prefix.** The existing **CTX column-header tooltip already explains that the value is estimated**; keep that explanation instead of repeating the approximation marker in every cell.

Example: `~123 456` should appear as `123 456`, preserving the application's actual number format and value. `N/A` and other genuine unknown/unavailable states must keep their current meanings.

Both changes in this FR are **presentation-only**: remove the Mini Watch CTX approximation prefix and clarify the daily CCost label in Mini Watch **and** full Watch. Neither change affects the underlying context or daily accounting.

## Additional owner request — rename the daily CCost label in both Watch views

Change the visible label **`Total Today` → `CCost Today`** in:

- **Mini Watch:** the compact daily CCost-and-prompts summary on the right of the title, including its initial loading state. Example: `CCost Today 6 152 · 106 prompts` (actual values and established number/unit formatting retained).
- **Full Watch:** the compact daily summary row above the subscription/account cards, where the existing CCost total is followed by the distinct prompt count and Token Mix category figures. Change only the leading label; preserve the cost, prompts, Token Mix information, data order and all status/provenance displays.

Use the application's existing spelling **`CCost Today`** (as already used for account cards), not `Total CCost` or the previous `Total Today`. In both views, the value still means the **same canonical global configured-local-day CCost** and distinct initiating prompts, including earlier pre-Watch activity. It is *not* a per-account or per-visible-row sum. The changed wording must not create a different metric, request, filter or calculation.

## Confirmed implementation context

Inspected current `qstoffe/cost-guard` `main`, `src/web/assets/mini.js`:

- `View` builds the CTX header with the existing tooltip `Estimated next incoming context for this prompt; N/A means unavailable`.
- `drawPrompts` already formats the intended value with `display(item.live_context, 'watch_next_context_tokens')`, then adds the `~` in this presentation expression:
  ```js
  const context = display(item.live_context, 'watch_next_context_tokens');
  const cells = ['#' + prompt.prompt_number, display(prompt, 'ccost'),
    display(item, 'watch_duration_ms'), context === 'N/A' ? context : '~' + context];
  ```
- `src/web/assets/mini.js` currently uses `Total Today` in the initial `this.daily` placeholder, `drawDaily` loading placeholder and the rendered `Total Today <cost> · <prompts> prompts` text. Replace those visible labels with `CCost Today` consistently, without altering the canonical data used.
- `src/web/assets/watch.js::daily` currently builds `el('strong', 'Total Today')`, and its Watch constructor sets `this.daily.setAttribute('aria-label', 'Total Today')`. Both the visible header and associated accessibility label should become `CCost Today`. The following CCost, prompt count and Token Mix elements must remain unchanged.
- `docs/web-mini-watch.md` currently describes the `~` marker for CTX and the `Total Today` heading; `docs/web-beta.md` describes the full-Watch `Total Today` line. Update these **current guides** for the new labels and CTX appearance. Keep historical completed specifications intact.

## Required change and scope

1. Render the already formatted CTX display value **without prepending** `~` for an available numerical estimate. Do not remove signs/characters that are genuinely part of a returned format; only remove the Mini Watch-added approximation prefix.
2. Keep the **CTX header tooltip and accessibility meaning** explicit that the context figure is **estimated**, not an exact measurement. Keep `N/A`, missing/unknown figures and any other actual source-state semantics intact.
3. Preserve number grouping, rounding, selected units where applicable, dynamic updates, table resizing/intrinsic metric-column sizing, right alignment, row colors and keyboard/focus behavior. Do **not** change the context estimator, data projection, source, server, polling, SSE ownership, daily/account logic or Mini Watch window geometry.
4. Do not globally strip tildes, change CTX in full Watch or modify unrelated `~` uses (for example duration/provenance/other estimates). Make the minimal Mini Watch-only CTX change.
5. Replace **only the intended global daily summary labels** with `CCost Today` in Mini Watch and full Watch, including Mini's loading state and Watch's existing accessible section name. Preserve the exact existing formatted cost, prompt count, Token Mix, daily state/retention semantics, click/focus behavior and layout. Do not rename unrelated headings, alter the account cards or apply a blanket replacement across historical files.
6. Update the current Mini Watch and full Watch documentation and their focused rendering/accessibility tests. No backend or daily acquisition changes.

## Acceptance

- In Mini Watch a known CTX estimate is displayed as its **formatted number with no added leading `~`**; numeric values updating between publications follow the same rule.
- `N/A` and legitimate unknown states are unchanged. Header hover/focus still explains `Estimated next incoming context for this prompt; N/A means unavailable`; accessibility remains meaningful.
- Existing metric-column intrinsic sizing and narrow-window horizontal scrolling from FR000569 remain correct when CTX text becomes slightly shorter. Full Watch's **CTX values, data, Token Mix and layout** remain unchanged apart from the expressly requested daily label.
- **Mini Watch:** the visible daily summary starts with `CCost Today` instead of `Total Today`, both before data arrives and with known cost/prompt data. The cost and `N prompts` portion, canonical day scope, no-data/loading, partial/retained and rollover behavior remain identical.
- **Full Watch:** the daily summary row starts with `CCost Today`; the prompt count and Token Mix categories still follow with the same values/formatting, including partial and unavailable states. Its `aria-label` and any directly matching accessible heading reflect the new wording. Other Watch pages/metric labels are not renamed.
- Extend or adjust the **existing focused Mini Watch rendering tests** (such as `development/tests/integration/mini_watch.cjs` and `development/tests/integration/probe_mini_watch.cjs`) to verify visible CTX text, tooltip and daily header in loading/observed states. Extend existing full Watch daily-row/accessible-name tests to verify the new text while retaining numeric and Token Mix parity. Run relevant product and repository validation without weakening existing assertions.
- Update `docs/web-mini-watch.md` and the full-Watch daily section of `docs/web-beta.md`, making no retrospective edits to completed FRs.

**Authoring boundary:** This is an in-place revision of the already published FR 000571. Preserve its permanent ID, Ready priority 000110 and identity-state watermark; update only this FR file on `main`. Do not implement, change version/history, produce a release, modify the running Web Beta, or introduce unrelated fixes during FR editing.
