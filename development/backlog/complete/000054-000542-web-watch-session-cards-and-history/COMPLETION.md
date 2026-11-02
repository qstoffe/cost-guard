# Completion — FR 000542

Date: 2026-11-02. Product version: v80.123.

## Delivered scope

Web Beta Watch now uses unframed active prompt cards and collapsed-by-default
Earlier Prompts containing five eligible distinct sessions with up to five rows
each. Headers link canonical session IDs and separate full-session CCost and
overlap-safe execution duration from the visible row slice. The nine columns,
structured model/effort, Watch context, units, prompt-local tool/skill disclosures,
amber running rows and observed terminal grace follow the approved specification.
Concurrent prompts retain separate cards; history excludes active/grace sessions
before limiting and replenishes continuously.

Four bounded isolated capture workers share per-session canonical analysis and
publish rows before optional full totals. Revision/generation guards reject stale
results; separate account-history/detail lanes avoid blocking Live or borrowing
its mutable service. Existing shared cadence and native account scheduling remain;
actual capture duration drives the existing EMA. Watch-only report/account chrome
is removed. CLI, Accounts, Models, settings and session transport limits retain
their intended behavior. No new endpoint, detail lease per card or browser-side
valuation/acquisition engine was introduced.

README, user Web docs and architecture owners now describe the new contract.
Version/date/history were updated without ZIP, tag or GitHub Release generation.
The original approved FR payload is preserved intact in this completion bundle.

## Verification

- Final-candidate Full: all 122 files passed, zero failures, 58.3s with four
  isolated workers. Working-tree validator: all 11 checks passed, zero failures;
  four existing design warnings remain (README and three legacy Python modules).
- Focused Watch/live run before checkpoint: 23 tests passed. A later 122-file Full
  had one failed foundation file solely from the version-history hard cap; compact
  wording reduced it to 31,904 bytes without raising budgets (also below the cap
  with Windows line endings). This failed run is
  not a PASS; the final Full above passed after the repair.
- Rendered fixture: nine cases passed on Chrome/156 Windows, Classic/Web light/Web
  dark × 1920×1080, 1366×768, 360×800. Includes unscrolled active visibility below
  expanded history, no frames/nested active vertical scroll, narrow horizontal
  panning, keyboard/focus/disclosure/scroll stability, colors and 100 cards.
  [JSON and screenshots](../../../tests/evidence/watch-cards/browser.json).
- Fresh read-only V2 probe: one owner/two streams/three accounts, two active plus
  one historical card, three cards with rows/totals, at most four rows/card and four
  pending captures; detail first/latest access and frozen consistency passed.
  Owned workers closed and shared OpenCode was untouched. No model inference.
- Deterministic regressions cover complete 10,000-prompt totals and overlap-safe
  duration, 100 active prompts, concurrent/restart/terminal/stale-result races,
  history ranking, bounded fair acquisition and deliberately delayed totals while
  another session finishes. Read-only live first-row/total timestamps were both
  3.082s, so they do not independently establish progressive phase timing.

## Delegated exception and remaining uncertainty

The **Decision Delegate**, not the owner, approved the full isolated-services
architecture and bounded synthetic headless browser checks. On continuation it
also explicitly authorized a limited acceptance #9 exception after final gates:
**headless viewport verification completed; native-fullscreen verification
excepted**. Nine rendered cases and independent layout observations were adequate
without expanding disruptive desktop automation. This is not an unconditional
acceptance #9 PASS or a blanket test waiver; no additional desktop permission was
granted.

Native fullscreen/physical display and physical input, screen-reader/macOS
behavior, real-source browser/SSE integration and independently measured live
progressive timing remain unverified. The real-source probe and blocked-total
deterministic test prove different things. Full catalog/history convergence was
not measured by the live probe. Detailed evidence and reasoning:
[Watch cards journal](../../../journal/web/watch-cards.md).
