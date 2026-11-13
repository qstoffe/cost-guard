# FR 000706 — No uncertainty question marks before numeric CCost in tables

**Owner-approved Ready to Develop — 2026-11-14.** Permanent identity **000706**; Ready queue priority **000014**, directly after FR000705 (000013). **FR-authoring only:** publish this standalone request and advance the permanent-ID high-water mark in one documentation-only commit. Do not implement product changes, run live tests, modify versions/releases, migrate backlog repositories, or change unrelated backlog items as part of authoring.

## Owner-observed problem

In the Cost Guard **Web Watch** table, the **CCost / C Cost** column sometimes displays a leading question mark before an actual numeric cost (for example, `?123` Credits or `?$1.23`). Current implementation uses that prefix when some usage/pricing is unavailable and the visible amount covers only the priced subset. The owner does **not** want that uncertainty signal in a value cell: **if the application has a cost number to display, show the number plainly. Period.**

This is a presentation policy for **numeric cost values in tables**, not permission to fabricate a missing valuation or to treat incomplete source evidence as complete. It is **not** a request to change quota, Capacity, Remaining, or their estimate/unknown markers.

## Required behavior and scope

1. **A numeric CCost never has an uncertainty `?` prefix.** Show the already-calculated numeric value exactly as otherwise formatted, in the chosen Credits or USD unit. Examples (illustrative only):
   - `?123` → `123`
   - `?$1.23` → `$1.23`
   - `?<0.1` → `<0.1` if the existing formatter produced a real tiny-positive value.
   - Complete values already lacking a question mark remain unchanged.
   Do not substitute `Partial 123`, a warning glyph, a new badge, a hover-only "partial number" label, or other per-value uncertainty decoration merely to replace the removed prefix. Ordinary, general help that CCost is a **reference valuation rather than a bill** can remain.

2. **Audit all shipped tabular numeric cost displays**, not only one Web Watch column: full Web Watch running/earlier prompt and session tables, Mini Watch (including PiP), Sessions and session details, historical/normal reports, Token Mix tables and percentage-cell cost tooltips, model/publisher/date/group totals, and analogous CLI report/Watch table outputs. Include numeric CCost subtotals and numeric breakdown lines in table cell tooltips, total/footer rows, and cost unit switching. Apply the same no-`?`-before-a-real-number presentation principle to any *other* numeric table cell whose leading `?` solely marks an incomplete/uncertain computed value. This is a scoped audit of tabular numeric values, **not** a blind removal of punctuation or question marks throughout the UI.

3. **No invented values or changed calculations.** Keep all canonical raw CCost Decimal amounts, pricing fallback rules, request/token observations, missing-price/missing-usage flags, completeness/provenance state, source identity, aggregation, sorting, totals, rate computation, and internal diagnostics truthful and unchanged. A displayed positive priced subtotal may still be incomplete internally. Removing a display prefix must not silently recalculate the subtotal, count unpriced work as free, set `cost_complete=true`, alter persisted data, or redefine CCost as billed cost.

4. **Genuinely unknown is different from an available numeric value.** When no usable cost can be derived, preserve the application's established standalone unknown/unavailable representation (`?` **only if that specific field intentionally uses it**, otherwise `N/A`, `—`, `Loading…` or the existing legitimate state). An actual supported zero remains zero, not `?` or "unknown". Do not change cold-loading, verified-empty, invalidated-source or authoritative-unavailable logic merely for visual consistency. Do not show `?` concatenated to any numeric amount, including rounded `0`/`$0.00` that represents a real numeric result.

5. **Explicit exclusion — quota/Capacity estimation and unknowns.** Do **not** change quota bars, subscription/account quota figures, Capacity, Remaining, native balances/limits, quota extrapolations, or their existing uncertainty/estimate indicators, including a standalone `?` for unknown capacity and `~` for an estimated value. These are separate semantics expressly excluded by the owner. Do not globally change `ccost_amount` or shared formatting in a way that inadvertently removes legitimate quota indicators or breaks another consumer; choose the correct presentation boundary with focused tests.

6. **Consistent policy on existing and forthcoming features.** One data value must render without the uncertainty prefix in every relevant surface and under both Credits/USD settings, including asynchronous refreshes, historical/reloaded views, fixed snapshots, detail popovers, Mini and Full Watch. Avoid Web/CLI divergence unless the output is explicitly outside numeric-table scope. Earlier FRs requiring visible `?` for a **numeric CCost with partial pricing** must be interpreted as superseded **only for that display marker**; their source-accounting, truthfulness, tooltip content unrelated to this marker, and other requirements remain intact. In particular coordinate with pending **FR000704** (Mini CCost detail values) and **FR000705** (Token Mix cost tooltips).

## Repository evidence and starting points (static code/docs inspection; not a runtime repro)

- `src/numbers.py::ccost_amount(value, unresolved=True)` currently prefixes `?` to a real Credits/USD cost. Be careful: the helper also handles unknown/zero conditions and multiple consumers; preserve their legitimate semantics.
- `src/application/display.py::amount_tokens()` chooses the `unresolved` state for several cost keys and manually prefixes `?` to `run_ccost`; `history_tokens()` similarly prefixes `?` for partial Token Mix category and total costs. Search all display-token producers and consumers, not just these named lines.
- `src/web/assets/render.js` and the specific Web Watch, Mini Watch, Sessions, Token Mix and reporting renderers consume these formatted display values. Inspect both normal cells and cost-value helpers/tooltips, as well as CLI formatting paths.
- `docs/usage-and-cost.md` explicitly documents `?123` / `?` before partially priced CCost, alongside a special plain-subtotal exception. Update relevant user-facing documentation when implementing so it states the new consistent numeric-value rule and continues to distinguish genuinely unavailable amounts from reference valuations.

## Acceptance and regression checks

- **Primary visible case:** a Watch row with nonzero known-priced CCost and incomplete price/usage coverage displays the numeric amount with **no leading `?`**, in both Credits and USD. The same row with complete coverage has the same presentation. A fully unpriceable row still uses its legitimate unknown/unavailable state, never a fabricated zero.
- **Cross-surface matrix:** exercise partial-coverage numeric amounts in all audited cost columns, table totals, CCost breakdown/value tooltips and Token Mix cost-related cells, Full Watch, Mini/PiP, Sessions/report tables and applicable CLI output. Assert no `?123`, `?$1.23`, `?0`, `? <amount>` or equivalent concatenated uncertainty prefix appears around a real numeric CCost. Verify no replacement partiality label or icon is introduced just for those values.
- **Canonical-state preservation:** test same partial vs complete source fixtures before/after; numeric totals, raw precision, sort order, token counts, request attribution and completeness fields remain unchanged. A genuinely missing price/token never becomes zero or falsely complete. Keep snapshot/refresh and unit-toggle consistency.
- **Exclusion regression:** unknown quota Capacity remains `?` where intentionally specified; supported estimated quota Capacity/Remaining and other quota indicators retain their existing notation, help and semantics. Confirm ordinary question punctuation and other legitimate standalone unknown markers are unaffected.
- Update focused formatter/projection tests and representative browser/CLI rendering assertions; report what was actually covered. No paid-model live tests are necessary for this presentation request.

**Deliverable:** every tabular **numeric CCost** reads as a plain cost number, without exposing partial-coverage uncertainty as a question-mark prefix, while genuine unknown states and quota/capacity behavior remain intact.
