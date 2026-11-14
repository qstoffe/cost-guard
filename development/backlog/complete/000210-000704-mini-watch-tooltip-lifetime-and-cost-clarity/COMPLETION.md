# FR000704 — Mini tooltip clarity and reliable stationary hover

Implemented for **v81.48 (2026-11-14)**. The approved [FR.md](FR.md) is preserved
unchanged. Current `main` remains the supported source distribution; no ZIP, tag
or GitHub Release is produced. Delivery PR: [#310](https://github.com/qstoffe/cost-guard/pull/310).

## Delivered behavior

- Shared help has one open-only watchdog, no inactivity cutoff during confirmed
  trigger/popup hover, and retained departure/identity/visibility/ARIA safeguards.
  Full Watch clock targets and prompt cells remain connected during metric refresh.
- Mini has the exact compact subscription/header/action help, localized reset and
  Activity wording, exceeded-only red Ctx help, and prompt/whole-tree Total groups.
  Groups sum canonical unrounded request contributions once; Full Watch's richer
  individual-agent detail and the 2 MiB event/replay cap remain unchanged.
- Only the live prompt Duration value is yellow. Whole-session Duration is N/A
  because the cost observation has no authoritative session execution interval.

## Actual verification

- Final local Full including exclusion-gate regressions: **196 files, 2,423 tests: 2,419 passed,
  four platform skips, zero failures/errors**. Package validator: 11 passes,
  zero failures, seven existing advisories; no cap or baseline raised.
- Actual Chromium 141 Document PiP at native 125%: old-base PiP **RED** reproduces
  the 30-second cutoff; **twelve 61-second GREEN holds** pass through three-second
  updates with zero pointer movement. Eleven read their trigger; Full CCost reads
  its associated hovered popup. Native hover and matching hit tests are required.
- Independent keyboard/mouse and touch portfolios pass exact CCost/Total help,
  both units, safe running-Duration fragments, selection/focus and lifecycle.
  Four theme/scheme combinations, narrow bounds, 0/1/3/5 rows, no passive native
  resize and close/reopen teardown pass. Native Windows/macOS ARM/Intel CI passes.
- The [journal](../../../journal/web/mini-tooltips.md) retains actual failed attempts,
  corrections, source-backed accounting checks and measured browser evidence.
  [Run 43549260080](https://github.com/qstoffe/cost-guard/actions/runs/43549260080)
  passed the complete independent core portfolio; its original mixed step failed.
  Final cumulative PR checks additionally cover the bounded exclusion classifier.

## Explicit Decision Delegate dispositions

1. **Minor installation-verification exception:** the combined live Watch probe
   failed its 90-second global Earlier-history wait; Earlier convergence is
   UNVERIFIED and that invocation's session-cost stage NOT RUN. Source/accounts
   succeeded. A bounded explicit-root probe passed independent population, Decimal,
   ownership, report and controlled Full/Mini parity for 36 physical requests,
   cold 36/warm zero valuations, with no model calls. Decision Delegate accepted
   this evidence instead of another global discovery run, not as full-history PASS.
2. **FR000704-specific mixed-opening exclusion:** original Total-heading hover
   after mixed touch/keyboard input remains **FAIL**, with later mixed cases
   **NOT RUN**. The native guard is negative despite positive trusted arrival;
   a matched unbound button reproduces the negative selector independently of its
   help listener. Decision Delegate accepted this isolated gap only after all
   independent core acceptance passed. Existing
   [Suggestion000684](../../suggestions/000684-mini-help-mixed-input-hover-opening/SUGGESTION.md)
   records measurements, uncertainty and unchanged future acceptance.

Neither disposition waives stationary lifetime, new Total access, accounting,
orphan cleanup or future tooltip requirements. Physical Windows PiP→browser chrome/
other-app transitions, screen readers and the owner's intermittent symptom are
**NOT RUN / not proved**. Stale positive CSS with no exit event is not an OS cursor API.
