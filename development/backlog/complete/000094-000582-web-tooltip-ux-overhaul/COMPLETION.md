# Completion — FR 000582

Implemented 2026-11-05 as **v80.163**, based on `02c6800`.

- Audited every shipped Web/Mini help surface; rewrote beginner-facing CCost,
  token mix, model/subagent, context, quota, status, report and Settings guidance.
  The inventory and reusable standard are in
  `development/architecture/modules/web-help.md`.
- Added one shared, text-only help controller per document: preserved line breaks,
  hover/focus, Escape without focus movement, pointer transfer, touch pin/toggle
  and outside dismissal, current-state updates and viewport clamping. Adjacent
  cues preserve selectable values and exact metadata; native titles no longer
  duplicate explanatory popovers. Theme, totals, units, source/accounting and
  browser-owned PiP behavior are preserved.
- Updated affected VM/browser tests, added focused shared-help regressions to the
  normal suite, and retained Mini alignment/selection/lifecycle assertions.
- Updated product version/date/history, user help, architecture/navigation and
  ordinary-delivery progress (count 33). Moved the original whole FR bundle intact
  using the next observed completion ordinal, 000094.

## Verification

- Full local suite: **141 files passed, zero failures**, 86.1 seconds.
- Working-tree validator: **11 passes, zero failures**; six advisory pre-existing
  prose/design warnings, with no raised budgets.
- Shared-help headless browser audit: **Chrome 156.0.8078.80 and Edge
  156.0.4314.58 passed**, full Watch plus actual Document PiP, Classic/Web
  light/Web dark, mouse/keyboard/touch, Escape/render suppression, pointer transfer,
  long hostile exact title, retained/partial data, metadata reveals and 150% Mini
  text. Rendered Models, Sessions/Snapshot, Accounts, Date reports, Token Mix,
  active-hour and Settings help/disclosures were checked.
- Broader Chrome Mini browser probe passed: placement, themes/contrast, quota
  orientation, session-total alignment, narrow/zoom layouts, history scrolling,
  hidden-opener SSE and close/reopen/terminal lifecycle.
- Read-only real V2 installation Watch/detail probe passed with zero owned-work
  cleanup failures; the shared OpenCode service was never stopped.

Evidence, commands, causal test repairs and limitations:
`development/journal/web/contextual-help.md`.

## Explicit limits

Browser UI audit reports use immediate in-memory synthetic jobs. The unrelated
Node-hosted cancellation fixture's Models job hang remains unexplained; this
delivery makes no report-process fix claim. An earlier load-overlapped historical
catalog-count failure did not recur in the unchanged focused/final Full tests.
No physical desktop, screen-reader, Firefox/Safari, macOS or other-engine proof is
claimed. No acceptance requirement was waived and no delegate exception was used.
No inference, dependencies, ZIP, tag or GitHub Release was created.
