# Mini context deltas — FR000653

2026-11-09, v81.2. Scoped canonical correctness change, not a claim to have captured
the owner's exact private incident.

## Reproduction and correction

The real V2 normalizer, canonical analysis and prompt block reproduce a narrow loss:
one prompt, complete I/C/W/O, incoming 100,000 and same-event next 112,000. Current
active membership already gave +12,000. Removing current membership while retaining
the complete source pair gave Next 112,000 but delta null solely through the early
`active_prompt is False` return. Exact zero was lost in the same branch. No previous
prompt is needed, and the correct initial baseline is 100,000, never zero.

Historical Watch now uses a guarded own-root input baseline when no richer eligible
session/compaction anchor exists. It checks positive known first input, provider/model,
and intervening boundaries/compactions. Retained complete historical pairs survive
undo or current-history pruning; missing/deleted/incompatible evidence stays unknown.
Current continuation/warnings remain unavailable for inactive/retired history.

A second causal path allowed a running compaction to invalidate current context,
then resurrect an older provisional estimate. Provisional text is now limited to an
eligible prior baseline without an intervening move/live compaction, never a failed
real-request estimate. Running prompts removed from active history remain unavailable.
Short canonical reasons/provisional text travel in the existing Live projection.

`_coherent_watch_deltas` retains the established richer adjacent anchor contract;
its changes only keep short detail consistent when reconciliation changes the delta.
Mini never subtracts rounded browser values. Historical Next stays session-scoped,
delta stays representative-prompt-scoped, with an explicit distinct-time note.

## Deterministic and browser evidence

- `fixtures/context_deltas.py`: invented raw V2 requests and a real V1 SQLite shape;
  normalization → analysis → prompt block → Live, not injected numeric delta tokens.
- Positive/zero/missing input and categories, removed active membership, model/provider
  mismatch, in-prompt reset, moved/archived history, running root updates and compaction
  invalidation extend their existing owning tests. Existing negative/compaction/child,
  attribution, warning and lifecycle tests retain their semantics.
- One old running regression used a fixture containing a *later completed compaction*
  while claiming before-compaction behavior. Its scenario now explicitly uses the
  uncompacted fixture, retaining its numeric-context assertions; a separate regression
  requires unavailable context after the rewrite. No acceptance or test waiver.
- Headless Edge 157 and Chrome 156 help probes passed source-driven running
  112k/+12k → 117k/+17k, move invalidation/recovery, inactive historical 300k/+12k,
  exact zero and waiting-first-request cases through shipped HTTP/SSE/Full/Mini DOM.
  The same keyed row, keyboard focus and open tooltip survive updates. Existing
  hover/touch/Escape, threshold severity/multiplier, text-only previews and four-column
  geometry assertions also pass.
- Integrated browser was disconnected. Permitted hidden Document PiP is browser
  evidence, not physical desktop/macOS or screen-reader proof. No visible desktop
  interaction, model execution, raw prompt telemetry, new acquisition or source writes.

## Real-installation scope

The first read-only real Watch/detail probe ended with a local HTTP connection reset
after about 45 seconds while this working source was still being edited. It is not
a PASS or proof of the owner's N/A cause. Fresh frozen-source verification and final
suite results are recorded with the delivery evidence below.

## Final verification

- Full suite: 180 runner entries, 2,207 tests; 2,205 passed, two existing native
  macOS/zsh tests skipped on Windows, zero failures (130.3 seconds).
- Working-tree package validation: zero failures, seven advisory prose/module budget
  warnings; all hard budgets, Python 3.11 syntax, imports and v81.2 bindings passed.
- Full headless Edge PiP acceptance passed the existing theme/font/unit/width and
  Activity matrices, 0/1/3/5/6/10-session density, source-driven context help, history
  handoff, stable focus, AX membership, Fit/scroll and no-passive-resize checks.
  Chrome's focused source-driven help probe also passed. Evidence paths in this
  session: `scratch:/mini-edge-final.json`, `scratch:/mini-help-chrome.json`,
  `scratch:/full-tests-final.json` (ephemeral; durable outcomes are summarized here).
- A broad real-source 90-second attempt reached 695/3,040 history roots without
  certification, with no runtime phase errors before cleanup. That unrelated global
  winner check is **INCONCLUSIVE**, not a context failure or a completed history audit.
- `probe_web_live.py --context-deltas --detail` now has an explicit task-focused
  observation path independent of full Earlier certification. Frozen-source run
  passed: one real V2 running row with numeric next/delta and matching prepared
  tokens, one Live owner, two advancing verified SSE streams, consistent one-row
  live/frozen session detail, zero phase errors and zero retained owned workers at
  cleanup (5.65 seconds). Earlier remained loading; no historical-real-source or
  private-incident baseline reconstruction is claimed.

No approved exceptions, exclusions of requested functionality, new dependencies,
source mutations, model calls, GitHub Release or ZIP. Native physical/macOS acceptance
remains outside these browser/source results. Documentation and module navigation
are updated; completed FR000645 evidence is unchanged.
