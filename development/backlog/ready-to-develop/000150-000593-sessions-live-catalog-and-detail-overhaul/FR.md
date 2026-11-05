# FR 000593 — Web Beta Sessions: live, minimal session catalog and unpaged live prompt history

## Owner request, intent and sequencing

**Owner-approved executable Ready Feature Request, 2026-11-05.** Give **Sessions** in Cost Guard Web Beta a comprehensive UI/lifecycle overhaul so it matches the cleaner, table-first **Models** and **Watch** experiences. Remove the user-facing **Snapshot/Freeze/Follow-live** workflow, report-control clutter, frame/card wrappers, filters, and nested vertical table scrolling. A compact, automatically updated session catalog leads to a clean **session-name hyperlink**; that link opens a single session page with all prompts, updated live and displayed in chronological order.

**Sequence:** the owner requested FR000592 (false Watch loading warning) as a **separate FR immediately before this one**. Coordinate this redesign with in-flight **FR000590** (value-first tooltips, Watch `Context:` warning styling and CCost detail) and the existing cleaner Watch/Models table design; do not overwrite other workers' branches or reintroduce old tooltip icon/cursor behavior. FR000591 (Mini geometry) is independent.

This is a **large, intentional Sessions-specific refactor**. The absence of Snapshot from the **UI** does **not** authorize abandoning immutable, revision-checked source acquisition, cache/analysis consistency, retained evidence, or the read-only OpenCode boundary. Keep any necessary internal frozen/canonical page/revision guards invisible to users; eliminate the `Snapshot` *experience*, not data integrity.

**Authoring boundary:** publish this FR in Ready and update identity state only. No source code, tests, docs or version bump while authoring.

## 1. Remove the report shell/clutter on both Sessions routes

For both **`/#/sessions`** and **`/#/sessions/<id>`**:

- Remove the visible route heading **“Sessions”** / **“Session <ID>”** from the upper generic page toolbar, and remove its **Refresh snapshot**, **Cancel**, **Reading this report**, **Output includes reasoning**, **Snapshot**, **Follow live/Freeze snapshot**, **Search displayed report tables**, **Presentation filter only**, **Source and reading guide**, and related report/status boilerplate. No separate **filter/search box** for the list or detail, no “catalog order frozen; row values…” explanation, and no snapshots/capture timestamps being promoted as primary UI.
- Remove “Advanced session scope”, “Latest sessions / restart browsing”, the session table's filter and outer section/panel/card/bordered scroll frame. Retire only the **Sessions-specific** presentation of these controls. **Do not remove them globally** from other routes that legitimately use finite report scopes, refresh or cancel.
- Retain navigation through the main app and relevant truthful **shared host/auth/source warnings** where essential. Errors, unavailable content or partial/retained evidence must remain distinguishable from known empty results even though verbose report disclaimers are removed. Provide accessible names/landmarks without an extra visible title/card.
- Use the same Web light/dark and Classic table vocabulary as the current Models/Watch layouts. No standalone tooltip `?` buttons; applicable column-heading help and conditional value tooltips follow FR000590. No second tooltip engine or dense legalistic paragraphs.

## 2. Sessions list — exactly six columns, modern single-line design

Display a single clean, unframed table directly below normal app navigation, with these columns in **exact order**:

| Order | Heading | Content |
| --- | --- | --- |
| 1 | **Last activity** | Full **local date and clock time** of the latest known activity for this root/session, correctly updated when authoritative activity advances |
| 2 | **Session name** | The human-readable session title **as a hyperlink** to the corresponding session detail; not the raw session ID |
| 3 | **Model** | One meaningful model name when single-model; **`Multiple models`** when several different models contributed, based on actual canonical evidence; unknown remains honest |
| 4 | **CCost** | Whole-session reference cost, with existing unit selection and partial/unknown semantics |
| 5 | **Prompts** | Canonical number of prompts in the session |
| 6 | **Duration** | Actual canonical execution duration (not a formatted-string ordering key) |

- **No separate Session ID column**, no “Session / name” multi-line combo, no “Model / effort” heading, no “Running at snapshot”/archived badges cluttering a second line. **Every data row stays one line**; no line wrapping in any cell. Session name alone is elastic and consumes remaining horizontal space, truncating long titles with **ellipsis**. Full original names stay accessible; no need for a redundant visible `?`.
- Other columns use their **minimal intrinsic widths** sufficient for actual displayed values and headings, including current CCost unit, local datetime, large counts and sortable labels. If the viewport is truly too narrow to fit the intrinsic minimums, permit necessary **horizontal** overflow/panning without wrapping or hiding actual numeric cells; never introduce an internal **vertical** table scrollbar.
- All **six headings are sortable** with accessible sort state, hover/focus help, clear direction and deterministic tie-breakers. Default is **Last activity, newest first** (**descending by timestamp**; this is the intended order even though the owner called it “ascending” verbally). Other columns sort by their real canonical data: session title locale/text, model or the multi-model semantic display, **unrounded CCost**, numeric prompt count and **duration in milliseconds**, not rendered strings, currency punctuation or K/M abbreviations. Missing/partial values use deliberate stable ordering; no malformed dates or misleading “0”.
- Sorting must apply to the **full available Sessions catalog**, not silently only to the currently loaded 50 rows. Current `src/web/assets/render.js::table()` sorts/filters `session_usage` *within a remote page*; that is insufficient. Implement a bounded **source/server-side sorting/paged list index** or an equivalent coherent full-list sort source, with revisions and scalable metadata/cache use. Do **not** eagerly hydrate the full history of every session to achieve an interactive CCost/Duration sort; if an exact global sort needs a derived index, maintain it with truthful completeness and cost/performance safeguards. Avoid deceptive partial-only ordering. If a truthful full-catalog sorted key cannot be established, report that limitation rather than silently declaring acceptance.
- **50 sessions per page**, newest first by default. Under the table, put a **minimal footer** containing **Previous**, a readable `Showing 1–50 of N sessions · Page 1 of P` (or equivalent correct numbers/empty state), and **Next**. No filter/card wrapper or separate pager box above the table. The table extends vertically for its 50 rows; **the browser document scrolls**.

## 3. Live catalog behavior and stable pagination

- **No manual Refresh**: while viewing **page 1** of Sessions, newly discovered sessions enter automatically and the displayed first 50 are reconciled to the chosen sort order; under default Last activity descending, incoming newest sessions appear **at the top**, pushing the oldest visible rows off the bottom of that page. Show current metrics of already visible sessions as practical without replacing entire stable DOM unnecessarily.
- Target **roughly 5–15 seconds when healthy**, and no **multi-minute lag** to show a newly observable session (for tests, aim for `<= 30 seconds` after the shared source recognizes it). Prefer **piggybacking on the existing shared Web Live/Watch catalog or events** and a **bounded, coalesced host-owned refresh** rather than a per-browser-tab full catalog scan or costly 1-second polling. Source support, cache reuse and actual latency determine the final schedule. Avoid extra model inference or independent long-running providers.
- With a **non-default sort**, page 1 remains ordered by that actual selected key. A new session joins the first page **only if its sort position belongs there**; it must not always be prepended when sorting by CCost/Prompts/Duration/Model/Name.
- Once the user navigates to **page 2 or later**, **freeze that browsing view's membership and order** against newly arriving sessions so results don't shift or duplicate/skip while paging through older content. Reuse an internal catalog epoch/revision or anchored cursor as needed, but **do not call it a user-facing Snapshot**. Existing known row data may refresh safely, but newly arriving sessions must not change the page's membership or shift its boundaries. Return to **page 1** to resume the latest catalog and currently selected sort. Changing the sort resets to **live page 1**. Browser Back/Forward must not produce duplicate/omitted rows.
- When the source actually fails, hold **retained** rows with honest compact host/status information, not fabricate new arrivals, empty the list, silently switch sources or claim current freshness. Recovery updates page 1 and keeps older browsing stable until deliberately reset.
- Preserve stable session identities in the URL and row reconciliation even though IDs are no longer visibly listed. Existing `/#/sessions/<id>` bookmarks, Watch session-name links and legacy `/#/sessions/<id>/live` links must resolve to the same unified detail page (canonicalize obsolete mode route without breaking deep links).

## 4. Detail page — minimal hierarchy and entire live session

When clicking a session name from the list or **Watch** (or opening a bookmarked session URL), present **only this primary hierarchy** at the top, with **no outer card**:

1. Simple **`Show all sessions`** hyperlink at the top, going back to the Sessions catalog (preferably restoring list navigation/appropriate page as practical, without a user-facing Snapshot mode).
2. The **session name as the main large page heading** (not the raw ID, “Session history”, “Session <ID>” toolbar or “Report table”).
3. Directly below: **`Session ID: <full exact ID>`** as ordinary selectable text, for copying/identification (not another heading).
4. Next: **`Context: <current/next incoming session context>`** in the same clear form and warning behavior as Watch's post-FR000590 **`Context:`** line. The intended measure is the latest valid **session-level next-request context**, not first-prompt Ictx, the sum of prompt contexts, or a stale arbitrary previous request.
5. Under that, the **single unframed prompt table**.

The Context line must reuse **the same canonical context estimator and price-threshold severity** as Watch: warning triangle for approach, stop/octagon icon for exceeded thresholds, same severity coloring, thresholds, warning text, price impact and hover/focus/tooltip behavior as the earlier Watch FRs. No independent browser calculation or guessed thresholds. If unknown, show honest `N/A` without inventing a warning. **Do not add a redundant “Total CCost” line** here: the whole-session cost already appears in the table's footer total.

Remove from the detail display **Follow live / Freeze snapshot**, **Refresh / Cancel**, **First / Previous / Next / Jump to latest / Go to row**, **Snapshot frozen** and report/search/filter/status boxes. Also remove the **reference cost per active hour / active execution**, “Token Mix order”, “Output includes reasoning”, “Next incoming context” report prose, the old summary block, and “Source and reading guide” disclosure. Tooltips on *relevant headings/cells* should carry useful definitions instead; do not hide essential source-state warnings.

## 5. Detail prompt table — exact columns and chronological live rows

Use **one complete, unpaged, vertically document-scrolling** table with **ten columns in this order**:

1. **Prompt**
2. **Model**
3. **Effort**
4. **CCost**
5. **Calls**
6. **Duration**
7. **Ictx**
8. **Ictx CCost**
9. **Extra CCost**
10. **Token Mix %**

This preserves all **eight existing numeric/concept columns** while adding **Model** and **Effort** *before CCost*. Remove decorative **`~`** from all displayed headings (`~Ictx`, `~Ictx CCost`, `~Extra CCost`); the explanation of any real estimate/incompleteness belongs in accurate tooltip semantics, not a tilde. Keep each column's existing underlying meaning/cost basis. Model and Effort derive from correct canonical **main prompt** evidence (consistent with Watch), and should not be faked by splitting a decorative combined string if structured fields exist.

- Every row is **single-line**; **Prompt** is the only flexible grow/ellipsis column. Put the original prompt **clock time**, then (for actual running work) uppercase **`[RUNNING]`** in square brackets, then the prompt number (`#N`) and its short text on that same line. A running row has **yellow text across all cells**, matching Watch's semantic running color in each theme. When canonical evidence confirms completion/abort/stop, remove `[RUNNING]` and revert to **normal theme foreground**, not a hard-coded white in light mode. Preserve other meaningful error/partial state semantics, but avoid a second full explanatory row. Do not infer finish from silence or stale/partial observations.
- Display the **whole canonical session history, first prompt at top and last at bottom**. **No sorting** on this detail table, no pagination, and **no fixed-height/internal vertical scrollbar**. Whether the session contains 10, 100 or more prompts, the browser **page** scrolls through all of them. For unusually large sessions, optimize DOM reconciliation/rendering or incremental loading transparently, without user-facing pages, duplicate/missing rows or a hard 50-row cap. Document scrolling, focus/selection and live updates must remain usable.
- The first prompt should not jump when new rows arrive at the bottom; preserve the user's **scroll position, text selection and keyboard focus** during live updates. Append/reconcile changed rows by stable ID rather than replacing the entire table every tick. New/corrected live CCost, Calls, Duration, Model/Effort, Token Mix and context fields update using the existing canonical Live/session-detail source. Ended prompts freeze their final known duration; retained/unknown data does not falsely advance.
- **Column heading tooltips for all ten fields** follow the shared component and FR000590 rules (including exact text hover hit areas, modest hover-open delay, no standalone `?` icons). Use useful **conditional cell tooltips** such as complete local time on the prompt's clock and richer CCost breakdown where supported, sharing FR000590's server-owned data/partial-scope constraints rather than duplicating an unbounded analysis pipeline. No tooltip overload on every ordinary cell.
- All non-Prompt columns adopt **intrinsic minimal widths** for their heading and displayed numeric/text values (including units), with Prompt filling remaining space. On narrow screens allow necessary **horizontal table pan only**; vertical scrolling remains on the document. Keep sticky headings where they work without nested scroll containers, keyboard semantics, and light/dark/Classic contrast.
- Preserve the existing **footer totals row**, retaining the label **`Complete session`** and its correct **whole-session** CCost, Calls, Duration, context-cost components and Token Mix values. Add empty/appropriate cells for Model and Effort without shifting totals under wrong headings. Footer totals are not a sum of only currently visible/incrementally loaded rows; use canonical whole-session totals, display units and known/partial rules.

## 6. Acquisition/API/performance contracts

- Today's `src/web/assets/session.js::View` uses **50-row** `/api/detail` pages and **1-second browser polling**, and `src/application/session_detail.py::SessionDetails.page()` emits a 50-row immutable slice over a revision-checked `SessionHistory`. Refactor to support the whole visible history **without a UI page chooser**. It may use bounded internal chunk requests/cursors, incremental reconciliation or equivalent, but retain per-root consistency, revisions, safe response limits, lease bounds and cancellation/race protections. Don't push enormous blobs on the global SSE stream or run per-row backend requests.
- Keep the **single existing Live acquisition owner and isolated detail/history worker lanes**. Reuse catalog revision/invalidation and Watch data where safe; bounded server-side list refresh and 5-second-ish detail acquisition are acceptable if measured. Avoid new full catalog/prompt hydration per tab per second, long synchronous browser loops and duplicate price/source scans.
- The list's sortable **Last activity** timestamp requires an exact source-backed root activity field. Current `SessionUsageRow` exposes no such field; extend a safe exported DTO using existing root activity topology. The current remote Sessions page is sorted by activity but **exposes only 50 rows plus a catalog revision**. Implement global sort keys and live membership truthfully rather than relying on the old within-page `render.js::table()` sorter.
- Running metrics must preserve correct **source V1/V2 compatibility, causal subagents, canonical costs, absence/unknown/partial state**, source-change stop rules, human-readable title fallback and output limits. The UI is not allowed to rewrite OpenCode histories or persist a new user ledger. No model inference or extra paid provider calls.
- The removed **Snapshot UI** does not remove the need to track last-known *observed* values during transient failure. Preserve confidence/truth in existing data while keeping the normal screen visually quiet and actionable.

## 7. Acceptance and testing

1. **Shell stripped:** Both Sessions routes have no visible generic Sessions/Session-ID toolbar heading, Refresh snapshot, Cancel, Snapshot/Follow live, report search/filter, Reading this report, Advanced scope, enclosed report/table card, or nested vertical table scrollbar. Other routes keep their own required controls.
2. **List format:** exactly `Last activity | Session name | Model | CCost | Prompts | Duration`, single-line rows, only name grows/ellipsizes, name is the clickable link; correct datetime, single vs multiple model text and current units. No visible raw session ID, snapshot status badges or extra per-cell lines.
3. **Sorting/pager:** all six headings sort the **entire** available catalog using real keys with deterministic ties, Last activity DESC by default. Footer is Previous / accurate range + total sessions and pages / Next; 50 per page; no page-only mis-sorting, fake zero, swallowed row or duplicated page boundary.
4. **Healthy updates:** opening page 1 and creating new sessions causes their automatic appearance in the correct positions promptly (target 5–15 s, healthy acceptance <=30 s after source observation) without manual Refresh, repeated expensive report jobs or heavy tab polling. Page 2+ holds membership/order stable across new arrivals; returning to page 1 resumes latest; changing sort returns to page 1.
5. **Navigation:** click session **name**, Watch card title, or legacy deep link to get the same unified session detail with **Show all sessions**, the real title, `Session ID: <full ID>`, correct `Context: <value>` and one table. No stale Snapshot/Live mode URLs or visible mode switches.
6. **Detail table:** exact ten columns and correct `Complete session` footer, no tildes, no sort/pager, all session rows ordered oldest→newest. Running prompts render clock + `[RUNNING]` + `#` + preview on one line with yellow row text; final observations remove marker and use normal theme text. Model/Effort accurate and values update live without user Refresh.
7. **Context warnings/tooltips:** same canonical Watch next-context severity, triangle/octagon icon, red/yellow styling, price warning explanation and display logic, without a redundant Total CCost summary line. All meaningful heading/value help is accessible, concise and compatible with FR000590.
8. **Scalability & truth:** sessions with 0/1/50/100/1000+ prompts and large catalog, multiple models/subagents, active/aborted/ended prompts, partially priced data, V1/V2, source loss/reconnect, catalog mutation, deleted/archived sessions and title/metric changes remain correct. No unbounded poll, API size breach, source mutation, lost prompt, misleading empty result or scroll/focus jump.
9. Update focused **unit/DTO, server API, JS DOM/browser and real-source-safe regression tests** for both routes and supported themes/zoom/viewport sizing. Update current Web Beta/Sessions help/docs and the relevant Web architecture/module notes; keep historical completed FRs unchanged. Record actual measured refresh latency/work and remaining platform limitations rather than inventing passing evidence.

**Publication boundary:** Ready FR only with backlog watermark update. Product implementation must follow normal selection/delivery later.
