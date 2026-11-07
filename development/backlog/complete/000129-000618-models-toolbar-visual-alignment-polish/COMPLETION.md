# FR 000618 — Completion

Implemented 2026-11-07 in v80.198.

## Outcome

- The Models price-control group has its own semantic CSS class, normal system-UI
  typography and Watch-matching compact button/text metrics. Numeric price tiers
  and ratios retain monospace; other views' controls are unchanged.
- Centered action/date/checkbox geometry, flexible wrapping, readable long feedback
  and coarse-pointer label/action targets replace the previous top-aligned row.
  Refresh remains a native one-time button, not a toggle.
- A keyboard regression exposed existing disabled-button focus loss. The explicit
  price action now restores focus after completion without stealing focus from a
  user who moves elsewhere. Refresh semantics, factual upstream timestamps,
  retained failures, pricing calculations, filters and sorting remain unchanged.
- The complete original task bundle moved intact to this directory. Maintenance
  progress advances ordinary count 67 → 68 only with the merged delivery.

## Verification

- Final local Full: **155 isolated files, zero failures**, 111.0s.
- Actual pre-fix browser evidence: monospace button/date, 40.25px button height.
  Post-fix: system UI, 30px height, 12px font, exact Watch toggle metric parity;
  coarse-pointer action/labels 44.25px.
- **240 real-DOM toolbar cases PASS**: five widths (360/800/1280/1366/1920),
  Classic/Web light/dark, four text scales (100/125/150/200%), and four feedback
  states, including long synthetic date/error/label stress. Actual geometry,
  fonts, overflow, clipping, overlap and checkbox alignment are asserted.
- Native Enter/Space and touch activation, focus retention/no focus theft,
  disabled duplicate guard, success, controlled upstream offline/invalid failure,
  retry, exact table/time retention, independent filters, sorting and help pass.
- Existing canonical Models browser probe: all six layout/tier/filter/sort cases
  PASS; 360-light and 1280-dark toolbar screenshots visually inspected.
- Real V2 installation: authenticated actual spawned refresh made a new upstream
  observation (29 rows), preserved Watch's pinned catalog, and passed normal/full
  Models probes. Zero remaining owned threads/processes and no cleanup failures;
  shared OpenCode was not stopped and no inference was started.
- Working-tree package validation: 11 passes, zero failures, six existing advisory
  warnings. No hard cap changed, no ZIP/tag/GitHub Release produced.

Evidence and historical failure distinctions are in
[the Models pricing journal](../../../journal/web/models-pricing.md). Local evidence:
`scratch:/models-toolbar-before.json`, `scratch:/models-toolbar-after.json`,
`scratch:/models-layout.json`, `scratch:/models-live.log`,
`scratch:/full-tests-final.json`. The broad-pattern monolithic test experiment
timed out; its causal listener-cleanup issue was fixed and the final supported
isolated Full run passed. No failed or unrun experiment is counted as PASS.

## Documentation, decisions and limits

Architecture/code-map, the existing journal, README/version history and runtime
version metadata were updated. User instructions are unchanged, so
`docs/web-beta.md` needs no edit. No current user/Decision-Delegate requirement or
test exception was requested or granted.

Integrated Review was disconnected. Evidence uses hidden Chrome with an owned
temporary profile and equivalent root-font scaling, not physical desktop zoom,
screen-reader, other-engine or touch-hardware acceptance. Failure retention uses
controlled provider faults; the real upstream check succeeded. One unrelated live
history-batch error was observed; the scoped Models success is not a whole-history
health claim. Natural multiline feedback can increase row height rather than clip.
