# CLI → Web display baseline

FR 000430; source baseline `20d0a90a5943b72d5ab241a97bffaaf6e2236313`, checked 2026-10-26.
This is the shared formatting foundation, not a claim that every Beta page is a terminal facsimile.

## Contract and ownership

`src/display.py` contains pure CLI-owned money, native-unit, multiplier/threshold,
token/context and duration primitives extracted without changing terminal behavior.
`src/numbers.py` retains CCost direction, exact reference rates and balanced shares.
Presentation imports these owners; application never imports presentation.
`src/application/display.py` adds immutable `display` strings and `display_roles`
only to allowlisted DTO fields. Opaque externally keyed maps remain opaque.
`projection.py` and `live_projection.py` export the same raw exact fields as before.
Finite reports and detail captures carry their configured timezone into cell tokens;
Live uses its existing report service timezone. No browser calculation, acquisition,
valuation or ranking is added. The DOM consumes tokens as text, not HTML.

Raw fields remain the only numeric sort inputs. Unknown tokens fail closed to N/A,
never raw unbounded Decimal text. Native reference rates are the explicit exception:
every meaningful digit survives; only threshold labels are compacted. Source unknown,
unavailable, incomplete and provisional evidence remains distinct from zero/success.
`?` marks incomplete known CCost, N/A unknown valuation, `—` unavailable account
attribution, and `--` unknown Token Mix categories/shares. Estimated status is explicit.
Roles map to readable text plus accessible palette classes; color alone is not status.

## Same-input inventory and remaining page work

`test_web_display.py` builds each ReportKind once and feeds that **same projection**
to ReportRenderer and the application exporter. Fixed synthetic source, catalog,
scope/config/clock fixtures are used; Watch uses the same warning prompt projection.
`test_application_reports.py` independently compares facade/raw report values across
both generations. `web_views.cjs` consumes actual facade results over loopback HTTP;
`web_display.cjs` checks golden DOM text, role classes, notice placement and exact sorting.

| CLI owner/scope | Web mapping and foundation | Page-specific follow-up, not intentional information loss |
| --- | --- | --- |
| Normal: concepts/sample, Models, model notices, Accounts, report notes | Overview uses the same frozen normal sample and server ranking; Publisher/Model/Relative CCost/(all-only exact native rates)/Release date. Promotion/new notices follow Models; report notes last. | 000450: sparse overview, concepts/Token Mix placement and complete section inventory; 000440: visual navigation. |
| Models: selectable vs all catalog | Same canonical model order, aligned one-decimal multiplier tiers, blank empty-sample cells and exact all-only native price reference. New/promotion/superseded roles retained; explicit catalog controls and exact numeric user sorting. | 000480 implemented; [Models checks and limits](models-display-parity.md). Physical/assistive-technology acceptance remains separate. |
| Watch: run/Today, retained session/prompt groups, context/tools, independent accounts | Same Watch projection, run origin, retained row order, raw subtotals, frozen duration values and provisional status. | 000460: one live table, terminal grouping/column layout and width-dependent context formatting; normal samples must never replace Watch scopes. |
| Sessions/list | Same root list, model/effort, total CCost, prompt count and duration; initial server order untouched. | 000470: default recent scope and intuitive navigation; separate Session id/Name terminal columns currently share a browser cell. |
| Session/detail | Same complete tree and eight metrics: Prompt, CCost, Calls, Duration, ~Ictx, ~Ictx CCost, ~Extra CCost, I/C/W/O %. Totals remain complete, never page sums. Compaction/no-call numeric sparsity preserved. | 000510: model divider/clock/breakdown placement, full percentile cell-role mapping and explanatory layout. Snapshot vs observed-retained Live remains explicit. |
| Accounts | Same account/provider/plan order, independent Normal observations, billing/native quotas, Pace, CCost periods/attribution; consumed credits round up, remaining/Pace down. Shared CLI reset tiers use frozen report time and configured timezone. | 000490 implemented: shared structured cards, known-only remaining bars, explicit blocked/unlimited/unknown/stale states and readable classified failures. [Accounts checks and limits](accounts-display-parity.md); physical/assistive-technology acceptance remains separate. |
| Date/Range | Same inclusive configured-local range, selected prompt rows/totals and full-session links. Shared detail metric tokens. | 000510: final prompt grouping/notices/explanations. No change to cutoff/DST/history semantics. |
| Token Mix | Same available history and independent model sample; balanced tenths percentages, compact raw-volume tokens and priced category CCost. | 000510: final concepts/column grouping/layout; unknown telemetry is not reconstructed. |

Intentional browser-only differences: native links/back navigation, explicit refresh,
Snapshot/Live controls, search/sort/filter, 50-row bounded paging, sticky headers,
accessible palette rather than ANSI, and locale-formatted **snapshot chrome** (same
instant; data-cell timestamps use configured CLI timezone). Browser filters/order
never recompute totals or change acquisition. Native catalog reference-price digits
are intentionally exact, not accidental excessive precision.

## Golden boundaries and evidence limits

Goldens cover zero/negative/missing/deep Decimal values; sub-0.1 CCost; upward CCost,
downward remaining/Pace; fixed money; 59.5-second minute rollover; `8.0x → 16.0x
(>200K)`; exact `0.000000123456789` native rates; unknown telemetry; running/estimated/
partial/threshold roles; configured-local timestamps and exact values whose rounded
cells tie. Existing terminal tests guard against extraction changing CLI behavior.

The deterministic DOM harness is not a physical browser, screenshot, contrast
measurement or screen-reader proof. No model inference or UI automation is used.
Do not relabel the page-specific remaining work above as intentional differences.
