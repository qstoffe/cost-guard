# FR 000578 — Mini Watch: right-anchored pipe separator for session Total CCost

## Owner request and backlog decision

**Owner-approved executable feature request, 2026-11-04.** Permanent identity **000578**; Ready priority **000180**, after the existing Ready FR000577 (000170). This is a focused **Cost Guard Web Beta → Mini Watch** presentation improvement. Drafting this FR does **not** authorize implementation in this session.

FR000574 introduced the combined first column **`Session / Total CCost`** in both the running/recently-ended prompt table and the collapsible **Earlier Sessions** table. It intentionally avoided a separate total-cost table column so long session titles retain as much width as possible. The owner likes the combined-column design but wants a cleaner **soft divider**: replace `/` with `|` and anchor the total-cost label/value at the far **right edge of the same first column**, while the session label/title stays at the **left**.

## Requested presentation

1. **Both Mini session tables:** apply identical first-column treatment to the running/recently-ended prompts and to expanded Earlier Sessions. Do not change their other columns or their separate table/disclosure behavior.
2. **Column heading:** inside the *one existing* first `th`, place **`Session`** left-aligned and **`| Total CCost`** right-aligned. Do not render the heading as one centered string. The pipe belongs to the right-hand header suffix, not to the title label or a separate column.
3. **Each session cell:** inside the *one existing* first `td`, place the session title/fallback ID left-aligned, with **`| <whole-session CCost>`** right-aligned against that cell's right edge. Replace the current ` / <amount>` suffix rather than adding a second separator. Keep a compact, consistent gap around the pipe; it is a visible text character, not a column border.
4. **Elastic title, protected suffix:** the session title alone expands into the space available between the left and right portions and gets an end ellipsis (`…`) when necessary. Its beginning remains visible; the right-hand pipe and **entire formatted cost/state** never truncate, wrap or disappear. Short titles stay at the far left; the amount stays at the far right, rather than immediately following the title. When a title fits, show it in full.
5. **Preserve space:** this remains **one physical table column with two internal alignment regions**, not an additional `Total CCost` column, a fixed-width cost subcolumn sized to the long header, or a reserved blank block equal to `Total CCost` on every row. The row's short numerical amount should occupy only its natural rendered width, leaving the rest available for the session title. Right edges of header suffix and row suffix align to their respective first-cell right edges; their pipe positions need not form an artificial vertical rule if the suffix texts have different lengths.
6. **Responsive and existing semantics:** use the already-established constrained title/suffix layout (currently `.mini-session-value`, `.mini-session`, `.mini-session-total`) or equivalent. Keep full **`| Total CCost`** header legible at ordinary Mini widths. When the entire table cannot fit at extreme manual narrowing/zoom, preserve the existing horizontally scrollable session region instead of clipping metric headings, silently hiding suffixes, increasing the PiP geometry, or letting cells overlap.

Illustrative appearance (not prescribed spacing):

```text
Session                         | Total CCost
A very long session title th…            | 482
Short session                             | 23
```

The same scheme applies to Earlier Sessions, even though that table has only `Session` and `CTX` columns.

## Scope and compatibility

- Keep **`Total CCost`** as the full-session/root-tree cost and the separate running-table **`CCost`** as the *individual prompt* cost. The longer label is deliberate so two metrics are not both called CCost.
- Preserve the full canonical session title on focus/hover/click and for assistive technology, accurate accessible column/row naming and explanatory help, the session-ID fallback, pricing/partial/unknown/loading states, and Credits↔USD formatting. Header help must continue distinguishing the two CCost scopes.
- Preserve running/terminal styling and grace, Earlier Sessions' default-collapsed disclosure and ranking, CTX, prompt number, Duration, stable live updates, sticky headers, vertical scrolling, Mini window placement/size, account quota display, and light/dark themes. No new data aggregation, browser valuation, storage, SSE source, backend acquisition, CLI/full Watch layout change, or separate setting.

## Acceptance criteria

1. In **both** Mini tables, the first header visibly reads `Session` flush left and `| Total CCost` flush right **within the same column**; all row titles are left-anchored and their `| amount` suffixes are right-anchored. The former slash separator is absent from this presentation.
2. With short and very long names and several differently sized values, the left and right parts remain separated by flexible empty space; only long titles ellipsize. The full pipe-and-cost suffix is always visible, including zero, `N/A`, `Loading…`, partial-pricing indicators, large totals and both display units.
3. No dedicated cost table column or fixed header-sized reservation steals extra title width; other headings and cells remain aligned and untruncated. Narrow widths/zoom use the existing region's horizontal pan without overlapping text or PiP overflow.
4. Header tooltip/accessible name still communicates **whole-session** CCost; each session cell exposes the complete original title and accurate cost scope. Keyboard focus, pointer hover/click and screen-reader labels continue working.
5. Cover collapsed/expanded Earlier Sessions, multiple running prompts, live rerenders, theme/unit changes, narrow/standard/resized Mini and both tables' sticky-header/scroll behavior in targeted DOM/layout regression tests. Update `docs/web-mini-watch.md` (and relevant Mini documentation) when implemented.

**Implementation boundary:** this task is to record an approved backlog Feature Request only. Do not change Mini code, docs, tests, release/version metadata or deployed behavior while authoring this FR.
