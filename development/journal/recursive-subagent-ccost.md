# Recursive subagent CCost — FR000700

## Diagnosis and independent oracle (2026-11-13)

This is a purpose-built V2 wire reproduction, **not the owner's private Sol/Astra
incident**. That particular incident was not read or reproduced. Existing child-link
recursion was already intentional; a blanket claim that all subagent spend was
missing would be false.

Two causal faults were established:

- `analysis.valuation.unique_usage` applied the fork/billing fingerprint across
  different sessions inside one tree. Independent parallel siblings with equal
  completion time/model/cost/token counters could lose one physical request from
  session and aggregate totals while prompt entries still contained both.
- Web cost grouping merged different child sessions sharing model/effort/tier,
  hiding individual subagent contributions even where the money was present.
  Linked children without request parts also lacked a source-qualified completeness
  contract; the old warning did not establish either zero usage or missing spend.

`fixtures/recursive_costs.py` provides two initial main requests, a different-model
child, same-model sibling with colliding counters, another-provider sibling,
grandchild, background great-grandchild finishing after a later main prompt,
repeated link observations and one child request outside its prompt window.

Independent Decimal oracle:

| Owner | Physical calls | CCost |
| --- | ---: | ---: |
| Root main | 3 | 183 |
| First child, including outside-window request | 2 | 204 |
| Same-model sibling | 1 | 102 |
| Other-provider sibling | 1 | 61 |
| Grandchild | 1 | 61 |
| Great-grandchild | 1 | 61 |
| **Whole tree** | **9** | **672** |

The initiating first prompt is **509 / 7 calls**, the later prompt **61 / 1**,
and explicit outside-row work **102 / 1**. Session roles are **183 main + 489
subagent = 672**. No residual is allocated to a random prompt.

Executing baseline `1afa76e`'s `unique_usage` function over the **same newly acquired
synthetic entries** produced **8 requests / 570 CCost**; the repair produced
**9 / 672**. This isolates the deduplication defect; it is not a full historical
application replay. The regression also checks period/provider sums, Token Mix,
analysis serialization, cold/warm incremental root cache, Sessions scalar/cache,
session-detail export and active/history Full/Mini prepared help in both units.

## Repair contract

Physical source/session/invocation/message/step identity canonicalizes recaptures.
Within-tree multiplicity survives cross-tree fork matching. Repeated captures prefer
more complete telemetry, then later completion/publication; no source ledger is added.
Coverage states distinguish observed usage, complete inactive no-execution history,
pending activity, partial acquisition and unavailable usage. Response text/reasoning
without counters is an observed unknown-usage request, not zero or a lost call.

Safely priceable known categories remain a partial subtotal. Unknown placeholder
counters never price; missing input categories cannot select a multi-tier price.
Reference CCost and actual billing remain independent. Contributions persist amount
separately from completeness; source coverage is recomputed on the acquired snapshot.
Analysis 21, scalar summary 7 and token-mix evidence 2 lazily rebuild affected
disposable facts. Scalar role amounts must be finite, nonnegative and reconcile.

Application exports individual stable `Subagent N` groups and bounded omission
amount/call counts, with own-request totals for multi-group agents. Full Model,
CCost and Calls retain recorded selectors and default-effort evidence; Mini receives
shorter prepared prompt help. Whole-session values explain main versus linked work
and detail includes outside-row requests. Browser code does not price or fetch on
hover. Raw private source IDs are not tooltip identities.

## Verification and limits

- Focused post-repair checks: 27 tests passed; after final fixture/probe corrections,
  another 48 tests passed.
- Validator at v81.44: 0 failures, 7 existing advisory/design warnings; no budget
  increases, rebaseline, package ZIP, tag or Release.
- Initial final Full attempt: 193 groups, 5 failed in 166.4 seconds. Causes were
  selected-unit sparse help overlays mistaken for canonical data, obsolete
  missing-telemetry/whole-session help expectations, and probe-only guard diagnostics
  assuming a full host in an exception-preservation test. These were repaired,
  not waived.
- Final `py -3 development/tools/run_tests.py --suite full`: **193 groups PASS,
  0 failures, 163.4 seconds**, four isolated workers with existing 240-second group
  ceilings. The new recursive regression is included, not just run separately.
- Initial rendered attempt exposed a probe error: changing `ReportView`'s unit
  without the Settings pathway's Mini rerender left cached compact help in the old
  unit. The probe now mirrors that production rerender. This is not evidence of a
  product settings failure.
- Final hidden Chrome **157.0.8103.51** / actual Document PiP Watch-only matrix:
  **PASS**. Shipped authentication/HTTP/CSP/SSE carries synthetic data. Both Full
  tables show separate agent model/effort/Calls/category subtotals; 30-group omission
  remains bounded and scrollable. Credits/USD compact Mini prompt help and Full/Mini
  whole-session roles agree. Focus, hover, pointer transfer, touch, Escape, retained
  open help on updates, hostile long titles, Classic/light/dark, 360/1280 widths
  and 100%/150% zoom pass. Not physical desktop, screen-reader or other-engine proof.
- Read-only `probe_web_live.py --prompt-cost --session-cost`: authenticated V2,
  one Live owner, 330 Live reads and 199 frames, then **prompt selector timeout at
  91.27 seconds**. `source_guard` stayed unchanged; there was no source access/auth
  failure. No eligible completed/resolved Earlier comparison succeeded; session-cost
  stage was **NOT REACHED**. Account-history pending is not Earlier certification.
  Cleanup reported no failures/owned processes, with two account helper threads still
  pending at the final observation. The process subsequently exited.

Earlier interrupted live runs edited watched runtime files during probing and hit
the host's deliberate `source_changed` shutdown. That is a verification-sequencing
error, not established native-source restart or CCost failure. Freeze runtime/version
before live verification; first guard-delta diagnostics retain public relative
filenames without disabling/resetting the guard.

Decision Delegate directed a bounded exact authorized task-root native snapshot,
independent invocation identity/Decimal sums and cold/warm cache/controlled projection
comparisons, with no unrelated context sample, account providers or inference.
`probe_recursive_root.py` then **passed** on the receiving task's exact metadata-
verified root: complete V2 snapshot, **56 physical requests / 2 sessions / depth 1**,
**317.18460000 = 99.71880000 main + 217.46580000 subagent CCost**, complete observed
coverage. Independent raw invocation identities and pinned-catalog Decimal sums
match canonical population, unique prompt/compaction/unassigned ownership, Sessions
row, session-detail and controlled Full/Mini projections. Disposable cold cache
valued 56 requests; fresh-repository warm reuse valued **0** and wrote nothing.
Acquisition **1.055 seconds**, total **1.133 seconds**. No account providers,
unrelated context sampling, native source writes or model calls started by the probe.
The real observation contains only one descendant level; deeper recursion remains
source-shaped synthetic proof.

### Decision Delegate disposition

Decision Delegate explicitly accepted a **minor FR000700-only verification
exception** for the missing observed native Earlier cost comparison. Relevant
real-installation accounting proof is meaningfully met by the independently
reconciled native root/cache result, recursive source-shaped RED/GREEN and rendered
integration. Global Earlier qualification is a distinct observation dependency;
another active-root capture would not establish it and offers insufficient new
discrimination. No demonstrated product defect is waived; no Suggestion or On Hold
is required for this isolated caveat.

The original prompt observer remains **FAILED — timeout**; its subsequent session
observer remains **NOT RUN**. Native Earlier selection/publication and its observed
cost comparison remain **UNVERIFIED**. The native root/cache probe independently
passed. Depth greater than one was not observed live; the required recursive
fixtures supply that evidence. The owner's particular incident remains
unreproduced. This decision does not waive Full failures, normal PR checks,
protected merge or default readback.

Final local Full and validator succeeded as recorded above. Before delivery, latest
`main` was integrated through `201061d`; its intervening change only added unrelated
backlog documentation/identity metadata, not product or tests. v81.44 remains the
next product version. Main is the supported distribution; no ZIP/Release is produced.
