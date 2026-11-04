# Completion — FR 000571

2026-11-04 · v80.151 · base `711e45b21ef6c9d5ff84f02653205f2a0efdea56`.

## Delivered scope

- Mini Watch renders CTX's existing display token without adding an approximation
  prefix. Grouping, zero, N/A/missing context, source characters and estimate guidance
  remain intact; full Watch context is unchanged.
- Mini and full Watch global daily summaries use **CCost Today**, including Mini
  loading states and full Watch's accessible section name. Canonical daily values,
  prompts, Token Mix, currency/retention/rollover and account cards are unchanged.
- Current guides, focused rendering/accessibility regressions and release facts
  updated. Original specification/payload moved intact; proposed ordinary progress 22.

## Verification

- Local Full: **138 bounded units, zero failures, 90.5s**; package validation:
  **11 passes, zero failures**, six pre-existing advisory size/design warnings.
- Hidden Chrome 156.0.8078.80 and Edge 156.0.4314.58, emulated scale 1.5: **PASS**.
  Includes loading/observed labels, CTX updates/N/A/tooltips, intrinsic sizing,
  narrow-window scrolling, units/themes, keyboard, lifecycle and single SSE.
- Read-only installed V2 Watch/Daily probe: **PASS**, reconciled category CCost,
  two active/two historical cards and clean owned shutdown. Daily prompt-count
  completeness remained false; no invented completeness or shared-service stop.
- New VM checks reproduced both original presentation defects before the fix.
  Browser expectation corrected from assumed N/A to the fixture's actual `120k`.

[Evidence, checks and limits](../../../journal/web/mini-watch.md#fr-000571--v80151-2026-11-04).
Journal updated; architecture boundaries unchanged, current Watch wording corrected.
No outstanding implementation or release ZIP. Native OS geometry, screen-reader and
physical macOS behavior were not exercised; headless proof is not OS proof.

## Decision Delegate-approved CI exception

On 2026-11-04 the **Decision Delegate** explicitly authorized merging FR 000571 /
PR 154 without completed `native (macos-15-intel)` verification if it remains queued
without a runner and is the sole missing check. On tested implementation SHA
`0fbd02a09a8fb794f69e2da3ace0ff0aa4678c6b`, run `41874147908` completed Linux common,
Windows 2025 and macOS 15 ARM successfully; Intel job `126728878795` remained queued
after an eight-minute foreground wait and fresh status check. Neither test failure
nor a GitHub outage was established. This job covers unchanged native launchers,
lifecycle, AppKit and compilation; the passing local/rendering/other-platform
evidence justifies this task-only exception. **Intel-native behavior is unverified**,
not PASS. The delegate authorized this reporting-only correction and extends only
the queued Intel exception to its successor SHA; other checks remain required.
No workflow/protection changes, force, cancellation or duplicate rerun authorized.
