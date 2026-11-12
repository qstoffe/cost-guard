# Suggestion 000684 — Restore Mini hover opening after mixed touch and keyboard help

**Non-executable owner inbox proposal; no Ready priority or implementation approval.**
Origin method: `selected-worker-deferral`, Cost Guard FR000683, 2026-11-12.
Source revision: `c33e761099823a3705849e01825bdfc042bcaa29`, with FR000683's
v81.31 shared hover guard. Origin/owning repository: Cost Guard; component:
`src/web/assets/help.js` and the actual Chromium Document PiP integration.

## Excluded behavior and observed impact

FR000683's finite orphan protection is independently verified, but its acceptance
to preserve intentional hover interaction is **not fully met**. The existing
`probe_mini_fit.cjs` full invocation and focused `help-only` mode fail in
`probe_mini_duration.cjs` at Total-heading hover after the mixed-input sequence.
This is **FAILED**, not simply absent proof. The Decision Delegate authorized
scope-limited completion with this separable gap published; that is not owner
approval to implement this proposal. The failing assertion remains intact.

Reproduction uses a fresh owned headless profile, shipped HTTP/CSP/SSE and actual
Document PiP, scale/zoom 1. On **Edge 157.0.4341.46** and **Chrome 157.0.8103.51**:

1. Run the existing `probe_mini_fit.cjs` `help-only` scope, retaining the preceding
   prompt-help keyboard/hover/touch, selection, Duration and publication changes.
2. Focus Total's heading intentionally with Tab, dismiss with Escape, blur, move
   outside, then deliver the original single real CDP mouse arrival inside Total.
3. Trusted mouse pointer entry/movement and mouseover/mousemove are delivered;
   buttons are zero and native mouse `firesTouchEvents` is false. At the unchanged
   600ms opening check, the exact connected heading reports `:hover === false`.
   The safe opening guard cancels. The popup does not appear within the probe's
   15-second observation. Eventual `:hover === true` does not reopen it by itself.

Normal entry/panel transfer, other Mini value help, keyboard and touch alternatives
pass separately. No accounting, source-integrity, security or data-loss effect is
identified. Physical-desktop reproduction, other targets/engines and general
prevalence remain **UNVERIFIED**; this is not a diagnosis of the owner's original
intermittent abandoned tooltip.

## Investigation and limits

- At 600ms, negative hover persists before/after geometry/style/hit-test reads.
  The target is the same connected button, visible document/open window, with
  unchanged rectangle and an exact hit at the recent event's coordinates. A hit
  at remembered coordinates cannot prove the pointer remains in that OS window.
- Synchronous native reads from opener and a function defined in PiP agree. Quiet
  observation without CDP commands for 1.3s also fails; opener polling is not the
  established cause. Bringing PiP forward and a target-local evaluation do not fix it.
- Explicit touch-emulation enable/disable, two predetermined within-label mouse
  moves 100ms apart, and a pre-entry compositor screenshot do not fix the failure.
  No retry-until-PASS input or production forced redraw was retained.
- One bounded no-input trace sees negative hover through the natural five-second
  Mini render, then positive hover on its following animation frame, without new
  input. This is correlation, **not proven causation**. Mini's measured live-table
  layout is a useful investigation lead, not permission to change its cadence.

The shared opening guard, one-second watchdog, finite thirty-second stale-signal
lease and missed-every-exit browser/virtual-clock tests remain intact. Do not
replace them with indefinite CSS/remembered-coordinate trust, force-render polling,
an OS mouse hook or an extra Mini interval merely to satisfy this test.

## Smallest future outcome and acceptance

When separately approved, restore the original intentional mixed-input Total
hover path without resetting its 600ms opening deadline or compromising silent
exit protection. Establish whether the cause is product layout/ownership,
Chromium hover state or a demonstrable harness precondition. Keep the original
sequence/assertions, browser versions and physical uncertainty visible.

Both browsers should pass that path and the full duration/help matrix; genuine
stationary reading, label-to-panel transfer, selection, keyboard/pin and exact ARIA
cleanup remain usable. Missing every exit event, silent opening exits and stale
CSS must still recover finitely; closed/focus/pinned states must own no watchdog.
Run the previously unreached history-readiness subprobe and remaining duration
cases, or report them separately rather than claiming a whole Mini PASS.

Targeted semantic comparison found no equivalent current proposal or rejection:
000400 concerns Legacy retirement, 000676 controlled live costing and 000680 a
static benchmark. Historical shared-help fixes address orphan dismissal and
intrinsic targets, not this newly reproduced negative-hover opening interaction.
See the [FR000683 journal and decisions](../../../journal/web/contextual-help.md#fr-000683-bounded-hover-watchdog-2026-11-12).
