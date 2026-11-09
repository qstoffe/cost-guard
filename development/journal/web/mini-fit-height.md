# Mini Watch manual Fit Height — FR000637

2026-11-09, v80.216. Scoped frontend change; no source, accounting or settings changes.

## Implementation and causal findings

- One compact ↕ native button joins the existing grouped header. Its accessible
  name is **Fit Mini Watch height**; standard ContextHelp supplies hover, focus and
  touch help without a new help surface/status line. The inert intrinsic header
  clone includes its full box/gap in both Earlier states and real/reference Today cases.
- `DisclosureSize` remains the single resize owner. Explicit fit clears disclosure
  restoration/pending observations, measures current visible content at the actual
  width, and issues at most one active height-only request. It never applies the
  disclosure's width-rounding correction. Clamps/refusal preserve normal scrolling;
  passive publications/settings do not resize, fetch, toggle or save geometry.
- Manual measurement bypasses the opening/disclosure two-row reserve entirely.
  Hidden Earlier and external help overlays contribute no layout; actual header,
  messages, empty states, rows, quotas, borders and body padding remain. CSS zoom is
  accounted for when converting rendered width/padding to natural clone dimensions.
- The first undersized/tall native test exposed an old estimator weakness: treating
  the side frame as zoom made the inferred top frame depend on **old window height**.
  At 600×850, an actual 154.25px document requested height184, leaving a 142px viewport
  with scrolling. Manual fit now excludes the same conservative16-DIP side-frame
  estimate as opening. This is still a platform-dependent estimate, not an OS claim.
- True 150% page zoom additionally exposed 2–3 DIP native quantization on unchanged
  clicks. A scroll-free fit already within the small 4-CSS-pixel rounding allowance
  is not resized again; actual document overflow does not qualify for that guard.

## Verification

- Final shipped-source deterministic Full: **175 files, zero failures**, 125.6 seconds.
  This includes reserve-free clone cleanup, old-height-independent targets, CSS zoom,
  rapid/manual/closed/disconnected fits, native refusal and snug-rounding guard regressions.
- Working-tree validator: **11 passes, zero failures**, seven existing advisory
  prose/module budgets; v80.216 consistency and architecture imports pass.
- Fresh real-installation read-only V2 daily probe: **PASS**, 1199 requests, 39 initiating
  prompts, complete prompt/cost coverage, reconciled category costs and quiet Credits/USD
  parity. One Live owner, two verified SSE streams, three accounts, advancing sequence
  and preserved run origin. Owned threads/processes 0, cleanup failures [], all owned
  Live/HTTP workers closed; shared OpenCode untouched. Elapsed 10.95s.
- Initial Full ran 175 files: 174 passed; the hidden synthetic batch wake's 2s timeout
  failed while multiple browser matrices were running. Focused rerun passed in 0.60s
  without code/test changes. This initial failure is retained, not called PASS.

### Native browser matrices

All use `node development/tests/integration/probe_mini_fit.cjs <absolute-browser>
<owned-output.json> <device-scale> <real-page-zoom> [scope]`. Zoom is set and queried
through the disposable browser's native settings, not inferred from CSS zoom.

| Browser / scale / page zoom | Scope | Outcome / recorded layouts |
| --- | --- | --- |
| Chrome 156.0.8078.80 / 1 / 100% | Full | PASS / 302 |
| Edge 157.0.4341.42 / 1 / 100% | Full | PASS / 302 |
| Chrome / 1 / 125% | Opening width; manual fit | PASS / 104; 98 |
| Chrome / 1.5 / 150% | Opening width; manual fit | PASS / 56; 98 |
| Chrome / 2 / 200% | Opening width; manual fit | PASS / 56; 98 |

Full includes 56 themed/font/value opening cases, native disclosure/lifecycle/history
and prompt-help regressions, plus the new manual matrix in **both size modes**:
0/1/2/4/20 prompts × 0/1/3 quotas, grow/shrink/idempotence, real expanded history,
pointer/Tab/Enter/Space/touch, delayed hover and keyboard help, rapid clicks, 100/125/150/200%
CSS zoom × system/serif fonts × Classic/Web light/dark, narrow table panning, capped
vertical scrolling, no activation, refused/unsupported APIs, actual-width resizeTo
fallback, overlay exclusion and advancing SSE without passive resize. The original
shared stream/storage/lifecycle assertions remain active.

At normal scale the empty-content sample fits **600×201 outer / 584×159 inner**, with
**4.75 CSS px** spare height and **zero** requests on an unchanged second click, in
both browsers. Taller/fewer-row cases shrink to their actual content, not two rows.

**Native clamps are not width-preservation or scroll-free PASS:** compounded 200% zoom/
DPR2 returned 600×220 → **461×312** from exactly `resizeBy(0,186)`; the next explicit
click returned 366×392 from `resizeBy(0,181)`. Chromium also moved native position.
Both still scrolled vertically; those achieved widths/positions are browser changes,
not app width-fit/move requests. No automatic retry, width repair or clipped-overflow
workaround follows. Reclicking after such a native width change is a fresh measurement,
not the unchanged-geometry idempotence case. Screen/height caps and scrolling remain tested.

Two test-assumption repairs preserve stricter semantic checks: source snapshot replay
could overwrite locally injected long Today text between opening and inspection, so the
header matrix's synthetic input is explicitly pinned until that matrix ends (then restored
before real SSE/lifecycle checks). A zoom-quantized already-snug 6.7px margin correctly
caused zero requests, so a former unconditional “must shrink2 DIPs” assertion became
the existing <8px natural-height/zero-scroll contract. Earlier failures are not PASS or
waivers; all final successful scopes retain actual native-call/overflow assertions.

Representative synthetic native screenshots (application content, not physical OS frames):
[Default opening](../../architecture/governance/verification/mini-fit-height/opening.png),
[Earlier expanded](../../architecture/governance/verification/mini-fit-height/expanded.png),
[Web light/help](../../architecture/governance/verification/mini-fit-height/web-light.png),
[Web dark/help](../../architecture/governance/verification/mini-fit-height/web-dark.png).
Raw bounded trial files remain in this worker's `scratch:/full-chrome-verified.json`,
`scratch:/full-edge-verified.json`, `scratch:/manual-125-complete.json`, `scratch:/manual-150-verified.json`,
`scratch:/manual-200-final.json` and `scratch:/width-{125,150,200}-verified.json`;
these names describe separate files, not a wildcard read requirement.

## Limits

The integrated Review browser was disconnected; browser probes use only owned strictly
headless disposable Chrome/Edge profiles and synthetic publications through the shipped
HTTP/auth/CSP/SSE stack. This does not prove physical desktop frames/manual dragging,
monitor transitions, macOS, screen-reader behavior or other browser engines. No desktop
input, model calls, service stop, source mutation, new dependency or release ZIP is used.
