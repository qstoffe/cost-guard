# FR 000607 completion — 2026-11-06

Implemented in **v80.187**, with a scoped physical-verification exception below.
The original specification is preserved intact in `FR.md`.

## Outcome

- Fit on open/Default synchronously measures the current styled header's intrinsic
  width before requesting native PiP, with padding and a small rounding allowance.
  No replacement fixed Fit width, table-driven opening width or native resize loop.
- Existing content/warnings/accounts and two-running-row height fitting now use that
  width. Styles load before first content mount to avoid an initial scrollbar/wrap
  feedback loop; style failure/close races are covered.
- Earlier Sessions, current/manual width, Remember last size and position coupling,
  Settings persistence and passive Live behavior retain their contracts. Native caps
  retain accessible wrapping/scrolling and truthful limitation feedback.
- Settings help, user docs, Web architecture wording and the Mini journal are updated.
  No accounting/acquisition/layer boundary or distribution-policy change. Ordinary
  progress advances to 57 only when this PR's state reaches default.

## Checks and evidence

- Local Full: **152 bounded units, zero failures**. Focused Mini/Settings: **20 tests**.
- Working-tree validator: **11 passes, zero failures**, six existing advisory warnings.
- Five serial real Chrome/Edge **strictly headless** native-PiP runs, **62 layouts each**:
  Chrome scale1, Chrome1.5, Chrome1.5/actual125% browser zoom, Edge1,
  Edge1.5/actual125% browser zoom. Device scaling is emulated, not physical OS proof.
  Header snapshots cover fonts/themes, Credits/USD, long counts, loading/unavailable;
  unclamped achieved layouts fit on one row and fail fit at 6 CSS pixels narrower.
  100%-zoom observed outer widths: **378–497 DIPs**, versus the former nominal 650.
  Existing height reserve, disclosure/manual/Remember, no-passive-resize and Activity
  checks pass. Each zoomed run separately records **four header and two dense native
  clamp cases as limited-fit results, not exact-fit PASS**.
- Fresh read-only real V2 probe: coherent one-owner/two-stream Live, three accounts,
  complete/reconciling Daily (1,786 requests, 54 prompts), advancing Watch cards,
  clean owned shutdown in 18.56s. Shared OpenCode untouched; no inference.
- Full retained browser results, inspected opening screenshot, source-probe output,
  cause and limits: [Mini journal](../../../journal/web/mini-watch.md#fr-000607--v80187-intrinsic-opening-width-2026-11-06)
  and `development/architecture/governance/verification/mini-width/`.

## Approved exception and remaining uncertainty

**Decision Delegate**, not the user, authorized omitting physical headed opening,
actual Windows 150%-display-scale/native-frame proof, and physical manual-drag/
remembered-bounds checks **for this FR only**. Integrated browser was disconnected;
achieved native headless layout/bounds and real-source checks adequately establish
this bounded improvement. Disruptive desktop work is not indispensable, so On Hold
was rejected. No visible-desktop/shared-input permission or future waiver was given.

Physical OS scaling, native frames/work areas, monitor transitions and physical
dragging/restoration remain **unverified**; pre-opening frame/zoom estimation and
native clamps retain practical uncertainty. No unrun physical check is PASS.
No ZIP, tag or GitHub Release was created.
