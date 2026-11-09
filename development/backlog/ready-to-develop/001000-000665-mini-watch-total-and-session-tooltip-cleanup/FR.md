# FR 000665 — Mini Watch: simplify Total and Session tooltips, hide Total's partial-pricing marker

**Owner-approved Ready Feature Request, 2026-11-10.** Permanent identity **000665**, Ready priority **001000**, after FR000664 (000990). **FR-only publication:** add this file and atomically advance `development/backlog/identity-state.json` highWatermark **664 → 665** on `main`. No product-code, tests, version/release, unrelated backlog or source-data changes in this documentation commit.

## Owner complaint and intended result

The **Cost Guard Web Mini Watch Document Picture-in-Picture** window has a unified five-column table `Activity | Session | CCost | Total | Ctx`. The **CCost** value correctly represents the selected/current representative **prompt** and its rich prompt-specific tooltip is useful; **do not change that tooltip**.

However, the **Total** value represents the **whole session**, while its tooltip currently misleadingly repeats that **one prompt's** number/model/effort/duration. The owner prefers **no value tooltip whatsoever on Total**. The **Total column heading tooltip** should contain just its existing opening sentence and nothing else. The **Session** value tooltip should give the full session title and the representative prompt's number and first 25 characters of its supported preview, without the redundant phrase `in this session`.

Separately, the owner does **not** want a visible **`?` partial-pricing prefix on the Mini Watch Total amount**. Show the source-backed known priced session subtotal normally without repeating that qualification in the displayed Total; do **not** change CCost's existing behavior or pretend genuinely unavailable cost is zero.

### Desired user-facing example

```text
Mini Watch
Activity  Session                    CCost    Total    Ctx
21:20     My coding session          ?12      148      172k
```

**The amounts above are illustrative only.** The CCost column deliberately retains its own established display and tooltip; only Total's `?` is suppressed. The value of Total continues to represent the entire canonical root session, including any properly attributed linked subagents.

Hover/focus the **Total column header**:

> The entire session’s reference cost, including attributed linked subagents.

Hover/focus the **Session cell**:

```text
My coding session's full title
Prompt #21: Implement pagination for…
```

**Total cell value:** plain readable/selectable text, **no tooltip at all** on mouse hover, focus, click or touch.

## A. Remove the misleading Total value tooltip completely

1. In `src/web/assets/mini.js::View.sessionRow()`, **keep** `ContextHelp.value(promptCost, () => row.costHelp)` on **CCost** (third column). **Remove** `ContextHelp.value(sessionCost, () => row.totalCostHelp)` on **Total** (fourth column) and do not install a replacement native `title`, `ContextHelp`, info icon or row-level hover.
2. Remove the now-dead `row.totalCostHelp` construction in `View.rowHelp()`. In particular **never call `this.promptDetails(...)` for the Total value**, because it adds the representative prompt's model, effort, prompt number, duration, calls and related prompt-specific state to a whole-session amount. Do not replace it with another elaborate whole-session popover.
3. Keep the Total amount in a normal noninteractive text element, maintaining existing CSS, five-column width, text selection, color, source-prepared unit changes, and an accessible factual `aria-label` if useful (e.g. `Whole-session reference CCost: 148`). Remove leftover `help-value` class, `tabindex=0`, popover bindings and interactive affordances from this one cell. Do not strip keyboard help on the **column header**, on **CCost**, on **Session**, on **Activity** or on **Ctx**.
4. The old requirement in FR000654 that **both** CCost and Total value tooltips show a highlighted running `Duration` is **explicitly superseded for Total only**: no Total value tooltip exists anymore, so there is nothing to tick/highlight there. The **CCost tooltip's** yellow running-Duration fragment and existing live updates are unchanged.

## B. Total column header: exactly one sentence

The tooltip attached to **the Total heading** (the header remains keyboard/hover/touch accessible through its existing help control) must be exactly:

```text
The entire session’s reference cost, including attributed linked subagents.
```

This is the current first clause converted to its own complete sentence. **Remove everything after `linked subagents`:** specifically `not provider billing. N/A means unavailable; ? means partial pricing.` and any equivalent trailing messages. Do not make the heading tooltip a substitute for the removed Total cell tooltip.

Keep the separate **CCost header** text as it is. Do not change global help texts in other sections, provider billing explanations or other columns.

## C. Mini Total amount: silently omit partial `?`, preserve known subtotal

**Verified source behavior:** `View.drawCost()` currently displays `ReportView.display(cost, 'known_ccost')` for a session summary with priced work, and `src/application/display.py::amount_tokens()` formats `known_ccost` with `unresolved = !values.complete`, which can produce `?562` despite a legitimate known subtotal of 562. The existing `drawCost()` already returns `N/A` for an observed session with zero priceable requests and `Loading…` when summary evidence is pending.

**New Mini-only display contract:**

- When the **canonical whole-session known priced subtotal** exists (including when some requests are unpriced), show the usual formatted number **without `?`**: e.g. `?562` becomes simply `562` in the **Mini Total cell only**. This is the owner's explicit preference to ignore that *visible qualifier*; it does not mean the missing part was priced.
- **Do not** remove the prefix globally or change raw canonical `known_ccost`, `complete`, `observed_requests`, `priced_requests`, source revision, Cost Guard CCost reference-calculation semantics or how **CCost** or Full Watch/Accounts/CLI show uncertainty. The known subtotal must not include made-up costs for absent request pricing.
- Prefer an existing **server-prepared, unit-correct, prefix-free known subtotal display token** (if its provenance/zero/unavailable semantics match) or a narrowly scoped Mini presentation field. Do **not** implement brittle string manipulation of `?...` text, guess USD/Credit units in JavaScript, round raw values client-side or coerce unknown to zero.
- Preserve `N/A` when no amount can honestly be calculated (including observed requests with **no priced request**), `Loading…` while source evidence is pending, and **real zero** when the supported completed source actually proves zero. Preserve actual unit switches and the whole-session/subagent attribution; do not accidentally display current prompt cost in Total.

## D. Session cell tooltip: full title, direct prompt number and 25-character excerpt

In `View.rowHelp()` keep the **first line** as the **full untruncated session name** (fallback to stable session ID when no title). On the next line use:

- `Prompt #21: <preview>` when a legitimate prompt number **and** supported preview exist.
- `Prompt #21` when numbered but no supported preview exists, without a trailing empty colon.
- `Prompt number unavailable` when the number is missing (and, if a supported preview genuinely exists, present it under a short `Prompt: ...` label). Never invent a number or expose a raw prompt because the preview is unavailable.

**Remove the literal phrase `in this session`** and its awkward grammar from the prompt-identity line. Do not repeat `Prompt preview:` when a normal `Prompt #N: ...` line is already present.

The existing `promptPreview(prompt)` helper already uses `Intl.Segmenter` to normalize whitespace, cap content to **25 visible Unicode grapheme characters** (no split emoji/combining marks), avoid unsupported/compaction previews and append a single `…` only if text was **actually shortened**. **Reuse that helper** rather than introduce another source fetch, a UTF-16 substring bug or duplicate trailing periods. Keep textual HTML-like input literal, not interpreted markup; no full prompt export. A 25-character/emoji-safe bounded preview is a presentation-only excerpt, not a new permission to retrieve prompt content.

Keep Session title truncation in the table cell as it is; only the tooltip contains the full title and compact prompt identity/preview. Preserve existing running/historical representative selection and updates to an already open Session tooltip.

## E. Coordination and acceptance

**Scope:** `src/web/assets/mini.js` is the primary code owner; check `src/web/assets/mini.css` and `src/web/assets/help.js` only if necessary for noninteractive Total semantics. `src/application/display.py` is relevant for the source-prepared cost display token but should **not** have its global financial formatting changed for this FR. Update `docs/web-mini-watch.md` and the narrow existing Mini tests during implementation; completed historical FR000654 remains untouched.

**Acceptance criteria:**

1. The **Total column header** tooltip contains **exactly** the single sentence above; no N/A / `?` / partial pricing / provider-billing appendix. The header help still opens by hover/focus/touch and closes normally.
2. **Total cell values** have no popover on hover, keyboard focus, click or touch; no `ContextHelp.value` target, leftover `tabindex`, tooltip `title` or prompt-specific text. Values remain readable, selectable and accessible, including `N/A` and `Loading…`.
3. **CCost value tooltip** is unchanged, including prompt ID, model, effort, calls, running Duration highlighting, cost groups and honest prompt-specific partial/unknown semantics. The CCost header is unchanged.
4. Where the correct known whole-session cost is `?562` due to incomplete pricing, **Mini Total displays `562`**; where no priceable cost exists it still displays **`N/A`**, and source pending still displays **`Loading…`**. Test normal Credits/USD, known zero, partial and complete costs, linked-subagent totals, recent grace and historical rows. Underlying source data/complete flags do not change.
5. Session value tooltip is exactly `<full session name>\nPrompt #N: <25-char preview>…` for truncated previews, with **no `in this session`**. Test shorter (no false ellipsis), exact 25, longer than 25, ZWJ emoji, combining accents, whitespace and literal HTML-like text; no missing prompt-number fabrication or prompt-text fetch.
6. Existing focus/selection and already-open Session/CCost help update correctly through SSE, completion/resumption, source corrected values and Credits/USD changes; no stale hidden Total help survives. No changes to Activity, Ctx, account Mini rows, native PiP resizing/scroll, five-column layout, Full Watch or cost calculation.
7. Update `development/tests/fixtures/mini_sessions.cjs`, `development/tests/integration/probe_mini_help.cjs`, `probe_mini_duration.cjs` (which currently expects **two** running-duration tooltips), and relevant focused Cost Guard browser tests. Replace the previous two-tooltip assertion only for **Total**; **do not weaken CCost's** duration/hover/focus/touch regression coverage. Real Document PiP check in Classic/Web light/dark, narrow width and keyboard/touch, plus synthetic source data, without paid model calls.

**End state:** Mini Watch's CCost tooltip remains useful for the represented prompt; the **Total value is quiet and plain** with a concise header definition, and Session's tooltip presents the full name plus the compact `Prompt #N: excerpt…` line.
