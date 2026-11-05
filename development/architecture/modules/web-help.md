# Web contextual help: writing and interaction

Owner: `src/web/assets/help.js`; shared styles: `app.css`. Applies to the main
application and separate Mini Watch document. FR 000582 audit: 2026-11-05.

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
  explicit `?` button beside selectable values, titles and previews. Do not turn
  selectable data into help-only buttons or override its selection cursor.
- `ContextHelp.attach(action, textOrFunction)` augments actions such as sorting
  and checkboxes without replacing click behavior or their pointer cursor. Prefer
  a separate cue when the explanation should be independently tappable.
- Functions read current display tokens. `ContextHelp.refresh(container)` updates
  open help without reopening it; `ReportView.syncUnits` refreshes once after text
  updates. Never price or total data inside a help function.
- One manual Popover per document holds noninteractive `role="tooltip"` text with
  preserved line breaks. The active trigger references it via `aria-describedby`;
  other description IDs survive. No duplicate native `title`/`aria-description`,
  HTML injection, storage, request or dependency.
- Hover/focus opens; delayed exit permits pointer transfer into help. Escape closes
  without moving focus and rendering cannot reopen it. Tap/click pins passive help;
  repeat activation or outside tap dismisses. Focus leaves normally. Removed
  triggers close help. Position/size clamp to the viewport; long exact data wraps
  and scrolls instead of clipping outside it.
- No links/buttons or focus trap inside tooltips. Interactive advanced help uses
  native `details/summary` or a suitable nonmodal disclosure. Critical status stays
  visible outside hover help.

## Whole-application audit inventory

| Surface / entry points | Disposition |
| --- | --- |
| Full Watch: all ten active/historical headings | Rewritten shared buttons; explicit I/C/W/O and I+E lines, model/subagent caveat, Ictx versus next context |
| Watch: exact Started/Finished dates, full preview, extra-model flag | Verbatim metadata/short explanation on adjacent buttons; values remain selectable |
| Watch: session Context/CCost and price warning | Concise shared context/cost help; severity and canonical threshold remain visible |
| Watch: Today count, account Today, primary/secondary period CCost, exact reset | Shared cues; scope, native independence, partial/estimated attribution and reset retained |
| Watch: activity and Earlier Prompts | Native disclosures retain full lists/counts; expanded activity cues explain all-call totals, red outcome subsets, missing evidence and direct skill failures without repeating lists |
| Mini: both tables’ headings | Shared buttons; session/prompt and historical-next context explicit, no I-beam help targets |
| Mini: session title/cost and prompt/history status | Verbatim title on explicit cue, short status/observation lines; row ARIA no longer repeats the entire tooltip |
| Mini: Today, freshness, Earlier Sessions, quota bars, return-to-tab | Shared help; relevant retained/partial/estimated notes, native quota versus period CCost, visible critical notices |
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
