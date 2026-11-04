# Completion — FR 000578

Implemented 2026-11-04 for v80.158, from main `57f2505fcf9f7365a8ce4eb28e23f894d21c7770`.

Both Mini tables retain one first column with Session/title left-anchored and
`| Total CCost` / `| amount` right-anchored. Header intrinsic minima protect both
labels; row costs occupy only natural width. Long titles alone ellipsize, retaining
canonical title/ID and whole-session scope in accessible labels and existing help.
Other columns, canonical costs/states/units, history disclosure, scrolling, lifecycle,
SSE, full Watch and requested PiP geometry are unchanged.

## Checks and evidence

- Local Full: 140 bounded units, zero failures, 1663 tests passed, one Windows zsh/PTY
  skip, 91.6s. Focused Mini passed after the new regression first failed on old code.
- Working-tree validator: 11 passes, zero failures; six existing advisory warnings.
- Hidden real Chrome 156 / Edge 156, scale 1.5: 91 layout cases each, including 54
  edge-alignment/natural-width cases across three sizes, font/CSS zoom, three theme
  combinations and both units. Existing focus/disclosure/sticky/shared-scroll/live
  tests and actual hidden pointer hover/click pass; inspected screenshot confirms the split presentation.
- Read-only installed V2 session-cost parity: four requests/all priced, zero new
  valuations/cache writes, one owner/two streams/three accounts. Owned close 0.1053s,
  no pending owned threads/processes. History read error/no Daily publication limits
  this probe; no completeness claim for those independent lanes.

Detailed [evidence, probe corrections and limits](../../../journal/web/mini-watch.md#fr-000578--v80158-2026-11-04).
Architecture module and Mini guide updated; no new architecture boundary.
The entire specification bundle moved intact to Complete ordinal 000090 (prior
maximum 000089). Maintenance nextState is included; only merged default counts it.

## Limits

No requirement/test exception or Decision Delegate approval was used. Physical DPI,
OS-native/manual interactions, actual browser page zoom and screen-reader speech remain
unverified; headless layout/CSS zoom/enlarged-font/DOM labels are the evidence obtained.
No ZIP, tag or GitHub Release was generated. GitHub checks/merge truth remain in the PR.
