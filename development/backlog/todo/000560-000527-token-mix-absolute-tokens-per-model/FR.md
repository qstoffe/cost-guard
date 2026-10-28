# FR 000527 — Show absolute token volume alongside per-model Token Mix and CCost

## User request and existing functionality

A colleague wants a compact comparison of which AI models consume tokens and reference cost. Cost Guard already has python cost-guard.py --token-mix with total tokens and per-model Prompts, Calls, I/C/W/O shares and CCost, and Web Beta has an explicit deep Token Mix page. Creating a second report or appending large extra report sections to the default CLI output would duplicate functionality.

The pending FR000521 already owns model-/publisher-aware comparisons and adds a separate publisher Token Mix table. This FR must be coordinated **after FR000521** and preserve its model/publisher semantics.

## Required behavior

- Add a clear **absolute total token volume per model** to the existing per-model historical Token Mix table, preferably a compact, sortable Tokens column. Keep model, Prompts, Calls, I/C/W/O percentages, category CCost and per-model total CCost, along with the overall total.
- Count the same canonical deduplicated physical attributed requests that already feed the per-model Token Mix; total volume is the sum of known I/C/W/O token categories (including reasoning folded into Output). Don't infer token counts from percentages or reprice pooled tokens. Where telemetry is partial, make the volume's incompleteness explicit rather than showing a confident zero.
- Preserve exact aggregation for sorting and totals. Prefer recognizable compact K/M/B formatting while keeping appropriate detail/definitions. A model can contribute to multiple prompts and a prompt may contribute to multiple models; avoid adding model-row Prompts to claim a global unique prompt count.
- Reuse the same Python report/application projection in CLI and Web Token Mix. Respect FR000521's publisher aggregation, identity, unknown classifications and performance constraints. Web stays an explicitly user-triggered potentially expensive scan with progress/cancel; no automatic deep history acquisition.
- Use the currently configured CCost unit from FR000526; do not introduce an independent hardcoded dollar comparison column, actual billing claim or a new provider/API call. Do not enable extra default CLI report sections.

## Acceptance

Known model-specific token totals reconcile against canonical category totals across large/small histories, mixed-model prompts, subagents and available deleted/pruned limits, with clear unknown/incomplete states. Sorting uses raw values; CLI narrow terminal and Web scroll remain usable. FR000521's publisher and model tables remain consistent and no analysis is duplicated, with deterministic report/DOM tests. The original --token-mix mode and its explicit Web capture semantics remain recognizable.

**Priority:** Normal / after FR000526 and FR000521.
