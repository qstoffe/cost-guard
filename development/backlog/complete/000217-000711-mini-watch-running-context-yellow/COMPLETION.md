# Completion — FR000711

Implemented in v81.55, 2026-11-14. Mini Watch's verified Running rows use the
existing running-yellow foreground for all five cells, including Ctx. Independent
ordinary/red Ctx styling remains on non-running rows; canonical warning eligibility,
numbers, source severity and accessible help are unchanged. The whole original
specification is preserved alongside this report.

## Verification and scope

- Browser-observed RED before the fix: neutral Ctx versus four yellow Running cells.
- Actual headless Chrome/Edge Document PiP: 192 computed-style matrix cases each,
  plus unknown/pending Ctx; both themes/schemes, lifecycle transitions, repeated
  refreshes, all five cells/descendants, immutable inputs and keyboard/hover/touch help.
- Supplemental Edge lifecycle/units/width/reopen probe passed after repairing raw
  JSON synchronization and outdated non-running Ctx expectations in the harness.
- Full: 200 groups, 2459 passed tests, four macOS-only skips, zero failures.
- Working-tree validator: 11 passes, zero failures, eight existing advisory warnings.
- Real V2 read-only probe: 39 coherent projections, one Running prompt, owned
  acquisition closed; no paid model request or shared OpenCode interruption.

**Approved narrow exception:** Decision Delegate excluded the unrelated supplemental
Total-heading mixed-input hover-opening failure. The composite `help-only` invocation
remains **FAIL**; subsequent unreached Duration cases are **NOT RUN**, not PASS.
Required Ctx colors and input help passed independently in both browsers.
Full and required CI are not waived. No physical-desktop or live-browser color
proof is claimed; browser matrices use synthetic canonical-shaped publications.

The [journal](../../../journal/web/mini-watch.md#running-ctx-color-precedence-fr000711)
records the decision, failure, existing Suggestion000684 link, artifacts and uncertainty.
No architecture ownership changes, dependencies, ZIP, tag or GitHub Release.
