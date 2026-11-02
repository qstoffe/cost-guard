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

## Limits and continuity

No requirement/test exception was requested or granted. No model calls, prompt
abort/restart/resume, model changes, account-based termination or service stop
were performed. Rendered native/browser paint was not assessed; the visible
change is an allowlisted text label covered by DOM integration, not layout work.

The owner's exact historical quota case was **not reproduced**: no affected
Cost Guard session, source snapshot or runtime version was supplied. The
fixture-proven mechanisms are not asserted to be that incident's root cause.

Architecture/navigation and current lifecycle documentation were updated in
place. Reusable findings and proof limits are in
`development/journal/web/watch-terminal-lifecycle.md`. No ZIP, tag, GitHub Release,
installation or ordinary-checkout changes form part of this delivery.
