# Mini header and Settings option scrolling — FR000635

2026-11-09, v80.214. Scoped frontend change, not a fresh whole-Web or backend audit.

## Implementation and causal evidence

- Mini's mismatched .8/.75rem header and independent flex wrapping became a shared
  .8rem/1.5 typographic rhythm. The title/toggle form a group; the whole Today readout
  reflows below it when necessary. Extreme native clamps can wrap the group too.
  Earlier has stable text, no pseudo-element arrow, an outlined collapsed state and
  a filled/underlined selected state. `aria-pressed`, `aria-expanded`, controlled
  section visibility and demand dataset change together before native measurement.
- Opening still measures inert clones in both states, reserves wider real/reference
  Today text, 8 CSS pixels and the measured gutter. Native disclosure requests stay
  bounded and height-only; no passive geometry repair, new stream or acquisition.
- A trusted wheel over an overflowing Fit option originally left scrollTop at zero.
  Nonpassive capture/bubble handlers received no native popup wheel events in the
  tested Chromium; a scoped passive listener receives noncancelable input and forwards
  delta units to the visible absolute help pane. It does not cancel native scrolling,
  select, save, focus or dismiss. No overflowing visible pane means no forwarding.
- A further real drag test found that help *inside* an option inherited native option
  activation and saved on release. A same-pane sibling experiment removed commitment
  and allowed native dragging. Painted panes now live outside option ancestry but
  inside the same native picker; pointer/focus preview identity is independent of
  selection and persists while entering the pane. Hidden accessible descriptions,
  native options/selectedcontent, narrow/touch in-flow help and fallback remain.
  No global wheel handler, mouse-event cancellation or custom combobox was added.

## Deterministic and rendered verification

- Final shipped-source deterministic Full: **175 files, zero failures**, 151.1 seconds
  (earlier Full also passed). Pixel/line/page wheel normalization, boundary guards,
  preview retention, fallback exclusion and atomic Mini state are executable regressions.
- Validator: 11 passes, zero failures; seven existing advisory prose/module budgets.
- Chrome 156.0.8078.80 full native Settings: PASS, including actual Input wheel over
  real Fit and very long synthetic help; selected/unselected/Default options; reversal,
  end/boundaries, direct wheel, scrollbar movement before/after release, unchanged
  selected value/write count and open popup; native keyboard/AX, persistence/rollback,
  three themes × 360/520/1280 widths × CSS zoom100/200, touch, actual browser200%
  and feature-disabled native fallback. Native scrollbar samples synchronize painted
  thumb position and input frames; they are not synthetic dispatchEvent proof.
- Chrome and Edge normal-scale full Mini: PASS. Chrome's full probe records 204 layouts
  including the 56-header matrix (themes, system/serif fonts, Credits/USD, localized/long,
  loading/unavailable and partial backing data), actual text ranges/centers/fonts,
  contrast >=4.5 when pressed, no arrow, stable horizontal positions, click/Enter/Space,
  fit/remembered lifecycle, native clamps, document scrolling and existing history/cards.
- Chrome focused width matrices at actual zoom125%/DPR1 and zoom150%/DPR1.5: PASS.
  Compounded zoom200%/DPR2 width matrix: PASS. Dedicated `high-scale` probe: PASS in
  **both** sizing modes, with collapsed/expanded screenshots, trusted clicks, actual
  requested/achieved bounds, <=1 active height-only request per action, no passive
  resize, no document horizontal overflow, and scrolling to Earlier/active/accounts.
- Actual hidden-opener/visible-PiP Enter/Space history-demand probe: PASS; accepted
  expand/collapse/close leases, fresh collapsed reopen and exactly one EventSource.
- The integrated Review browser was disconnected. All browser evidence above uses
  owned strictly headless disposable profiles/fixtures, not the person's browser.

## Real installation and Decision Delegate exception

### Edge-specific native scrollbar exception

Edge **157.0.4341.42** full Mini passed. Settings is **PARTIAL**, not full PASS:
all other Chrome-equivalent wheel/native/AX/keyboard/save/fallback/theme/zoom/touch
checks passed, but the actual native scrollbar-drag check **FAILED** (scrollTop0 of
2967, preview retained, popup open, value unchanged, writes0). Clearing device-metrics
emulation did not resolve it: actual inner1256×908, outer1280×1000, DPR1, visual
viewport offsets0/0 and scale1. Native mouse frames, thumb-paint synchronization
and recomputed bounds still failed. No guessed offset or product mouse-event hack
was introduced; the cause is unproven. The `without-drag` continuation reports
PARTIAL and preserves the original failure, not an equivalent full run.

**Decision Delegate** approved this one narrow acceptance exception after the
distinct native-viewport diagnostic and remaining matrix. Chrome156's strict real
drag PASS is complementary, **not equivalent Edge proof**. Manual Edge scrollbar
dragging remains unverified and **potentially affected**. Further harness/visible-UI
investigation is deferred; normal strict tests still fail if that gesture fails.

### Real-source component assertions and teardown

Daily-only real V2 checks succeeded: 963 requests, 33 initiating prompts,
prompt_count_complete=true, cost_complete=true, category costs reconcile, quiet daily
Credits/USD parity. One owner, two tested SSE streams, preserved run origin, advancing
sequence/verified stream IDs, and two accounts were observed in 2.69 seconds.
**The command nevertheless FAILED (exit 1)** at `probe_owned_workers_remaining`:
one quota HTTP daemon remained in SSL read; main Live/HTTP workers had closed,
owned processes=0, cleanup failures=[] and no host failure. Clean shutdown/eventual
provider-request completion is **not verified**.

Earlier unsuccessful evidence is retained, not relabeled PASS:
1. A version edit triggered SourceGuard during the first live trial.
2. `--watch-cards --daily` timed out at90 seconds before daily/SSE assertions, with
   Earlier verification unavailable after615/2996 roots and connection_timeout.
3. The old full compounded-scale probe failed unconditional no-scroll/width-stability
   assertions when Chromium clamped width536 to331 despite a height-only request.
   It is not a full high-scale lifecycle PASS; focused clamp coverage above replaces
   that invalid assumption rather than fighting native bounds.

**Decision Delegate** approved scoped acceptance after the independent daily and
both-mode high-scale evidence. For this frontend delivery, successful full-real Earlier
verification and further quota-daemon teardown investigation are deferred; no repeat
cold scan, teardown retry or backend expansion is required. The delegate inspected the
documented 0.2-second shared account join budget, which permits in-flight provider HTTP
daemons; the observation does not establish a frontend teardown regression. This is a
Delegate exception, **not owner approval** or a claim of complete real-history proof.

Physical desktop frames/manual drags, screen readers, macOS and Firefox/Safari are
unverified. No visible desktop actions, model calls, source writes, shared OpenCode
stop, dependency additions, package ZIP or release publication occurred.
