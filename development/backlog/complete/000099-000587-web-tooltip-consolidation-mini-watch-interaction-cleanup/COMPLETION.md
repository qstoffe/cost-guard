# FR 000587 completion

2026-11-05 · Cost Guard v80.168 · implementation base `a7b41c1`.

## Delivered scope

- Mini keeps actual column-heading help and the return-to-Watch action, without
  routine header/row/table-level question marks or Earlier Sessions help. Both
  Session/Total CCost headings have two named explanations with a blank line.
  Full underlying titles remain selectable and accessible; outcomes and meaningful
  unavailable/partial/stale/authentication guidance are not hidden in tooltips.
- One subscription cue groups Primary quota and Additional quotas from existing
  view data, with native Used/Remaining amounts/limits, real periods/resets, observed
  period CCost and concise server-owned reference/attribution caveats. No source
  timestamps/enums, invented capacities or acquisition changes.
- Full Watch removes prompt-preview popups from both tables. One whole-daily-card
  explanation sits at the far-right edge. Quota usage/Capacity help consolidates at
  Capacity; account Today gets a cue only for useful attribution details.
- Shared controller separates hover, keyboard-focus and pinned help. Document
  exit/outside movement/window blur dismiss orphaned hover within bounded grace;
  mouse-owned focus cannot strand it. Actions dismiss immediately on activation,
  without stationary-focus or Live resurrection. Passive pin/keyboard/Escape,
  pointer transfer, accessible descriptions and teardown remain supported.
- Whole-app retained/removed/consolidated/repositioned rationale is recorded in
  `development/architecture/modules/web-help.md`. Current Web/Mini guides, version
  metadata/history and `development/journal/web/contextual-help.md` are updated.
  Ordinary progress advances to 38 only when this PR reaches default.

## Actual verification

- Full: **142 test files, zero failures, 87.0s**, four isolated workers, no competing
  browser matrix. An earlier overlapping run failed the unchanged historical
  catalog-TTL count assertion; unchanged final Full passed. No weakened assertion
  or claimed causal fix; timing causation remains unestablished.
- Working-tree validator: **11 checks PASS**, six existing advisory budget warnings;
  no raised cap/baseline. `git diff --check` clean.
- Hidden **Edge 156.0.4314.58**, actual Document PiP/shipped HTTP/CSP/SSE: shared-help
  and complete Mini probes PASS. Before-fix browser exit stranded focused hover;
  after-fix return/heading/quota and main Watch heading/daily exit checks close it.
  Mouse/touch/Enter/Space navigation/dismissal, keyboard ownership, deliberate missed
  trigger leave, panel transfer, Escape, pin/outside-dismiss, Live updates, Classic/
  Web light/dark, both tables, title selection, sticky/narrow/zoom/units/quota and
  disclosure/native-API lifecycle matrices passed. Other Web routes were exercised.
- Daily help: exactly one direct-card cue, far-right with no overlap/page overflow
  at 1280/360 widths and 100%/150% CSS zoom. The regression found and repaired a
  generic margin override. Fresh Mini/Watch screenshots inspected.
- Real-installation read-only V2 Watch/daily probe PASS: one owner/two streams/three
  accounts, active/history cards, coherent daily costs and advancing stream IDs.
  Owned workers closed without cleanup failure; shared OpenCode was not stopped.

Portable compact evidence and precise limitations:
`development/architecture/governance/verification/web-help-587.json`.

## Explicit verification exception and remaining uncertainty

**Decision Delegate, not the user**, approved an **FR 000587-only** exception after
explicitly reconsidering acceptance 9 and the actual-browser/PiP wording. Only
physical pointer travel into native browser chrome/another application and native
blur proof where headless emitted none are waived. Adequate actual hidden PiP
reproduction/regression does not justify desktop disruption; no visible desktop
action was authorized or performed. All other applicable tests remained required.

Physical OS-pointer/browser-chrome/other-window checks were **not performed**, not
PASS. All five headless target-focus attempts emitted no native blur; evidence
records **`native:false`**, followed by an explicit synthetic window blur to test
the handler. That is not native event-delivery proof. Native OS event delivery,
physical focus and monitor behavior remain unverified. No physical-desktop,
screen-reader, macOS or other-engine acceptance is claimed. This exception grants
no future authority; implementation is delivered with these verification limits.

No accounting, new polling, CLI, browser-native chrome, release ZIP, tag or GitHub
Release change. No unfinished implementation or additional task is claimed here.
