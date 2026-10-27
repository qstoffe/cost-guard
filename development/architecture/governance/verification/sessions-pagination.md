# Sessions pagination and Windows console evidence

Observed 2026-10-27 on Windows / Python 3.14 / local Edge. Product v80.96.

## Deterministic acceptance

`development/tests/test_session_list_pages.py` exercises 0, 1, 100 and 1,001 roots;
canonical activity/id descending order, disjoint second pages, complete CLI-row
parity, bounded selected-root analysis, omitted unused prompt identities, archived
roots, partial source warnings, removed/added sessions, changed source identity,
invalid sizes/offsets/revisions and beyond-end rejection. Existing Web display,
Sessions/detail, live, lifecycle and CLI suites retain their independent coverage.

`py -3 development/tools/run_tests.py --suite full`: PASS, 109 files, 0 failing
files, 53.6 seconds (four isolated concurrent test files). The successful run
followed removal of reviewed temporary PNGs and completion of browser probes.
Earlier failed runs exposed oversized PNGs in the checkout and then a concurrent
browser-profile/layout inventory collision; neither was a product failure. One
later run was interrupted by a server restart and has no PASS claim.

## Actual browser

Run `development/tests/integration/probe_web_sessions.py --browser <explicit Edge executable> --output <owned JSON>`
separately from package/layout tests. Synthetic canonical first/second/detail DTOs
feed the actual served app, route handlers, DOM and browser history. The probe
does not read installed history or invoke models/accounts. Optional
`--keep-screenshots` retains synthetic images for visual inspection; remove those
reviewed temporary images before package validation.

PASS for light desktop, dark narrow and fresh direct-link/reload-equivalent cases:
50 initial rows, five distinct older rows, same-Web detail, Back/Forward, explicit
restart invalidating cached list observations, accessible pager labels and bounded
table scrolling. Light/narrow cases made five fixture captures including restart;
direct older link made one. Desktop viewport/table widths: 1170/1051 px. Narrow
viewport/table/content widths: 504/433/550 px; the table scrolls without document
horizontal overflow. Reviewed actual light/dark screenshots retained the existing
visual style, wrapped navigation, collapsed Advanced scope and canonical table.

This is real headless Edge, not physical mouse, keyboard-only or screen-reader
acceptance. Synthetic transport does not prove installed-source browser/SSE
integration. Existing full session-detail contract is unchanged.

## Real installation

`development/tests/integration/probe_session_pages_installed.py <owned JSON>`:
PASS with acquired V2 data and 1,994 available roots. First page: 50 rows,
23,105 compact JSON bytes, 3.452 seconds; next page: 50 distinct older rows,
2.495 seconds. These are one-run observations, not a before/after speedup or a
cross-page atomic snapshot. Page requests acquired no accounts and invoked no
model. The live shared OpenCode service was not stopped.

## Windows console investigation

`development/tests/integration/probe_sessions_console.py <owned JSON> --managed`:
PASS. Real `ReportJobs` children spawned from detached console-subsystem
`python.exe` hosts had a console (`GetConsoleWindow` nonzero); paired GUI
`pythonw.exe` hosts produced report children without one. This reproduces the
source-proven spawn mechanism, not an invented CLI dispatch from the browser.

The same probe launched this clone's production managed Windows host/tray with
external browser handoff deliberately disabled, verified `pythonw.exe` process
identity, and completed an authenticated `/api/reports` Sessions request: 50 rows
out of 1,994 roots. It stopped only its newly owned host. Native tray presence is
legitimate; a finite report console is not. Unit tests pin GUI interpreter choice,
unchanged detached process flags and fail-closed behavior if the pair is absent.
Process isolation, deadlines, cancellation and parent-loss cleanup remain intact.

No physical Sessions mouse click or external browser handoff was claimed in that
native probe; browser click routing and detached-worker behavior were measured
independently. macOS native acceptance and assistive-technology testing remain
outside this Windows delivery. No inference, new dependency or release ZIP.
