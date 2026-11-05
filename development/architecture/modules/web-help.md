# Web contextual help: writing and interaction

Owner: `src/web/assets/help.js`; shared styles: `app.css`. Applies to the main
application and separate Mini Watch document. FR 000587 selective follow-up: 2026-11-05.

## Writing patterns

- Answer “What am I looking at?” first, in plain English. A simple field needs one
  sentence, not a standard-size card. Do not lead with internal implementation names.
- Separate ideas with `\n`. Use occasional blank lines to group metric components;
  let CSS wrap naturally, never insert arbitrary hard-wrapped lines.
- Example: `Estimated prompt cost, not your bill.\nI — First request’s incoming
  context cost.\nE — Output, later requests and linked subagents.`
- Say **N/A = unavailable, not zero** and **? = partial pricing/data** where they
  affect interpretation. Keep estimates, retained observations and unsupported work
  honest. Do not repeat every caveat on each model/date cell.
- Distinguish prompt/session/day scopes, reference CCost/billing/native quotas and
  token percentages/cost. A main model’s name does not describe every contributing
  model. Do not claim unlinked work is counted.
- Advanced sources and long diagnostics belong in an optional named disclosure,
  not a beginner header. Exact source strings, titles and previews are data:
  preserve them verbatim with `textContent`, never HTML.
- Icons are optional semantic reinforcement, never the only status/explanation.
  Inherit semantic colors in Classic and Web light/dark; do not copy a palette.

## Interaction and implementation

- `ContextHelp.button(label, textOrFunction, document)` creates a labelled,
  keyboard/touch/hover passive trigger. Dotted underline and `cursor: help` make
  help discoverable without relying on a cursor change alone.
- `ContextHelp.beside(valueContainer, textOrFunction, accessibleName)` adds an
  explicit `?` button beside a value when it adds useful information. Do not turn
  selectable data into help-only buttons or override its selection cursor.
- `ContextHelp.attach(action, textOrFunction)` augments actions such as sorting
  and checkboxes without replacing click behavior or their pointer cursor. Activation
  immediately dismisses help instead of pinning it. Prefer
  a separate cue when the explanation should be independently tappable.
- Functions read current display tokens. `ContextHelp.refresh(container)` updates
  open help without reopening it; `ReportView.syncUnits` refreshes once after text
  updates. Never price or total data inside a help function.
- One manual Popover per document holds noninteractive `role="tooltip"` text with
  preserved line breaks. The active trigger references it via `aria-describedby`;
  other description IDs survive. No duplicate native `title`/`aria-description`,
  HTML injection, storage, request or dependency.
- Hover/keyboard focus opens; 150ms exit grace permits pointer transfer into help. Escape closes
  without moving focus and rendering cannot reopen it. Tap/click pins passive help;
  repeat activation or outside tap dismisses. Focus leaves normally. Removed
  triggers close help. Position/size clamp to the viewport; long exact data wraps
  and scrolls instead of clipping outside it.
- The controller owns an explicit **hover / focus / pinned** origin. Mouse-owned
  focus never prevents hover exit; deliberate keyboard focus survives unrelated
  pointer movement. Captured document `pointerout` with null related target,
  document/root leave, outside pointer movement and window blur cover missed trigger
  leaves. Pointer re-entry cancels the one bounded exit timer; outside movement cannot
  continually postpone it. No polling or recurring fallback runs while closed.
- Visibility hide/pagehide and removed-trigger observation clean up open help/timers.
  Escape/actions suppress immediate reopening; content refresh cannot show help.
  Action suppression survives window-focus restoration, but new hover after leave
  or new intentional keyboard focus can show it again. Touch does not open hover help.
- No links/buttons or focus trap inside tooltips. Interactive advanced help uses
  native `details/summary` or a suitable nonmodal disclosure. Critical status stays
  visible outside hover help.

## Whole-application audit inventory

| Surface / entry points | Disposition |
| --- | --- |
| Full Watch: all ten active/historical headings | Rewritten shared buttons; explicit I/C/W/O and I+E lines, model/subagent caveat, Ictx versus next context |
| Watch: exact Started/Finished dates, prompt preview, extra-model flag | Keep useful full dates and actual additional-model information; remove full-preview popups in both tables, including short visible previews |
| Watch: session Context/CCost and price warning | Concise shared context/cost help; severity and canonical threshold remain visible |
| Watch: daily summary, account Today, primary/secondary quotas, exact reset | Reposition one whole-summary cue to the far right; no mid-count icon. Consolidate identical usage/Capacity explanations at Capacity, preserve exact reset dates and scope/basis caveats. Account Today cue only for meaningful attribution notes |
| Watch: activity and Earlier Prompts | Native disclosures retain full lists/counts; expanded activity cues explain all-call totals, red outcome subsets, missing evidence and direct skill failures without repeating lists |
| Mini: both tables’ headings | Keep actual heading targets, no extra `?`; Session and Total CCost are two named sections separated by a blank line. Prompt CCost and active-next versus historical-last-valid-next context remain distinct |
| Mini: session title/cost and prompt/history status | Remove every row cue/duplicate value help. Keep full underlying selectable title and row accessible naming, prompt outcome/stop cause and confirmed unavailable/partial notes |
| Mini: Today, freshness, Earlier Sessions, quota bars, return-to-tab | Remove both header cues and all Earlier Sessions help; no table-level replacement or progress-bar popup. Keep useful return action help with immediate activation dismissal. Critical host/auth/source warnings stay visible, not observation logs |
| Mini: subscriptions | One cue groups Primary quota and Additional quotas from existing view data, native orientation/amounts/limits, real resets, observed Used CCost and concise server-owned capacity/attribution caveats. No timestamps/raw sources; no new acquisition |
| Models: checkboxes and multi-sort | Short action help on focus/hover/tap, preserving action cursors and sorting/filtering |
| Models: More information, price evidence and promotion notes | Concepts shortened into named lines; exact source evidence/terms remain optional visible data |
| Sessions, Snapshot/Live, reports/date range, Token Mix, active-hour | Shared report-sort help; Reading this report and Sample/price coverage shortened and line-separated. Scope forms and visible context/retention/billing/active-hour details remain persistent disclosures/data |
| Accounts | Observation details stays a keyboard/touch-native disclosure with exact source/native-money/pace/billing facts; no native title explanations existed |
| Settings | Visible ARIA-associated explanations rewritten; retain native selects, save feedback and default labels, no redundant popovers |
| Navigation / host status | Visible action labels retained. Host warning becomes one real details disclosure, not CSS-hover plus native tooltip. Observation lines shortened; hidden status has no redundant title |

Audit searched every shipped Web asset for `title`, `aria-description`, tooltip roles,
Popover creation and dynamic hints. Remaining document/route/session titles are data,
not tooltip APIs. No native-title metadata exception is needed: exact metadata uses
the same accessible helper. Visible provider notes and true disclosures intentionally
retain source-specific facts.

Regression owners: deterministic `integration/web_help.cjs` covers origin, missed
leave/document exit, repeated movement, suppression, blur/visibility/teardown and
document isolation. Hidden `probe_web_help.cjs` / `probe_help_lifecycle.cjs` use
actual Chromium Document PiP plus main Watch with real CDP pointer/key/touch input.
Mini probes retain selection, sticky headers, narrow/zoom/theme/unit/disclosure
coverage. Headless evidence does not prove physical OS pointer/window transitions.
