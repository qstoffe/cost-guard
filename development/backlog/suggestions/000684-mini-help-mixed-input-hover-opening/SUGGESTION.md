# Suggestion 000684 — Restore Mini and Models hover opening after mixed touch and keyboard help

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

## Models reproduction and FR000703 exclusion — 2026-11-14

FR000703's stable-refresh portfolio independently passed its retention/DOM/AX cases,
but the appended canonical Models promotion-help journey **failed**, not merely
lacked evidence. Decision Delegate authorized scope-limited FR000703 delivery
excluding this ancillary mixed-input interaction, without weakening product help
guards or claiming a whole-portfolio PASS. This extends the existing proposal;
it grants no implementation approval and establishes no identical internal cause.

The shipped HTTP/CSP/SSE harness with a fresh owned headless Chrome
157.0.8103.51 document retains one `.model-relative.promotion` target across
Classic 360 → 1366 → 1920. Keyboard focus, exact multiline prices/promotion/Token
Mix content, Escape and bounds succeed. After earlier touch/open/outside-dismiss
cases, the original single mouse arrival in the 1920 case does not open help.
Trusted mouse entry/movement reaches the same connected trigger; native hover is
true at arrival but false at the unchanged 600 ms production guard. No intervening
pointer departure or focus loss is recorded.

Distinguishing controls, without rebuilding the target or forcing the panel:

- Fixed Classic 1920: two keyboard/Escape/blur/single-arrival hover cycles before
  touch pass; touch opening/outside dismissal passes; the post-touch hover fails.
- Touch capability enabled once before all input and left enabled throughout:
  the same two pre-touch passes and post-touch failure recur. Delivered mouse
  events remain trusted `pointerType: "mouse"`. Repeated capability toggles and
  resizing are therefore not required to reproduce this failure.
- Pass-through logging reads the native guard result before geometry diagnostics.
  Bounds, viewport/scroll offsets, identity, connectedness, document focus and
  the descendant hit at the arrival coordinates remain valid at the failed guard.
  This does not prove current physical OS pointer presence or a Chromium defect.
- Separate keyboard/mouse and touch journeys each pass all nine existing
  Classic/Web-light/Web-dark × 360/1366/1920 configurations, using one fresh
  document per journey and retaining its target across all cases. Exact content,
  bounds and named dismissal assertions remain strict. These are **not** mixed
  interaction proof. Terminal authorization feedback also passes independently.

The original mixed assertions/artifacts remain **FAIL**; later unreached mixed
cases are **NOT RUN**. Browser-versus-emulation causation and physical-desktop
prevalence remain unknown. No new Edge comparison or global source acquisition
was performed for this Models investigation.

Future acceptance includes both the original Mini path above and the original
same-node Models mixed-input nine-configuration journey, without resetting
between cases to obtain success. Preserve exact content, focus/touch alternatives,
Escape/outside dismissal, ARIA cleanup and bounded popovers, together with the
600 ms opening guard, silent-exit cancellation/watchdog and finite stale-signal
lease. Investigate actual ownership/layout/browser/harness causation; remembered
coordinates or a forced positive `:hover` must not substitute for safe presence.
See [FR000703 evidence and Decision Delegate disposition](../../../journal/web/stable-refresh.md).

## FR000704 measured isolation and scoped exclusion — 2026-11-14

Chromium **141.0.7390.37**, actual headless Document PiP at native 125% browser zoom,
reproduced the original Total-heading mixed-input **FAIL** on PR310. Trusted mouse
entry/move reported positive native hover, then the unchanged production opening
guard read **false after 600.3–600.4ms**. The target stayed identical and connected,
the document focused, with no recorded departure. At 15 seconds native hover had
become positive again; the closed popup did not reopen without new input.

A matched unbound Total button was installed before the Duration sequence, retained
through it and never attached to `ContextHelp`. Its trusted arrival also hovered
true, then native hover was **false at 651.9ms**, with the same geometry, identity,
focus and remembered-point hit, and no departure. Native results were observed
before diagnostic geometry reads. This separates the observation from that button's
help listener, not from every layout/browser interaction; it does not prove a
Chromium defect, current physical pointer location or desktop prevalence.

The independent fresh keyboard/mouse journey **passed** twelve 61-second native
stationary holds across Mini and Full Watch, exact CCost/Total help and both units,
Duration/focus/selection transitions, four theme/scheme combinations, narrow native
125% bounds, 0/1/3/5 rows, stable native size and PiP close/reopen. Fresh touch
Duration/Total access passed separately. The old-base **PiP-only RED** reproduced
the 30-second cutoff. Full Watch's discovered clock/cell replacement was repaired,
not excluded. These passes are not mixed-input proof.

**Decision Delegate authorized FR000704-specific scope-limited completion**, conditional
on those core results, which passed on `2bbccb8`. Only this measured mixed Total-heading
opening is excluded; unreached mixed cases remain **NOT RUN**. The original probe,
nonzero result and **FAIL artifact** stay intact. CI can treat only the exact guarded
trace/configuration as nonblocking for PR310 and its own main delivery, after both
independent core journeys pass. Missing/different evidence and all core failures
remain fatal; there is no blanket `continue-on-error` or future-tooltip waiver.

Future acceptance above remains unchanged. Evidence:
[measured run](https://github.com/qstoffe/cost-guard/actions/runs/43549260080),
[FR000704 journal](../../../journal/web/mini-tooltips.md). Physical Windows transitions,
assistive technology and the owner's intermittent incident remain unverified.
