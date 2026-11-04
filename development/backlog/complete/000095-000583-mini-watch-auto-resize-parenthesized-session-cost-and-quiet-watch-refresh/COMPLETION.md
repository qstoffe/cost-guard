# FR 000583 completion

Implemented 2026-11-05 as **v80.164**. Base `30736ab6`; unrelated backlog-only
default `8147b1f9` retained. Original specification/body preserved intact.

- Earlier Sessions performs one gesture-bound height-only resize only for newly
  introduced vertical overflow. Expanded CSS uses the extra space; actual achieved
  bounds permit pre-expansion restoration, and manual resizing wins. Unsupported,
  rejected, missing-activation and clamped requests silently preserve usable scrolling.
  Publications/settings never auto-fit, move or reopen PiP; no geometry is persisted.
- Both Mini tables keep existing title-only ellipsis and edge alignment with
  `(Total CCost)` / `(<whole-session value>)`, including truthful zero/unknown/partial
  formats, units and accessible complete title/scope.
- Full Watch quietly retains prompt/session figures during brief refreshes, removes
  both original flashing labels and the equivalent top retry message, and preserves
  help provenance plus meaningful 30-second sustained-delay/unavailable/partial and
  host/auth/connection guidance. No acquisition/accounting/lifecycle API change.

## Verification

- Local Full: **141 bounded units, 1659 passed tests, one platform skip, zero
  failures, 89.9s**. Earlier concurrent browser/Full run had one catalog-count failure
  in the unrelated 872-root historical fixture; its unchanged complete rerun without
  browser load passed. No assertion, timeout, dependency or gate weakened.
- Working-tree validator: **11 passes, zero failures**, six existing advisory warnings.
- Hidden actual Chrome 156 at scales 1/1.5 and Edge 156 at 1.5: **113 layout cases /
  18 grouped checks each**. Native pointer/keyboard growth/restoration, measured
  outer/inner geometry, fallbacks, absent activation, manual native/CDP bounds,
  short-area clamp simulation, no unnecessary/SSE resize, Classic/Web light/dark,
  units/narrowness/ellipsis/help/sticky scrolling, placement and one SSE pass.
- Both Watch card types preserve figures and exact heights across five real-DOM
  retry/refresh cycles. Virtual sustained failures, unavailable state and recovery
  remain truthful. Original-source deterministic reproduction confirmed both labels.
- Read-only real V2 session-cost/report parity: four requests/all priced, no fresh
  valuations/cache writes/model calls, owned close complete; shared service untouched.
  One history batch failed and Daily was unpublished, so complete history/Daily
  health is not established by that probe.

An additional exploratory scale-2 run failed the existing placement harness before
new feature checks: native bounds clamped 500×340 to 436×296. It is not a scale-2
PASS. Physical dragging, monitor transitions, native-frame pixels, touch hardware,
screen-reader and macOS proof remain unverified. No requirement/test exception was
requested or granted. No release ZIP/tag/GitHub Release created.

Affected user/module docs and existing Mini journal updated; boundaries unchanged.
Full measurements, commands and investigation limits:
[Mini journal](../../../journal/web/mini-watch.md)
and [generated evidence](../../../architecture/governance/verification/watch-disclosure-refresh/).
