# FR 000642 — completion

Implemented in v80.222, 2026-11-09, from main
`4d7eca5a1f073a405a62dfeb2d93fdfa6b1410c6`.

- One chronological, session-keyed **Activity | Session | CCost (Total) | Ctx**
  table; all distinct active sessions survive, certified finished/grace candidates
  fill unused slots to five. Latest genuinely running focal prompt represents a
  concurrent session; whole-session cost remains independent. Full Watch is unchanged.
- Five styled body-row viewport, internal scrolling for extra active sessions,
  measured table/header opening width, full start/finish-offset help and retained
  duration details. Explicit one-shot Fit, manual/remembered dimensions and history
  demand/close withdrawal are covered. Earlier button/Duration column are removed.
- Current user/Settings/module docs and deterministic/native tests updated; obsolete
  two-table/disclosure test branches retired. Journal consolidated with historical
  evidence linked by immutable revision; no architecture boundary or budget raised.

## Verification

- Final local Full: **179 bounded files, zero failures, 148.5s**.
- Working-tree validator: **11 passes, zero failures, seven advisory size warnings**.
- Actual owned headless Edge PiP: **79 layouts each** at normal zoom/device-scale1
  and actual150%-zoom/emulated device-scale2. Earlier125%/scale1.5 matrix also passed.
  Includes four oversized paired-cost cases, density/accounts, Activity/focus/help,
  DOM/AX readiness, pointer/keyboard/touch Fit, remembered manual reopen and one SSE.
- Eight accepted real authenticated history-lease transactions passed after the
  compatibility-runner rewrite. Relevant read-only real V2 installation probe passed;
  no inference or shared OpenCode service stop.

[Evidence and commands](../../../architecture/governance/verification/mini-activity-642.json)
and [reusable findings](../../../journal/web/mini-watch.md) distinguish earlier
failed iterations, corrected regressions and native-limited cases. High-scale
clamps use reachable scrolling, **not** exact-fit PASS. Physical OS geometry,
manual OS dragging, macOS pixels and screen-reader speech remain unverified.
No requirement/test exception was requested or granted. No ZIP/tag/Release.

The intact FR moved from Ready to this Complete bundle. Ordinary progress advances
91 to92 only on merged main. Exact-HEAD CI and merge outcomes belong to the delivery
PR/run; this report does not predict them.
