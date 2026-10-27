# FR 000200 — Keep session reports as one-shot snapshots with provisional running metrics

## Problem and desired outcome

A plain session-detail invocation, `python cost-guard.py <session-id>`, currently renders the ordinary eight-column session report, then automatically starts a session-scoped Watch dashboard via `src/bootstrap.py` when any projected prompt remains `in_progress`. The presentation changes unexpectedly and the process waits for the running work to end. A request for a report should instead mean **one static snapshot of the selected session at report generation time**, regardless of whether prompts are running.

The snapshot must include the running prompt(s), clearly marked `[RUNNING]`, and show useful **provisional metrics from already-observed requests** rather than withholding metrics solely because a prompt has not yet finished. No automatic tracking, refresh or switch into Watch follows the report.

## Required behavior

1. **One-shot, always:** `python cost-guard.py <session-id>` produces one regular session report, then exits normally, even when one or more prompts/compactions/background tasks are running. The output does not change afterward. Remove the implicit transition to `WatchCoordinator.run_until_inactive()` for this command; no extra source polling or wait-for-inactive loop.
2. **Preserve the complete existing session-report layout:** the usual `Prompt`, `CCost`, `Calls`, `Duration`, `~Ictx`, `~Ictx CCost`, `~Extra CCost`, and `I/C/W/O %` columns, chronological prompts/compactions, model labels, subagent breakdowns, summaries, context notices, explanatory notes and normal formatting. Show `[RUNNING]` on any active item using the existing lifecycle evidence, without implying it has terminated.
3. **Use currently known usage for running prompts:** `CCost` and `Calls` already project observed causal requests and must remain available with existing unknown/partial-price semantics. Also compute provisional `I/C/W/O %`, `~Ictx CCost`, and `~Extra CCost` while running **when defensible observed token/request data permits**, instead of categorically setting them to unknown due to `in_progress`. Use the same definitions, source-neutral attribution, reference catalog, rounding and causal de-duplication as the completed report; do not invent unreported tokens, prices, account billing or completed requests. No data / insufficient or ambiguous evidence remains `N/A`, `running` or the existing suitable unknown indication, never fabricated zero or a falsely complete cost breakdown.
4. **Snapshot duration:** show the running elapsed wall-clock duration available at the report snapshot, if supported by existing lifecycle timing, frozen at that instant. Preserve the established execution-duration semantics and honest `N/A` cases for completed prompts and the overlap-safe session total; do not synthesize a completion timestamp. Report generation is finite even if the running duration is incomplete.
5. **Honest provisional presentation:** the active row's `[RUNNING]` marker makes clear that metrics can grow or change after this report was taken. A concise explanatory note may clarify this if needed; do not clutter each metric or silently claim final/verified usage. Maintain distinction between reference CCost, actual billing, cached input, and unknown pricing. Totals, mix breakdowns, threshold highlighting and warnings must reflect the *same snapshot* without accidentally mixing completed-only and running-only logic.
6. **Strict scope boundary:** explicit `python cost-guard.py <session-id> --watch` remains the current session-scoped Watch dashboard and its existing indefinite behavior. Global `--watch`, ordinary dashboard, date, session-list, Token Mix, quotas, V1/V2 source selection and reconnect policy are unchanged by this FR. A future web-based UI/session-detail Watch design is intentionally out of scope.

## Current implementation references

- `src/bootstrap.py`: after `ReportRenderer(config).render(projection)`, the session plus `in_progress` condition constructs `WatchRenderer` and `WatchCoordinator` and calls `run_until_inactive`. Remove this automatic follow-up, retaining explicit `--watch` dispatch.
- `src/reports/service.py::_build_session_detail` and `src/reports/prompts.py`: continue to create the standard complete session-detail projection and totals.
- `src/reports/prompt_rows.py::PromptRowProjector.prompt`: currently forces running `token_mix_percent`, `incoming_context_ccost`, and `extra_ccost` to `None`. Permit properly supported provisional values using the existing `mix_percent`, `_context_ccost` and `_extra_ccost` computation boundaries (including correct partial/unknown handling) without introducing a second valuation engine.
- `src/presentation/report.py`: preserve current report columns, running label, displayed metrics and frozen presentation; render no interactive Watch frame.
- `src/analysis/duration.py`: preserve existing proven terminal boundaries and overlap-safe totals while presenting a finite running elapsed snapshot when supported.

These are implementation pointers, not instructions to force changes into a particular layer if a smaller, better-scoped seam is found.

## Acceptance examples / regression coverage

- Completed session: a plain session ID invocation prints the same normal report and terminates, with no Watch renderer/coordinator.
- One running prompt with observed usage: one report contains `[RUNNING]`, known CCost/Calls, supported provisional I/C/W/O split and incoming/extra CCost; the process exits immediately after output. Waiting or subsequent OpenCode updates never mutate that printed report.
- Running prompt before its first measurable model call, partly priced request, incomplete token evidence or unsupported input/context attribution: no synthetic zeros or unjustified 100%-complete percentages; known subsets and unknown cases remain honest.
- Running duration is a fixed snapshot value rather than a live counter. Completed duration and total accounting remain consistent with existing semantics.
- Multiple running prompts, linked child work, background-only progress, compactions, abort/error, model changes and context-warning thresholds remain represented with stable row ordering and no duplicates.
- `<session-id> --watch` and global `--watch` retain their existing Watch behavior; date/range and other report modes do not unexpectedly inherit new watch lifecycle behavior. Add proportionate focused synthetic regression tests; no new permanent validation gate or release target.

## Publication

Owner-requested **normal-priority FR000200**, allocated after the current GitHub `main` backlog identity high-watermark 190. FR-only publication: add this pending specification and advance `development/backlog/identity-state.json`; do not change product code, tests, version, packaging or any existing in-progress FR. Implementation remains a separate future workflow.
