# Web presentation and configured-local dates — FR000657

2026-11-10; product v81.7. Scoped presentation change, not a new valuation/source
integration or a whole-runtime architecture reassessment.

## Implementation and source audit

- Models ends after both existing tables/controls with an unboxed heading, one safe
  official Artificial Analysis link and one short sentence. The official
  `https://artificialanalysis.ai/agents/coding-agents/` page was retrieved on this
  date and contained **Artificial Analysis Coding Agent Index vs. Cost per Task**,
  the composite definition and cost/performance axes. No stable chart anchor was
  established, so the canonical page is used. No ingestion or background request.
- Token Mix alone removes the prepared display token's leading `Partial `, in both
  currency variants and both tables. It retains N/A, known subtotals, original
  tokens, completeness/priced-request counts and exact numeric sorting. The
  existing total-title help carries separated partial-pricing/telemetry paragraphs;
  complete/empty usage omits inappropriate qualification. Remove the Token Mix
  partial class/style, not the shared Watch/CLI policy. Empty/operational state
  handling and existing row-level unavailable-cost help remain distinct.
- `render.js::timestamp` joins explicit Gregorian/Latin numeric fields with `h23`
  and an explicit IANA zone. It is used by Token Mix observed help, host/source
  notices, legacy report snapshots/retained rows, live Sessions and AI Stats range
  help. Missing/invalid timestamp or zone returns N/A, never browser-local fallback.
  Validated Settings exposes the effective timezone alongside existing preferences;
  this adds no timezone editor and never changes raw source timestamps.
- Existing server tokens already cover Watch, Mini, Accounts observations/exact
  reset help, Session detail, comparisons, benchmark fetches, pricing and AI Stats
  dates. They retain configured-zone DST/UTC-offset behavior. Numeric `web_reset`
  replaces the weekday-only Web reset label; original CLI `reset` is unchanged.
  Release/promotion ISO dates retain calendar-date semantics. Audit found no other
  browser Date formatting sites; source guard tests reject implicit locale clocks
  and browser-local field getters. Raw timestamps/sorts, source/user text, payloads,
  URLs, identifiers, CLI and diagnostic output are not rewritten.

## Verification

- Initial Full: all 181 groups executed; 180 passed. One lifetime VM mock lacked
  the new timestamp interface. It now uses the real presentation implementation;
  focused `test_web_loading.py` passes. Final Full result is recorded in completion.
- Focused display, remaining/report DOM, Models, Settings and session-detail tests
  pass, including quiet partial/unknown/empty values, dual units, raw preservation,
  observed help refresh, exact sorting and numeric Web versus unchanged CLI reset.
- `validate_package.py --working-tree`: 11 passes, zero failures, seven advisory
  existing prose/module-budget warnings. No cap increase, ZIP or Release.
- Hidden Chrome Models browser: six light/dark × 360/1366/1920 cases pass (356–376
  checks each), including final link-only structure, no frame/background/padding,
  safe official destination, keyboard focus and existing independent table controls.
- Hidden Chrome and Edge Token Mix: 65 rows in each of two 13-column tables;
  three themes × three widths, exact bidirectional sorting, both units, stable
  quiet refresh/focus/pan, keyboard/Escape and actual title hover/touch pass.
  Explicit en-US/sv-SE × New York/Tokyo browser zones preserve configured Stockholm
  clocks through spring/autumn DST and the year boundary; UTC is independently
  checked. Partial, complete, no-priced and empty title-help states pass without
  changing the report facts. Edge additionally searches rendered Models, Watch,
  Accounts, AI Stats, Comparisons and Settings plus their available help for US
  date ordering, English month-first dates and AM/PM. Empty Comparisons is not a
  populated-history browser proof; existing deterministic comparisons tests cover
  its unchanged configured-local start/precise timestamp tokens.
- Hidden Chrome actual Sessions `--dates-only`: shipped authenticated HTTP/DTO/DOM,
  50-row configured-UTC activity unchanged across two locales/two browser zones;
  Stockholm DST fixed expectations; 1001-row Session detail and every clock-help
  value searched for numeric-date/24-hour leaks. The old broad Sessions browser
  mode was attempted and stopped at obsolete navigation/explicit-report-loading
  expectations (Comparisons nav fixed; Token Mix now auto-loads). The new targeted
  mode tests current date behavior without asserting obsolete capture semantics;
  it is not a PASS for that old broad mode.
- Hidden Chrome real Document PiP `dates-only`: midnight/unknown finish and autumn
  repeated-hour offsets, stable focused help, hover/touch/Escape, both units,
  Classic/Web light/dark × 650/520/280 widths pass. PiP/opener locale and timezone
  emulation do not shift server-prepared times. The first attempt hit Chromium's
  shared-renderer locale-override conflict; applying it once to the opener repaired
  the harness. Token Mix's old unit-switch probe similarly needed an explicit
  Credits starting state now that Web defaults to USD. Neither required product
  behavior changes.
- Read-only real V2 installation: Accounts (3 cards, one acquisition owner), live
  Sessions (3053 available, real scalar/detail DTO checks), Normal (29 catalog
  rows, 25 selectable, 14 latest selectable) and all-models (29 rows) complete.
  Two streams retain one Live owner and advancing publications. No model calls,
  source mutation or shared OpenCode stop; owned workers close cleanly. This is
  integration evidence, not an independently reconstructed private-history oracle.

## Limits

Integrated Review browser was unavailable (`browser.disconnected`); all actual
browser/PiP evidence above uses permitted fresh-profile hidden Chromium. Browser
timezone emulation tests display independence, not mutation of the owner's OS
settings. No physical desktop, screen-reader or macOS native proof is claimed or
needed for this Web-only change. No paid inference, new dependency, benchmark
blending, native UI changes or acceptance exception was authorized/requested.
Detailed synthetic receipts remain in this worker's logical scratch:
`scratch:/models-chrome.json`, `scratch:/token-mix-chrome.json`,
`scratch:/token-mix-edge.json`, `scratch:/mini-dates-chrome.json`, and
`scratch:/sessions-dates-chrome.json`. The durable facts above do not depend on
those disposable browser profiles or paths surviving cleanup.
