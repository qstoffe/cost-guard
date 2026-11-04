# FR 000580 — Full Watch: compact Session Context / CCost summary and distinct price-threshold severity

## Owner request and backlog decision

**Owner-approved executable feature request, 2026-11-04.** Permanent identity **000580**; Ready priority **000200**, following the existing Ready FR000578 (000180) and FR000579 (000190). Scope is **Cost Guard Web Beta → full Watch**, for the summary shown immediately below each **Running Prompts** and **Earlier Prompts** card/table. This is an authorized backlog FR, **not implementation in the authoring session**.

FR000572 introduced a line such as `Session Context: 190K · Session CCost: 328`, with an inline price-threshold warning. The owner wants less repetition, a single concise context/cost expression, a duplication bug fixed, and a **clear visual distinction between approaching a price tier and actually crossing it**. The session CCost amount is not itself subject to the context-price threshold.

## 1. Combine the summary label and values

Use **one logical summary line** below each full Watch prompt table, with exactly one shared label followed by both values:

- **Normal:** `Session Context / CCost: 190K / 328`
- **Approaching:** `⚠ Session Context / CCost: 242K / 328 (Approaching price threshold >272K; 1.9x more expensive)`
- **Exceeded:** `[red stop/octagon ! icon] Session Context / CCost: 290K / 328 (Price threshold >272K exceeded; 1.9x more expensive)`

All quantities/thresholds above are illustrative; use authoritative formatted application data, not these hardcoded numbers. Display the **actual context value** before the slash and the **full-session CCost** after it. Do not repeat `Session` for the second metric or retain `· Session CCost:`. Keep `CCost` exactly as the project spells it.

The summary's **context** is the estimated next incoming context for the latest valid session continuation (not prompt-local `ECTX` or `Δ Ctx`), and the **CCost** is the same canonical entire root/session-tree total as before (not per-prompt price, a quota, or billed cost). Preserve available/unknown/partial/loading cost and context states, existing Credits/USD formatting, cached totals, current-session ownership, and full details/accessible help. At narrow widths wrap naturally without hiding a figure or warning; no extra columns/rows or separate warning footer.

## 2. Fix duplicate “Approaching price threshold” and simplify guidance

**Observed bug:** the full Watch renderer currently computes a prefix such as `Approaching price threshold` or `Price threshold exceeded` **and appends the canonical `warning.text`**, which already contains those words. In `src/web/assets/watch.js` `Card.drawSummary()` this produces a repetition like `Approaching price threshold: Approaching price threshold >272K`. Eliminate duplication for **both approaching and exceeded** severities.

- Render the relevant canonical warning **once**, inside **one outer pair of parentheses after both summary values**, with no repeated threshold label, extra colon, doubled punctuation, or unnecessarily nested parenthetical around the multiplier.
- Preserve the real threshold boundary/operator (e.g. `>272K`), the distinction between approaching versus exceeded, and whichever **canonical price impact** is supported: `1.9x more expensive` when a multiplier exists or the established next-input CCost range when that is the supported explanation. Do not fabricate or replace unavailable impact details.
- Prefer formatting structured semantic parts (warning kind, canonical threshold, multiplier/range, states) so rendering and color spans remain robust; if reusing canonical `warning.text`, avoid pre-pending text it already includes. Avoid changing canonical threshold logic or trying to infer warning severity from the formatted string.
- Tooltip and screen-reader output must also have **one** warning explanation, not a cleaned visual line with a duplicated accessible announcement.

## 3. Severity-specific icon, color and text emphasis

Keep the main summary **ordinary theme foreground color by default** in Classic and Web themes; use narrow inline color roles only as follows:

| Element | None | Approaching threshold | Price threshold exceeded |
| --- | --- | --- | --- |
| Leading icon | No icon | Existing recognizable **orange/amber warning triangle** | Distinct **red stop-sign/octagonal icon with exclamation mark** (or similarly unmistakable red stop/error glyph); **not** the amber triangle recolored |
| **Context numeric value** (`190K`, `242K`, `290K`) | Ordinary | **Orange/amber** | **Red** |
| **Relative-price multiplier text** (`1.9x more expensive`) | Not shown | Ordinary text | **Red** when available |
| `Session Context / CCost:` label, slash separator and **session CCost amount** | Ordinary | Ordinary | **Ordinary, never severity-colored** |
| Rest of warning explanation, including canonical price-threshold wording and boundary | Not shown | Ordinary | **Ordinary** |

Choose the stop icon so its red appearance is reliable and themeable (e.g. a small inline SVG/icon with a red octagonal outline and exclamation symbol), instead of depending on OS-specific emoji color. Both warning icon types must have meaningful accessible severity names, and the textual **Approaching** / **exceeded** explanation must remain visible so meaning does not depend on icon or color.

Do **not** apply severity color/weight to the **entire** `.watch-session-summary` for exceeded as the current CSS does. Specifically, **do not turn the full-session CCost number, `CCost` label, slash, or all warning text red**. If the impact is not a multiplier but a cost range, keep the range legible in normal text unless there is a separately justified semantic highlight; the owner's red-emphasis request specifically concerns the *relative multiplier*. The contextual numeric figure and only that figure receive severity color; the adjoining `K` or `M` unit belongs with the figure.

The price-warning is **about increased pricing of the next context beyond a model tier**, *not* a claim that accumulated session CCost exceeded a spending budget. Preserve this distinction in accessible help.

## 4. Investigated implementation surface, compatibility, and acceptance

Current main source shows:

- `src/web/assets/watch.js` creates `.watch-session-summary` with `warningIcon`, `contextLabel`, `warningText`, `costLabel`, `costStatus`. Its `drawSummary()` builds `Session Context: ...`, hardcodes `⚠`, composes duplicate text by adding a severity label to canonical `warning.text`, and appends ` · Session CCost: ...`.
- `src/web/assets/app.css` has `.watch-warning-icon` in warning color and `.watch-session-summary[data-severity="exceeded"]` coloring the **whole line** orange. Replace this with targeted theme-aware spans/icon styles for numeric context and multiplier.
- `src/analysis/context.py`, `src/reports/watch_context.py`, `src/application/display.py` already supply canonical warnings, severity, threshold text and formatted cost impact. Reuse, rather than alter, the canonical price-tier decisions and calculation.

Acceptance criteria:

1. Under **every running and earlier prompt card**, the summary is precisely one shared `Session Context / CCost: <context> / <cost>` structure. No redundant second `Session` label, missing values or additional warning footer.
2. An approaching warning has **an amber triangle and amber context number only**; all other inline content, including multiplier, cost and labels, uses ordinary theme-appropriate foreground. A normal row has no icon or warning coloring.
3. After **crossing the actual canonical tier boundary**, the icon becomes a visually distinct **red stop/exclamation icon**; only the context figure and any **`Nx more expensive`** multiplier become red. The label, separator, session cost, boundary text and remainder of the explanation stay neutral. When the context falls back below threshold, the severity and coloring change back atomically.
4. Both severities show the canonical explanation **exactly once**, including its threshold and available multiplier or alternate price range, with coherent punctuation and a single parenthetical after the paired values. No `Approaching price threshold: Approaching price threshold`, no analogous exceeded duplication, and no duplicate icon tooltip/ARIA reading.
5. Verify unknown context, near-boundary and exact crossing, disabled approaching threshold, no multiplier, missing/partial pricing, USD/Credits switching, compaction/model/epoch changes, source corrections, multiple concurrent cards of one session, and Earlier re-entry. No stale icon or old warning when current data changes.
6. Verify DOM/style, readable contrast and focus/ARIA in **Classic**, **Web light** and **Web dark**, and at narrow widths, without changing prompt-table metrics, history ordering, activity details, existing one-stream Live behavior or canonical cost caching. Update existing focused Web Watch/browser fixtures (including `development/tests/fixtures/watch_context_browser.cjs` and related regression checks) and `docs/web-beta.md` / current module documentation after implementation.

**Out of scope:** Mini Watch's own tables/CTX, Sessions report pages, CLI Watch, CCost valuation, actual pricing thresholds, backend data acquisition/caching, full Web theme redesign, changing user settings/defaults or shipping product changes while writing this FR. Do not rewrite the historical completed FR000572; this newly approved FR supersedes **its summary text/color presentation only**.
