# FR 000682 — AI Stats: total tokens, token consumption rate, honest card loading, and optional fastest-model fact

**Ready to Develop — owner-requested, 2026-11-12.** Primary work: two useful token-volume cards and truthful per-card loading. Secondary/conditional work: a fun Top 3 model inference-speed fact **only if reliable, inexpensive source timing exists**. This is an AI Stats-only enhancement, not a general telemetry or benchmark platform.

## User goal and reviewed current behavior

On Cost Guard Web `/#/ai-stats`, the owner wants to know **how many tokens were consumed in the selected period**, and **how many tokens per hour** that represents, presented like the existing three-row **AI Hourly Rate** card. The page is deliberately lighthearted; brief amusing interpretations are welcome.

The owner also suggests a **Top 3 fastest models by output generation tokens/second**, but specifically **not** total prompt duration (which includes tools, waiting, other models and subagents). The owner is unsure whether historic OpenCode data can support this reliably and does not want a long extra loading cost just to populate a novelty card.

Finally, on cold/partial loads or period changes, the owner has seen ordinary-looking zero/no-activity stats before enough data was available. Requested UX: **the cards themselves exist from the start, but any not-yet-ready card contains only plain `Loading…`** — no title, icon/emoji, fake value, fun copy, placeholders or other card content. When ready, reveal the complete card together.

Code observations on `main` when drafted:

- `src/web/assets/ai-stats.js` has **ten fixed cards** (four Overview, six Fun Facts), plus a conditional matched-runs extra, and five periods: Today, 7 days, 30 days (default), This month, All time. The first card already has Calendar / Workday / Active AI hourly rates.
- `src/analysis/ai_stats_rates.py::hourly_rates` already calculates the corresponding calendar-day, workday-eight-hour and unioned-active-hour denominators; `src/analysis/ai_stats.py::StatsObservation` prepares the existing stats from deduplicated canonical requests.
- `src/reports/ai_stats.py::StatsAcquisition` publishes usable **partial-slice figures** while work continues and exposes `ai_stats_work.scopes[period].ready`; currently `AIStatsView.valid()` only checks the shape and ten numeric metrics, while `AIStatsView.update()` renders the period row even when that scope is **not yet ready**. Partial-slice zero-looking facts can therefore be presented as final-looking cards. FR000678 fixed synthetic zero-on-error fallback, but **this partial-to-ready visual transition remains distinct**.
- `src/reports/ai_stats_evidence.py` retains compact deduplicated token facts and prompt/compaction execution intervals. `NormalizedMessage` includes created/completed timestamps and optional V2 `time.streamed`, but AI Stats' compact `TraceEntry`/evidence has no verified per-token generation interval. Historical prompt/session elapsed time and `time.streamed` by themselves are **not proof of pure inference time**.
- The existing `fun-1` policy deliberately allows playful bounded **cost/time estimates** where the source is imperfect. **Do not use guessed costs, fallback token quantities or guessed prompt intervals as measured token-volume/TPS facts.**

## 1. Add two token cards to Overview (required)

**A. Total Tokens** — a compact period total shown in the familiar AI Stats card style. Put next to the cost cards. Count actual normalized physical request token usage across the selected period: **Input + Cached input (cache read) + Cache write + Output** with the repository's established reasoning/output-folding convention, counted once. This is **token traffic/volume**, not a context-window size, unique tokens, billable consumption, quota used or Credits/CCost. Repeated context reads can make the number large, and that is expected.

- Use the same authoritative selected-period membership as current AI Stats/Token Mix, including child/subagent work, canonical request identity, step-vs-message precedence, deduplication and archived sessions when available. Respect current source, revisions and selected `now`, and use observed request completion time without arbitrary proration across periods.
- Use **actual usage**, not the existing `fun-1` `_request_costs` guessed-token/cost filler or an inferred total from dollars. Preserve exact integer arithmetic until display; compact K/M/B-style text may be rounded for readability but title help should explain the precise represented total/category scope.
- Explicitly distinguish a genuine ready, evidenced zero from pending, missing usage fields, source gaps and incomplete scope. Never silently turn missing token categories into zero. A known partial subtotal may be shown only with an honest concise qualifier; do not advertise it as a complete total.

**B. Token Consumption Rate** — a separate card (preferred over crowding the total card), matching the visual structure and order of `AI Hourly Rate` **exactly** with three labeled rows:

| Row | Meaning |
| --- | --- |
| Calendar average | Total Tokens ÷ (same nominal local calendar days × 24 hours) |
| Workday average | Total Tokens ÷ (same eligible configured workdays × 8 hours), or `No workdays` |
| Active AI average | Total Tokens ÷ the same overlap-safe **AI Working Time** in hours |

- Use the existing five-period rules, user timezone, DST/calendar logic, and the configured `SE`/weekend-only workday calendar. The rolling 7/30-day request populations and nominal date-slot denominator must match the existing cost-rate card, even though they are different concepts. No new independent time clock.
- All three rates use **the same Total Tokens numerator**; format as tokens/h (e.g. `18.4K tokens/h`) and keep calculations exact until final formatting. No USD/Credits conversion; switching monetary display units must not change either new card.
- If token usage or the denominator is insufficiently evidenced, avoid a precise-looking invented rate; use the established concise unavailable/partial semantics. Zero active time does not imply a nonzero rate. Tooltip/help briefly explains the three formulas and the difference between token throughput per **activity hour** and actual model generation speed in **tokens/second**.

The intended default presentation becomes six Overview cards: AI Hourly Rate, Total AI Cost, **Total Tokens, Token Consumption Rate**, AI Working Time, Average Cost per Session. Keep the existing six Fun Facts and optional matched-run fact unchanged unless necessary for integration.

## 2. Show empty card shells with plain Loading until data is ready (required)

- On a **cold visit or newly selected period without a validated ready snapshot**, render the normal responsive grid with the appropriate number of card shells. Each pending card's **entire interior is only `Loading…`** (plain text, no emoji, title, help icon, trait, value, zero or decorative spinner). Do not show a single loose page-level loading paragraph in place of all cards. Keep layout stable.
- The current source already exports selected-scope `ai_stats_work.scopes[period].ready`. Use authoritative scope readiness as the minimum gating rule; a card can render earlier only when **its complete metric-specific evidence is proven** independently, never just because a partial projection produces finite/zero numbers. No invented client-side timer or time-derived `ready`.
- Once a card is ready, commit its **title, icon, complete values/rows, details/link, contextual help and playful trait together**. For the three-rate cards, do not show individual rate rows before their needed input is ready. Preserve the selected period and matching source/observation generation so stale, foreign-period or older partial results cannot overwrite ready cards.
- An **already-valid, ready same-period last-good snapshot** may remain visible during quiet background refresh as today; avoid regressing focus, scroll, hover help, filters or unit/theme updates. Period switching must not carry the old period's values into a pending new one.
- **Terminal/unrecoverable failure without a valid result is not `Loading…` forever.** Show a short truthful unavailable/error state (with ordinary automatic recovery where supported), not ten happy zeros or a misleading endless spinner. A truly empty **ready** period can still display the intentional fun zero cards. Do not reintroduce Retry/Refresh buttons; FR000678's host-owned recovery still applies.
- Semantic accessibility: pending card is readable as a status without repeated announcement on every poll; preserve logical order, stable grid geometry and focus through transition; respect narrow viewports, screen zoom, Classic/Web themes and keyboard/touch help.

## 3. Optional Fun Fact: Top 3 Fastest AI Models (bounded feasibility, no extra slow history)

The user likes the idea of a single **podium/list card** showing up to three fastest distinct model identities in **generated output tokens per second** during the selected period. This is **secondary** and **must not jeopardize correctness or perceived load speed** of the first two features.

**First establish feasibility from actual supported source data**, with a small sanitized timing inventory and tests. OpenCode V2 has assistant message created/streamed/completed timestamps and part/step metadata; these do **not automatically prove** first output token/last output token or exclude provider queue/TTFT/tool stalls. In particular, publicly reported OpenCode TPS defects show absurdly high estimates when a final metadata burst makes a tiny `streamed - created` interval look like whole generation. Do not copy that approach or label a prompt/session wall-clock rate as pure inference.

**Only implement the Top 3 card if** all of the following are met:

- A repeatable, **source-qualified** interval for actual output generation (not waiting for first token, tool execution, model routing, prompt wall time, background time or pause) is present or can be safely derived from already-acquired per-response events; timestamp semantics and native version/source support are verified, not assumed.
- Output token numerator and actual timing denominator belong to **the same independently identified model invocation**. Group by stable provider/model identity (and preserve variant/effort distinctions where they affect comparability); exclude duplicate tool continuations, mixed/unattributable entries, incomplete/failed/in-flight/zero-token/zero-duration entries, implausible atomic-burst intervals and known low-confidence samples. Never sum session duration across models.
- Calculate per-model aggregate TPS using **sum of eligible generated tokens ÷ sum of matched genuine generation seconds** (not average of rounded individual TPS). Require a reasonable nontrivial sample and show **sample count/coverage** alongside each ranked model, with deterministic ties. No speculative provider/model joins or claims of controlled benchmark superiority.
- Reuse the **existing AI Stats bounded acquisition/slices/cache** and captured evidence: **no second full-history scan, network request, model inference, new daemon/worker, private transcript collection, unbounded raw event persistence or additional wait before other cards are ready**. Expensive or missing timing must never block the ten existing stats or the two required new cards.
- When timing cannot be qualified, **do not fabricate a winner**. Either omit the optional card or show a compact honest `Not enough reliable timing data` result after the relevant work settles, with a playful but truthful explanation. Record the feasibility finding and relevant source limitations as part of this FR's delivery; the main FR is still complete without a TPS ranking if these conditions fail. Avoid a separate implementation detour unless explicitly approved later.

An existing **Biggest AI Speed Gap** fact compares whole matched **run durations**, not generation TPS. Do not reuse that value or confuse the two notions of speed.

## Tone and copy

Keep existing AI Stats' mildly mischievous, friendly personality. Illustrative post-load copy (implementer may tune wording):

- Total Tokens: **“The robots have been snacking on context again.”**
- Token Consumption Rate: **“The silicon buffet even has office hours. Allegedly.”**
- Reliable Top 3: **“The silicon sprint finals — actual generation only.”**
- Unavailable TPS: **“No stopwatch, no podium.”**

Short, varied, evidence-appropriate one-liners are preferable to heavy jokes. **Pending cards contain exactly plain Loading and nothing else.** No jokes, emojis or fake achievements during loading or failure. Keep help factually clear, avoid shaming the user for high token use, and don't imply account billing/remaining quota.

## Acceptance and verification

1. All five period selectors (Today / 7 days / 30 days / This month / All time) yield the expected **Total Tokens** using an independent oracle over canonical deduplicated I/C/W/O + reasoning accounting. Check child agents, repeated cache reads, step/message overlap, clone dedup, archived/moved roots, old/new source revisions, missing fields, pending work and empty periods. Pricing unavailable must not prevent token counts.
2. The new token rate card reproduces the existing cost rate card's three **time denominators** for identical period/timezone/workday calendars, including SE holidays, no workdays, DST transition, local midnight, rolling-period edges, active time overlaps/unknown and All-time first positive evidence. Numerators differ only by dimension (tokens versus CCost); display never converts tokens to money.
3. Cold load with partial first/second/final historical slices cannot expose false zero/partial final-looking metrics. **Exactly Loading as each pending card's entire contents**, while period-select buttons and stable card grid remain usable; ready content appears atomically. Genuine ready zero and failed/unavailable are visually distinct, and last-good same-period refresh remains useful.
4. Period switches while jobs are queued/running, repeated navigations, invalidated cache, automatic retry and late out-of-order publications do not flash previous-period data or override ready values. No new Retry action, false 100%/fake completion or extra heavyweight history requests.
5. If TPS is implemented, provenance, per-response timing and low-confidence exclusions are proved against synthetic examples including tool waits, slow TTFT, multi-model sessions, reasoning, atomic final bursts, rapid continuations, failed responses and missing timestamps. False six-digit TPS must not win; rank up to three only qualified models. If not feasible, document why and verify other cards remain entirely independent of it.
6. Profile representative **cold and warm AI Stats, period changes and two-tab reuse** against current behavior. Keep the host-owned finite scan/checkpoint/sharing, API payload size, bounded process limits and default cache reuse; no second source crawl for TPS. Show truthful measurements and any relevant tradeoff, not a claim of zero overhead.
7. Update `src/analysis/ai_stats.py`, `src/analysis/ai_stats_rates.py`, `src/reports/ai_stats.py`/compact evidence and `src/application/{ai_stats,projection,display}.py` as appropriate; extend `src/web/assets/ai-stats.js`/scoped CSS and matching validation. Revise fixed `ten metrics` schemas/tests/fixtures, `development/tests/test_ai_stats.py`, `test_ai_stats_resume.py`, browser probes `probe_ai_stats*.cjs`, `docs/web-beta.md`, README/architecture navigation where affected. Change `fun-1` view policy/cache contracts deliberately if the new count/readiness contract requires it; do not invalidate unrelated history caches needlessly.

**Non-goals:** a general Tokens page, new user preferences, provider benchmark API, billing/quota semantics, new paid calls, source writes/deletes, model speed claims based on prompt duration, a new scheduler or a redesign of Token Mix/Watch/CLI.

**Done means:** two clearly explained, source-based token cards work for each selected period; pending facts visibly say only `Loading…` instead of pretending no prompts exist; confirmed empty/errors/last-good remain honest; and the optional fastest-model fact is either demonstrably qualified and cheap or explicitly excluded with a concise evidence-backed explanation.