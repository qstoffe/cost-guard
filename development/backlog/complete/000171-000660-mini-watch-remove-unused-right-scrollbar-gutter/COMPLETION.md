# Completion — FR 000660

Implemented 2026-11-10 as v81.10 against `0da05445ee574952d268fa8d8502cdc2b8fb5b0d`.

## Outcome

Removed only `.mini-prompts`' unconditional `scrollbar-gutter: stable`. The unified
table fills equal existing body insets without internal overflow; genuine internal
scrollbars, the five-row viewport, sticky cells, document scrolling and narrow table
panning remain. No changes to JavaScript, opening/Fit measurement, metrics, acquisition,
subscriptions, settings or other tables. No new dependency or release ZIP.

The complete original FR bundle is retained here without body/attachment changes.
Ordinary progress advances to 110 only with this delivery's merge.

## Verification

- New actual-DOM regression failed on the original CSS: unused 15 px gutter,
  left/right insets 7.5/22.5 px. Fixed insets are 7.5/7.5; real overflow retains
  the browser's 15 px classic scrollbar or zero-width overlay scrollbar.
- Four full headless Document PiP runs passed **508 layouts**: Edge classic-width
  at 100%/125% zoom, Chrome overlay at 100%/125% and DPR 1/1.5. Geometry and
  original-declaration/fixed screenshot pairs cover Classic/Web light/dark,
  0/1/3/5/6/10→5→1 rows, last-row reachability and sticky headers. Existing
  focus/selected text/touch, width/height/manual/Fit/Remember, document/narrow
  scrolling and one-SSE/passive-no-resize checks also passed.
- Local `run_tests.py --suite full`: **181 groups, zero failures, 152.3 s**.
  Two native macOS zsh/PTY tests skipped on Windows, not asserted as platform PASS.
- Working-tree package validation: **11 passes, zero failures, seven advisory
  warnings** (existing prose/module budget debt). No caps/baselines were raised.
- Relevant real-installation `probe_mini_source.py`: V2, 20 coherent publications,
  two running rows, three accounts, 7.756 s; owned close 0.117 s. Zero real historical
  rows observed; deterministic/synthetic cases supply transition/history proof.
  No inference or shared OpenCode stop.

See the [scoped journal](../../../journal/web/mini-watch.md#unused-scrollbar-gutter-fr000660)
and [public synthetic measurements/screenshots](../../../architecture/governance/verification/mini-gutter-660/summary.json).
The code map and current Mini/user/version documentation were updated. Architecture
boundaries are unchanged; no whole-repository architecture update was needed.

Integrated browser was disconnected, so owned hidden browsers supplied browser proof.
Physical desktop/work-area/monitor frames, macOS pixels and screen-reader speech were
not tested or changed. No acceptance waiver, substantial exclusion or deferral.
