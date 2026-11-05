# FR 000589 completion

Implemented 2026-11-05 as v80.170. Original specification is retained intact.

## Outcome

- Shared main/Mini help labels and retained `?` cues have no dotted/dashed underline.
  Genuine links and semantic threshold/stale-warning decoration are unchanged.
- Passive header help has intrinsic text-sized targets and text-only hover color;
  padding/gaps do not open help, change to a help cursor or highlight the cell.
- Mini's Session and Total CCost remain edge-aligned in the same column but are
  separate text-sized help buttons, not one stretched invisible hitbox.
- Sortable report/Models headers retain original button click/keyboard/ARIA behavior;
  only the inline label owns hover and panel positioning. Existing shared lifecycle,
  focus/touch ownership, pointer transfer, Escape and refresh suppression remain.
- Current user guide, help module contract, release history and journal updated.
  Ordered ordinary-delivery progress advances from 39 to 40 only when merged.

## Verification

- Full suite: PASS, 143 files, 1,687 passed tests, zero failures/errors, 89.5s.
  One existing macOS zsh/PTY case is skipped on Windows.
- Working-tree validator: PASS, all 11 checks, six existing advisory budgets.
- Edge 156.0.4314.58 and Chrome 156.0.8078.80: actual hidden Document PiP/main
  help probes PASS, 24 header matrix cases and 36 layout observations each;
  Classic/Web light/dark, narrow/150% zoom, computed styles, text/padding/gap hit
  testing, bounded exit/panel transfer, keyboard/ARIA/Escape/touch and report help.
  Sorting outside labels remains functional. Synthetic screenshots inspected.
- Complete Edge Mini regression PASS: sticky headers, scrolling, selectable long
  titles, alignment, 560/800/280 widths, font/CSS zoom, themes/units/quotas,
  native API/disclosure lifecycle and one SSE.
- Read-only real-installation Watch/daily probe PASS: V2, one owner/two streams,
  three accounts, active/history cards, coherent daily costs, advancing IDs and
  no leaked owned workers. Shared OpenCode service untouched.

No requirement/test exception was requested or approved. Headless native blur was
not emitted; the existing injected blur test checks only the handler. Physical OS
pointer/window/chrome, screen-reader, macOS and non-Chromium acceptance remain
unperformed/unverified. Actual browser/PiP geometry uses real CDP pointer input;
no physical desktop PASS is claimed. Synthetic reports are not process proof.

Evidence and causal probe-fixture notes:
`development/journal/web/contextual-help.md` and
`development/architecture/governance/verification/web-help-589.json`.
No dependencies, inference, CLI/accounting/acquisition change, ZIP, tag or Release.
