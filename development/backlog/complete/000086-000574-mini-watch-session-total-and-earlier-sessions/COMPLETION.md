# FR 000574 — Completion

Implemented in **v80.154, 2026-11-04**, from `main` base
`7df4a6a9a8c826f537970c4348c872bdb8fb4381`.

- Running table: **Session / Total CCost | # | CCost | Duration | CTX**. Only the
  session title truncates; a nonshrinking slash/full-session-cost suffix stays visible.
  Full-title focus/hover/click help and accessible scopes distinguish prompt/session costs.
- Neutral, collapsed-by-default **Earlier Sessions** header disclosure retains its
  choice through Live updates. Up to three newest canonical eligible sessions show
  **Session / Total CCost | CTX**, oldest-to-newest, above running rows in one scroll
  region. Active/grace duplicates are excluded; running rows are uncapped.
- Both tables reuse existing server-owned session totals/current-session context,
  canonical history and display-unit tokens. Prompt metrics, daily/native accounting,
  one SSE, PiP opening dimensions and independent subscription scrolling are preserved.
  No new scan, valuation, connection, polling or dependency.
- User guides, version facts, module contract/code map and
  [journal/evidence](../../../journal/web/mini-watch.md) updated. Complete bundle moved
  intact; merged progress advances ordinary count to 25.

## Actual checks

- **PASS:** local Full, 139 bounded units, zero failures, 84.9s; final validator,
  11 passes, zero failures, six existing advisory warnings.
  1653 tests passed; one standard macOS zsh/PTY execution skip on Windows, owned by macOS CI.
- **PASS:** focused Mini projection/Node regressions; final real hidden Chrome
  156.0.8078.80 and Edge 156.0.4314.58 Document PiP/HTTP/CSP/SSE at emulated device
  scale 1.5. Tests cover history counts/order, shared scroll and every running row,
  real keyboard disclosure/scrolling/full-title focus, units, retained/empty/partial
  states, expanded themes/enlarged/narrow layouts, unchanged dimensions and one SSE.
- **PASS:** real installed V2 read-only session-cost/full-report parity: four priced
  requests, zero fresh-cache revaluations, no cache writes/inference, one acquisition
  owner/two streams; 13.204s, joined owned close, shared OpenCode untouched.
- Initial Full had one existing timing-sensitive historical catalog-count failure
  during overlapping probes; isolated final standard Full passed without weakening
  assertions/deadlines. Initial browser publication-sync and format-expectation defects
  in the new test harness were corrected, not waived. Details in the journal.

## Explicit unperformed scope / approved exception

**Decision Delegate-approved, FR 000574 only:** fresh physical Windows-150% PiP
rendering/native-chrome observation and actual screen-reader speech were not performed.
Hidden real PiP used **emulated device scale 1.5**, not physical display-scaling proof.
Actual OS DPI/frame rendering and assistive announcements remain unverified;
historical native measurements are context only. No visible probe/desktop permission
was granted. No implementation requirement, failing test, CI check or Git protection
was waived. Delivery is subject to normal verified PR merge; this file is not merge proof.
