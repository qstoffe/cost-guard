# Web contextual help: writing and interaction

Source revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Checked revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Last checked: 2026-11-06
Status: current

Owner: `src/web/assets/help.js`; shared styles: `app.css`. Applies to the main
application and separate Mini Watch document. FR 000601 grouped-detail follow-up: 2026-11-06.

## Writing patterns

- Answer “What am I looking at?” first, in plain English. A simple field needs one
  sentence, not a standard-size card. Do not lead with internal implementation names.
- Separate independent facts with concise `•` bullets or `\n`. Use blank lines to group metric components;
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
  keyboard/touch/hover passive trigger. Labels use `cursor: help`, without dotted
  or dashed underline/border decoration. Never add standalone `?` cues; genuine unknown-data question marks remain.
  Header buttons have intrinsic text width, zero padding and no hover background;
  only hovering their text changes its color. Never stretch help across a header.
- `ContextHelp.value(visibleText, textOrFunction)` makes the exact intrinsic label/value
  a focusable passive target with immediate help cursor. Preserve text selection/copy;
  selecting text must not pin help. No full-card, progress-track or padding target.
- `ContextHelp.attach(action, textOrFunction)` augments actions such as sorting
  and checkboxes without replacing click behavior or their pointer cursor. Activation
  immediately dismisses help instead of pinning it. Do not add a separate cue.
- `ContextHelp.heading(action, text)` returns a text-sized inline label for a
  sortable header. Keep click, keyboard focus and ARIA descriptions on the original
  action; bind pointer entry/exit, movement fallback and panel positioning to the
  label. Update that returned label, not the action's entire content. Empty action
  space still sorts but neither opens help nor highlights the header/label.
  Mini's Session and Total CCost are separate intrinsic buttons in the existing
  edge-anchored grid; its empty middle track is not a help target.
- Functions read current display tokens. `ContextHelp.refresh(container)` updates
  open help without reopening it; `ReportView.syncUnits` refreshes once after text
  updates. Never price or total data inside a help function.
- `ContextHelp.dismiss(container)` cancels pending/open help within a disabled or
  saving subtree without moving focus or dismissing unrelated targets. Settings
  uses this before locking controls; native option previews stay inside their picker,
  never a competing tooltip layered over the list.
- One manual Popover per document holds noninteractive `role="tooltip"` text with
  preserved line breaks. The active trigger references it via `aria-describedby`;
  other description IDs survive. No duplicate native `title`/`aria-description`,
  HTML injection, storage, request or dependency.
- Pointer hover opens after the single shared **600ms** delay; keyboard focus and
  explicit passive taps open promptly. A separate **150ms** exit grace permits pointer transfer into help. Escape closes
  without moving focus and rendering cannot reopen it. Tap/click pins passive help;
  repeat activation or outside tap dismisses. Focus leaves normally. Removed
  triggers close help. Position/size clamp to the viewport; long exact data wraps
  and scrolls instead of clipping outside it. Convert viewport coordinates and bounds
  through effective CSS zoom for top-layer positioning; retain the readable 34rem width cap.
- The controller owns an explicit **hover / focus / pinned** origin. Mouse-owned
  focus never prevents hover exit; deliberate keyboard focus survives unrelated
  pointer movement. Captured document `pointerout` with null related target,
  document/root leave, outside pointer movement and window blur cover missed trigger
  leaves. Pointer re-entry cancels the one bounded exit timer; outside movement cannot
  continually postpone it. No polling or recurring fallback runs while closed.
- Pending opening cancels on exact-target leave/change, document/window exit,
  unrelated focus/action, visibility hide/pagehide and removed-target observation.
  Stable hovering does not restart the timer; re-entry starts fresh. Visibility
  hide/pagehide and removed-trigger observation also clean up open help/timers.
  Escape/actions suppress immediate reopening; content refresh cannot show help.
  Action suppression survives window-focus restoration, but new hover after leave
  or new intentional keyboard focus can show it again. Touch does not open hover help.
- No links/buttons or focus trap inside tooltips. Interactive advanced help uses
  native `details/summary` or a suitable nonmodal disclosure. Critical status stays
  visible outside hover help.

## Whole-application audit inventory

| Surface / entry points | Disposition |
| --- | --- |
| Full Watch: all ten active/historical headings | Shared buttons; explicit I/C/W/O and I+E lines, exactly two Model bullets, concise Effort without N/A tautology, Ictx versus next context |
| Watch: Started/Finished, Model, Calls, CCost cells | Clock text reveals real dates; accessible model star proves causal linked agents even when one model suppresses the popup. Model help requires distinct provider-qualified models. CCost/Calls share main/subagent role/model/effort/tier groups and contributing-session counts, not per-agent sections. Token Mix remains header-only; no preview popups or generic N/A help |
| Watch: session Context/CCost and price warning | Concise shared context/cost help; severity and canonical threshold remain visible |
| Watch: daily summary, account Today, primary/secondary quotas, exact reset | Four scoped daily text targets; Today/Capacity labels and numbers share intrinsic targets, reset clock owns exact date. Numeric inferred Capacity has `(guesstimate)`; verified native and unknown figures do not. Preserve native factual lower block |
| Watch: activity and Earlier Sessions | Native disclosures retain full lists/counts; expanded activity cues explain all-call totals, red outcome subsets, missing evidence and direct skill failures without repeating lists |
| Mini: both tables’ headings | Session and (Total CCost) have different help inside one column; dead space has none. Prompt cost and active-next versus historical-last-valid-next context remain distinct |
| Mini: session title/cost and prompt/history status | Remove every row cue/duplicate value help. Keep full underlying selectable title and row accessible naming, prompt outcome/stop cause and confirmed unavailable/partial notes |
| Mini: Today, freshness, Earlier Sessions, quota bars, return-to-tab | Remove both header cues and all Earlier Sessions help; no table-level replacement or progress-bar popup. Keep useful return action help with immediate activation dismissal. Critical host/auth/source warnings stay visible, not observation logs |
| Mini: subscriptions | Exactly two primary-window facts on the visible text: Capacity, then Next reset. Select canonical unit/provenance and reset tokens; no secondary or CCost prose. Warnings remain visible; Full Watch/Accounts retain richer help |
| Models: checkboxes and multi-sort | Four semantic label-only definitions preserve full sorting click/keyboard/Shift actions and accessible action names; Relative CCost groups ratio, actual global completed sample, token categories, hidden fallback and source thresholds |
| Models: price refresh and promotion notes | No More information/cards. Explicit price action and genuine fetch time precede the table; promotion/availability facts stay visible. Unitless ratios distinguish the Copilot-credit basis from Credits/reference USD and billing/native quotas |
| Sessions/detail, Token Mix, active-hour | Shared sort help; Reading this report and Sample/price coverage are line-separated. Session context/retention and finite-capture guidance remain visible; the retired Reports date form has no help surface |
| Accounts | Observation details stays a keyboard/touch-native disclosure with exact source/native-money/pace/billing facts; no native title explanations existed |
| Settings | Intrinsic label and current-choice help replace visible paragraphs; native customizable option previews share their text with an accessible fallback disclosure. Retain native focus/selection, save feedback and changing default labels |
| Navigation / host status | Visible action labels retained. Host warning becomes one real details disclosure, not CSS-hover plus native tooltip. Observation lines shortened; hidden status has no redundant title |

Audit searched every shipped Web asset for `title`, `aria-description`, tooltip roles,
Popover creation and dynamic hints. Remaining document/route/session titles are data,
not tooltip APIs. No native-title metadata exception is needed: exact metadata uses
the same accessible helper. Visible provider notes and true disclosures intentionally
retain source-specific facts.

Regression owners: deterministic `integration/web_help.cjs` covers split action/label targets, origin, missed
leave/document exit, repeated movement, suppression, blur/visibility/teardown and
document isolation. Hidden `probe_web_help.cjs` / `probe_help_lifecycle.cjs` use
actual Chromium Document PiP plus main Watch with real CDP pointer/key/touch input.
`probe_help_headers.cjs` adds computed decoration/cursor/background checks and
text-to-padding hit tests in both tables, themes and narrow/zoomed layouts, plus
sortable Models/Sessions labels. Compact panels can cover their source header;
pointer hit tests use exposed padding, not coordinates underneath the popover.
Mini probes retain selection, sticky headers, narrow/zoom/theme/unit/disclosure
coverage. Headless evidence does not prove physical OS pointer/window transitions.

## Server-owned detail boundary

Analysis retains canonical linked-session evidence (including links without requests) in
the revisioned analysis cache. `reports/prompt_costs.py` groups canonically attributed
requests by session/model/effort/tier and values categories at each request's actual catalog
tier. Unknown counters never become fabricated zero. `application/prompt_costs.py`
combines those unrounded parts by producer role/provider/model/effort/tier before
exporting at most 24 groups, honest omitted cost/calls, full distinct-model count and
preformatted Credits/USD text. Missing request evidence cannot claim a full Calls sum;
the browser never prices, allocates aggregate cost or reacquires source data on hover.
`test_prompt_cost_detail.py` owns causal scopes, same-model links, model-only switches,
concurrent/nested work, partial telemetry/pricing, tiers, corrections and bounded detail.
`probe_help_values.cjs` adds real delayed value/PiP flows and both-table cost/unit checks.
`probe_cost_groups.cjs` checks grouped backend wire data, conditional accessible model
stars, Calls/header-only Mix, 241 virtual seconds of stable Full/Mini totals and Loading.
Full Watch footer keeps Context/warning first and Total CCost second with unchanged math.
