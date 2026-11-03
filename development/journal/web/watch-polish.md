# Full Web Watch cards and reset display — FR 000560

2026-11-03, v80.140. No acquisition, quota-accounting or lifecycle change.

## Ownership and regressions

- `app.css`: Watch-specific 30rem subscription tracks, .43rem title padding,
  1.25rem rounded teal bars, per-quota red emphasis and muted header-only tint.
  The grid selector must outrank the later generic `.account-grid` rule; progress
  thickness must outrank the generic Accounts rule. Shared Watch session frames
  replace sibling border-top rules; the expanded nonempty Earlier section keeps
  exactly one stronger separator, with no outer group frame.
- `application/display.py`: a Watch-slot token uses canonical deadline/timezone,
  `duration_text` below seven days and unchanged `format_reset` otherwise. No
  formatted-string parsing. Generic nested reset tokens remain unchanged.
- `live_projection.py`: Watch account display uses the current publication clock,
  not the retained account-history projection's older timestamp. Native observation
  timestamps/provenance remain unchanged. No provider poll or browser timer added.
- `watch.js`: canonical per-window `exhausted` flags alone select red styles;
  restriction/stale/partial warnings survive. Rebuilt accepted account publications
  clear obsolete exhaustion. Absolute reset dates remain keyboard-focusable titles.

`test_web_watch_quota.py` pins seconds/minutes, 88min, multi-day/seven-day,
expired/unknown/not-started, midnight and both DST transitions, both windows and
advancing publication time. Generic reset tokens, native Used/Total and independent
CCost remain covered. VM cases include 0/49.9/50/75/99.9/just-below-100/100%, missing
denominators, unlimited, partial, stale and restriction-only observations.

## Rendered checks

`serve_web_watch.py` and `probe_watch_cards.cjs` passed 12 synthetic rendered cases
in Windows headless Edge 156.0.4314.58: Classic/Web light/Web dark at 2560×1080,
1920×1080, 1366×768 and 360×800. All load current shipped assets. Each also checks
150% and 200% root-font enlargement (not physical browser zoom), long labels,
single-card left alignment, overflow, capped widths, subgrid alignment, keyboard
disclosures, ten-column horizontal scrolling, top-layer header help, keyed updates,
selection/focus, warning/activity placement, history transitions and 100 cards.

Measured default desktop cards are 450px, header padding 6.45px with unchanged
12.75px font, bars 18.75px. Exhausted header/usage contrast ratios respectively:
Classic 6.43/7.83, Web light 5.69/6.54, Web dark 7.23/8.25. Primary and secondary
exhaustion independently and together, reset recovery, stale retained exhaustion,
restriction without numeric usage and unlimited/no-bar states passed. Body and
unrelated CCost colors stay unchanged. Representative Classic desktop, Web light
mobile and Web dark laptop screenshots were inspected.

## Real installation and limits

Fresh `probe_web_live.py --watch-cards` passed against read-only V2: one acquisition
owner, two advancing streams, three accounts, preserved run origin, one active and
two historical cards, two cards with rows, one row/card and four bounded pending
captures. First rows appeared at 6.734s. All owned workers closed, no pending work
or cleanup failure; shared OpenCode remained untouched. The account-history batch
was interrupted during shutdown; Daily publication/completeness is not claimed.

Synthetic browser and real-source HTTP checks are complementary, not an end-to-end
real-account browser run. No live exhaustion/reset mutation, inference, personal
browser profile, physical input/zoom, screen-reader, Firefox/Safari or macOS proof
is claimed. No requirement/test exception was requested or granted.

Final local product checks: Full passed all 133 files with zero failed files in
77.1s; working-tree validator passed all 11 checks with zero failures and six
existing/advisory warnings (public prose plus three pre-existing module design
budgets). No packaging, release ZIP, model call or provider mutation was performed.
