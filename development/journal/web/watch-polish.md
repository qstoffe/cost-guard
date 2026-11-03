# Full Web Watch cards, reset display and context markers

The historical 450 CSS-pixel cap below is superseded by FR000566's
[scale-aware physical-width correction](watch-account-pixels.md). Historical DPR1
and root-font evidence is not proof of a 450-physical-pixel cap at Windows150%.

## v80.142 — FR 000562 (2026-11-03)

`watch.js` now places each finite quota's own observed-period CCost in numeric
parentheses immediately after Used, preserving native Used/Total and units.
Unavailable/unpriced cost is omitted; a known empty window shows (0). Focusable
provenance retains the specific window, numerical independence and partial/estimated
attribution. Reset is the first detail directly below its matching bar, then pace.
Today/global daily scopes, acquisition, accounting and Mini are unchanged.

`live_projection.py` adds a full-Watch-only `context_cell`, explicitly matching
canonical guidance's owner ID. Its current continuation tokens include hidden
compaction/epoch invalidation; unrelated rows retain their own numbers without a
borrowed warning. The old `live_context` is unchanged for Mini. Full Context numbers
have no approximation prefix; approaching/exceeded use the same gold/orange triangle
and retain the complete footer. Focusable named icons describe severity and reference
that footer. In-place updates prevent focus/selection from freezing a stale warning.
No browser threshold calculation or new analysis/acquisition owner is introduced.

### Measured browser geometry

Windows headless Edge 156.0.4314.58, current assets, synthetic loopback fixture,
Classic/Web light/Web dark: all 12 viewport/theme cases passed. Every account in
each case had these widths (CSS px):

| Viewport | Default 15px root | 150% text (22.5px) | 200% text (30px) | Singleton/default |
| --- | ---: | ---: | ---: | ---: |
| 360 | 315 | 300 | 285 | 315 |
| 1366 | 450 | 450 | 450 | 450 |
| 1920 | 450 | 450 | 450 | 450 |
| 2560 | 450 | 450 | 450 | 450 |

Restoring the former effective 30rem rule/max-width behavior in actual DOM layout
at 150% text reproduced **675px** desktop cards in all themes. This explains a
plausible 670–680px overgrowth mechanism, not proof of the owner's exact browser
configuration. New grid tracks and card caps both use 450px; narrow cards shrink.
Font enlargement is text-size emulation, not physical browser zoom; viewport scale
and device-pixel ratio were 1. Browser zoom may enlarge physical pixels while CSS
pixels remain the layout unit. No page overflow or clipped account text occurred.

At the default root, bars measured **12.4375px** (.83rem), versus the previous
18.75px: 66.3% of their former height. Track radius is **2px**, with matching
Chromium/WebKit/Gecko fill selectors. Primary Reset gaps were **3.75px** and
secondary gaps **0px**. The probe checks per-window native/cost currency independence,
aligned subgrid tracks, singleton cap, exhausted/partial/unlimited/reset recovery,
theme contrast, keyboard focus, warning transitions and ownership, unknown compaction,
multiple rows, preserved selection, history transitions and 100-card layout.
Representative Classic desktop, Web light subscriptions and Web dark mobile
screenshots were inspected. Firefox/Safari engines, physical zoom, screen readers,
native desktop input and real-account browser paint were not executed or claimed.

### Real installation and verification

Fresh `probe_web_live.py --watch-cards` passed against read-only V2: one owner,
two advancing streams, three accounts, preserved run origin, one active/two history
cards, three cards with rows, one row/card and four bounded pending captures.
First rows appeared at 6.459s. All owned workers closed without cleanup failures;
shared OpenCode was untouched. Shutdown interrupted account-history work, so Daily
publication/completeness is not claimed. No inference, quota manipulation or extra
provider polling was added. Synthetic browser and real-source HTTP proofs remain
complementary, not an end-to-end real-account UI claim.

Focused tests cover exact thresholds/disabled approaching, per-window identity in
reversed source order, known zero/unavailable/unpriced/partial/estimated cost,
compaction/epoch changes, owning versus unrelated/concurrent rows, and rejection
of older captures/generations. Full passed all 133 files; the working-tree validator
passed all 11 checks with six advisory/pre-existing warnings. No requirement/test
exception, release ZIP, model call or provider mutation was requested or performed.

## Historical v80.140 — FR 000560

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
