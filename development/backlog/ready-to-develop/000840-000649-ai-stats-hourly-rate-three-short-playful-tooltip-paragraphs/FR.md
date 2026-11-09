# FR 000649 — AI Stats: make AI Hourly Rate tooltip short, three-part and genuinely funny

**Owner-approved Ready Feature Request / UX copy polish, 2026-11-09.** Permanent identity **000649**, temporary Ready priority **000840**, following currently Ready FR000646 (000810), FR000647 (000820), and FR000648 (000830). **Backlog authoring only:** create this FR plus increment `development/backlog/identity-state.json` highWatermark **648 → 649**, in one documentation-only commit. No product source, tests, current docs, settings, version/release or unrelated backlog edits now.

## Problem: the original playful AI Stats spirit got lost in one tooltip

**Cost Guard Web → AI Stats → first Overview card, “💸 AI Hourly Rate”** now contains the three correctly differentiated figures introduced by **completed FR000644**:

- **24h average:** period CCost spread over nominal 24-hour calendar days.
- **Workday average:** that same period CCost spread over eight scheduled hours per eligible workday, excluding configured weekends/holidays.
- **Robot · 8h shift:** a **hypothetical eight-hour fully active AI/robot shift** at the period's actually observed/best-effort **cost per active AI execution hour**, **not** Workday average × 8.

These are the right three concepts, and **the owner wants to keep all three numbers, the labels, calculation semantics and playful trait**. The problem is the **tooltip**: it was made much longer, more technical and more formula-heavy than the other nine cards. It currently contains literal divisions, calendar-hour counts, active-hour counts, selected-period totals, mathematical equals signs, rolling-window caveats and an imaginary total for all shifts. That turns the otherwise fun page into a dull math lecture.

**Requested replacement: exactly three brief, separate paragraphs in the title tooltip, with exactly one blank line between paragraphs**, corresponding **one-to-one, in order**, to the card's three displayed values. Make the copy **funny, mischievous, slightly dystopian**, about tireless robots, the corporate payroll, the fictional replacement of humans, or the robot becoming too expensive to employ. The purpose is to make the person **smile/laugh**, not learn the calculation formula. **No formula block, long explanatory monologue, raw arithmetic or giant technical footnote** in the default tooltip.

The existing other cards have the desired spirit, such as **“Your token bonfire. Bring marshmallows.”**, **“The calendar’s boss level.”**, and **“The biggest robot party running at once.”** The first card should feel like it was written by the same mischievous narrator.

## Desired tooltip shape and voice

The standard tooltip is a **single existing ContextHelp panel** with precisely three short paragraphs, separated by `\n\n`, each naturally tied to its corresponding value. Prefer **one punchy sentence per paragraph**, at most **two short sentences** where genuinely useful. The metric names may be used as lightweight labels, but the text should feel like a joke, not three manual entries:

    24h: This robot charges rent even while you sleep. HR calls it productivity.

    Workday: Weekends and holidays are off the clock. The silicon payroll is feeling generous.

    Robot shift: At this rate, your replacement is already picking a desk.

**The above is a synthetic copy example, not mandated final wording or a factual statement about employment.** The target is dry, dark, slightly dystopian workplace satire. Another example for a **very expensive robot shift**:

    Robot shift: Breathe easy. At this price, the robot can't afford to replace you.

And for an idle / empty active-hour period:

    Robot shift: The robot hasn't clocked in. HR is still writing its job description.

In all three sections, keep the metric meaning **recognizable in ordinary language** with just a few words. The 24h paragraph is about spreading period cost around the clock; Workday is about spreading the same cost across a human eight-hour schedule with weekends/holidays excluded; Robot shift is a **hypothetical continuous eight-hour active AI day**, not the cost the period actually incurred per eligible workday. Avoid a joke so misleading it reverses that distinction.

**Preferred voice:** witty, irreverent, inventive, gently dystopian and concise; more “the robot has filed for your job” or “HR can finally relax — the robot is too expensive” and less “total ÷ 168 scheduled hours = …”. There is no requirement to repeat the exact same catchphrase on every selected period. **One clever punchline beats a dense wall of clever-sounding text.**

## Optional amount-aware robot joke — do it well, without fake facts

The owner specifically likes **different punchlines depending on whether a robot looks relatively cheap or ludicrously expensive**:

- **Cheap/low burn:** the robot may be a comically threatening bargain (“Your replacement has already submitted its timesheet.”).
- **Very high burn:** human employment humor turns reassuring (“Relax. Nobody's replacing you with a robot that expensive.”).
- **Middle / ordinary:** amusing neutral workplace satire without pretending to know the user's wage (“The robot wants a salary, a charging dock and a promotion.”).
- **Zero, no active-time basis, missing or weakly supported scenario:** humorous idle/uncertain wording, **not** a confident cheap-replacement comparison based on a meaningless zero.

**Where feasible and easy, choose the Robot paragraph from the existing canonical raw Robot per-eight-hour cost (or a consciously documented simple tiering of the original active-hour rate).** Use fixed deterministic tiers in canonical reference Credits, independent of whether Web currently displays USD or Credits, with boundary tests. Tune thresholds for useful variety with realistic project reference-cost ranges rather than inventing human salaries. The request is **about more entertaining copy, not numerical comparisons with real salaries**. The words “cheaper than you”, “replace you”, etc., are explicitly **fictional jokes** — Cost Guard has **no actual hourly wage, job security, employer HR or labor-cost data**. Avoid presenting any comparison to an actual user's compensation as verified evidence.

This tiering is an **enhancement to the tooltip's personality, not a new data-acquisition or financial feature**. If a fixed, well-crafted three-paragraph tooltip is objectively funnier/clearer than a complicated conditional system, a simple solution is acceptable; do not turn this small copy fix into a fourth metric, pricing model, preference setting or salary calculator.

## Verified implementation today and narrow integration point

1. **`src/application/ai_stats.py::rate_tokens()`** currently creates the three visible display tokens **`calendar_rate`**, **`workday_rate`** and **`robot_day`**, plus **`rate_help`**, a long string that concatenates the explanatory intro, detailed 24h division, rolling-local-date note, Workday-hours division, active-hours division, ×8, and hypothetical all-shift total. **This function is the primary place to replace the boring help copy.**
2. **`src/web/assets/ai-stats.js`** already attaches the **existing `ContextHelp.button('AI Hourly Rate', () => ReportView.display(retained.metric, 'rate_help'))`** and renders the **three separately labeled values** in an `.ai-stat-rates` container. Keep those DOM nodes, card count, order, and on-demand behavior. No replacement popover framework, hover icon, extra box, separate help icon for each number or expanded fourth row.
3. **`src/web/assets/app.css`** already applies **`.context-help { white-space: pre-line; }`**, so literal **`\n\n`** in the server-prepared `rate_help` can render the intended **one empty line between the three paragraphs**. Keep the same shared help typography, panel constraints, focus/touch/keyboard affordances and refresh behavior.
4. **`src/application/ai_stats.py::COPY['hourly-rate']`** already provides a separate playful short **trait line** and has existing active-hour thresholds. This FR targets **the long tooltip**, not removing/replacing the trait (which is already good) or changing the numeric rates. If conditionally choosing joke variants, share existing display-policy ownership and keep the trait independent.
5. **`src/web/assets/ai-stats.js::empty()`** has a **static hourly-rate fallback `rate_help`** that currently is a single explanatory paragraph. Update it to the same **three-paragraph playful style**, with an appropriate zero/idle Robot joke. The fallback must not reintroduce the prior wall of text or fake a running robot.
6. FR000644's former request to expose detailed equations and projected W-shift total in tooltips is **expressly superseded on this particular help surface by this newer owner UX decision**. The underlying numbers, raw facts and private analysis may stay as they are; no need to delete source metrics or break tests that validate actual arithmetic. **Do not expose an “advanced calculations” panel just to retain prose nobody asked to see.**
7. Existing **FR000633 fun-first AI Stats policy** prohibits audit-style diagnostics, `Partial/Unavailable/Observed/Estimated` disclaimers, missing-evidence essays and intrusive technical caveats. This FR reinforces that policy. The tooltip should not contain source/provenance lecture, selected-period clock math, raw divisions or a hidden technical appendix.

## Scope and behavior requirements

1. **Exactly three paragraphs** in the existing **AI Hourly Rate title's** help, one each for **24h**, **Workday** and **Robot shift**, in that order. One **blank line** separates paragraph 1/2 and 2/3. No introductory preamble, fourth paragraph, trailing unrelated section, separate workday-hours section, big monospace formula or list of every input value.
2. **Keep each paragraph very short:** aim for one succinct sentence / roughly **10–22 words** including a short label, only occasionally two concise sentences; the full tooltip should be readily readable **at a glance** and materially shorter than the current long help. Give the writers freedom to improve the examples while retaining meaning and humor.
3. **No detailed calculations in tooltip:** no `÷`, `×`, `=` formula chains, decimal bookkeeping, `168/720 hours`, holiday-count tables, W-shift totals, or repeated raw CCost figures. The figures are **already on the card**. Use an evocative sentence and, if necessary, a small “eight-hour shift” hint instead.
4. **Stay accurate at the concept level:** 24h covers all-day cost normalization; Workday spreads the **same period cost** across scheduled work hours excluding weekends and configured holidays, **not** a filter of actual costs; Robot 8h shift is an intentionally **hypothetical** continuous-active cost, **not the historical actual workday cost**. The humor cannot portray the third value as an observed bill or imply the user's actual personal wage is known.
5. **Use playful cheap/expensive conditional humor if it can be done with a small, dependable display-only tier rule**; condition on **raw reference Credits / real usable active-hour basis**, not formatted USD string, status messages, arbitrary local wages or current account quota. Include an obvious idle/zero variant so empty evidence does not produce “you're replaced” for a robot that never ran. Keep all variants equally short and three-paragraph.
6. **No change to data:** all existing 3 displayed values and their units, `hourly-rate` metric identity, underlying actual active-hour ratio, cost/workday calendar math, UTC/DST behavior, 5 period filters, source/scoped snapshots, selected Credits/USD, rounding and other nine AI Stats cards and their fun traits are unchanged. No new model calls, reports, tests of employer compensation, settings, external holiday API or background job.
7. **Dynamic and accessible:** if period/CCost display unit/actual rate changes while help is open, the correct three paragraphs update through the existing prepared `rate_help` and `ContextHelp.refresh` without stale jokes, lost keyboard focus, unwanted popup reopening, separate network request or a full card remount. The text stays literal plain text with preserved paragraph breaks and good contrast in Classic/Web light/dark.
8. **Tooltip stays optional:** do not print the joke paragraphs permanently in the card body, increase every other card's height, turn them into click-to-open panels or remove the original short trait text. Keep the three compact numeric rows and current mobile responsiveness.

## Acceptance tests / definition of done

- **Structure and length:** for all five AI Stats selections (Today, 7 days, 30 days, This month, All time) and both Credits/USD representations, `rate_help` has **exactly three non-empty paragraphs separated by exactly one blank line** (`\n\n`), with no leading/trailing empty paragraph and no bulky formula string. The actual `role=tooltip` rendering shows three visually distinct pieces of text, not one paragraph with `\n\n` printed literally; source updates preserve the breaks.
- **Copy quality:** each section briefly signals which of 24h/Workday/Robot it belongs to and uses light, slightly dystopian workplace/robot humor. It contains no four-line math explanations, wage claims, unaudited user-comparison facts, status/provenance caveats or pointless duplicate text from the card. Review the **actual English copy** and its rhythm, not only a regex/count assertion.
- **Varied scenarios:** use deterministic fixtures for **cheap/normal/expensive Robot**, **zero total**, **zero workdays**, **no active AI-hour basis**, and selected-period change. Cheap Robot makes a playful replacement joke; expensive Robot suggests the human is safe from its outrageous operating cost; zero/unsupported Robot does not claim to have hired/paid/benchmarked a nonexistent worker. If fixed-tier variants are implemented, verify boundaries, versioned display inputs and currency independence.
- **Invariants:** compare before/after raw numeric values and display tokens for all three rates, current `hourly-rate` trait line, other nine cards, period selection and full `AI Working Time` against existing tests; **only `rate_help` and directly related copy/fallback** change. No change to report acquisition, cost model, salary data, CCost accounting or card layout.
- **Browser and access:** use the existing **`development/tests/test_ai_stats.py`**, application display/projection tests, **`development/tests/integration/probe_ai_stats_states.cjs`** and **`probe_ai_stats_layout.cjs`** (or nearest current equivalents) to verify real hover, focus, touch, Escape, dynamic refresh, source-retained help, 360px and zoomed viewports in Classic/Web light/dark. No panel clipping/scroll sprawl, focus loss, extra status or disappeared data, and all ten cards remain.
- **Docs:** update the current **`docs/web-beta.md`** only if its general title-help description materially needs correction. Preserve the existing detailed numeric definitions **in user docs** where they belong; **they do not belong in a fun tooltip**. Do not rewrite completed historical FR000644 or its completion record.

**FR-only publication boundary:** add `development/backlog/ready-to-develop/000840-000649-ai-stats-hourly-rate-three-short-playful-tooltip-paragraphs/FR.md` and advance `development/backlog/identity-state.json` from **648** to **649** in one optimistic docs-only main commit; leave executable code/tests/current docs/version/release and all other backlog items unchanged now.
