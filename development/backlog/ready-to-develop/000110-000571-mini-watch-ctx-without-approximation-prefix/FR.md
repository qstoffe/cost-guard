# FR 000571 — Remove the approximation tilde from Mini Watch CTX values

## Owner request

**Owner-approved executable FR, 2026-11-04.** Permanent identity **000571**, Ready priority **000110**, following the existing Ready FR000570.

In **CostGuard Web Beta → Mini Watch**, the **CTX** column currently displays a leading `~` before numeric context-token values to indicate an estimate. **Remove that visible `~` prefix.** The existing **CTX column-header tooltip already explains that the value is estimated**; keep that explanation instead of repeating the approximation marker in every cell.

Example: `~123 456` should appear as `123 456`, preserving the application's actual number format and value. `N/A` and other genuine unknown/unavailable states must keep their current meanings.

This is a small, presentation-only change **specifically to Mini Watch's CTX cells**, not a change to context calculation or the full-size Watch page.

## Confirmed implementation context

Inspected current `qstoffe/cost-guard` `main`, `src/web/assets/mini.js`:

- `View` builds the CTX header with the existing tooltip `Estimated next incoming context for this prompt; N/A means unavailable`.
- `drawPrompts` already formats the intended value with `display(item.live_context, 'watch_next_context_tokens')`, then adds the `~` in this presentation expression:
  ```js
  const context = display(item.live_context, 'watch_next_context_tokens');
  const cells = ['#' + prompt.prompt_number, display(prompt, 'ccost'),
    display(item, 'watch_duration_ms'), context === 'N/A' ? context : '~' + context];
  ```
- `docs/web-mini-watch.md` currently describes the `~` marker for CTX. Update this **current guide** to describe the new display and the existing estimate tooltip. Keep the historical FR000569 and other completed specifications intact.

## Required change and scope

1. Render the already formatted CTX display value **without prepending** `~` for an available numerical estimate. Do not remove signs/characters that are genuinely part of a returned format; only remove the Mini Watch-added approximation prefix.
2. Keep the **CTX header tooltip and accessibility meaning** explicit that the context figure is **estimated**, not an exact measurement. Keep `N/A`, missing/unknown figures and any other actual source-state semantics intact.
3. Preserve number grouping, rounding, selected units where applicable, dynamic updates, table resizing/intrinsic metric-column sizing, right alignment, row colors and keyboard/focus behavior. Do **not** change the context estimator, data projection, source, server, polling, SSE ownership, daily/account logic or Mini Watch window geometry.
4. Do not globally strip tildes, change CTX in full Watch or modify unrelated `~` uses (for example duration/provenance/other estimates). Make the minimal Mini Watch-only change and update its user guide.

## Acceptance

- In Mini Watch a known CTX estimate is displayed as its **formatted number with no added leading `~`**; numeric values updating between publications follow the same rule.
- `N/A` and legitimate unknown states are unchanged. Header hover/focus still explains `Estimated next incoming context for this prompt; N/A means unavailable`; accessibility remains meaningful.
- Existing metric-column intrinsic sizing and narrow-window horizontal scrolling from FR000569 remain correct when CTX text becomes slightly shorter. Full Watch remains unchanged.
- Extend or adjust the **existing focused Mini Watch rendering tests** (such as `development/tests/integration/mini_watch.cjs` and `development/tests/integration/probe_mini_watch.cjs`) to verify visible CTX text and tooltip, with appropriate normal and unknown-value fixtures. Run relevant product and repository validation without weakening existing assertions.
- Update `docs/web-mini-watch.md`, making no retrospective edits to completed FRs.

**Authoring boundary:** Publishing this FR and the exact backlog identity-state update is documentation-only. Do not implement, change version/history, produce a release, modify the running Web Beta, or introduce unrelated fixes during FR creation.
