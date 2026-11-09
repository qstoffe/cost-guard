# Completed FR 000643 — Mini Watch neutral historical foreground

Implemented in v80.223 (2026-11-09), based on main `217e835d5d16734f5333b690cfa649b5de1be350`.

## Result

Mini historical rows now unconditionally inherit the theme foreground. Running and
source-certified recent-terminal active cards retain the existing yellow/green/red
classes. The same keyed row clears old terminal emphasis when it moves to history;
outcome accessibility remains truthful. No new timeout, source read, palette, badge,
setting, sorting/selection change, cost change or Full Watch change.

## Verification

- Regression reproduced before the fix; focused Mini tests then passed.
- Local Full: **179 test files, zero failures, 170.3s**.
- Package validator: **11 checks passed, zero failures, seven advisory warnings**;
  no budgets or structural baselines raised.
- Real headless Edge 157 Document PiP over synthetic canonical shipped HTTP/SSE:
  **91 layouts passed**, including 12 lifecycle/computed-color cases and the existing
  width/density/help/Activity/AX/Fit regression matrix.
- Real-installation `probe_web_live.py --accounts`: **PASS**, V2, one owner/two
  coherent advancing streams, three accounts, clean final owned-worker gate.
- Final 12-case supplementary color run passed in-place historical unit/theme switches;
  validation and color results are recorded
  in [compact evidence](../../../architecture/governance/verification/mini-history-643.json).

[Journal](../../../journal/web/mini-watch.md#historical-foreground-correction-fr000643)
records the initial fixture failure and three failed exploratory live probes:
unobserved invocation, interrupted deep-history check, and immediate early-close
quota-worker assertion. None is relabeled PASS. Actual natural personal-source
history/lifecycle colors and physical OS frames are not claimed. Delegate assessed
the scoped verification as sufficient and directed the successful Accounts alternative;
**no acceptance waiver or deferred product scope**.

Docs, module contract, navigation map, version/history and ordered maintenance progress
were updated. FR body is preserved intact; new evidence is outside the task payload.
No ZIP, tag or GitHub Release was created. GitHub PR/check/merge truth belongs to the
delivery PR, not this pre-merge report.
