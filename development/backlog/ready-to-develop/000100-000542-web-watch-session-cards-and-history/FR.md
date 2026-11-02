# FR 000542 — Redesign Web Beta Watch with live prompt cards, recent sessions and full-session totals

## Owner goal and scope

Replace the cluttered Web Beta Watch report with a compact, naturally updating list of unframed prompt/session cards. Follow the visual language of the improved Models page and the CLI Watch metric, timing and status semantics, while giving the Web a deliberately different history selection and progressive loading model.

This is one coordinated Watch-page FR: card presentation, lifecycle, full-session aggregates and asynchronous acquisition must agree. The owner approved creation on 2026-11-02 and delegated minor design choices. Priority: **000100**; permanent identity: **000542**. This publication creates the backlog request only.

The owner's final choices supersede the earlier suggestions made during dictation: there is **no single combined prompt table and no 100-prompt history**. Earlier Prompts contains **five distinct historical sessions**, each showing **up to five prompts**. Active content consists of one logical card per running prompt. This intentionally supersedes the single-table, retained-row subtotal, normal status/header and startup-Earlier presentation requirements of completed FR000460 where they conflict. Preserve the delivered Models design from FR000537/FR000540 and the Classic/Web settings from FR000538/FR000539.

## Inspected baseline

Inspected repository main at `f8baf6337c6a3f83db056e3dbf82c90e1f69b133` on 2026-11-02:

- `src/web/assets/watch.js` renders a filtered, paginated combined table (50 rows per page), status/run/today/token-mix text, valuation disclosure and model notices. Shared toolbar/search elements in `index.html` appear above it. Models already has route-specific suppression of that chrome and an unframed, page-scrolling table.
- `src/application/live_projection.py::project_live` and `src/watch/coordinator.py::_build_projection` supply **retained/capped row subtotals**, not complete historical session totals; whole-session duration is absent. Renaming those subtotals would be incorrect.
- CLI defaults: long-running tool threshold **10 seconds**; recent terminal display window **30 seconds**, using `watchRecentEventSeconds`; session acquisition uses an adaptive coordinator rather than a fixed browser polling interval. CLI history is globally capped/startup-oriented and cannot supply the requested ongoing five-session history unchanged.
- Existing session navigation is `#/sessions/<session_id>`. Existing complete-session aggregation, context analysis and source/cache facilities are reusable, but current `SessionHistory` acquires full history before returning a page. `SessionDetails` has bounded history/lease counts and ticks on the live loop; opening an existing detail lease for every card would not support the 100-running-prompt case or independent progressive loading.
- The selectable themes are **Classic** (fixed dark, CLI inspired) and **Web** (OS light/dark). Current Web `.running` styling is green; Watch must receive the requested yellow/amber running semantics.

## 1. Minimal Watch page and section order

Keep the shared application branding/navigation, then render the Watch content in this order:

1. A compact, **collapsed-by-default Earlier Prompts** disclosure with the existing arrow interaction.
2. The **always-visible active card list**; this list is not collapsible.
3. The existing account/subscription usage cards, with the limited cleanup in section 8.

Remove the current Watch heading and all normal report chrome preceding the old table: **Refresh snapshot**, **Cancel**, **Search displayed report tables** and its input/help/placeholder, scope controls, normal Watch notice/name/explanation text, and the Watch-specific prompt filter. Remove the old table caption, **Previous/Next/page counts**, enclosing table/card panels and retained-row subtotal headings. Do not replace these with another toolbar.

Also omit the normal Watch running-count/next-refresh/status line; Watch/run CCost and Total Today CCost summaries; Watch token-mix lines; Run scope / valuation disclosure; and new-model/promotion announcements on Watch. Model announcements belong to Models. Do not add these back to explain the new loading behavior.

Scope this cleanup to Watch. Shared navigation and the existing normally hidden, exceptional host/offline/stale/error notification still provide truthful failure feedback; normal healthy operation must have no replacement status banner. Show loading/failure information locally where the affected card/field belongs.

## 2. Unframed active cards

- Use a logical card for each running prompt, grouped only by spacing and consistent typography: **no enclosing border, parent panel, shaded card box or table frame**. Align cards and tables to the full available main-content width, as on Models.
- Sort active cards by the focal running prompt's original start timestamp, **oldest first, newest last**; deterministic session/prompt identity breaks ties. Do not sort by latest tool event or session title update.
- The active list grows and shrinks with its content. **No fixed height, independent vertical scrollbar, row/card virtualization that hides active records, pagination or filtering.** If 100 prompts run simultaneously, all 100 cards are present and the document/page scrolls.
- Use **No running prompts** once initial active acquisition has confirmed there are no running prompts. Do not show an empty-success state while loading or on source failure. This message may coexist with recently finished cards during their brief terminal display window; those cards must visibly have terminal outcomes.
- Each active card has three parts: the shared header, its prompt table, and tool/skill activity for the focal prompt. Final activity summaries may remain during the terminal grace period; running-tool indicators stop immediately when execution ends.

### Identity, consecutive prompts and concurrent prompts

Use stable canonical session and prompt identities. A card's focal prompt has at most four earlier prompts from the same session as context. The source can represent multiple genuinely running prompts within one session: retain a separate card per such running prompt, even if session titles/totals repeat. Derive activity for each focal prompt; never attach the newest prompt's tool/skill data to another running prompt.

For ordinary sequential work, a new prompt in a session may reuse that session's recently completed card, showing the new prompt last and the preceding prompts above it, instead of keeping a redundant terminal-only duplicate. Reorder by the new focal start time. An old completion timer must never remove the newly running card. This reuse must not hide a still-running concurrent prompt.

A session is eligible for Earlier Prompts only after it has **no running card and no remaining terminal-grace card**. Starting a new prompt removes that session from historical membership immediately and replenishes history from the next eligible session. Share acquisition and totals by session even when several active cards use it.

## 3. Shared card header and complete-session totals

Use the same header on active and historical cards:

1. **Session title alone on its own first line**, as an understated heading/link. No time, ID, status or aggregate on that line. Navigate to the existing Sessions route with that exact session selected, using its canonical ID (`#/sessions/<session_id>`), not its title. Follow existing safe untitled-session handling if a source title is absent.
2. A separate compact line with **Session Total C Cost: …** and **Session Total Duration: …**. Allow clean wrapping on narrow screens.

Both totals cover **every canonical prompt in the full session**, including prompts before Watch/browser/host startup and beyond the five visible rows. A session with 10,000 prompts must report the full session, not five prompts, a retained-row subtotal, a Watch-run subtotal or a recent time window. Apply the same definition to both sections. Preserve canonically attributed compaction costs in full-session totals even when synthetic compaction entries do not consume one of the five visible user-prompt slots.

Reuse canonical complete-session aggregation and attribution. Session Total C Cost includes the current prompt's known/provisional contribution and existing linked-child attribution without double counting; honor the existing Credits/USD preference. Session Total Duration is accumulated prompt execution time over the whole session, including current execution where supported, **not the age of the session or the wall-clock span including idle gaps**. Preserve the existing overlap-safe interval-union definition from `src/analysis/duration.py::accumulated_duration`; for ordinary sequential prompts this equals their accumulated execution durations. Do not silently replace it with addition that double-counts simultaneous work.

Load these fields independently of recent prompt rows. Use **Loading…** until available, and preserve meaningful provisional/partial/unavailable states. Never substitute a known five-row sum or fabricated zero while labeling it Session Total. Updates to active totals must incorporate new/corrected canonical data; historical totals must refresh when that session changes.

## 4. Shared five-prompt table

Use the same compact, unframed table/header treatment as Models: readable aligned headers, consistent spacing and restrained column separators, with no separate filtering/paging controls or vertical scroll region. Reuse the **visual** design, not Models filters or clickable sorting: the chronological order below is fixed.

| Position | Heading | Value and meaning |
| --- | --- | --- |
| 1 | **Date / Time** | Original prompt start in the application's configured timezone, exactly `YYYY-MM-DD HH:mm`, on every row. |
| 2 | **Prompt** | Existing canonical prompt number/preview and applicable outcome marker/label. |
| 3 | **Model** | Canonical model display value, in its own column. |
| 4 | **Effort** | Canonical effort value, in its own column. |
| 5 | **CCost** | Prompt CCost using the effective Credits/USD display preference and existing valuation provenance. |
| 6 | **Model Calls** | Existing canonical model-call count. |
| 7 | **Duration** | CLI Watch-equivalent prompt duration, including live elapsed behavior while running. |
| 8 | **Δ Context** | CLI Watch delta-context value; spell out Context, not Ctx. |
| 9 | **Context** | CLI Watch Next Incoming Context value, shortened to Context only in the heading. |

Expose separate structured Model/Effort values if the current DTO only contains a combined string; do not parse formatted display text heuristically. The context columns must use Watch semantics (`watch_delta_context_tokens` and `watch_next_context_tokens`), not the similarly named ordinary-report fields. Preserve signs, approximation markers, unavailable values and genuine context warnings. A concise header tooltip/accessibility description may explain that Context means estimated next incoming context.

Active card: display the focal running/recently finished prompt **last**, preceded by up to four earlier prompts from that session, oldest-to-newest. In normal sequential work these are the session's five latest prompts. For concurrent active prompts, anchor each card's five-row slice at its own focal prompt, so no real running prompt disappears and its activity still matches the final row.

Historical card: display the session's **five latest actual prompts**, oldest-to-newest within that slice; show all available when there are only one to four. Session selection is based on actual prompts, not title updates or synthetic compaction bookkeeping; preserve relevant compaction/context information through the canonical prompt projection without treating a synthetic event as an extra user prompt.

Do not fill missing rows with blank placeholders. Normal horizontal panning is acceptable on narrow screens for nine columns; do not introduce a nested vertical scrollbar or truncate essential metric values just to force them into the viewport.

## 5. Active tool/skill activity

These rows describe **only the card's focal prompt**, including the same canonically attributed child work as CLI Watch. Historical cards omit this whole third section.

### Tool calls

- Count-first, lowercase summary, e.g. **52 tool calls · 25 × read · 14 × shell · …**.
- Show up to **five named tool groups**, ordered by descending canonical call count with tool-name ties. If more distinct tools exist, append **N × other**, where N is the sum of calls in all omitted tool groups, not their number.
- Keep the summary readable with natural wrapping; do not inherit CLI terminal-width clipping. Five named groups is the presentation cap, not an acquisition/data cap.
- An arrow disclosure is available even with five or fewer groups. When expanded, show **all distinct tools, including those already in the summary**, one per line with call count and tool name. Keep consistent order and preserve relevant failure/cancellation markers.
- Count canonical deduplicated physical calls, not repeated observations of the same call. The sum of the full breakdown must equal the total.

### Skills

- Use the same count-first presentation with lowercase **skills**, replacing the CLI's `Skills (N)` wording.
- Preserve the CLI's current meaning: **N distinct confirmed custom/non-built-in skills**. Built-in and unknown/unverified-origin skills remain excluded. Existing data has skill identity and failure information, not per-skill invocation totals; do not invent counts.
- Show the first **five skills in the existing most-recently-loaded order**, with deterministic ties; if more exist, append **M other**, where M is the number of omitted distinct skills. Example: **7 skills · skill-a · skill-b · skill-c · skill-d · skill-e · 2 other**.
- Always support disclosure, including when the full list fits inline. Expanded content lists **every included skill**, one per row, including the five already shown. Preserve confirmed failure information. No multiplication prefix implying an unavailable per-skill invocation count.

Both disclosures start collapsed, retain their independent expanded states across refreshes, and support keyboard/focus/ARIA behavior. With no usage, show **0 tool calls** / **0 skills**; expanding shows a small truthful empty state. Avoid resetting scroll, selection or focus on every live update.

### Long-running tool

The third activity row follows CLI behavior: once a tool has been running for **at least 10 seconds**, show its name and elapsed duration. If several qualify, use the existing longest-running-tool selection. Reuse `RUNNING_VISIBLE_AFTER_MS` and canonical attribution rather than introducing a Web-only threshold. Hide the row when no tool qualifies and clear it immediately when the tool/prompt stops.

## 6. Lifecycle, colors and refresh

### Running and terminal state

- Apply yellow/amber **text across the running prompt row**, not to every row in the card. Do not paint contextual historical prompts yellow simply because their session is active.
- Successful completion uses the CLI-equivalent lime/success color; abort/error uses the critical red color. Preserve meaningful outcome markers/accessible text so status is not conveyed only through color. Existing context warnings must remain understandable within this treatment.
- Retain a just-finished card in the active area for the CLI recent-event period: **30 seconds by default**, respecting the effective `watchRecentEventSeconds`. The timer follows the CLI's observed terminal transition; merely loading old history must not replay fresh completion flashes.
- At expiry, remove that terminal card from active membership. Once the session has no other running/recent card, it becomes eligible for the five-session history. A newer prompt or an unrelated timer must not cause disappearance, duplication or stale data to overwrite a live card.
- During the grace period retain final tool/skill summaries if useful, but no ongoing-tool indicator. Historical cards have no activity section and use ordinary historical presentation; do not perpetually color all historical successes lime. Keep terminal outcome meaning available in the existing row labels/markers.

### Theme baseline

Use existing theme variables with Watch-specific running/terminal roles where needed; no new theme setting. A restrained initial design is an accent-colored session link with moderate weight (approximately 600), no panel background, and a muted totals line with aligned/tabular digits.

| Role | Classic | Web light | Web dark |
| --- | --- | --- | --- |
| Session link | Existing cyan/accent `#78dce8` | Existing accent `#2457c5` | Existing accent `#9cbfff` |
| Secondary totals | Existing muted `#adb3ba` | Existing muted `#51627b` | Existing muted `#a6b5cc` |
| Running | CLI-like yellow/amber, start with `#ffce73` | Readable dark amber, start with `#815000` | Yellow/amber, start with `#ffcf7b` |
| Recent success | CLI-like lime `#87ff00` | Accessible dark lime/green, start with `#3f6212` | Lime/yellow-green, start with `#a3e635` |
| Aborted/error | Existing error `#ff8d98` | Existing error `#b1263b` | Existing error `#ff9aad` |

These are initial token-aligned proposals; refine shades/spacing after visual checks while keeping CLI semantic roles and legibility in Classic plus both Web appearances. No requirement to copy arbitrary user ConsoleColor overrides into CSS.

### Shared cadence

Reuse the existing host-owned Watch coordinator and publication model. Do not add a separate acquisition engine or fixed polling loop per card/tab. Preserve:

- Automatic post-refresh delay `clamp(ceil(6 × refresh-duration EMA), 5, 30)` seconds; the current EMA weights slower work by 0.60 and faster work by 0.20.
- Explicit numeric interval behavior: active `max(5, configured)` seconds; idle `max(30, 3 × active)` seconds.
- V1 scheduled polling and V2 buffered/coalesced event hints, including the existing five-second earliest refresh behavior.
- Up-to-one-second presentation wakes for elapsed display, terminal expiry and ready publications without forcing another source read.
- Independent account acquisition (currently 60 seconds) and its existing freshness/retry behavior.

Prefer sharing these policies/functions over copying constants into Web code. Enrich the server projection where needed; keep cost, lifecycle, source truth and history membership authoritative on the server. Retain existing SSE/reconnect sequencing, without restoring the removed normal next-refresh/status text.

## 7. Earlier Prompts: five recent sessions and bounded scrolling

### Selection and contents

Hardcode **five historical sessions** for this iteration; no setting is needed. Choose the five most recently used **eligible distinct sessions**, ranked by the original start timestamp of each session's latest actual prompt, newest session first; use canonical IDs for deterministic ties.

Exclude sessions represented by running/terminal-grace cards **before** applying the five-session limit, and replenish from further eligible sessions. Do not accidentally show only three historical sessions because two of the first five catalog entries are active. Do not use session metadata `updated_at`, title edits, tool events, completion-observation time or synthetic compaction entries as substitutes for the latest prompt.

There is **no age cutoff and no Watch-start cutoff**. A session last used weeks ago still appears if it belongs to the latest five eligible sessions. Running 100 or 10,000 consecutive prompts in one session occupies one historical card showing its latest five prompts; the other four eligible sessions remain available.

Continuously maintain membership as prompts start/finish and sessions change; this is not the CLI's startup-only Earlier representatives or its global retained-row cap. Historical cards have exactly the shared header/full-session totals plus the prompt table, with **no active activity section**. Do not attach an Earlier marker to individual rows. If fewer than five eligible sessions exist, show those; if none exist after acquisition, show **No earlier prompts** within the expanded disclosure.

### Height and interaction

The expanded historical list alone lives in a **bounded-height container with vertical scrolling**. Cards/tables inside it remain unframed, without per-card scrollbars or paging. Collapse it to its one-line label/arrow by default on fresh page load; preserve the user's current choice through live updates.

Use roughly **3½ full five-row session cards** as a density target, not a rigid pixel mandate. At **1920×1080 fullscreen**, with normal zoom and an active prompt, expansion should still leave a useful part of the first active card visible below it. Use a viewport-aware maximum height that accounts for navigation/margins; visibility of active work takes precedence if 3½ full cards cannot fit. Do not impose that height limit on the active list or make it sticky merely to meet the target. Keep the history scroll position stable when new data arrives where practical.

## 8. Limited account-card cleanup

Keep the existing account/subscription usage cards at the bottom. For **Watch only**:

- Remove the section heading beginning **Watch accounts · …** / independent-observation/recovering wording.
- Remove the explanatory quote/callout boxes below the primary account metrics, including the current explanatory `ccost_notes` / `provider_ccost_notes` presentation around CCost/observed accounting.
- Remove the entire **Observation details** disclosure and its contents from every account card.
- Remove **Unaccounted usage (estimate)** from Copilot cards.

Retain primary account identification, quota usage/remaining/reset and the main account cost/usage figures. The owner's reference to boxes around CCost today is a request to remove explanatory decorations, not the account cards themselves or the primary figures. Keep genuine unavailable/stale/error states legible within the retained primary data. Scope renderer changes so this cleanup does not remove detail from the separate Accounts page. Broader account-card redesign is future work.

## 9. Progressive, active-priority acquisition

This requirement is about observable independence, not just placing Loading text in front of the existing full-history blocking path:

1. Prioritize discovering and publishing active cards immediately. Independently start historical-session loading in the background **even while Earlier Prompts remains collapsed**.
2. Publish each card's identity/header and up-to-five prompt rows as soon as available, independently of its full-session CCost/duration calculation. Load totals separately and fill their placeholders when ready.
3. Allow independent sessions to progress without waiting for one slow session or an all-cards barrier. Slow historical acquisition or a 10,000-prompt aggregate must not stall live prompt publication, terminal transitions, elapsed display or account updates.
4. Use bounded concurrency and shared/deduplicated canonical reads, caches and aggregates. The owner's thread examples express asynchronous independence; they do not require one OS thread/process per card or unbounded request fan-out. Do not repeatedly rescan all complete histories on every presentation tick.
5. Current detail transport/history limits must not cap the number of active cards. Reuse underlying history/analysis facilities where suitable, but do not open one independent Sessions-detail lease/acquisition loop for every card. Do not concurrently mutate a shared ReportService that has not been made safe for that access.
6. Associate results with session/prompt identity and source revision/generation so late historical/totals responses cannot overwrite newer active data or resurrect an evicted card. Preserve correct totals when the five-row slice changes, when a session moves between sections, and when more than one active card shares a session.
7. Keep failures local and truthful: missing/partial totals remain unavailable/partial rather than zero; failed history does not hide healthy active content. Reuse existing recovery/error handling. On navigation release only obsolete view-specific work/transport; do not stop the host-owned Watch engine or shared work still needed by other views/tabs. On host shutdown clean up its owned work through the existing lifecycle. Preserve the established host/transport boundaries.

## Affected areas and implementation organization

Likely owners: `src/web/assets/watch.js`, `render.js`, `app.js`, `app.css`, `live.js`, `index.html`; `src/application/live.py`, `live_projection.py`, `session_detail.py`; existing reports/session-history/aggregate and Watch projection helpers; focused Web/Watch integration tests and `docs/web-beta.md`.

Implement in coordinated stages within this FR if useful: (1) shared projection/history/aggregate and lifecycle support; (2) minimal card UI, metrics and disclosures; (3) progressive integration, account cleanup and verification. Preserve canonical valuation, skill classification, source acquisition ownership, settings and session navigation. Do not change CLI layout/history policy to make the Web fit, introduce a Sessions-page redesign, add a history-size setting, or broaden the account redesign.

## Acceptance

1. **Page cleanup:** Watch has the Earlier Prompts disclosure, active cards and cleaned account cards. No old Watch title, report toolbar/search/filter, combined table/pager, run/today/token-mix summaries, normal next-refresh/status text, valuation disclosure or model notices. Global navigation and exceptional failure feedback still work; other routes retain their intended controls.
2. **Active scale/order:** fixtures with 0, 1 and 100 simultaneous prompts show a truthful empty state or every expected card in ascending prompt-start order. The active list uses document scrolling with no vertical inner scroll/paging/cap. Decreasing active counts shrinks the layout.
3. **Cards/metrics:** header title alone links to the correct session; totals occupy their own line. Both sections use the nine exact columns in order, per-row `YYYY-MM-DD HH:mm`, separate Model/Effort, correct Watch context values and effective CCost units. One-to-five rows are chronological; the active focal prompt is last. Warnings/unknowns/outcomes remain truthful.
4. **History semantics:** select five distinct eligible sessions by latest real prompt, independent of Watch start and age; include old sessions when needed. A 10,000-prompt session occupies one card with only its latest five prompts and a complete-session total. Excluding active sessions happens before limiting; history replenishes and reorders as eligibility changes.
5. **Lifecycle races:** running yellow; observed successful completion lime/success and abort/error red for the configured recent window (30-second default); then correct history eligibility. Restarting the same session inside that window cannot be removed by a stale timer. Multiple actual running prompts in one session remain visible with correctly attributed per-prompt activity, shared totals, and no historical duplicate. Startup history does not replay completion flashes.
6. **Tool/skill disclosures:** cover 0, 1, 5 and more than 5 distinct groups. Summaries cap named groups at five and aggregate other correctly; expansion includes the complete list including inline entries. Custom skill count/exclusions remain CLI-equivalent and no unsupported invocation counts appear. Longest qualifying tool appears at the CLI's 10-second threshold and disappears on completion. Expansion/focus/scroll survive refreshes.
7. **Full totals:** compare complete-session CCost and accumulated execution duration with canonical full-history aggregates, including old prompts, more than five rows, concurrent work, attributed children, provisional running values and unavailable data. No retained-row subtotal, idle-session age or incomplete amount is mislabeled as a complete total.
8. **Progressive behavior:** with deliberately slow history and aggregate work, active cards and prompt rows render/update before totals finish; history loads while collapsed; independent cards fill progressively. Loading/failure states are field-local. Delayed responses, navigation, concurrent cards, reconnects and shutdown do not duplicate, regress or resurrect data. Verify bounded shared acquisition rather than one scan/lease per card.
9. **Visual/scroll verification:** check Classic, Web light and Web dark at 1920×1080 fullscreen, a laptop viewport and narrow/mobile width. Tables use Models styling without frames; active work page-scrolls; only expanded history vertically scrolls; the 1080p design leaves part of the first active card visible. Check long session/tool/skill names, nine-column horizontal overflow, focus/keyboard disclosures, row colors and stable updates.
10. **Account/refresh regression:** primary account usage remains, requested explanatory/Observation details/Unaccounted usage content is absent on Watch, and Accounts is unaffected. Verify shared adaptive/event-driven Watch cadence, independent account refresh and CLI behavior with focused existing tests. Update affected user-facing documentation; report any unverified visual/platform evidence honestly.

These are acceptance criteria for the eventual feature implementation. Creating this backlog-only request does not require a product test run, version bump or release.
