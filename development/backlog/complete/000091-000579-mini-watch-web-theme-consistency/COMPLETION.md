# FR 000579 — Completion

Implemented in **v80.159, 2026-11-04**. The original specification is preserved in
`FR.md`; delivery ordinal 000091 is independent of permanent identity and Ready priority.

## Result

Reproduced the reported discrepancy before designing the fix in actual hidden
Chrome Document PiP over shipped HTTP/CSP/auth/SSE: the Web owner naturally resolved
light while Mini resolved dark, although both had `data-theme="web"` and the expected
stylesheets. Mini's content background was `#0c1422`, versus the owner's `#eef2f8`.

Mini now inherits the owner's computed semantic properties before attaching content
and styles. Confirmed Settings and owner light/dark media changes update it directly.
Classic removes those Web overrides and uses its unchanged CSS. Web-only canvas,
quota-panel, muted empty-state and scrollbar rules complete the shared palette.
No hardcoded duplicate palette, extra stream, storage, acquisition, preference,
window geometry or full-Web styling change was introduced. The Session/Total CCost
grid and status/accounting meanings remain intact. The appearance listener is released
on close/replacement; reopening uses the current appearance.

## Verification

- New deterministic owner-palette regression first failed against the old controller,
  then passed; media-only updates, round trips, fresh opening and listener disposal
  join the existing lifecycle, keyed-DOM, units, retained-data and canonical-metric tests.
- **Full local suite: PASS**, 140 bounded units, four workers, 92.1s, zero failures.
- **Working-tree validator: PASS**, 11 passes, zero failures; six existing advisory
  prose/Python design-budget warnings. No assertions, caps or dependencies weakened.
- **Hidden Chrome 156.0.8078.80 and Edge 156.0.4314.58: PASS**, actual Document PiP,
  emulated device scale 1.5, 108 layout cases each. New cases deliberately make PiP
  and owner media preferences opposite, verify complete resolved-role parity,
  backgrounds/surfaces/controls/help/quota fills, text contrast, live Settings/default
  round trips, media-only changes, compact/narrow focus/popovers and single SSE.
  Existing density, independent scroll, sticky headers, session pipe alignment,
  units, terminal/empty/retained states and lifecycle checks also pass.
- **Classic baseline comparison: PASS**, all computed properties on 15 representative
  elements, sampled tokens and inner dimensions are identical before/after with the
  same synthetic data/browser. This is not a claim about native frame pixels.
- **Read-only installed V2 probe: PASS**, 64 coherent publications, one running prompt,
  three accounts/two available period costs, four known-finish history cards;
  26.068s, owned close 0.151s. No inference or shared OpenCode stop/mutation.

Evidence and screenshots: [Mini theme investigation](../../../architecture/governance/verification/mini-web-theme/reproduction.json),
[journal](../../../journal/web/mini-watch.md). User guides, current version/history
and the Web module contract are updated; no architecture boundary/flow change.
Maintenance progress advances only when this delivery merges to the default branch.

## Limits

Browser verification is headless with synthetic data, media emulation and native-API
window resizing, not physical manual dragging, OS appearance-setting interaction,
native frame recoloring, assistive speech or macOS rendering. Browser-native chrome
is expressly out of scope. The integrated browser was disconnected; owned hidden
Chrome/Edge supplied the browser evidence instead. No requirement/test exception
has been requested or granted; no physical/native proof is claimed.
