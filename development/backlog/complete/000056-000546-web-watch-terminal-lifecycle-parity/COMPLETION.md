# Completion — FR 000546

2026-11-02 · v80.125

## Delivered scope

Web capture and retained Session detail now separate retained historical usage
from current authoritative lifecycle. A complete V1 transaction/V2 paginated,
revision-bracketed tree uses shared canonical causal analysis for execution;
partial reads default to unproven and cannot manufacture a terminal outcome.
Persisted assistant-attempt ends survive omitted idle rows. Later real assistant
attempts, supported tools, children and background work remain representable.

Cards stop duration/live activity on terminal publication, preserve final usage
and normalized stop reasons, and keep the existing finite observation highlight
separate from running state. Complete zero-call/compaction reclassification
retains observed history without inventing success or a source end. Generation
and capture-time rejection prevent delayed rows/totals/failures from overwriting
newer state. The frontend consumes exported truth, including allowlisted quota
causes; it adds no timeout, cost-growth or account-percentage heuristic.

Shared downstream cards carry terminal `in_progress=False`, so terminal grace
does not contribute to running counts/cost/duration. Mini Watch itself belongs
to the separately approved follow-up and is not implemented by this fix.
Cadence, four capture workers, 60-second continuation grace, ordering, page
layout, Today and account scopes remain unchanged.

## Reproduced mechanism and evidence

The new actual V2→isolated worker→capture/retention→card→export regressions first
failed for (1) a retained omitted active child overriding a fresh quota terminal,
(2) an omitted idle row resurrecting the same attempt and (3) delayed captures
replacing terminal state. Export also lacked the canonical abort reason.
These failures are now covered by passing deterministic regressions.

Coverage includes absent/zero/positive usage, failed/interrupted/success outcomes,
cold/repeated reconstruction, transition/grace/history, source partial/outage/
recovery, complete reclassification, retained detail, live children/slow tools/
background work and later legitimate attempts. Existing tests retain concurrent
focal and old-generation coverage. The new test file is in the existing runner,
not a separate product gate. DOM integration verifies quota-cause presentation.

## Actual verification

- `py -3 -B development/tools/run_tests.py --suite full`: PASS, 125 files,
  zero failures, 72.9 seconds; four bounded workers.
- `py -3 -B development/tools/validate_package.py --working-tree`: PASS,
  11 checks, zero failures. Four pre-existing design warnings remain (README,
  analysis/context, reports/service and Watch coordinator); hard caps unchanged.
- Focused lifecycle/Web tests: PASS, including the formerly failing cases.
- `py -3 -B development/tests/integration/probe_web_live.py --watch-cards --detail`:
  PASS against the real V2 installation. One live owner, two SSE streams,
  preserved run origin and advancing sequence; 2 active/2 history cards,
  3 row/total cards, at most 2 visible rows per card, 4 pending captures.
  First rows/totals at 9.513 seconds; detail paging/freeze remained consistent.
  Owned workers/HTTP host closed; shared OpenCode was untouched.
- `git diff --check`: PASS.

After normally merging the unrelated backlog-only default update `05c4dc9`,
Full passed again (125 files, zero failures, 63.2 seconds). The primary real
cards/detail probe also passed again: one owner/two streams/three accounts,
preserved origin/advancing sequence, 1 active/3 history cards, 3 row/total cards,
at most 5 rows/card and 4 captures; rows/totals at 4.616 seconds, consistent
detail paging/freeze, owned workers closed and shared OpenCode untouched.

Initial hosted Windows CI reported a failure in the existing launcher-lifetime
test `test_batch_waits_for_status_process_then_exits_with_its_result`
(`AssertionError: False is not true`); the new lifecycle tests were not reported
failed. Native/browser phases passed in that job. Raw GitHub job logs returned
HTTP 401 through the approved transport; accessible check annotations supplied
the test identity/error. The test has a five-second startup-file assertion and
passes locally; the precise hosted cause is not established. This initial
failed check is not PASS or waived; final PR checks remain required.

## Limits and continuity

An additional `probe_web_live.py --watch-cards --daily --detail` run failed with
`probe_daily_timeout` at its 120-second daily-publication limit. Detail was not
reached on that run. Its cause is unknown; live Daily liveness remains unverified
by this delivery, not PASS. Inspection of the shared-source diff found only
completeness flags, no new blocking waits/retries reachable from Daily.

The foreground **Decision Delegate** explicitly authorized a scoped workflow/test
exception: successful supplementary Daily acquisition and baseline comparison
are not prerequisites for this lifecycle fix, given passing primary evidence.
It did not waive preservation of Today, discovered causal failures, Full,
validation, the primary live probe or actual PR checks. No source-churn diagnosis
is asserted. The unchanged Daily pipeline and passing deterministic Today tests
are evidence, not a substitute live-Daily PASS.

No model calls, prompt abort/restart/resume, model changes, account-based
termination or service stop were performed. Rendered native/browser paint was not assessed; the visible
change is an allowlisted text label covered by DOM integration, not layout work.

The owner's exact historical quota case was **not reproduced**: no affected
Cost Guard session, source snapshot or runtime version was supplied. The
fixture-proven mechanisms are not asserted to be that incident's root cause.

Architecture/navigation and current lifecycle documentation were updated in
place. Reusable findings and proof limits are in
`development/journal/web/watch-terminal-lifecycle.md`. No ZIP, tag, GitHub Release,
installation or ordinary-checkout changes form part of this delivery.
