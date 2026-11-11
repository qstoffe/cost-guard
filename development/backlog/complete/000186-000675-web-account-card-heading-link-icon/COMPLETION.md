# Completion — FR 000675

Implemented 2026-11-11 in v81.25. Both independent deliverables are included.

## Result

- Accounts and Full Watch share a small decorative outline chain inside each
  trusted heading link. Unknown providers remain plain text. Destinations,
  new-tab safety, accessible names, wrapping, keyboard focus and inert card/header
  padding are preserved; quota-track redraws retain the attached heading.
- Reproduced and fixed stale native-quota retention freezing the entire account
  DTO, including fresh CCost Today and explanations. Only native quota slots are
  retained now; incoming accounting advances independently.
- Source/history/valuation/account projection and independent global Watch Today
  regressions verify Stockholm winter/summer/DST and UTC rollover, empty new-day
  zero, completed post-midnight Copilot Pro+, OpenAI Pro Light and qualified Claude
  Pro usage, late telemetry, partial/unknown prices, deduplication and account
  isolation in both USD/Credits. Existing FR000673 pricing/attribution is reused.

No acquisition, provider alias, price, quota, billing, authentication or Mini Watch
policy was changed. Existing architecture boundaries and dependencies are intact.

## Verification and repaired failures

- Focused stale-publication regression failed before the fix; 38 focused tests
  passed afterward.
- Local Full ran all 183 then-registered groups: 182 passed; the foundation group
  failed only because version metadata changed during its parent/child run.
  After metadata stabilized, that entire 11-test group passed (63.32s).
- The newly registered two-test midnight matrix passed separately. Explicitly
  active old-day roots initially exposed an overstrict fixture-reuse assertion;
  the corrected assertion preserves intentional active-root rechecks and passed
  on continuation (1.15s). No accounting expectation was relaxed.
- Hidden Chrome157: nine actual HTTP/SSE daily publication phases passed; 48
  heading layouts passed at normal zoom and another 48 at real 125% browser zoom.
  The initial broader driver then hit an obsolete test-only text-node selector;
  after its repair, remaining full Accounts compatibility checks passed, including
  native focus, selection/help, grid geometry, live recovery and existing PiP.
- Actual read-only installation probes passed with three account projections,
  reconciled daily pricing/categories and owned-worker shutdown. No inference was
  started and the shared OpenCode service was not stopped.
- Working-tree validator passed (11 passes, zero failures; seven pre-existing
  advisory warnings). Final delivery also checks whitespace and the latest base.

Detailed cause, synthetic trace, exact artifacts, repaired failures, timing and
evidence-access routing decision: [journal](../../../journal/web/account-today.md).
No acceptance exception was used; no ZIP, tag or GitHub Release is produced.

## Limits

An empty new local day legitimately has zero cost. This independently reproduced
stale-card defect does not retroactively establish the cause of the owner's
private zero/N/A incident. The real probe observed zero Copilot Today and positive
OpenAI/Claude Today; synthetic qualified requests independently verify each
positive path. Partial/unpriced evidence remains partial/unknown, not fake zero.
No new live model inference, physical assistive-technology or macOS proof is claimed.
