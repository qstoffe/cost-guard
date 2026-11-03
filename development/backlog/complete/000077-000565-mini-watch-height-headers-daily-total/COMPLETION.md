# FR 000565 completion — 2026-11-03

Product v80.145. Mini Watch opens/reopens with a measured conservative 560×250
screen-DIP request, centered column labels and semantic data alignment, plus a
separate right-aligned Total Today header from the full Watch's canonical daily
publication/display tokens. No accounting, source, full Watch layout or data-owner
change. Manual resizing remains free; no automatic post-open resize is used.

## Verified

- Actual Windows DPI **144 / 150%**, Chrome **156.0.8078.80**: unchanged 450-DIP
  baseline measured **729 physical pixels** of visible native frame, reproducing
  the reported discrepancy. Corrected first openings measured **428–429**, and
  reopenings after manual enlargement with dense/long/warning content **428**.
  Even raw native capture bounds including invisible resize border were <=438.
  Native chrome/security controls remain intact; sampled openings did not overshoot.
- Controlled genuine browser zoom **80/100/125/150%**; DOM inner/outer/DPR, DPI-aware
  GetWindowRect/client/DWM bounds and full window-only captures independently
  distinguish document CSS pixels, screen DIPs and physical pixels. No DPR-only
  or requested-size-only PASS. Native before/after captures and measurement table
  are retained in the [Mini journal](../../../journal/web/mini-watch.md).
- **PASS:** final local Full, **136 bounded units, 290.0s**. An earlier concurrent
  run's historical-report catalog-count failure and a focused 25s harness timeout
  are retained in the journal; isolated historical tests and final Full pass without
  weakening assertions or changing unrelated source behavior.
- **PASS:** working-tree validator, 11 checks, no failures; six existing advisory
  prose/Python design-budget warnings remain. No hard cap was raised.
- **PASS:** real hidden Chrome/Edge HTTP/CSP/SSE lifecycle/layout checks, Classic/Web
  light/dark, live units, separate daily click target, all five centered headings,
  semantic row alignment, sticky headers, independent/narrow scrolling and retained
  updates. Chrome emulated scales 100/150/200% pass layout, not physical OS proof.
- **PASS:** VM daily parity with full Watch despite prior activity outside visible
  rows, Credits/USD, zero/unknown/partial/loading/retry/stale/offline observations,
  source corrections and canonical day replacement; lifecycle/race/keyed-DOM cases.
- **PASS:** read-only installed V2 acquisition, 80 coherent publications before
  Daily became available, five known-finish history cards, three accounts; 28.282s,
  owned close 0.106s. No inference or shared OpenCode stop.

## Scoped exception and unverified scope

The **Decision Delegate**, not the owner, authorized bounded own-profile native
Chrome/PiP testing because integrated browsing lacked PiP and headless evidence
could not establish the required physical footprint. No personal browser profile,
shared desktop input, unrelated focus cycling or Windows display change was used.

The same Delegate explicitly substituted controlled genuine browser-zoom testing
on this 150%-scaled workstation for inspecting the owner's **original personal
Chrome zoom**, which remains unknown. This supersedes the earlier withheld
diagnostic exception and applies only to this FR/same-task delivery. The mandatory
470-physical-pixel cap at actual 150% Windows scaling was **not waived** and passed.

Actual Windows 100%/200% display settings, other-platform native frames, minimized
restoration, OS z-order and screen-reader speech were not verified. Higher OS
scales can yield a larger physical footprint; no universal 470px guarantee is
claimed. No native minimum prevented the required 150% result. The browser rejected
an experimental automatic resize for lack of a new PiP user activation; that
approach was removed, and the regression mock now rejects it rather than hiding it.

Architecture/module navigation, user help, version/history and the Mini journal
were updated. No archive was built. Complete ordinal **000077** follows the highest
current Complete name; maintenance progress advances only when this PR merges.
