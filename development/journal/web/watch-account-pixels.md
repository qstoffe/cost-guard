# Full Watch account-card raster width — FR 000566

2026-11-03, v80.146. Scope: full Watch subscription/account grid only.

## Reproduction and correction

The v80.145 assets still used a **450 CSS-pixel** grid/card cap. With the same
synthetic long-label account in hidden Windows Chrome 156.0.8078.80, effective
scale 1.5 produced **450 CSS px / 675 captured raster px**. The uncropped before
image independently measures card pixels x=57…731 inclusive, width 675; the adjacent
magenta ruler spans x=57…506, width 450. This is a demonstrated CSS-to-raster
mismatch, not a stale `30rem` cascade. It is consistent with, but does not prove,
the owner's ~670 on-screen observation or the cause in their existing browser.

`watch.js` now sets a Watch-root-only custom width:
`floor(448 / (devicePixelRatio * visualViewport.scale))` CSS px. Desktop page zoom
is already included in DPR; it is not multiplied a second time. Visual viewport
scale adds pinch only. Resolution-media changes, window resize and visual-viewport
resize update the retained view without polling, acquiring sources or replacing
focused cards. Both grid tracks and card border-box caps consume the same value.
Text is not scaled; long identities/usage/warnings wrap and narrow tracks shrink.
Accounts, Mini, native usage, CCost, resets, progress and Context semantics retain
their existing owners. No global zoom/transform, hardcoded 150% breakpoint or
backend change is involved.

## Measurements and retained evidence

All values below use a 1280×900 CSS viewport, one synthetic account and default
text. Raster spans are scanned from **uncropped PNG pixels**, not inferred from
the DOM clip width. Fractional placement can antialias one ruler edge; saturated
magenta spans are 449–450 pixels. The product cap assertion remains strictly ≤450.

| Effective scale | Before CSS / raster | After CSS | Cropped PNG width | Uncropped painted span |
| --- | ---: | ---: | ---: | ---: |
| 1 | 450 / 450 | 448 | 448 | 448 |
| 1.5 | 450 / 675 | 298 | 447 | 447 |
| 1.875 | 450 / 844 rounded | 238 | 446 | 447 |
| 2.25 | 450 / 1013 rounded | 199 | 448 | 447 |

Before fractional raster figures above are rounded products, not retained
independent before-image measurements; the independently scanned baseline is 1.5.
The [retained evidence](../../architecture/governance/verification/watch-account-pixels/)
contains that before ruler image, after ruler images including fractional scale,
and compact machine measurements. Images must be viewed at native PNG resolution
for pixel counting; Markdown previews can rescale them.

`integration/probe_watch_account_pixels.cjs` passes **216** cases: effective DPR
1/1.5/1.875/2.25, Classic/Web light/Web dark, root text 100/150/200%, 1/3 cards,
360×800, 1280×400 and 1280×900. Long unbroken/non-ASCII identities, primary/native
cost text and secondary quotas remain unclipped with no horizontal page overflow.
Existing-card DPR changes at unchanged viewport dimensions preserve actual keyboard
focus; a separate 1.25 visual-viewport pinch simulation applies the factor once.
Narrow/short resize checks retain the card and focus. These are CDP scale/text
simulations, **not actual Chrome page zoom or Windows OS-setting changes**.

The same hidden browser then loads an actual development **WebHost v80.146** with
synthetic data through shipped bootstrap/session/HTTP/SSE/CSP. Served `/app.css`
and `/watch.js` SHA-256 values equal checkout bytes, use `Cache-Control: no-store`
and unchanged `style-src 'self'`. The real Watch classes consume a 298 CSS-pixel
cap at DPR1.5; six cards measure 447 estimated raster pixels each. Reload preserves
version, geometry and content. This establishes development-host integrity, not
the owner's already-running host/cache. The unauthenticated theme fixture alone
is not used for that claim.

## Read-only workstation check

Windows reports build 26300 (Windows 11); read-only native primary-monitor DPI
inspection returns 144 effective DPI (150%). This observation is **not** a native
card measurement. `probe_web_live.py --watch-cards` separately passed against real
V2: one owner, two advancing streams, three accounts, one active/two history cards,
two cards with rows, one row/card and four bounded pending captures; first rows
at 7.853s. All owned workers closed, no cleanup failure; OpenCode was untouched.
Daily was not published before bounded shutdown; interrupted account-history
phases are recorded, not Daily-completeness or end-to-end real-account paint proof.

## Scoped decision and remaining uncertainty

Final local verification: Full passed all 136 files with zero failed files in
295.6s using one concurrent file; the existing Watch browser regression passed
12 cases in the same Chrome version. Earlier Full runs found a missing VM browser
API stub (repaired in test seams), then a timing-sensitive historical report
catalog-count assertion under concurrent browser load. The final serial run
passed that historical assertion unchanged; no unrelated production/test behavior
or timing limit was weakened. The working-tree validator passed all 11 checks
with six existing/advisory warnings. No test waiver or release ZIP was used.

**Decision Delegate, 2026-11-03, FR000566 only:** proceed/complete/merge with native
desktop before/after measurements at Windows 100%/150%, actual Chrome page-zoom
verification and owner-machine physical E2E **unverified**. The delegate inspected
the FR/assets/baseline/probe and preferred adequate non-disruptive evidence over
shared-desktop interference. This is not user approval, a waiver of the physical
width/readability objective, a future blanket exception or desktop-use permission.
No external Chrome window, OS display change or personal profile was used.

The owner's exact page zoom, existing served asset/version/cache and physical
on-screen widths remain unknown. Firefox/Safari, macOS, screen readers, arbitrary
extreme pinch factors and physical multi-monitor transitions were not verified.
Do not describe this delivery as full native acceptance or CSS-only proof.
