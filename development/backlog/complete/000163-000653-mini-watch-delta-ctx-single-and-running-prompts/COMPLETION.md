# Completion — FR000653

Implemented 2026-11-09 in v81.2.

- Fixed the reproduced historical gate: retained complete 100,000 incoming / 112,000
  own-event next now keeps +12,000 (and exact zero) after active-history removal,
  without reviving live continuation/warnings. Richer comparable prior anchors remain.
- Guarded the own-prompt fallback against missing input, different roots/models/providers
  and in-prompt rewrites. Unknown/deleted history and unexplained shrink stay unavailable.
- Running root requests update canonical Full/Mini deltas; move/compaction cannot
  resurrect stale provisional context. Existing Live exports short canonical reasons
  and provisional text, not new acquisition or browser-side arithmetic.
- Mini keeps four columns and historical session Next versus representative prompt Δ.
  Next/Δ/guidance use separate short paragraphs; row/focus/open-help identity survives.

## Verification

- Full suite: 180 entries, 2,205 passed tests, two native macOS/zsh skips, no failures.
- Package validation: no failures, seven advisory budget warnings; v81.2 consistent.
- Real V1 SQLite and normalized V2 → analysis/report/Live fixtures, running tool loops,
  historical/zero/missing/reset/model/provider/archived/moved guards and existing
  negative/compaction/attribution/warning/lifecycle regressions passed.
- Full headless Edge PiP theme/unit/width/density/Activity/AX/Fit/scroll/help matrix and
  Chrome focused help passed, including source-driven 112k/+12k → 117k/+17k,
  invalidation/recovery, historical 300k/+12k and waiting-first-request behavior.
- Read-only real V2 context export/formatting and consistent live/frozen detail passed;
  one numeric running row, one owner, two advancing SSE streams, clean owned shutdown.

## Limits and documentation

The owner's exact private incident was not captured. A separate broad 90-second
Earlier-history attempt was inconclusive at 695/3,040 roots; the successful context
probe does not claim global history certification. Integrated browser was disconnected;
headless PiP does not prove physical desktop/macOS or screen-reader behavior.
No test/FR exception or functional deferral was requested or applied.

Updated current Web/Mini guidance, module analysis/help/navigation and the
[causal evidence journal](../../../journal/web/mini-context-deltas.md). FR000645
historical evidence remains intact. Billing, CCost, quota, membership, acquisition
boundaries and ordinary main distribution remain unchanged; no ZIP or Release.
