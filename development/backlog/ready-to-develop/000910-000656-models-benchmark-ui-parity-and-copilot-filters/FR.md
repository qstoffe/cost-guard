# FR 000656 — Models: harmonize benchmark UI, source controls and Copilot-based filters

**Owner-approved Ready Feature Request, 2026-11-09.** Permanent identity **000656**, Ready priority **000910**, following FR000655 (000900). **Backlog-only publication:** create this FR and advance `development/backlog/identity-state.json` highWatermark **655 → 656** in the same documentation-only commit on `main`. Do not implement product code, tests or releases during FR publication.

## Goal

On **Cost Guard Web → Models**, the new **Coding Benchmark – Cost per Task** table (introduced by completed FR000652) does not visually belong with **Models Reference Pricing**: it sits in a bordered/background panel, its source controls/date differ from the pricing section, it lacks manual refresh, and it shows many benchmark models irrelevant to the GitHub Copilot price catalog used by Cost Guard.

Make the two sections feel like one coherent, compact UI while retaining **two independent tables and two independent data sources**. Align headings, source links, fetched timestamps, refresh buttons and filter styling. Restrict benchmark rows to models that can be **confidently matched to the existing GitHub Copilot priced-model catalog**, then add **Publisher** and reorder/resize the columns.

## A. Unboxed benchmark section and unified source toolbars

1. Keep the two separate, equally styled section headings: **Models Reference Pricing** and **Coding Benchmark – Cost per Task**. Add clear, deliberate vertical whitespace between the upper table (including its controls/notes) and the lower heading.
2. Remove the **benchmark-only outer group box**: no large enclosing card/panel, tinted background, border or rounded frame behind/around the entire benchmark table. Its heading, controls and rows should sit naturally on the page, like the reference section. Retain ordinary table header backgrounds and subtle internal row/column separators where helpful; do not remove all table structure.
3. Under **each** heading, use matching controls with the **same CSS typography, gaps, alignment, button sizing, link style, responsive wrapping and status placement**, sharing the existing pricing toolbar components/styles where practical rather than duplicating mismatched patterns:
   - **GitHub Copilot** — an actual clickable link labelled **View source** (or consistent concise equivalent) to the official GitHub Copilot models/pricing list: https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing
   - **Terminal-Bench 4.0 · Harbor Hub** — retain an actual clickable **View source** link to the official Harbor leaderboard: https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4
   - Keep the existing **Refresh price list** action for GitHub and add a matching **Refresh benchmark** action for Harbor. Both links open their verified external pages safely and do not accidentally trigger a refresh.
4. Both sections display **Last fetched** with a matching Swedish-style numeric local timestamp, e.g. **2026-11-09 21:45** (`YYYY-MM-DD HH:mm`, 24-hour clock), using the application's **configured time zone** and the existing server-prepared pricing convention. Avoid benchmark's current browser-default `new Date(...).toLocaleString()` English/locale-dependent formatting; never change the underlying UTC source timestamp. A missing timestamp uses the same concise unavailable convention in both toolbars. Preserve the actual **last successful source fetch** timestamp through failures; do not update it merely because Refresh was clicked.
5. **Refresh benchmark must really refetch Harbor data on demand**, even when the existing automatic 24-hour cache is still fresh; a GET of the locally cached `/api/models/benchmark` response is not sufficient. Integrate an explicitly authorized, bounded, coalesced one-shot manual request with the host-owned `BenchmarkLane` instead of a separate browser-to-Harbor fetch, new daemon or timer loop. Provide a short **Refreshing…** state and a quiet success/failure outcome, retaining last-good rows and fetched time until a valid complete new snapshot succeeds. Disable/coalesce repeated clicks while in flight and preserve existing fetch/caching/security budgets and independence from the price-list refresh; the price list must remain usable if Harbor is down.

## B. Exactly two benchmark filters, same logic as reference pricing

Immediately above the benchmark table, add the same styled checkbox controls as the existing GitHub reference section, with the **same exact labels**:

- **Show all Copilot-priced models** — **unchecked by default**. When unchecked, only show benchmark rows matching GitHub-priced models currently marked selectable in OpenCode (existing `model_catalog.rows[].selectable` semantics); if selectable model availability is unverified, preserve the reference table's existing fail-open catalog semantics. When checked, show all **GitHub-priced matched** benchmark models, even if not currently selectable.
- **Latest versions only** — **checked by default**. Use the reference catalog's existing `superseded` and `superseded_selectable` distinctions, scoped to the first filter just as in the upper table. When unchecked, older reference-priced versions can appear **if Harbor has a matching benchmark result**.

**Hard upper bound independent of both checkboxes:** the benchmark must **never** show an entry for a model that does not exist in GitHub's reference price list. Even with **Show all** checked and **Latest versions only** unchecked, the maximum is the **intersection of Harbor-published benchmark configurations and GitHub-priced models**, not all Harbor rows and not all GitHub rows without benchmark data.

Both filters must update the benchmark table immediately, without fetching Harbor again or modifying the **upper pricing table's filter selections**. Initialize the benchmark's independent filter state to **all=false / latest=true** (same defaults as the upper table), preserving state through sorting, refresh and navigation where the existing view lifetime allows. Do not add a separate Effort filter in this FR.

### Matching and canonical model names

Reuse the project's existing validated GitHub model catalog and identity/supersession policy. Match Harbor rows to **publisher + exact/versioned canonical model identity** using only sound, documented equivalences (e.g. the existing verified Claude brand-prefix exception), not fuzzy text substrings or a loose family guess. When a Harbor model matches, display the **GitHub catalog's canonical Publisher and Model naming** rather than an inconsistent raw Harbor label. Preserve the official Harbor row/configuration identity, client, effort and source details separately; a model may legitimately have multiple clients/efforts and thus multiple benchmark rows.

If a benchmark model cannot be identified **unambiguously** as an actually GitHub-priced catalog model (including a missing/uncertain publisher or version), exclude it from this user-facing table rather than inventing a Publisher or sneaking it through `Show all`. This deliberately supersedes FR000652's older **display all eligible Harbor configurations** default; it does **not** change what the independent Harbor adapter fetches/caches internally. Price availability / model presence is not a claim about the user's subscription entitlement.

Keep the existing **New** highlight source of truth: only a matching **GitHub reference release date** controls it, never benchmark appearance/submission dates. Do not import GitHub price-list costs, promotions or release metadata into the benchmark task-cost math.

## C. Seven columns, exact order and compact sizing

Replace the benchmark's current six columns with **exactly seven**, in this order:

| # | Column | Source / display |
| --- | --- | --- |
| 1 | **Publisher** | Canonical publisher from the matched GitHub reference catalog |
| 2 | **Model** | Matched canonical GitHub model name; retain eligible New highlighting |
| 3 | **Effort** | Actual Harbor-tested reasoning effort |
| 4 | **Relative Task Cost** | Existing precise benchmark-relative sort key and compact ratio |
| 5 | **USD/Task** | Existing average USD per attempted benchmark task |
| 6 | **Coding Client** | Actual benchmark coding-agent/client identity |
| 7 | **Solved** | Existing benchmark percentage score |

**Sizing:** columns **Publisher, Model, Effort, Relative Task Cost, USD/Task and Coding Client** should use compact *content-fitting intrinsic/minimized* widths, without arbitrary generous minimums, forced 12ch/30ch blocks or `...` truncation. **Solved is the only column that expands** to occupy available remaining width. Align numerical data neatly; use stable header/cell alignment and sortable keyboard-accessible headers in the **new column order**. On genuinely narrow screens, preserve readable names/values through existing horizontal scrolling or sensible wrapping instead of clipping/eliding information. Remove the benchmark's current unconditional **52rem minimum width** where it causes avoidable wasted space. Keep the table readable in Classic/Web light/dark, zoom and long model/client cases.

**Preserve benchmark semantics:** one row per valid published model/client/effort/source configuration; keep independent sort state and default descending **Relative Task Cost** sort (now column 4). Filtering must not silently recompute the benchmark baseline from only visible rows: retain the full valid **Terminal-Bench 4.0** edition's lowest positive USD/Task as the existing relative-cost denominator. Consequently the minimum *visible* ratio may exceed 1.0x after GitHub intersection/filtering. Keep score, cost, zero/partial handling and USD-only benchmark unit unchanged regardless of the reference pricing Credits/USD setting.

## D. Implementation boundaries and acceptance

**Current ownership:** `src/web/assets/benchmark.js` (six-column benchmark table, source row, sort and locale-dependent fetched string); `src/web/assets/render.js::overviewModels()` (GitHub reference source toolbar and catalog filters); `src/web/assets/app.css` (`.benchmark-scroll` framed panel, minimum widths and shared `.model-price-controls`/`.model-filters`); `src/application/benchmark.py` (current release-date-only catalog join); `src/web/benchmark.py::BenchmarkLane` and `src/web/http.py` (host-backed automatic-only Harbor fetch and read endpoint). Reuse currently prepared catalog `selectable`, `superseded` and `superseded_selectable` fields and the existing server timestamp formatter. Maintain a clean ownership boundary between remote benchmark acquisition and model-catalog display/intersection.

Acceptance:

1. Both sections appear as normal page sections with equally styled headings/toolbars and visible separation; benchmark has **no enclosing bordered/background group card**, while table rows/headers remain readable.
2. Each has an official **View source** hyperlink, its own genuinely working refresh action, the same local **`YYYY-MM-DD HH:mm`** fetched-time convention, and coherent loading/disabled/error behavior. Manual Harbor refresh contacts Harbor despite a fresh cache, never changes pricing fetch state, and retains last-good data on failure.
3. Benchmark initially has **Show all Copilot-priced models unchecked** and **Latest versions only checked**, independent of upper table filters; all four checkbox combinations restrict the view to the correctly matched GitHub-priced catalog subset. Unmatched Harbor models never appear, and absent benchmark runs are never fabricated.
4. Publisher/Model values use the matched GitHub naming; multiple benchmark client/effort variants stay distinct, release-date New remains reference-driven, and no speculative/fuzzy publisher or model identities are shown.
5. Seven sortable columns appear in the required order with the first six tightly content-fitted and **Solved** flexing to use available width. No forced oversized panel/min-width or ellipsis; desktop/narrow/zoom and Classic/Web visual checks confirm compact alignment and usable horizontal panning.
6. Full-edition benchmark relative-cost denominator, actual task USD/success, source/caching independence, existing price-list behavior and accessible hover/focus/touch/sort semantics remain correct. Targeted Python contract, JS DOM and real browser/HTTP tests verify filtering, sorting, refresh, source links, timestamps, responsive layout and error/last-good preservation; no live model inference is needed.
