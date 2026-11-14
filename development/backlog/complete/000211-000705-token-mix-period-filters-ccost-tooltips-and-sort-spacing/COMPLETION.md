# Completion — FR 000705

Implemented for v81.49 (2026-11-14) in [PR #311](https://github.com/qstoffe/cost-guard/pull/311).

- Five backend-aggregated Token Mix scopes, default All time, with canonical
  event-time membership, reusable cached facts/valuations and stale-attempt safety.
- Both tables now have nine sortable columns, exact unit-aware category CCost
  help on percentage values, concise source-backed heading dates and one arrow.
- Token Mix/AI Stats period-row spacing matches Sessions; existing page defaults,
  CLI semantics, quiet refresh, partial telemetry and pricing meanings remain.
- Product version, current docs, code map and ordinary maintenance progress are
  included in this delivery. The original specification is preserved unchanged.

## Verification and limitations

Local Full passed: 197 groups, 2,428 tests, zero failures; four native macOS
zsh/PTY checks skipped on Windows. Package validation passed with seven existing
advisory warnings. Hidden Chromium probes passed theme/mobile, exact sorting,
periods, stale responses, keyboard/hover/touch help and control geometry.
Initial implementation CI passed common, Windows and both macOS architectures;
final-HEAD CI is checked before merge, not inferred from the earlier commit.

Real-installation managed reports completed all five scopes without job/result
errors. All time truthfully reported partial coverage with one omitted root;
the other four scopes acquired with no omitted roots. The initial strict probe
timed out without a report and is not counted as PASS. No manual oracle over
every private request, physical OS input or screen-reader output is claimed.
No paid inference, source mutation, service restart or release ZIP was needed.

Detailed ownership, regression repairs, measurements and evidence limitations:
[Token Mix period journal](../../../journal/web/token-mix-periods.md).
