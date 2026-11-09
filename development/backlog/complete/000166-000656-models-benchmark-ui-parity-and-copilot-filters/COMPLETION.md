# FR 000656 completion — Models controls and value help

Implemented and locally verified on 2026-11-09 for **v81.5**. GitHub delivery and
merge status are established by the associated PR, not by this local report.

## Delivered scope

- Unboxed five-column benchmark with compact Publisher/Model/Effort/Relative Task
  Cost tracks and elastic Solved; independent keyboard-accessible sorting retained.
- Consistent official-source toolbars and configured-local last-successful dates.
  Authenticated manual Harbor refresh uses the existing host-owned finite lane,
  bypasses fresh cache on explicit demand, coalesces requests and retains last-good
  rows/date after failure without refreshing GitHub prices.
- Exact qualified publisher/version Harbor ∩ GitHub matching, canonical GitHub
  names, release-based New state and independent Copilot/latest checkboxes.
  Ambiguous/unmatched rows stay excluded for every filter combination.
- Source-derived effort checkbox dropdown, including truthful missing effort,
  All/subset/new-option reconciliation, zero selection, retained state and ordinary
  keyboard/touch dismissal. Full-edition denominator remains unchanged.
- Intrinsic per-value help for each benchmark configuration's actual coding client
  and source USD per attempted task, without restoring the removed columns.
- GitHub reference header's two existing paragraphs retained plus one two-sentence
  Token Mix paragraph. Every numeric ratio gets exact published native USD tiers,
  preserved promotion facts, then the actual common pooled comparison percentages
  and eligible count; unavailable data never becomes invented observed history.
- Current user/module documentation and release metadata updated. Original FR
  preserved; the entire bundle moved from Ready to Complete. Ordinary maintenance
  progress advances from 104 to 105 only when this change is merged.

## Verification

- Full local runner exercised **181 isolated entries**: 179 initially passed; two
  obsolete heading/toolbar expectations failed. Their causal repairs passed all
  three affected tests. The original Full invocation was not an all-green run.
- Final focused regression group: **52 tests passed**, including matching/filter
  contracts, HTTP security, forced lane/cache/recovery, exact prices/tiers, sample
  populations, missing values and refreshed intrinsic help.
- Chrome layout probe passed all six light/dark viewport cases. Authenticated
  Chrome and final Edge probes each passed **12 interaction checks / 247 layout
  records**, including the 240 width/theme/text-scale/status combinations.
- Read-only real-installation cold/forced-refresh probe passed: **35** Harbor rows,
  **27** exact matched rows, **29** GitHub references and **100** actual completed
  priceable comparison prompts. Forced refresh retrieved the source again while
  fresh; retained GitHub pricing was unchanged. No inference or owned work remained
  at exit; the shared OpenCode service was not stopped.
- Final working-tree validator: **0 failures, 11 passes**, v81.5 consistency and
  seven existing advisory size warnings; no budget/baseline increase. Whitespace
  check passed.

Details, source observations, repair history and logical scratch evidence references:
[`development/journal/web/models-controls.md`](../../../journal/web/models-controls.md).

## Limits and decisions

No scope waiver or new dependency. Controlled browser fixtures are synthetic and
do not prove production process concurrency; separate finite-worker tests and the
real-source host probe cover that boundary. Integrated screenshot capture was
unavailable; hidden Chrome/Edge evidence was used without desktop interference.
No physical desktop, assistive screen-reader or native macOS acceptance is claimed.
No ZIP, tag or GitHub Release was created.
