# FR 000546 — Reconcile Web Watch terminal lifecycle with CLI after quota exhaustion

## Reported problem, scope and priority

The owner reports a prompt that stopped when its subscription quota ran out. **Web Beta Watch continues to show it as running indefinitely, while CLI Watch no longer treats it as running.** This makes the page misleading and would also corrupt the planned Mini Watch running count, Running CCost and longest-running duration.

Create a focused correctness fix for the Web card lifecycle and its authoritative source interpretation. Permanent identity: **000546**. Owner approved the reported fix on 2026-11-02 as part of the Watch follow-up. Ready priority: **000100**, ahead of **FR000545** (page cleanup, 000110) and **FR000544** (Mini Watch, 000120). FR000544 depends on this corrected running-state truth.

The observation is owner-reported. No affected CostGuard session ID, source snapshot or runtime version was supplied. Source inspection at main `389f9881bc4e00e4c0cbd0f6245fe2af86e037c2` confirms separate Web/CLI lifecycle paths and plausible divergence areas; it does **not** establish the exact root cause of that reported prompt. Reproduce with canonical source fixtures and record the actual mechanism found during implementation. Do not import unrelated session IDs from other repositories/tasks or claim the production case has been reproduced without evidence.

This FR fixes display/state reconciliation, not the underlying provider quota. It must not abort or restart real prompts, change models, resume work, or infer termination merely because an account is at 100% used.

## Desired outcome

Given the same selected source, canonical root/prompt/attempt identity and authoritative source revision, Web Watch and CLI Watch agree whether the prompt is still genuinely running or has reached its actual terminal outcome. They may intentionally present terminal history differently, but they must not disagree about ongoing execution.

On the first successfully accepted fresh capture containing the relevant authoritative terminal evidence, Web must publish that prompt as **not in progress**. Its running indicators and duration growth stop on the next corresponding presentation. Preserve known final usage and the real available outcome/reason, including quota failure/interruption; do not turn a failed or interrupted prompt into a successful completion simply to remove a running card.

Cold startup after the termination, tab reload, reconnect and later resync must reconstruct the same terminal truth without needing a live process-local interruption event. Later stale publications must not resurrect the same already-terminal attempt. A genuinely new attempt or later authoritative work must still be representable.

## Keep execution status separate from terminal highlight grace

The existing `watchRecentEventSeconds` highlight/grace (default **30 seconds from the observed terminal transition**) may keep a terminal card in the active area temporarily. During that interval:

- The prompt is not running; retain its correct terminal styling. Its duration no longer advances with the clock, while later authoritative corrections to final duration or usage remain possible.
- It contributes nothing to running count, running-only CCost or longest-running duration, including the future Mini Watch projection.
- Current tool/background “Running:” indicators end according to canonical lifecycle; historical counts/details may remain where appropriate.
- At grace expiry it leaves the active area and participates in the existing distinct-session history eligibility/order rules.

Repeated refreshes must not restart the grace indefinitely. Historical terminal data discovered on cold startup must not be promoted to new running work. Preserve established cold-start highlighting semantics without creating a new timeout-based completion policy.

The canonical `tool-calls` continuation grace (currently **60 seconds**) is a different rule from this 30-second terminal display period. Neither is a general timeout for declaring an old, slow or quiet prompt finished.

## Canonical evidence, retention and races

Reuse shared normalized terminal evidence and causal prompt construction. Resolve the defect at the appropriate acquisition/reconciliation/projection owner so the page, reports and Mini consumers do not each invent lifecycle filters.

Distinguish these cases explicitly:

1. **Fresh authoritative termination:** a supported persisted terminal outcome or quota/error cause replaces stale retained running evidence for that attempt.
2. **Complete authoritative reclassification/disappearance:** source analysis may legitimately drop or reclassify a previously observed prompt, including the existing zero-call/compaction case. Reconcile that with shared CLI semantics and proof of snapshot completeness.
3. **Partial or omitted acquisition:** a missing row or unavailable source alone proves neither completion nor continued live activity. Preserve appropriate retained data/freshness and do not fabricate a terminal outcome.
4. **Actual ongoing work:** valid later calls, live children, background activities and concurrent prompts must remain running when canonical causal analysis says so. Do not terminate a parent while supported work still belongs to it.
5. **Stale publications:** delayed worker results, retained snapshots and changed generations must not overwrite newer terminal evidence or erase a legitimate newer attempt.

Do not patch the frontend with an elapsed-time cutoff, a “no cost growth” rule, an account-percentage check, or a blanket “missing means complete” rule. Likewise, do not retain a running flag forever just because an old snapshot contained it. Truthful stale/unavailable state is distinct from current execution.

Keep the existing shared adaptive acquisition/event cadence and bounded workers. Specify detection in terms of the first accepted authoritative capture and subsequent publication, not a new unsupported hard wall-clock deadline. The current automatic source cadence is approximately 5–30 seconds plus acquisition/admission time, with event hints and presentation ticks handled separately.

## Inspected divergence areas — leads, not a prescribed root cause

### Web bypasses the CLI prompt-row lifecycle

`src/watch/web_coordinator.py::_hydrate` and `_hydrate_startup` return empty results; Web obtains cards from `WatchCards` and replaces the CLI-derived active count. Shared coordinator inheritance therefore does not imply shared row-state reconciliation.

The relevant Web path is `CardWorkers._capture` → `capture_rows` → `WatchCards.accept/project` → `live_projection.card_row` → `watch.js`. The CLI path goes through `WatchCoordinator._hydrate`, `ReportService.build_watch_root` and `WatchRowTracker`. The browser currently trusts exported `prompt.in_progress`; simply changing CSS is not a fix.

### Retained evidence differs

`src/reports/watch_capture.py` fresh-loads a snapshot and calls `src/reports/session_history.py::retain_snapshot`, which retains previous source objects omitted from the fresh capture. `src/watch/cards.py::WatchCards.accept` can also merge missing previously running rows into a retained capture; its stated policy is that a missing source row is not completion evidence. A transition normally requires the former running row to be seen with `in_progress=False`.

CLI `src/watch/tracker.py::WatchRowTracker._retained_missing_rows` explicitly terminalizes a formerly running row that disappears from stateless analysis, with a documented V2 zero-call/compaction case. This is a concrete behavioral divergence worth tracing, but copying that action indiscriminately into Web would confuse incomplete reads with authoritative reclassification.

### Normalization already handles supported terminal/quota evidence

`src/sources/opencode_v2_wire.py::normalize_terminal_lifecycle` associates persisted idle outcomes (succeeded, failed, interrupted) with the correct preceding assistant attempt, respecting boundaries and later work. `src/sources/opencode_errors.py::normalize_abort_reason` recognizes supported explicit quota causes. `src/analysis/causal.py::build_prompt_record` consumes that evidence while preserving real child/background/later work.

Web's isolated per-capture source does not inherit the coordinator source's process-local interruption-reason cache. That cache supplements actor/reason information; it must not be required for persisted terminal truth after cold startup. Investigate only as evidence warrants, without declaring source isolation the cause in advance.

## Acceptance and regression evidence

1. **Source-to-Web parity:** exercise quota/error terminal evidence through the actual Web capture/retention/card/projection route and the CLI/report route. Assert the same canonical terminal state, available reason and final usage. Merely flipping a mocked card row's boolean is insufficient for this regression.
2. **Usage variants:** cover terminal outcomes with absent, zero and positive usage, including a quota-related outcome that must not remain running because it lacks a final priced model call. Persisted evidence works without a live interruption cache.
3. **Live transition and grace:** observe a running prompt, then fresh authoritative terminal evidence. The next accepted publication stops running time/activity/count contribution; existing terminal grace runs once and history transition follows. No stale running-only cost survives in shared downstream data.
4. **Cold start and recovery:** starting Web after the failure, reloading/resyncing, source recovery and repeated refreshes match CLI/report reconstruction. Record partial/unavailable states honestly rather than defaulting to running or success.
5. **Retention/races:** test authoritative disappearance/compaction, partial omission, retained snapshots, old worker generations and delayed publications. Neither stale running resurrection nor false completion is acceptable. Later legitimate work/new attempts remain possible.
6. **No false positives:** slow tools, active subagents/children, background work, concurrent prompts and valid later calls remain running. An account showing 100%, another prompt starting, a quiet catalog, missing cost growth or a source outage alone does not terminate them.
7. **Shared consumers:** full Watch and the new Mini projection use the same corrected authoritative state; Mini adds no independent lifecycle heuristic. The fix preserves the page layout/account/Today work, prompt order and history selection defined in the related FRs.

Extend proportionate existing fixtures/tests such as `development/tests/test_opencode_terminal.py`, `test_watch_cards.py` and Web live integration coverage. The existing `test_watch_report_cold_start_and_resync_share_terminal_truth` covers CLI/report reconstruction but not the new Web card pipeline; close that specific coverage gap. Record the reproduced mechanism, actual verification and any remaining inability to reproduce the owner's exact historical case in the completion report.

This publication is backlog-only. No production session interaction, product implementation, release/version change or new permanent test gate is part of creating the FR.
