# FR 000529 — Fix Web Beta table scrolling and long-list navigation reliability

## Reported problem

A colleague testing Web Beta on Windows on 2026-10-28 found long lists effectively unusable: mouse/scroll interaction did not let them browse the list reliably. Web Beta is still optional Beta, so this is a pre-launch usability defect, not a reason to expand the CLI. The exact browser/input/route and cause are **not yet confirmed**.

The current Web shell wraps tables in independently scrollable .table-scroll containers with overflow:auto and max-height:65vh, sticky headers, and per-view paging. Watch tries to retain scroll anchors while redrawing rows on SSE updates; session detail separately has Follow live / Freeze snapshot behavior. These are credible investigation points, not established root causes.

## Required behavior

- Reproduce the reported failure in a real browser, identifying which route(s), mouse wheel, touchpad, keyboard or touch input and whether nested page scroll, internal table scroll, horizontal overflow, sticky header, focus, live redraw or page changes trap scrolling.
- Make long tables naturally navigable using available vertical and horizontal scroll. When pointer/focus is over an internal list, users can scroll that list; when at its boundary, page navigation is not confusing or unexpectedly blocked. Scrolling and row focus should not jump to unrelated positions during Live publications.
- Keep table headers legible, filters/search/paging accessible, row selections and anchors stable, and narrow window behavior workable. Avoid using arbitrary CSS overflow removal that makes 50-row paging, large reports or keyboard accessibility worse. Respect reduced-motion preferences and standard browser scrolling.
- Preserve existing canonical CLI-first values, frozen snapshot behavior, full-history totals, Web security/state boundaries, one live host and no new source/provider acquisition on navigation. Do not rewrite historical report calculations or silently auto-scan all Token Mix history.

## Acceptance

Real-browser interaction cases cover Watch idle/live changing rows, Sessions/Models/Accounts long tables, deep Token Mix, date reports and 50-row session Snapshot/Live paging. Test mouse wheel, touchpad when available, keyboard PageUp/PageDown/arrows, horizontal scroll, resizing and 360px layout, while recording unsupported input-device evidence honestly. A long list is browsable to the end with readable columns; focus, scroll offsets and text selection survive updates according to the current retention contract. Add proportionate DOM/CSS regression coverage, but do not call synthetic fixture scrolling a full physical-device acceptance.

**Priority:** Lower / before Web Beta production release. This is separate from completed FR000510's presentation parity and does not authorize Web promotion.
