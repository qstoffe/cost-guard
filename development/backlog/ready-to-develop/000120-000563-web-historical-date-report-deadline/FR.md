# FR 000563 — Resolve the deep historical-date report deadline exposed during FR000555

## Reason for this follow-up

**Owner-requested review follow-up, 2026-11-03.** Permanent identity **000563**, Ready priority **000120**, after existing FR000561/000562. This is a distinct, evidenced report-performance/cancellation issue, **not** a claim that the completed Web Daily/shutdown repair (FR000555, [PR #137](https://github.com/qstoffe/cost-guard/pull/137)) failed.

FR000555's [completion](../../complete/000068-000555-web-live-daily-shutdown-timeouts/COMPLETION.md) and [lifecycle journal](../../../journal/web/live-lifecycle.md) record a broad real read-only V2 run with `probe_web_live.py --watch-cards --daily --detail --reports`:

- Daily published in **17.856 s**; cards/detail/SSE were coherent.
- Normal, All-models and Sessions reports completed (**51.479 / 8.137 / 5.976 s**).
- The separate fixed historical-date report reached the existing **120 s job limit with history at 868/872 roots**. The overall broad run **FAILED**, and the planned deep-history cancellation checkpoint was not reached.
- Failure cleanup closed WebHost in **0.0884 s** with zero tracked owned resources. The initiating report failure and source-read state were retained.
- The cause of the historical-date slowdown, its possible pre-existence and its reproducibility under other loads are **not established**. A later alternative `--models` run passed; it was accepted as representative competing work for FR000555, not proof that this distinct historical-date path is healthy.

This FR exists because the actual report path still has documented failing evidence. Do not rewrite history by calling that run PASS or assuming the same redundant-catalog cause as Daily.

## Required outcome

Investigate the **actual historical-date report path** end-to-end (work planning, root selection, full-catalog/revision brackets, V2 transport, bounded workers, report subprocess/job status, HTTP/SSE publication and cancellation). Identify which operation or bounded work pattern consumed the 120 s; distinguish avoidable repeated work from genuinely slow source I/O, large eligible history, contention and harness artifacts. Collect sanitized timings, catalog/request counts, pending-root progress and a causal explanation without publishing private prompts or source payloads.

Where a demonstrable implementation inefficiency exists, fix it narrowly. Preserve every eligible root, canonical prompt/cost/account attribution, revision/completeness safety, existing Daily and ongoing Live publication, retained failure evidence, bounded shutdown, access/security limits and actual report results. No truncating the last roots, fake completed reports, hidden retries, new provider/model calls or blind extension of the 120 s deadline. Do not interfere with the shared OpenCode service.

If the only remaining constraint is source throughput rather than a fixable defect, classify it honestly: provide a bounded, actionable timeout/cancellation result with reliable phase/progress evidence and document what load is and is not supported. A universal live-source completion-time guarantee is not required.

## Acceptance evidence

1. **Baseline causal test:** Recreate the identified excessive-work or deadline mechanism against the version before any repair, using production report owners and representative controlled V2 fixtures. Include a many-root case representative of the observed 872-root campaign; a synthetic latency model must be called synthetic and must not replace a real-path check. A red baseline/green change is required for an asserted code fix.
2. **Correctness:** Compare before/after eligible roots, actual dates/periods, prompts, CCost totals and partial-source semantics. Any deliberate supported limitation must be explicit rather than silent data loss.
3. **Integration:** Re-run the fixed-date historical report with Daily/cards/detail/report work under ordinary and reasonable competing load, measuring publication, HTTP responsiveness, timeout classification, cancellation and zero residual owned workers. Retain failures and missing evidence rather than rerunning until one pass.
4. **Regression separation:** Keep FR000555's previously repaired Daily catalog batching, cancellable source reads, account-worker reaping and combined primary/cleanup error reporting intact. Test that a deep report cancellation does not block WebHost close or mask the first error.
5. **Delivery:** Record exact commands, results, code/version evidence, limits and why the original 868/872 failure was or was not addressed. Run relevant focused and normal product checks for code changes. A documentation-only diagnosis without a justified fix must be labeled as such, not represented as fully resolved.

## Scope and dependencies

This is lower priority than the two already approved Web Watch FRs 000561 and 000562. Do not change their finished-time/history sorting, Mini Watch redesign, quota presentation or Context markers. Existing tests and report timeouts are safeguards, not throughput targets to game. No ZIP/release or external installation is requested merely by this FR.
