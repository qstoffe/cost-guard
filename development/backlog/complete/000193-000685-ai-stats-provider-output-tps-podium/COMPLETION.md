# FR 000685 — Sampled response TPS podium and permanent best-effort Stats

Implemented for v81.32, 2026-11-12. The original approved FR is preserved unchanged.

## Delivered behavior

- Token Consumption Rate keeps its title/Overview position and now shows up to three
  provider/model/effort medal rows, generated-output tok/s and actual sampled count.
  Each score is summed output (reasoning once) / summed response seconds; no input,
  cache traffic, prompt-workflow time or external benchmark supplies the numerator.
- Independent observed step pairs take precedence. Supported V2 same-response stream
  end excludes later tool-only waiting while preserving actual response/tool overlap.
  Missing/invalid stream metadata retains a plausible completion/native-tool fallback.
  Canonical completion still determines the selected period. The pinned OpenCode 2.2.7
  control-flow trace and known approximate client/fallback biases are in the journal.
- Deterministic newest-eight plus identity-hash-24 sampling caps root/model summaries
  and final period/model samples at 32. Revisions/clock/future eligibility invalidate
  affected summaries. Canonical step/message/clone dedup precedes final sampling.
- Permanent Python/JS comments, architecture contract, user docs and regressions enforce
  **AI Stats = best effort / never Unavailable** on every ready card, including sparse,
  partial, estimated and empty evidence. Actual Loading, last-good retention and real
  page-level operational failures remain distinct. Existing cost/time/Total Tokens
  arithmetic is preserved; no source writes, paid inference or extra historical scan.

## Verification

Final Full: **185 groups passed, zero failed groups, 143.5s**, four isolated workers.
Validator: 11 passes, zero failures, seven existing advisory warnings; no raised budgets.
Focused endpoint/token tests: 15 passed after the final stream-end correction.
Hidden Edge: 19 checks passed, zero runtime errors, clean owned server/browser cleanup;
0–3 podium rows, all-card best-effort states, loading/recovery/last-good, responsive themes,
units, keyboard/help/focus and production two-tab slices (24 hydrations/12 children).

Read-only installation: optimized cold30 145.768s/13 slices, warm30 8.539s, warmAll 9.048s;
all five periods and twelve metrics checked, payload 432,456–432,476 bytes. That run
preceded the final stream-end edit; exact-version source and focused tests verify the
endpoint refinement. No redundant live scan was needed. Physical OS rendering, actual
screen-reader speech, touch hardware and non-Chromium remain unproved.

## Scoped decisions and limits

The foreground **Decision Delegate** approved the bounded hierarchical sampling design
and supported endpoint order, not a minimum-confidence gate. Historical-window samples
can lose older candidates and are not uniform reservoirs. The Delegate explicitly
accepted this FR's measured residual performance cost after optimization: fixed-history
512-root warm runs grew from 0.61–0.71s to 1.21–1.24s, with unchanged hydration/slices,
18 old-ten-metric parity checks, and about 4KB additional live payload. This is not a
performance-nonregression PASS or a waiver of responsiveness/loading/focus/tests.
Mutable-source timings are not paired causal benchmarks. No other acceptance or test
waiver, Suggestion, upstream service change, release/tag or ZIP was required.

Full evidence, initial failures/repairs, pinned source links, benchmark qualifications
and scratch locators: [AI Stats journal](../../../journal/web/ai-stats.md#sampled-response-podium--fr000685).
