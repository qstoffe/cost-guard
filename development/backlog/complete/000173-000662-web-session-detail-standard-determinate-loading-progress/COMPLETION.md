# FR 000662 completion

Implemented in v81.12 (2026-11-10). First session detail now reuses the centered
shared report loader: stable determinate bar, truthful verified row counts over
0–95%, unknown waits held, and 100% only after complete DOM application. Retained
history never reenters first-load progress. Malformed/duplicate/oversized chunks
and stale navigation cannot complete an invalid assembly. No source API,
acquisition, export, pricing, other report-loader behavior or polling change.

## Verification

- Full ran all 181 groups: 180 passed; one obsolete retained-loader node-count
  assertion failed. Corrected to require one keyed **hidden** bar and unchanged
  retained rows; current-source detail + real-HTTP views rerun passed 13 tests.
  The original Full run was not green; no failure was waived.
- Chrome and Edge each passed 48 CSS-layout cases and actual route/paging,
  220/1/0 rows, cancellation, retained focus/selection/scroll, hidden polling,
  mouse/keyboard/emulated touch and Back checks. Native Chrome page zoom independently
  passed another 48 cases at 100/125/150%; viewport and DPR prove actual zoom.
- Read-only real V2 installation passed detail/pinned paging/freeze and lifecycle
  checks; zero model calls, no owned survivors or cleanup failures; shared OpenCode
  untouched. Bounded scalar index/global-sort limits are not detail-loader failures.
- Working-tree package validator passed: 11 checks, zero failures, seven advisory
  existing design/prose-budget warnings. `git diff --check` passed.

Decision Delegate accepted browser acceptance6 adequacy after native page-zoom
proof, with measured CSS widths and matrix-only device normalization. No exception
or correctness waiver. Hardware input, OS scaling, spoken screen-reader and macOS
remain untested; no physical acceptance is claimed.

[Causal design, commands/results and limits](../../../journal/web/session-loading.md).
[Compact browser evidence](../../../architecture/governance/verification/session-loading-662.json).
Architecture module and current user/release docs updated. Ordinary progress112
is included in the same delivery; no packaged Release or ZIP.
