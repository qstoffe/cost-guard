# FR 000200 completion — one-shot session snapshots

## Outcome

Implemented in v80.79 (2026-10-26). Plain session detail prints the existing eight-column report once and exits without constructing Watch, even while work remains active. Supported running token mix and incoming/extra reference CCost use the completed-report definitions; missing telemetry, attribution or prices remain unknown. Totals include the same observations. Running duration uses the existing frozen observation clock, never a synthetic completion time.

[Delivery PR #55](https://github.com/qstoffe/cost-guard/pull/55) · [Implementation candidate](https://github.com/qstoffe/cost-guard/commit/4fd38283e052e46a3403697492964da5bbb03b3f).

## Changes and choices

- Removed only implicit session-to-Watch dispatch in bootstrap; explicit session/global Watch remains independent.
- Session-specific projection opt-in preserves existing date and Watch metrics. Existing analysis, causal attribution, pricing, rounding, lifecycle evidence and duration remain authoritative; no second calculation engine or polling loop.
- Running metrics require defensible token-category and attribution evidence. Mixed incomplete active telemetry makes aggregate diagnostics unknown rather than silently displaying completed-only values.
- Preserved table/model/subagent/context presentation. A concise provisional note explains the frozen snapshot. The running marker precedes the preview in session reports so long previews cannot hide it; cost warnings remain visible separately.
- Updated runtime version, release history and current usage documentation. Registered eight focused deterministic snapshot tests in the existing runner.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, 95 test files, zero failures (final run 54.9 seconds). Covers existing completed/aborted/compaction/background/child/duration behavior alongside the new regressions.
- New tests cover V1/V2 observed metrics and totals, missing telemetry/prices, ambiguous attribution, pre-first-call unknowns, frozen duration/output, narrow long-preview markers, unchanged Watch/date projections and plain/explicit-Watch bootstrap dispatch.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, 11 checks, zero failures. Four existing design-budget warnings remain (README, analysis context, report service, Watch coordinator); hard caps unchanged.
- Read-only real V2 installation probe: active session report returned 0 in 0.41 seconds, one visible running row, eight-column layout and provisional note, zero implicit Watch calls (forbidden-constructor canary). Bounded explicit session Watch initialization/render retained one active row; closed normally. No provider inference, credential mutation, source mutation or service restart.
- No UI/browser automation, ZIP, live-model evaluation or separate permanent release gate was needed. No feature-PR self-review or implementation agents used.

## Knowledge and limitations

Journal: **no-update**; this is a focused projection/lifecycle correction, not a new reusable integration investigation. Architecture: **no-update**; existing composition, analysis, reports and presentation boundaries are unchanged; the focused test is registered in the source-owned runner. Source/tests and current user documentation describe the behavior without duplicating them in a new journal leaf.

Explicit indefinite Watch was not left running: deterministic dispatch tests plus bounded real initialization/render prove the relevant unchanged seam. Missing history/telemetry/pricing is not repaired or inferred. Web migration remains future work; FR 000290 and later specifications and their attachments are retained. No pending cross-FR recovery artifact is needed by this change.
