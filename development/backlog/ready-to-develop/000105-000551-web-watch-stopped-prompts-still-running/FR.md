# FR 000551 — Fix remaining stopped prompts shown as running in Web Watch after FR000546

## Owner report and backlog decision

On **2026-11-02**, the owner reports that **some prompts have stopped long ago and are no longer considered running by CLI Watch, but Web Beta Watch still treats them as running**. Interrupted/aborted prompts and quota exhaustion are suspected examples; the exact termination cause of each affected prompt is not established.

The owner asked to keep an existing unfinished fix if one covered this report, or create a new FR if the earlier fix had already been completed. Live repository inspection found:

- **FR000546 — Reconcile Web Watch terminal lifecycle with CLI after quota exhaustion** is in `complete/000056-000546-web-watch-terminal-lifecycle-parity/`.
- Its implementation was merged in [PR #120](https://github.com/qstoffe/cost-guard/pull/120), merge commit `56d197442266b0b3defc2bdbb763276bfd9126b3`, on 2026-11-02, and is recorded as **v80.125**.
- The completion report explicitly says the owner's exact historical quota incident was **not reproduced**, because no affected Cost Guard session, source snapshot or runtime version was supplied.
- At inspected main `39d30421aa955872f37af88f6b814caf1ee4eeb7` (**v80.126**), no open Ready/On Hold FR or open PR separately covers this remaining lifecycle mismatch. FR000547 concerns presentation/native quotas, FR000549 quota-period accounting, and FR000544 the planned Mini Watch.

Create a distinct follow-up rather than reopening or rewriting the historical completion. Permanent identity: **000551**. **Ready priority: 000105**, after the existing accounting correctness fix FR000549 (000100), and before Watch presentation FR000547 (000115) and Mini Watch FR000544 (000120). Creation is owner-authorized by the conditional request above; this queue placement keeps correctness ahead of presentation without moving the existing first item.

The report establishes a continuing user-visible symptom, **not yet a reproduced regression in current main**. The installed Web host/CLI revisions, affected session/prompt/attempt IDs and source observations were not provided in this request. Do not assume the browser is connected to the newest host just because the repository has been updated, or claim a specific missing terminal cause without evidence.

## Desired outcome

For the same source and canonical session/prompt/attempt at comparable fresh observations, Web Watch and CLI Watch must agree on whether execution is still active. A prompt that authoritative current lifecycle evidence identifies as stopped must not remain yellow/running, continue accumulating elapsed running time, or contribute to running counts/cost/current-tool indicators indefinitely.

Preserve the actual supported outcome and final usage. An interrupted, failed, quota-stopped or otherwise retired attempt must not be relabelled successful merely to remove it from the active area. If evidence supports that work is no longer active but does not establish an exact end reason, preserve that distinction.

The existing finite terminal highlight is allowed, but it is separate from execution: the terminal row is not running, its duration stops growing, and repeated refreshes do not restart the grace. It leaves the active area under the established grace/history rules. Historical rows may remain in Earlier Prompts; removal from running does not mean deletion of their accounting/history.

## Investigation that closes the previous evidence gap

1. **Establish the compared runtimes and identities.** Record the running Web host version/revision, CLI version/revision, selected source and affected canonical identity where accessible. First reproduce against a host containing FR000546; verify against the follow-up fix afterward. A stale host or older installation is a possible explanation to verify, not an assumed diagnosis.
2. **Trace one concrete mismatch.** Use available read-only source evidence, retained captures, shared export and browser state to locate where CLI recognizes retirement while Web preserves or renders running. Inspect source normalization, capture completeness, retained history/current lifecycle reconciliation, scheduling/admission, card acceptance, exported state and browser application as appropriate. Determine whether Web receives a fresh relevant capture at all; a correct terminal rule cannot help a card that is never refreshed.
3. **Cover stops without a conventional final row.** Include failed/interrupted/quota outcomes with absent or zero final usage, and abandoned/uncleanly stopped attempts where the normal completion/abort event is missing but the existing canonical CLI/source lifecycle can establish that execution ended. Distinguish those cases from an unavailable or incomplete read, a quiet but live prompt, or an unproven termination.
4. **Reproduce the uncovered path.** Prefer a small sanitized fixture derived from the affected shape through the real source-to-Web route. If the exact local case is unavailable, record that limit and demonstrate a concrete post-FR000546 defect before claiming a fix. Passing the earlier fixtures or a DOM test with an already-terminal mocked row is not evidence that this remaining report is resolved.

Useful existing owners are `src/watch/web_coordinator.py`, `src/watch/card_workers.py`, `src/watch/cards.py`, `src/reports/watch_capture.py`, `src/reports/session_history.py`, `src/application/live_projection.py`, `src/web/assets/watch.js`, and the CLI coordinator/tracker plus shared source/causal analysis. Read the original FR, its completion and `development/journal/web/watch-terminal-lifecycle.md` first. These are investigation leads, not a prescribed root cause or requirement to redesign every layer.

## Required behavior and constraints

- Reconcile an observed running attempt on the first accepted fresh authoritative capture that establishes retirement; publish the corrected state on the next corresponding update. If capture scheduling/admission is the defect, fix that path within the existing bounded acquisition model.
- Starting Web after the stop, refreshing the tab, reconnecting and later resync must reconstruct the same state without relying on a process-local interruption event that occurred before Web started.
- Retained history, an omitted terminal row, delayed worker results, old generations and later totals must not resurrect the same stopped attempt. A genuinely later attempt or supported new work must still become running.
- Use shared canonical lifecycle meaning for Watch, detail and future Mini Watch consumers. Fix the responsible owner; do not add a separate browser-only filter or copy a CLI heuristic without checking its evidence.
- Preserve legitimate live tools, children/subagents, background work and concurrent prompts. Partial/source-outage cases remain truthfully uncertain/stale; omission alone does not manufacture success or an end.
- Do not use an arbitrary age, no-token/no-cost-growth timeout, account utilization percentage or another prompt starting as proof of termination. Retain existing continuation semantics and adaptive acquisition cadence; no new provider polling loop is requested.
- Do not abort, restart or resume real prompts, change models, or modify provider quotas to reproduce a display bug. Keep existing accounting, card layout and history selection.

## Acceptance and focused verification

1. **New failing regression:** reproduce a concrete remaining mismatch on a revision containing FR000546, through acquisition/capture/retention/card/export rather than only setting a mocked boolean. Equivalent CLI/report observations show why the attempt should no longer be running. The same case passes after the fix.
2. **Visible transition:** the corrected export and Web rendering stop running duration, styling, live activity and running-only aggregates. Terminal grace expires once; repeated refreshes do not keep the row active forever. Preserve final known usage and the supported stop reason.
3. **Cold and long-lived views:** cover Web opened after termination, a continuously open page, reload/reconnect and recovery, including a stopped attempt without a conventional priced final call. Verify the newly found termination/retirement shape, not merely the quota fixture already delivered.
4. **Retention and false positives:** retain the prior missing-child/omitted-idle/delayed-capture protections. Verify incomplete reads, stale publications and legitimate subsequent work so the fix neither resurrects stopped attempts nor hides active ones.
5. **Evidence-led completion:** record the compared versions/source, actual reproduced cause, the focused source/Web verification and what remains unverified about the owner's local case. If evidence shows only an outdated runtime, document the verified version-specific result explicitly rather than claiming a new source defect was fixed. Do not close this report as resolved solely because FR000546 is Complete or its old tests pass.

Extend proportionate existing coverage such as `development/tests/test_watch_card_lifecycle.py`, `test_opencode_terminal.py`, `test_watch_cards.py` and relevant Web integration checks. Reuse existing diagnostics and test infrastructure; no permanent new telemetry system or release gate is requested.

## Delivery scope

This is a focused follow-up correctness fix for remaining Web/CLI running-state divergence. FR000546 remains historical delivered work; FR000547 and FR000549 keep their separate scopes. Mini Watch must consume the corrected shared state when implemented.

Creating this FR is **backlog-only**: publish this document and advance the permanent-identity counter. Product implementation, version/release changes and interaction with the owner's running prompts are outside this authoring task.
