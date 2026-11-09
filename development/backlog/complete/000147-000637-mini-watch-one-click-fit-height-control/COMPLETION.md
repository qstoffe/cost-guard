# Completion — FR000637

Implemented 2026-11-09 in v80.216. The original specification/bundle is preserved intact.

- Added one compact accessible ↕ header action and standard hover/focus/touch help.
  It grows/shrinks the visible content in either size mode without intentionally
  changing width, disclosure, source data, preferences or position.
- Reused `DisclosureSize` and inert natural-layout measurement; manual fit excludes
  future two-row opening reserves, handles CSS/native zoom and snug rounding, and
  performs at most one direct native resize. Opening width includes all four header
  components. Passive publications never resize; native clamps/refusal retain scrolling.
- Updated current README/version/history, Mini guide, Web ownership/navigation and
  the [engineering evidence](../../../journal/web/mini-fit-height.md).

Verification: deterministic Full **175 files, zero failures**; working-tree validator
**11 passes, zero failures** (seven existing advisory budgets); Chrome156 and Edge157
full native-PiP probes **PASS**, 302 layouts each; focused browser zoom/font/theme,
opening-width/manual-fit and clamp matrices as recorded in the journal. Fresh real V2
daily/SSE probe **PASS**, with all owned workers closed and shared OpenCode untouched.

Limits: headless native/browser proof is not physical Windows frame/drag/monitor,
macOS or screen-reader proof. At compounded zoom/DPR the browser can shrink/move the
window despite a height-only call; those clamps remain scrollable and are recorded,
not called successful width preservation or scroll-free fit. Initial test failures
and subsequent causal/test-assumption corrections are retained in the journal. No
acceptance waiver, new dependency, model call, desktop input or release ZIP was used.

Maintenance progress advances ordinary delivery 85 → 86 only when this PR merges.
