# FR 000582 — Web Beta: application-wide tooltip UX and content overhaul

## Owner request and backlog decision

**Owner-approved executable feature request, 2026-11-04.** Permanent identity **000582**; Ready priority **000220**, after the current Ready FR000581 (000210). Scope: **every user-facing tooltip, hover/focus help, explanatory popover and equivalent contextual hint in the entire Cost Guard Web Beta application, including its separate Mini Watch window**. Write this as an approved Ready FR only; **do not implement product changes in the authoring session**.

The owner finds existing tooltip prose overlong, repetitive, technical, difficult for first-time Cost Guard users, and visually hard to scan. The particularly problematic full Watch **CCost (I + E)** and **Token Mix %** headers are dense walls of text. The full Watch **Model** header currently says **"Canonical focal model; additional model contributions remain included in cost, calls and token mix."** — technically suggestive but unhelpful for people new to AI. Mini Watch tooltips also commonly expose the text-selection I-beam cursor instead of the more appropriate contextual-help cue.

**The goal is a genuine, consistent UX/content audit of all current Web tooltips and a reusable standard for all future ones**, not a narrow edit of three strings or a CSS-only line-break patch. Preserve underlying metric semantics and important disclosures while making the explanations easy to read, short and actionable.

## 1. Shared content and visual design principles

1. **Write for a beginner.** Start with the plain-language answer to **"What am I looking at?"**, not implementation concepts like *canonical*, *focal*, *projection*, *root-tree*, *attributed physical model request* or *telemetry*. Explain AI/Cost Guard terminology without assuming prior familiarity. Retain precise advanced information only if it changes interpretation or prevents a misleading conclusion.
2. **Keep it short and sharp.** Prefer one short introductory sentence, then small named lines where there are multiple parts. Eliminate duplications, long caveat chains, needless self-reference and paragraphs that require re-reading. Do not make all tooltips uniformly long: a simple field can use one sentence; a four-part metric can use a concise four-line explanation.
3. **Use intentional line breaks.** Separate distinct ideas, parts, statuses and examples into individual lines; modest blank-line spacing is allowed when it improves grouping. A compact optional label/value structure, short bold labels or subtle separators are fine. Avoid arbitrary hard-wrapped lines, unnecessary bullet overload or large tooltip cards. The content should still wrap on narrow viewports/zoom.
4. **Make formatting reliable in every supported browser.** HTML `title` *can* contain newline characters, but the browser controls rendering and accessibility is inconsistent. For explanatory/multiline help use **one shared, semantic, custom tooltip/help-popover implementation** (or a small number of reusable variants with identical behavior), with structured DOM or text and `white-space: pre-line` / `pre-wrap` where appropriate. Do not rely on browser-native `title` for essential rich or multiline instructions. Avoid displaying a native `title` tooltip **and** a custom popover for the same explanation.
5. **Optional icons:** small, purposeful icons can reinforce a warning, estimate or other semantic difference, but never be the only explanation. No decorative icon clutter or visually noisy full-feature panels. Match Classic / Web light / Web dark and Mini surfaces and contrast.
6. **Show only relevant information.** Keep crucial **`N/A` = unknown/unavailable, not zero**, `?` = partial price/coverage, provisional/estimated/retained data, Credits/USD vs native quota, prompt vs session scope, and reference CCost vs billing where relevant. Explain them once and in the right place; no heavy technical diagnostics on a basic model/header tooltip. Preserve accessible advanced/source details via a concise optional help/disclosure when they genuinely matter.

## 2. Required concrete examples — edit the wording professionally

These are **content/structure examples, not exact mandated final copy**. The implemented English UI can refine phrasing after checking existing source semantics, but must be equally beginner-friendly and line-separated.

### Full Watch: CCost (I + E)

Today the tooltip is an unwieldy paragraph about reference pricing, first attributed requests, non-billing, token-category ambiguity and incomplete coverage. Replace with an easy-to-scan pattern, e.g.:

```text
CCost is the estimated reference cost of this prompt, not your actual bill.

I — Input context cost on the prompt's first model request.
E — Other cost: generated output, later requests and linked subagents.
Total = I + E (small differences can come from display rounding).

N/A — Cost information is unavailable, not zero.
? — Part of the cost cannot be priced.
```

- Preserve the precise existing definition: **I** is first attributed model request's incoming-context **CCost** (not the **I = Input tokens** category of Token Mix); **E** is remaining prompt-attributed reference-price usage, including subsequent/model output and causally linked children. Neither is an actual provider bill. When required, a tiny clarifier can distinguish the two meanings of `I`.
- Never imply that incomplete pricing balances perfectly, that all child work is always known, or that `N/A` means zero. Keep selected Credits/USD and current `CCost (I + E)` column value behavior.

### Full Watch: Token Mix %

Today the tooltip mixes categories, coverage and backend details in one long paragraph. Use a short opening and one line per component, matching the **existing I/C/W/O order**, e.g.:

```text
Share of the prompt's tokens: I / C / W / O.

I — Input: new input tokens sent to the AI.
C — Cached input: previously processed input reused.
W — Cache write: input saved for later reuse.
O — Output: tokens generated by the AI, including reasoning.

N/A — A reliable token breakdown is unavailable.
```

- Clarify that these **are percentages of tokens, not CCost or billing**, and that the segments are presented in I/C/W/O order; preserve partial/unknown rules. Keep any crucial distinction between the token categories accurate, using short accessible words rather than specialist telemetric prose.

### Full Watch: Model

Today: `Canonical focal model; additional model contributions remain included in cost, calls and token mix.`

Replace with plain-English explanation, e.g.:

```text
The AI model used for the main prompt.

If this prompt runs subagents, their work is included in the
prompt's CCost, Calls and Token Mix, even if they use different models.
This column still shows the main prompt's model.
```

**Verified source behavior (current main):** `src/analysis/causal.py::build_prompt_record()` starts with the root prompt's entries and adds causally linked child/subagent entries from `_task_invocations()`/`_child_work()`; `src/reports/prompt_rows.py::PromptProjector.prompt()` prices `record.entries` together for prompt CCost and derives the displayed Watch model from `record.main_model_id`. `src/reports/semantics.py::prompt_has_additional_model()` detects differing models among those entries. Consequently, the model shown need **not** represent every model that contributed to the prompt's costs. **This distinction must remain explicit in the tooltip** so users are not misled by a one-model label alongside multi-model totals. Qualify gracefully for unsupported/unpriced/unlinked work; do not promise unseen or unattributed work has been counted.

### Mini Watch: first-column and session/account help

Shorten the verbose session title/whole-session-cost tooltips and long subscription quota/status strings. Lead with user-relevant scope, e.g. `Session CCost — The total estimated cost of this entire session, including earlier prompts and linked subagents. Not your bill.` If a full title is visually truncated, make it easily available verbatim as before, separate from optional diagnostics. Put freshness, missing pricing, native quota-versus-CCost attribution and source status on separate short lines **only when relevant**. Keep `Ctx`/prompt versus earlier-session meaning intact.

## 3. Audit the whole Web app and standardize future tooltips

Inventory and rewrite **all user-facing tooltip/help content across every Web view** rather than only the examples:

- **Full Watch:** all table headings (Started/Finished, Duration, Prompt, Model, Effort, CCost, Calls, Token Mix, Ictx, Δ Ctx), price-threshold details, prompt previews, session totals, daily/primary quota and native reset details, hover/status help, activity, historical states.
- **Mini Watch:** both tables, the first column/full-title/full-session-cost help, CCost/Ctx/Duration headings, history disclosure, daily CCost, account/quota bars, warnings, observation/retained-data hints, and return-to-tab behavior.
- **Models, Sessions, Accounts, Reports, Token Mix, settings, navigation and status surfaces:** sorting/filter/checkbox descriptions, model/pricing evidence, cost/help labels, account/quota states and any existing contextual hints or native `title` explanations.
- Audit both **custom help/popovers** and simple **native `title` attributes**, `aria-description`, tooltip-role content and dynamically generated status hints. Important actual data (e.g. a truncated full prompt, exact date/time, full session title) must remain accessible, and a succinct one-line metadata reveal need not become a bloated rich popover; document any justified exception. Fix inconsistent terminology, misleading scopes, outdated copy, redundancies and duplicated overlapping tooltip mechanisms.
- Create a short, project-owned **tooltip writing/interaction guideline** for future work, with clear patterns and examples (when to use one line vs sections, plain-language default, optional advanced detail, how to explain unknown/partial values, contrast, icon policy, keyboard/touch behavior). Reuse one helper/style vocabulary to discourage future drift rather than duplicating strings/tooltip JS in each screen.

## 4. Tooltip interactions and cursor semantics

- On a **passive help target**, adopt the standard **`cursor: help`** indicator (usually arrow with a question mark) consistently in Full Watch and Mini Watch. The present `cursor: text` I-beam on Mini help headings/targets is misleading. Consider a tiny visible help cue or dotted underline where discoverability benefits; tooltip availability must not be discoverable **only** by cursor change.
- **Do not globally override cursor behavior.** Keep `pointer` on actually clickable links/actions and `text` where users should select/copy text. If an element is both selectable data and help, provide an unobtrusive, explicit adjacent help trigger or equally clear accessible behavior instead of breaking text selection.
- Follow established **WCAG 2.2 1.4.13** and WAI-ARIA tooltip guidance: appear on pointer hover and keyboard focus; dismiss via **Escape** without moving pointer/focus; remain visible long enough to read and while moving the pointer into the tooltip; close reasonably on pointer/focus exit; no keyboard focus trap or tooltip content with interactive controls under `role="tooltip"` (use a suitable nonmodal dialog/disclosure for truly interactive advanced content).
- Touch users need a reliable tap/focus help affordance; no hover-only explanation. Use consistent close/light-dismiss behavior, avoid opening two tooltips simultaneously and avoid re-triggering on ongoing renders or focus-preserving updates.
- Keep accessible relationships accurate (`aria-describedby` to concise readable tooltip content, labelled focusable trigger, no repeated text announcements from both `title` and ARIA, correct full-value fallback). Tooltips should be readable with keyboard, screen reader and zoom. If a tooltip carries critical status, do not make it the sole place the status appears.

## 5. Existing implementation notes and non-goals

Inspected current main on 2026-11-04:

- `src/web/assets/watch.js::columns` contains the exact dense **CCost (I + E)**, **Token Mix %** and **Model** descriptions. `columnHeader()` renders a `role="tooltip"` native Popover *and also attaches `button.title = explanation`*, potentially causing duplicated browser/custom help. `src/web/assets/app.css` already sets `cursor: help` for `.watch-column-help`.
- `src/web/assets/mini.js` relies heavily on per-cell and dynamic native `title`/ARIA text; `sessionRow()` additionally supplies a Popover for the session title, while `src/web/assets/mini.css` lacks a corresponding consistent help cursor for passive Mini help targets.
- `src/web/assets/render.js` and `src/web/assets/app.js` contain additional `title`-based hints (filters/sorting, model evidence and host status); `src/web/assets/settings.js` has field explanations; `index.html` includes host warning help. **Do not assume these are an exhaustive inventory**; inspect all pages, generated components and tests.
- Relevant external references: [MDN: HTML `title` and its multiline/accessibility behavior](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/title); [MDN: CSS `cursor`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/cursor); [W3C: WCAG 2.2 SC 1.4.13](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html); [W3C WAI-ARIA tooltip pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tooltip/) (pattern is work in progress; honor its useful behaviors without assuming universal implementation rules).

**Dependencies/coordination:** This FR follows the queued **FR000578** (Mini column alignment), **FR000579** (Mini Web themes), **FR000580** (Full Watch summary/warning design) and **FR000581** (Ictx/Ctx nomenclature). Use their **new** presentation conventions/terms, do not revert them by reintroducing older tooltips or all-caps headings. Shared UI work must preserve Classic/default appearance, Web light/dark and native PiP boundaries.

**Out of scope:** changing data, source/history acquisition, model selection, causal cost attribution, provider pricing, quota calculations, CLI, user preference defaults, adding analytics/telemetry, new background requests or forcing every basic title/date reveal to become a large interactive panel. Keep the app secure (same-origin resources, existing CSP, no HTML injection from titles/provider strings, no credential disclosure), fast (one bounded helper, no per-row expensive work), and compact.

## 6. Acceptance and verification

1. **Audit completed:** a documented inventory covers tooltip/help entry points on all Web Beta views **including Mini Watch**, and all in-scope text has been reviewed/rewritten or an intentional concise/metadata exception documented. New tooltip conventions are written down for future authors.
2. **Content quality:** no unexplained *canonical focal model* jargon in beginner help; the prompt model/subagent accounting caveat is correct and prominent; CCost and Token Mix have readable, concise, explicit **line-broken descriptions** in the required order and preserve the important N/A/partial/billing distinctions. Existing data are not changed.
3. **Visual/structural:** multiple lines and occasional intentional spacing render faithfully across browser and Mini, without one long uninterrupted paragraph, runaway width, clipped lines, overlapping tooltip surfaces or duplicate native-and-custom popups. Simple fields remain brief.
4. **Interaction:** each applicable help trigger has sensible cursor/help affordance, keyboard focus, hover, Escape, pointer transfer to tooltip, touch activation and dismissal. Help on Mini no longer defaults to a misleading text-selection cursor when the intended action is help; actual selectable values and clickable controls keep correct cursors.
5. **Accessibility and stability:** clear ARIA label/description, no duplicate screen-reader announcements, correct text on changed values/units/theme and fresh/retained state, focus not stolen, sticky headers, zoom and resize including 560×250-DIP Mini. Contextual warning truth, prompts/sessions scope and all screen-reader-only explanations remain available.
6. Verify representative **Classic, Web light and Web dark**, keyboard/mouse/touch paths and real browser hover/focus behavior in both full Watch and Document PiP. Include exact full-title/date reveals, negative/unknown/partial/billing cases, subagent with a different model, and all screens' tooltip entry points. Update focused Web JS/browser and Mini browser tests without inventing a permanent new product gate.

**Authoring boundary:** Publish the FR in Ready and advance the identity watermark only. No source-code, release/version/history, user-doc or test changes in this authoring session.
