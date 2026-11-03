# FR 000560 completion — v80.140

Implemented the full Web Watch presentation scope: 30rem-capped subscription cards,
slimmer same-font headers, thicker rounded teal bars, per-quota red usage/fill only
on canonical exhaustion and muted header-only tint. Independent statuses/CCost and
native usage remain intact; accepted recovery clears red styling. Watch-only reset
tokens reuse Duration notation and the existing publication clock, retaining exact
local deadlines and seven-day calendar/unknown/expired/not-started behavior.
Running and Earlier share individual rounded frames, no outer Earlier box and one
expanded/nonempty-only section separator. CLI, Accounts and Mini Watch semantics,
acquisition and quota/provider state are unchanged.

## Verification

- Focused quota formatting/projection/VM regressions passed, including deadline
  boundaries, midnight/DST, both windows and independent native/CCost semantics.
- Headless Edge 156: 12 rendered cases across Classic/Web light/Web dark and
  360/1366/1920/2560px, with 150–200% root-font enlargement, capped/single-card
  alignment, contrast, exhaustion/recovery/status states, keyboard/help/selection,
  ten-column overflow, per-session frames and history transitions. Representative
  screenshots inspected; no physical-browser/OS zoom evidence claimed.
- Fresh read-only real V2 Watch probe passed: one owner, two streams, three accounts,
  preserved origin and joined owned workers. No inference/provider mutation or
  shared OpenCode stop. Daily history was cancelled at close, not verified complete.
- Working-tree package validator: 11 passes, zero failures, six existing/advisory
  warnings. No release ZIP created.
- Full suite passed all 133 files with zero failed files in 77.1s (four isolated workers).

Architecture/docs and [durable evidence](../../../journal/web/watch-polish.md) updated.
No approved exceptions. Real-account browser exhaustion/reset transitions, physical
zoom/input, assistive technology and non-Chromium/macOS layout remain unverified;
synthetic browser and real-source transport checks are not end-to-end live pixels.
