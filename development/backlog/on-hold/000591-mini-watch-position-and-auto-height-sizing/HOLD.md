# FR 000591 — On Hold: native PiP resizing requires activation

## Decision and scope

On 2026-11-05, **Decision Delegate, not the owner**, directed this FR only to
On Hold after fresh installed Chrome/Edge measurements. The principal requirement
remains hands-free vertical resizing on Live content changes. Open-time or
eligible-click fitting with scrolling is not accepted as full delivery or an
approved reduced-scope implementation. No other FR is held by this decision.

The original `FR.md` is preserved unchanged. No product implementation was made,
no Complete ordinal was assigned, and ordinary maintenance progress was not advanced.
The original local `fr-000591` branch is retained; the hold/evidence publication is
on `fr-000591-on-hold` from actual remote default.

## Measured blocker

A minimal loopback fixture opened genuine Document PiP through hidden browser
input in disposable, strictly headless profiles. Native APIs were unmodified.
Every evaluation explicitly used `userGesture:false`; both opener and PiP
transient activation were checked inactive before and within every resize call.

- **Chrome 156.0.8078.80** and **Edge 156.0.4314.58** each rejected `resizeTo`
  (height +61) and `resizeBy` (height -47), called from both opener and PiP.
- All **eight** calls threw `NotAllowedError`, with the native message
  `resizeTo() requires user activation in document picture-in-picture` or its
  `resizeBy()` equivalent. Full messages are retained in the raw evidence.
- Every before/after measurement stayed **531×280 outer / 509×235 inner**.
  These are headless browser-reported dimensions, not physical desktop proof.
- The [Document PiP specification, §6.8](https://wicg.github.io/document-picture-in-picture/#resizing-the-pip-window)
  requires and consumes transient activation for both methods. Opening also
  consumes activation; `preferInitialWindowPlacement` couples cached size/position.

Observers and Live timers can measure content but cannot supply the missing
activation. Post-open resizing has the same restriction. Click-only fitting and
scrolling do not meet this FR's principal goal. No safe scoped alternative was
established; no synthetic activation, repeated reopening, native-handle workaround
or new privilege was used.

Evidence and reproducible diagnostic:
[feasibility journal](../../../journal/web/mini-watch.md#fr-000591--on-hold-feasibility-2026-11-05).

## Required owner decision before release

An owner must explicitly either:

1. Accept open/eligible-click fitting plus internal scrolling, with clearly
   disclosed position/size limitations and corresponding approved scope; or
2. Approve an alternative/platform capability that can satisfy hands-free resizing.

Do not release automatically on a date, browser update or dependency prose.
Independent position/size combinations, native vertical locking, the broad content
matrix and physical DPI/monitor/work-area behavior remain **UNVERIFIED**, not PASS.
The capability/geometry of future browsers is unknown.

## Diagnostic exception and unperformed work

For this FR only, **Decision Delegate** authorized a measurement-only exception to
the FR's browser-automation prohibition: strictly headless Chrome/Edge, disposable
profiles, hidden helpers, genuine hidden input to open PiP, no activation bypass,
no visible desktop effects. The exception does not authorize a product workaround,
waive the principal or independent-position/size requirements, or apply to future FRs.

No partial sizing/settings changes, broad acceptance matrix, product Full suite,
package validation, installed-source probe, version/release work or ZIP was run for
this development-only hold publication. The direct Repo Backlog instruction makes
product tests/version work unnecessary for this scope. No feature acceptance PASS
or completed delivery is claimed. Product architecture and user documentation are
unchanged because no shipped behavior changed.
