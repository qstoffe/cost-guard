# FR 000566 — Completion with explicit native-verification exception

2026-11-03, v80.146.

Full Watch account-card tracks and border boxes now divide a 448-pixel budget by
effective DPR/pinch scale, with a rounding margin below the requested 450-pixel
ceiling. Text is not reduced. Display/zoom changes update retained cards and
keyboard focus without source polling. Accounts, Mini Watch, accounting and other
Watch presentation semantics are unchanged. The original specification is intact.

## Demonstrated results

- Original 450 CSS-pixel card at emulated DPR1.5: **675 painted raster pixels**;
  corrected card: **298 CSS / 447 painted raster pixels**. Independent uncropped
  PNG scans include a 450-pixel ruler; fractional-scale evidence is retained too.
- **216** hidden Chrome cases passed: four effective scales, three themes,
  100/150/200% text, 1/3 accounts, desktop/short/mobile layouts. No clipped account
  content or horizontal page overflow. Same-size DPR change, pinch factor and
  actual retained keyboard focus are checked.
- Existing Watch browser regression: **12** cases passed, including CCost/native
  independence, quota/reset/progress/context states, alignment, disclosure,
  selection, history transitions and 100 prompt cards.
- Actual development WebHost v80.146 serves byte-matching CSS/JS with no-store and
  unchanged production CSP; Watch geometry/content/version survive reload.
- Full: **136 files passed**, zero failed files, serial bounded run in 295.6s.
  Earlier Full runs exposed a repaired VM browser-API stub and then a pre-existing
  timing-sensitive historical catalog-count assertion under concurrent load.
  The final serial Full passed that assertion unchanged; no test waiver was used.
- Working-tree validator: **11 checks passed**, six existing/advisory warnings.
- Read-only real-installation V2/Watch check passed and all owned workers closed;
  shared OpenCode was untouched. Daily completion and real-account browser paint
  are not claimed.

## Approved exception and unmet native scope

**Decision Delegate, 2026-11-03, FR000566 only**, authorized completion/merge with
native desktop before/after measurements at Windows 100%/150%, actual Chrome
page-zoom verification and owner-machine physical E2E **unverified**. Reason:
reproducible raster-scale failure and useful bounded correction can be verified
non-disruptively; shared-desktop interference is unnecessary. The delegate did
not waive the physical-width/readability objective or authorize desktop changes.
This is not owner approval or full native acceptance.

This workstation reports 144 effective DPI/150%, but that is not a card measurement.
The owner's exact zoom, already-running server/assets/cache and actual on-screen
before/after widths remain unknown. OS scaling and Chrome page zoom were not
changed; CDP scale/text simulations must not be presented as those native tests.
Firefox/Safari, macOS and screen-reader acceptance remain unverified.

Detailed measurements, screenshots, architecture ownership, verification scope and
decision attribution: [engineering findings](../../../journal/web/watch-account-pixels.md).
No release ZIP, inference, provider mutation or personal-browser-profile use.
