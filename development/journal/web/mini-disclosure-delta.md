# Mini Watch disclosure delta and action help — FR000639

2026-11-09, v80.219. Mini-only presentation/sizing correction; source, accounting,
history selection, settings persistence and Live ownership are unchanged.

## Causal change

- The pressed Earlier rule painted `inset 0 -2px 0 var(--accent-ink)` over its accent
  background. Removing that shadow leaves the intentional border/corners and shared
  focus/forced-colors indications. Computed styles and native-PiP cropped screenshots
  confirm uniform fill in Classic/Web light/dark at four CSS zooms.
- Disclosure previously called the whole-window reserved fit target, unlike explicit
  Fit's reserve-free target. A single inert hidden clone now measures collapsed and
  expanded root heights at the same effective current width. Their fractional difference
  includes real margins, wrapping, borders and section content; only the resulting
  native target is rounded. No running-row reserve or unrelated fit padding enters it.
- The same `DisclosureSize` owner adds that delta to the actual preceding height.
  Achieved bounds (including partial/zero/refused growth) and layout qualify baseline
  restoration. Changed layout/manual geometry instead subtracts the current delta.
  An inactive expansion contributes zero to a later active collapse. A baseline above
  the existing fit cap is never shrunk by an expansion attempt. No width correction,
  second native call, timer correction, passive source resize or persisted geometry.
  Native width changes qualify against the achieved-width layout only if content
  stayed unchanged during the request. This avoids subtracting a full pre-clamp
  delta from partial growth, without restoring stale content after an intervening update.
- Fit Height was incorrectly attached as passive ContextHelp, allowing click to pin
  help. It now uses the unchanged shared action-dismiss/suppression semantics, before
  the fit handler runs. No global passive-help behavior changed.

## Verification and limits

- Final-source Full suite: **177 files, zero failures, 134.0s** with four workers;
  2,150 tests passed, one existing macOS zsh/PTY-unavailable skip on Windows. Initial
  Full also passed before the achieved-width correction (177 files, 254.1s, two workers).
- Working-tree validator: 11 passes, zero failures; seven existing advisory budgets.
- Deterministic Mini tests: 9 tests passed, including fractional delta/clone cleanup,
  relative tall/short baselines, native clamps/refusal/activation, changed content,
  manual and rapid events, fit reserve exclusion and idempotence.
- Chrome 156.0.8078.80 and Edge 157.0.4341.42 manual-fit/help matrices passed: 98
  layouts each. Both size preferences, 0/1/2/4/20 running x 0/1/3 accounts, grow/shrink,
  no-op, synchronous pointer/Enter/Space/touch help dismissal, no stationary reopening,
  deliberate hover rediscovery, refusal/unsupported APIs and SSE non-resizing.
- Disclosure matrix: Chrome and Edge at 100% and Chrome at true 125/150/200% browser
  zoom passed, 115 recorded layouts each. Cases include both size-mode document gutters,
  0/1/3 Earlier x 0/1/4 running rows, 220/400/650-DIP baselines, repeated Fit-before-toggle
  cycles, empty/loading, changed history/active/accounts, manual geometry, narrow wrapping,
  four CSS zooms x two fonts x four theme appearances, forced colors, activation/refusal,
  zero and partial native growth. Header/contrast/ARIA matrices passed in Chrome and Edge,
  104 layouts each. Native requests remain strictly height-only.
- The critical stable-width sample measured **109 DIPs** of added layout and achieved
  **201 → 310 → 201** outer height. Repeated cycles did not drift; subsequent Fit did not
  shrink again. Fractional browser zoom is distinguished from application target padding.
- Final compounded DPR/page-zoom probes passed in both size preferences: DPR1.5/150%
  and DPR2/200%. At the latter, Chromium changed 624×278 → 425×338 from one `(0,218)`
  request. Collapse correctly requested only `(0,-60)` and achieved 425×278, not the
  earlier over-shrink to 119. Remembered mode returned 352 → 413 → 352. At DPR1.5,
  Remember's requested return to 360 achieved 361: a native one-DIP quantization limit,
  not exact-geometry PASS. No automatic correction or width repair followed.
- Initial delta trials failed on an old region-overflow assertion. Natural Mini layout
  scrolls the document, not the prompt region; the deliberately short native-resize
  fixture also needed an actually undersized baseline. The assertion now verifies
  document overflow and achieved partial growth/restoration. Those failures are not PASS.
- A compounded zoom trial could not click an offscreen header action. The probe now
  scrolls that actual control into view before trusted CDP pointer input; it does not
  substitute synthetic activation. Final 200% browser-zoom disclosure coverage passed.
- Fresh real-installation read-only V2 probe observed 27 coherent publications, one
  running prompt with complete running/cost coverage, three accounts and four quota
  projections (two numeric capacities). No finished history was available in that
  bounded sample; synthetic browser history covers 0/1/3 rows. Acquisition closed in
  0.202s; the shared OpenCode service remained untouched. Source time: 9.672s.
- OpenCode's integrated Chromium/Electron browser was tried but exposes no Document
  PiP API. Native API/layout proof uses owned strictly headless disposable Chrome/Edge
  profiles through shipped HTTP/auth/CSP/SSE, with synthetic publications and CDP input.
  It is not physical OS-frame/manual-drag, monitor-transition, macOS or screen-reader
  proof. Native rounding/clamps are measured limitations, not invented exact geometry.
  No desktop input, personal browser profile, inference, dependency or ZIP is used.

## Retained evidence

[Compact native measurements and cropped fill screenshots](../../architecture/governance/verification/mini-disclosure-delta/README.md).
Raw bounded trials are this worker's `scratch:/delta-chrome-verified.json`,
`scratch:/delta-edge.json`, `scratch:/delta-125.json`, `scratch:/delta-150.json`,
`scratch:/delta-200-visible.json`, `scratch:/fit-chrome.json`, `scratch:/fit-edge.json`,
`scratch:/width-chrome.json`, `scratch:/width-edge.json`,
`scratch:/clamp-dpr150-final.json` and `scratch:/clamp-dpr200-final.json`.
