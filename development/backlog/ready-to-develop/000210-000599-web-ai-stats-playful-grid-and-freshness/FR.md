# FR 000599 — Web Beta AI Stats: playful metrics grid, all-time history, and quiet freshness

## Owner-approved request and publication boundary

**Owner-approved Ready Feature Request, 2026-11-05.** Completely replace the existing Web Beta **Cost per Active Hour** page with a distinctive, playful **AI Stats** page: ten useful/entertaining metrics in a uniform responsive grid, colorful Unicode/emoji icons, a five-way period selector, concise metric tooltips, session links, and short data-driven RPG-perk/trait-flavored one-liners. This is a deliberate fun-facts/easter-egg companion to the serious Models, Watch, Sessions, Accounts and Token Mix pages. The owner has compared a table and cards and **explicitly selected grid, not table**.

**Ready priority 000210**, after the existing Ready FR000598. Coordinate especially with FR000593 (modern Sessions catalog/detail), FR000595 (retire Web Reports), FR000596 (Token Mix's quiet five-minute refresh), and FR000590 (shared contextual-help UX). The new AI Stats view is Web-only. **Publish this FR and advance the identity watermark only** in this authoring session; do not implement source/tests/docs, change version/release files or disturb another worker's branch.

The inspiration is the colleague's question, "What is the AI's hourly rate as if it were an extra consultant?" Keep that analogy entertaining but accurate: AI execution is **not measured human productivity**, CCost is **reference token valuation**, and tests/Explore/tool work are real parts of observed agent execution. No claims about salary savings, billed consultant invoices, or time a human would have taken.

## 1. Navigation, replacement, and strict scope

- Rename the main Web navigation item **Cost per Active Hour** to **AI Stats**. Prefer the canonical fragment route **/#/ai-stats**. Old **/#/cost-per-hour** hashes/bookmarks should resolve safely to AI Stats without running the retired period report or causing a redirect loop. Do not retain two visible navigation entries/screens.
- **Remove the entire existing Cost per Active Hour page presentation**: its old Today / Month to date / Rolling 30 days prose cards, generic report chrome, Snapshot/Refresh/Cancel toolbar in the healthy steady state, "Reading this report", verbose caveats, long explanatory footers, and current rate-only layout. This is a replacement, not a facelift or a table added below it. Remove dead view-only code/styles/help.
- **Preserve reusable canonical analysis** (the current active-hour/duration, request-deduplication, reference-cost, timing, source-revision and caching logic) and any independently used APIs/helpers. Preserve the **existing hourly-rate line on individual session Snapshot/Live detail** and its eventual FR000593 successor; this request is explicitly **not** a Sessions, Watch, Accounts, Models, Token Mix-content or CLI redesign.
- Render a normal accessible page with **AI Stats** as its identifiable heading/name. The page's internal sections are **Overview** and **Fun Facts**; do not introduce a giant dashboard, extra date report, graphs, sorting/filtering interface or a second session table.
- No extra user settings, server pricing calls, account/provider calls, new LLM inference, paid model calls, OpenCode writes, browser-stored private history, or claims of actual billing. Retain the user's current **Credits / reference USD** display preference and server-authoritative cost semantics.

## 2. Visual design — a genuinely playful but disciplined grid

- The successful view hierarchy is: **AI Stats** heading; one compact five-option period selector immediately below; **Overview** with the four core metrics; **Fun Facts** with the six playful metrics. Keep the ordinary app navigation and necessary source/error states but remove report-boilerplate clutter.
- Use **one consistent card component/grid language** for all ten stats. All cards have the same visual size/treatment, modest padding, gentle surface separation/rounding and clear typography. Do **not** make Overview's four cards physically larger than Fun Facts' six. Distinguish the two groups via simple headings and spacing only.
- Each card: a prominent **Unicode emoji/icon + short metric title**, a readable value, and (where appropriate) **one brief, witty, value-dependent subtitle**. The icon may be colorful; the layout remains coherent with existing Classic/Web themes, light/dark color tokens, native font fallbacks, contrast and current app spacing. Use native Unicode/emoji (no downloaded icon package, embedded sprite, icon font, new image asset, or network dependency). Exact emoji artwork varies by OS; do not rely on its appearance to communicate meaning. Hide decorative emoji from assistive tech when the title already names the metric.
- Preferred initial symbols: **💸 AI Hourly Rate, 💰 Total AI Cost, ⏱️ AI Working Time, 📊 Average Cost per Session, 🏆 Most Expensive Session, 🔥 Longest Session, 📅 Busiest Day, 🦉 Night Owl, ⚡ Coding Streak, 🔀 Peak Parallel Sessions**. Choose standards-supported substitutions only if native display/accessibility requires them.
- Grid adapts naturally: several equal cards per row on wide desktop, fewer on narrow screens, with no clipped figures, illegible unit labels, nested vertical scroll areas or wide table-style horizontal panning. Preserve natural document scrolling, correct reflow at about 360px, selection/focus/links, and meaningful labels if emoji are absent.
- Avoid oversized cards, wall-of-text notes, "gamification" machinery, progress/leaderboards, pop-up achievements, unnecessary decorative animations, or an intrusive refreshing banner. This should feel like a clean **retro RPG traits/perks easter egg**, not a parody game or an enterprise BI dashboard.
- Session-record cards show a concise human-readable session name under/alongside the record amount as a real link to the canonical root session page. Do not expose an ID as visible primary text, invent a title, auto-open a session, or render an inaccessible whole-card click target. Treat titles as escaped text.

## 3. Period selector and source scope

Use **exactly five visible options in this order**: **Today | 7 days | 30 days | This month | All time**.

- **Default is 30 days**, and entering AI Stats **automatically starts** the first bounded acquisition if no retained usable data exist. No persistent "Load", "Update Stats" or "Refresh snapshot" button is wanted.
- **Today:** configured-local midnight through observation time.
- **7 days:** exactly trailing **7 × 24 hours**, ending at observation time (not seven full calendar dates).
- **30 days:** exactly trailing **30 × 24 hours**, ending at observation time.
- **This month:** first midnight of the **current configured-local calendar month** through observation time; respect calendar length, locale timezone and daylight saving changes. It is **not** synonymous with trailing 30 days. Attach a short helpful tooltip to its visible label, e.g. "From the first day of the current local calendar month until now."
- **All time:** the entire **available recorded source history**, including available archived roots, not a claim to recovered deleted/pruned history. Its label tooltip should clarify "All available recorded sessions; deleted/pruned history cannot be recovered." Avoid repeating that caveat on every metric or as a large visible paragraph.
- The other obvious period labels need no gratuitous tooltip; brief 7/30-day rolling explanations are acceptable if useful. Use the same shared ContextHelp interaction as other Web views, not native browser title popups or standalone question-mark icons.
- Default 30-day history **must be reused** for Today/7 days and for This month when coverage suffices. If a 31-day month extends beyond the rolling-30-day acquisition, extend bounded coverage as needed; never claim complete month-to-date numbers from an insufficient 30-day cache. Switching periods should not gratuitously reread/reprice all history. **All time** may require a separate, genuinely broader acquisition with bounded progress (see §7).
- Times, daily grouping and night-time windows use CostGuard's **configured timezone** and correct DST behavior, never an assumed browser timezone. Costs use canonical **event/completion-time attribution**, not fabricated proportional token billing for a request spanning a window boundary. Clip observed execution intervals to the selected scope before aggregation.
- All cards update as one coherent selected-period result; no mix of 30-day cost with 7-day duration while loading. Period selection should remain selected and stable across quiet updates/navigation retention.

## 4. The exact ten metrics and their truthful definitions

**Overview — four equal cards**

| Metric | Visible value and source definition | Tooltip emphasis |
| --- | --- | --- |
| 💸 **AI Hourly Rate** | Canonical reference CCost attributed to the selected window divided by **unioned observed AI execution hours** in that window. Use unrounded Decimal math on the server; show CCost/h or reference $/h according to Settings. | This is AI execution-hour reference spend, **not** actual provider billing, agent-worker-hours, salary, or human hours saved. Unknown/zero time or incomplete pricing cannot create an exact rate. |
| 💰 **Total AI Cost** | Period's canonical deduplicated, attributable reference CCost in Credits or reference USD. | Estimated token-value equivalent, **not** charges to a subscription or a native quota deduction. Missing prices are not a free run. |
| ⏱️ **AI Working Time** | Elapsed **union of qualified execution intervals** across all root sessions in the period, including attributable subagents, tests, Explore, tools, background work and compaction, excluding proven idle gaps; overlaps counted once. | Wall-clock time in which observed AI execution was taking place, **not** summed worker hours, session age or human typing/thinking. |
| 📊 **Average Cost per Session** | Period reference CCost divided by the **number of distinct root sessions with attributable usage in that period**. Count each root once; 0 denominator is unavailable, not zero. | Explain the denominator and that one session may cross periods. Not billed per-session money. |

**Fun Facts — six equal cards**

| Metric | Visible value and source definition | Tooltip emphasis |
| --- | --- | --- |
| 🏆 **Most Expensive Session** | Highest **selected-period** canonical CCost attributable to one root session; show amount and link to actual session when accessible. Use stable deterministic ties. | Not necessarily the root's lifetime cost: requests outside the selected window are excluded. Do not split one request's cost across dates. |
| 🔥 **Longest Session** | Root session with longest **qualified, overlap-unioned execution inside the selected period**, clipping a long-running root at window boundaries. Show duration and session link. | Not lifetime wall-clock age, idle time or sum of concurrent child workers. |
| 📅 **Busiest Day** | Configured-local calendar **date** with maximum **overlap-safe unioned AI execution time across all roots during that date and selected window**. Show date and duration; stable ties. | Explain explicitly that two simultaneously running sessions do **not** count as two hours in one real hour. Partial boundary dates count only the observed portion inside the selection. |
| 🦉 **Night Owl** | Percentage of selected-period, overlap-safe **AI Working Time** falling between **22:00 and 06:00 local time**, split at local day/night and DST boundaries. Show 0% when positively measured; no invented rate with zero/unknown denominator. | Includes tool/test/child execution when qualified; measured AI activity after hours, not a claim the human was awake. |
| ⚡ **Coding Streak** | **Longest consecutive sequence of configured-local calendar dates** in the chosen period that have **positive qualified AI execution activity**. Show N days; distinguish longest streak from a currently active streak. | AI activity streak, **not** proof of Git commits, changes shipped or human coding. Cross-midnight execution can touch both dates, if actually observed. |
| 🔀 **Peak Parallel Sessions** | Maximum number of **distinct root/top-level sessions** with overlapping qualified AI execution intervals at the same instant within the selected window. Show a numeric count. | Parallel **sessions, not agents, prompts or model calls**. Subagents within one root do not inflate the count; inactive session ages do not count. |

**Common accounting/evidence rules**

1. Reuse canonical root/child attribution, unique physical model-request cost, prompt/compaction/tool/background duration evidence, overlap union, known/unknown source fields, pricing and existing derived cache. Concurrent independent requests incur separate CCost, whereas concurrent time is unioned.
2. Across all metrics, retain **known zero vs never observed vs partial/unavailable**; pricing gaps, missing end times, stale source, historic source migration gaps or inaccessible/pruned sessions must not silently become perfect zero/complete numbers. Running/incomplete observations may be provisional where defensible, never fabricated exact duration. Show a compact relevant unknown/partial indication, not a page of disclaimers.
3. Ratios and records must use the **same coherent acquired scope/evidence**. Treat concurrent/late-arriving requests, multiple models, archived root trees and cross-boundary activity consistently; no double-counting cloned requests or subagent sessions.
4. Record links use existing safe **/#/sessions/<root-id>** navigation and actual acquired session identity. If the record's source disappeared, do not show a broken confident link. A record may have an accessible link while the page has other unrelated partial data, with truthful per-value qualification.
5. Select the record using exact data, not rendered compact CCost strings. Backend/Python owns core numerical semantics; JS renders prepared values/tooltips and does not independently reprice tokens or derive an alternative accounting policy.
6. Clear names and tooltips matter more than arbitrary benchmarks. No extra eleventh "median" card or hidden session leaderboard is requested.

## 5. Fun personality: brief original one-liners driven by actual stats

The owner specifically wants **Fallout 1/2-era perk/trait flavor**: a small, cheeky observation that feels like an RPG character trait. Create **original copy**, not actual Fallout perk names, game quotes, icons or assets. These should be genuinely amusing for a night owl, a daytime worker, a big spender, a cautious user **and someone with zero proven activity**. They are personality, not factual productivity judgments.

- Try to show **one short, punchy, single-line comment on each card** when a meaningful condition can be determined. The text is subordinate to the main number; target roughly **3–9 words**, never an essay. It may wrap naturally on small screens without varying card geometry substantially.
- Use a **deterministic, curated mapping** from canonical underlying metric values to a few suitable variants: known zero; low/light; ordinary/middle; unusually high; source unavailable. Keep the chosen line stable while a period's underlying data remain unchanged, including unit/theme toggles, re-render or unmodified refresh. No LLM call/random chatter on every tick.
- Comedy must follow the **actual measurement**. For example, Night Owl 0% gets a daytime joke; 75% gets a nocturnal joke. Never give a "working hard" taunt from an unavailable denominator, call an unpriced session free, or assert the user coded when only an AI process was observed. Thresholds are implementation-calibrated against raw metric units/ratios; CCost thresholds must not change based on Credits/USD formatting.
- Not every card needs a forced joke if it sounds unnatural, but **at least one genuinely fun line should be visible for every successfully acquired dataset**, including fully empty/known-zero history. Prefer several per-card candidates; an unavailable source gets an honest playful source-unavailable fallback rather than a false "you did nothing" claim.
- No gamification scores, external profile, persistent achievements, AI-generated praise, insults about the user or productivity assertions.

**Concrete candidate copy for implementers (polish as necessary, keep it original and brief):**

| Metric | Low/zero or modest evidence | High/distinctive evidence | No reliable evidence |
| --- | --- | --- | --- |
| AI Hourly Rate | "Budget build. Dangerous potential." | "Premium silicon has expensive tastes." | "The accountant needs more evidence." |
| Total AI Cost | "The token furnace is on vacation." | "The token furnace demands tribute." | "The ledger remains mysterious." |
| AI Working Time | "A short shift for the silicon crew." | "Silicon overtime. No coffee required." | "The timekeeper lost the trail." |
| Average Cost per Session | "Tiny adventures. Tiny tab." | "Every conversation has a cover charge." | "No average without a party." |
| Most Expensive Session | "No boss fight on record." | "That boss fight came with a receipt." | "The boss left no receipts." |
| Longest Session | "A quick quest. Refreshing." | "That escalated into a full campaign." | "The marathon remains undocumented." |
| Busiest Day | "A perfectly peaceful calendar." | "The bots earned imaginary overtime." | "The calendar refuses to testify." |
| Night Owl | "Day-shift citizen. Suspiciously responsible." | "Certified nocturnal operator." | "Even the owl needs a clock." |
| Coding Streak | "One day. The legend begins." | "The calendar fears you." | "Your streak is hiding in the vault." |
| Peak Parallel Sessions | "One lane. Very civilized." | "A miniature parallel universe." | "The parallel universe is unobserved." |

For Night Owl especially, support several intermediate variants such as **"Occasional moonlighting detected."** and **"Half human, half moonlight."**. An ordinary/midrange profile deserves a gentle joke too, e.g. **"Standard-issue adventurer. Surprisingly functional."** when the chosen metric can support it. These are **examples of tone and condition classes**, not excuses to make a false claim or to display the exact same copy for every user.

## 6. Minimal contextual help, no visible explanation essay

- Attach concise **shared ContextHelp** to the **actual visible metric title text**, not empty card padding, not the whole card and not an extra standalone **?**. Maintain established FR000590 ~600ms hover intent, keyboard focus, tap, pointer exit/window leave cleanup, Escape and nonblocking link activation. No dotted underlines or duplicate browser-native tooltips.
- Provide a genuinely informative, metric-specific explanation for **all ten titles**, especially **Busiest Day**, **AI Working Time**, **Night Owl**, **Coding Streak**, **Peak Parallel Sessions**, CCost attribution and window clipping. Keep it understandable to a colleague without reading architecture docs.
- On the five-way selector, explain **This month** and **All time** directly on those labels; optional 7/30-day tooltip only if it adds clarity. Do not scatter "deleted sessions aren't counted" repeatedly across the page or put it in a permanently displayed warning. Source errors/incomplete coverage are exceptions: these **must** remain visibly truthful where required.
- Make the value and actual session-name link independently accessible, without tooltip interference. Tooltip text cannot be the only way to discover a significant source error, incomplete cost or missing value.
- Display current CCost units/rates consistently across all cards and tooltips; default Credits vs reference USD uses the existing Web Settings contract, with no fresh scan on switching units.

## 7. First load, All time progress, automatic freshness and one-hour stale policy

**No permanent manual Refresh / Update Stats UX.** Treat this as two distinct operations: a **bounded first acquisition** and later **quiet cached refresh**. Reuse proven finite job/source revisions/cancel/progress plumbing and cache/worker isolation, rather than implementing a second polling/report engine.

### 7A. Initial acquisition, lazy broader history and period reuse

- Navigating to AI Stats with no usable retained 30-day result automatically starts a finite acquisition. It may show an honest, compact **loading/progress bar** until the first coherent result is ready; keep the period selector usable and clearly label the phase. If percentage is not grounded in actual finite work, use indeterminate progress instead of fake percent.
- Once 30-day coverage is ready, Today and 7 days should be derived without a separate history scan; This month reuses coverage when sufficient and only extends it when month-to-date genuinely reaches farther back.
- **All time** is explicitly lazy: first selecting it may start a substantially larger, bounded historical read/analysis. Show real stage/count progress while that first complete all-time dataset is unavailable; allow cancel for a long-running all-time acquisition **without** showing a permanent Refresh/Cancel toolbar afterward. Preserve any already-ready 30-day cards/cache and let the user select those immediately. A failed/cancelled all-time job is not successful zero or an incomplete total presented as complete.
- Re-selecting a known cached scope should display it immediately when fresh, and never rerun an all-history scan just because the user changed tabs, currency/theme or the report was repainted. Cache source coverage, not merely one selected-period HTML screen.

### 7B. Quiet automatic refresh while actively viewing

- For **AI Stats**, aim for an **approximately 15-minute** low-priority **freshness check** while this route is active **and the browser document visible**. No high-frequency Live/Watch cadence, no continuous unnecessary source scan. The interval is a target, not hard real time.
- FR000596 **Token Mix keeps its own approximately five-minute cadence**; this FR does not change Token Mix's metrics, tables, sorting or normal first-load semantics.
- Prefer host/source revision signals, cached normalized history and dependency-aware incremental changes. Reconcile newly created, modified, removed, archived, completed or late-arriving root data and changed reference pricing when relevant; do not redo the entire source history just because a timer fired. Bound CPU, I/O and job lifetime, especially with large installations; prioritize Watch/Accounts/live functionality.
- Only one applicable refresh job in flight per relevant host/source/scope/cache identity; coalesce across tabs when feasible. No duplicate job storm, retry loop, or repeated expensive polling while the route is inactive. **Leaving a page stops new scheduled checks, but an already-running bounded acquisition may finish and publish to cache** even if the user has navigated away. Returning does not launch a duplicate. Hidden/background tabs schedule no new heavy refreshes.
- During an ordinary refresh with an accepted result already displayed, **keep all old cards, selected period, links, one-liners, keyboard focus and scroll position visible and usable**. Never show a spinner/overlay/flicker or replace cards piecemeal; commit one coherent new period result atomically when complete. A failed update retains the last valid values and truthful provenance.

### 7C. Explicit re-entry freshness bands — AI Stats **and** Token Mix

The owner additionally requests a **shared, deliberate one-hour maximum age for the *display of retained reports on re-entry***. Age is measured from **last successful data observation/acquisition**, not last page visit, last timer tick or failed attempt.

| State when opening/returning to one of these historical-statistics routes | Required UX |
| --- | --- |
| No completed cached dataset for requested scope | Show first-load progress (auto-start on AI Stats; retain FR000596's deliberate first-load behavior for Token Mix), then coherent results. |
| Completed cached dataset aged **up to its route-specific normal cadence** (AI Stats ~15 min; Token Mix ~5 min) | Show immediately, no unnecessary scan. |
| Data **older than normal cadence but at most 60 minutes** | Show cached data immediately; start at most one quiet background freshness check/update **as soon as the visible route is revisited**. No spinner or disruptive "Refreshing" chrome. |
| Data **older than 60 minutes on re-entry** | **Do not show possibly misleading old metrics as if current.** Preserve the last-good cache internally, but **temporarily withhold its normal metrics UI and show honest loading/progress** while a bounded new acquisition runs. Restore all coherent updated data on success. Do not claim that a timer tick made old data new. |
| First/return acquisition fails, times out, is cancelled or source is unavailable | No infinite progress and no fabricated zero/current stats. Show a compact, actionable failure/retained-stale state with true last-success observation; allow retry, and optionally explicitly reveal the old dataset **clearly labeled stale**, never silently as fresh. Preserve cache for eventual recovery. |

- The **60-minute loading exception applies when entering/re-entering a route or selecting a previously inactive stale scope**. Do **not** abruptly blank an already-open active page at minute 61 during a routine delayed background update; retain its accepted figures, showing a small stale/delayed cue only if materially necessary.
- This is an intentional **narrow refinement of FR000596**: its usual "never replace an existing good view with a spinner" still governs **normal background refresh and re-entry at ≤60 minutes**, but the **>60-minute return case supersedes that specific unconditional display rule**. Preserve the rest of FR000596 (five-minute cadence, cache-first incremental acquisition, first load, sorting, job limits). Implement the policy in a reusable Web cached-view lifecycle where appropriate; **do not** impose a 60-minute report cache rule on high-frequency/live Watch, Accounts, Sessions or Models, whose owners and freshness/source contracts differ.
- A source update already in flight may finish after the user leaves; no new off-page timers, and no work duplicated on return. Multiple open browser tabs must not fight over an old/new result or trigger parallel full-history scans.
- The selected period and relevant observation timestamps must be preserved correctly across route changes, new data, timezone boundaries and source/pricing revision changes. A 60-minute-old all-time acquisition and a recently captured 30-day scope are **not interchangeable**.
- First-load, over-hour refresh and all-time progress can have a small cancel/error recovery action; this is **not** permission to reintroduce always-visible Snapshot, Update Stats or Refresh bars on healthy views.

## 8. Correctness, implementation boundaries and performance

- Likely existing owners to inspect/reuse: src/analysis/active_hour.py, src/analysis/duration.py, canonical request/period CCost and session tree analysis; src/reports/service.py::build_cost_per_hour, src/reports/models.py, src/application/projection.py and display/CCost unit tokens; Web finite jobs/cache in src/web/jobs.py and composition; src/web/assets/index.html, reports.js, render.js, app.js, app.css, help.js; source/catalog revision and progress/cancel tests. Exact implementation is flexible; there should be a **single canonical calculation owner**, not ten unrelated browser-side formulas.
- Use documented existing report job limits and authoritative source revision validation. The FR000596 performance notes report **491 seconds for a real warm CLI history scan**, whereas Web jobs have a **120-second deadline**. A naïve All time full scan every 15 minutes is unacceptable. Measure representative 30-day and all-time performance, bounds, cache hit rates, incremental source changes and fresh/return UX before claiming completion. If complete all-time capture is too expensive, show bounded progress/explicit unavailability rather than lying with a partial result.
- Use event-time allocation for CCost, qualified active-duration union for time, exact time-zone clipping and stable tie-breakers. A long 31-day calendar month is the explicit coverage-edge case for This month. Preexisting source history not present cannot be magically restored.
- Avoid persistence of private prompt/session text into URL, storage or diagnostics. Existing authenticated Web host, CSRF, source read-only security and browser session protections remain unchanged. Titles are plain safe text; only normal canonical session locators may appear in link fragments.
- Keep **every unrelated view and CLI output** functionally unchanged. In particular, the session-detail rate from FR000530 must survive, Token Mix's new two-table presentation from FR000596 must survive, and the planned Sessions/Accounts redesigns must not be disturbed.
- Update current navigation/user documentation and architecture ownership notes when implementing, but preserve historical completed FR/release evidence unchanged. No new global framework, lasting release gate or migration merely to display these ten cards.

## 9. Verification and acceptance

1. Web main navigation says **AI Stats** and opens the clean **/#/ai-stats** view. Old **/#/cost-per-hour** routes are handled safely; the retired Cost per Active Hour page, verbose report prose and persistent Snapshot toolbar are gone. Session-detail hourly rate remains intact.
2. The healthy new page contains **exactly ten** equal-treatment Unicode/emoji cards in **Overview (4)** and **Fun Facts (6)**, with selected-period values, suitable short original data-driven one-liners, and no table or unnecessary chart. Verify Classic/Web light/dark, wide/360px, keyboard, touch, focus and screen readers.
3. The five period choices appear in their exact order; **30 days is default**, Today/7 days/30 days are correctly derived, This month uses the configured-local current month (including months longer than rolling 30 days), and All time uses all available history. DST, local midnight/month boundaries, rolling 7/30-day edges and time-zone changes are tested. This month and All time have useful text-bound tooltips.
4. All ten definitions are independently exercised: overlap-safe active time and busy day; nightly window 22–06; roots vs children for peak parallel sessions; streak across local midnight; session records with real selected-window costs/durations; concurrency and deterministic ties; correct clipped-period semantics and event-time request CCost attribution. Test running/aborted/incomplete, unknown duration/cost, true priced zero, archived/deleted history and source migration gaps.
5. **Most Expensive Session** and **Longest Session** link to the actual accessible root session; unavailable/disappeared records cannot become broken or invented links. A selected-period record must not accidentally display a whole-lifetime amount as its period amount.
6. The one-liners are short, stable and **truthful** for known-empty, low, normal and high profiles, including **Night Owl near 0%** and heavily nocturnal activity; unknown data never produce false "no use" copy. At least one enjoyable line appears for an otherwise fully valid zero-activity dataset. No copyrighted Fallout quotes or external image/model calls.
7. First navigation **automatically loads 30-day AI Stats** with bounded honest progress if necessary; today/7 days reuse cached 30-day coverage; This month extends as needed; first All time may display meaningful bounded progress/cancel. No permanent Refresh/Load button and no stale result masquerading as zero.
8. On a visible active AI Stats route, ~15-minute cache-first low-priority checking updates a **coherent complete grid** without flashing, disappearing cards, visible refreshing chrome, changing focus or multiplying expensive acquisitions. Inactive/hidden routes do not start repeated work; one in-flight job may finish after navigating away. Multi-tab coalescing/failure/backoff/performance limits are verified.
9. For **AI Stats and Token Mix**, deterministic lifecycle tests cover: no cache; age under normal TTL; normal TTL < age ≤60m; age **>60m on re-entry** showing progress rather than old normal values; age >60m **while already viewing** retaining accepted content; failed/slow/cancelled refresh with honest stale fallback; source change without wasted full scan; leaving/returning while a job is in flight; and two concurrent tabs. Token Mix keeps FR000596's **~5-minute cadence, exact tables/sorts and first-load contract**.
10. Changing Web Credits/USD, theme, period or navigation does not trigger provider calls, silent repricing, repeated full history acquisition, or a false new observation timestamp. Browser/source errors remain actionable, CLI/Web other pages work as before, and required finite-job/security/large-history regression checks complete with truthful results.

**No product implementation is authorized within this authoring session:** publish only the complete Ready FR and the matching increment of development/backlog/identity-state.json.
