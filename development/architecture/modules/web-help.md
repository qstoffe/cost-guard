# Web contextual help: writing and interaction

Source revision: e4d715e170917f5ef2d69d31a68dbc3eb297ff8a
Checked revision: e4d715e170917f5ef2d69d31a68dbc3eb297ff8a
Last checked: 2026-11-08
Status: current

Owner: `src/web/assets/help.js`; shared styles: `app.css`. Applies to the main
application and separate Mini Watch document. FR000612 checks only the optional
passive heading API and AI Stats usage; other audit rows retain their prior scope
at `50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3`.

## Writing patterns

- Answer “What am I looking at?” first, in plain English. A simple field needs one
  sentence, not a standard-size card. Do not lead with internal implementation names.
- Separate independent facts with concise `•` bullets or `\n`. Use blank lines to group metric components;
  let CSS wrap naturally, never insert arbitrary hard-wrapped lines.
- Example: `Estimated prompt cost, not your bill.\nI — First request’s incoming
  context cost.\nE — Output, later requests and linked subagents.`
- Say **N/A = unavailable, not zero** and **? = partial pricing/data** where they
  affect interpretation. Keep intrinsic estimates and unsupported work honest. Once
  useful content exists, ordinary retained refresh is silent, including hidden help
  and live regions; preserve provenance internally, not as a replacement caveat.
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
- `ContextHelp.heading(action, text, passive=false)` returns a text-sized inline label for a
  sortable header. Keep click, keyboard focus and ARIA descriptions on the original
  action; bind pointer entry/exit, movement fallback and panel positioning to the
  label. Update that returned label, not the action's entire content. Empty action
  space still sorts but neither opens help nor highlights the header/label.
  AI Stats month/all selectors opt into `passive=true` so a tap can explain their
  scope while retaining normal selection. Default sorting/action dismissal is unchanged.
  Selector labels inherit their button's foreground, including on hover; selected
  foreground/background do not cross-fade through unreadable intermediate colors.
  Mini's Session and CCost (Total) are separate column headings. Each cost heading
  explains prompt cost followed by the entire session's cost in parentheses.
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

FR000628 scoped delta (v80.208): actual reference-CCost N/A text is a shared help
target, not a blanket rule for noncost N/A. Watch merges reasons into rich details;
Mini retains stable independent prompt/session spans and compact prompt details.
FR000634 removes even N/A help from the global daily summary in Full and Mini;
other cost scopes retain dynamic help, whose empty content closes an open panel
without moving focus or reopening it. Sessions initial pending acquisition remains Loading.
Token Mix uses neutral fallback when its aggregate lacks per-request causal proof.
`domain/reference_cost.py` owns bounded typed facts; pricing diagnoses only existing
failed valuations, application freezes allowlisted copy and browser never acquires
or prices on hover. A separate diagnostic signature invalidates explanation caches
without changing the rate signature. See [classification and evidence](../../journal/web/ccost-unavailable.md).

| Surface / entry points | Disposition |
| --- | --- |
| Full Watch: all ten active/historical headings | Shared buttons; explicit I/C/W/O and I+E lines, exactly two Model bullets, concise Effort without N/A tautology, Ictx versus next context |
| Watch: Started/Finished, Model, Calls, CCost cells | Clock text reveals real dates; accessible model star and help expose causal linked agents even for one shared model. Main-only model switches retain help without a star. Model/CCost omit tier prose without changing tier grouping/rates; Calls copy is unchanged. CCost adds distinct canonical child-prompt count before each subagent group's category bullets, separate from sessions/requests; missing boundaries stay qualified. Token Mix remains header-only; no preview popups or generic N/A help |
| Watch: session Context/CCost and price warning | Concise shared context/cost help; severity and canonical threshold remain visible |
| Watch: daily summary, account Today, primary/secondary quotas, exact reset | Global Today label, amount and prompt count are plain semantic text with no help targets, title, source aria or completeness disclaimer. Account-specific Today and quota help remain. Period Capacity and nonmonthly 30-day equivalent share one intrinsic explanation. Inferred period Capacity and every numeric monthly extrapolation use `(guesstimate)`; native and unknown figures do not. Preserve native factual lower block |
| Watch: activity and Earlier Sessions | Native disclosures retain full lists/counts; expanded activity cues explain all-call totals, red outcome subsets, missing evidence and direct skill failures without repeating lists |
| Mini: both tables’ headings | Session names only; CCost (Total) explains prompt versus whole-session reference cost, not billing. Active-next versus historical-last-valid-next context remains distinct |
| Mini: session title/cost and prompt/history status | Both tables' Session text reveals the full title and represented canonical Prompt # (unknown stays unavailable). Both paired-cost values use the same compact prompt model/effort/duration/known-calls renderer, with linked/mixed/pricing/outcome facts. Running uses its focal; history its actual representative. No row-wide popup, native title, cue, detailed I/C/W/O breakdown, passive source-refresh flags or raw prompt text |
| Mini: Today, freshness, Earlier Sessions, quota bars, return-to-tab | No global Today or Earlier Sessions help, table-level replacement or progress-bar popup. Loaded rows and certified empty history refresh silently, with no timed refresh warning. Keep useful return action help with immediate activation dismissal. Critical host/auth/source failures stay actionable, not observation logs |
| Mini: subscriptions | Primary-window Capacity, then Next reset; applicable raw Capacity/current Remaining estimate help follows. Select canonical unit/provenance and reset tokens; no secondary or unrelated CCost prose. Warnings remain visible; Full Watch/Accounts retain richer help |
| Models: checkboxes and multi-sort | Four semantic label-only definitions preserve full sorting click/keyboard/Shift actions and accessible action names; Relative CCost groups ratio, actual global completed sample, token categories, hidden fallback and source thresholds |
| Models: price refresh and promotion help | Explicit price action and genuine fetch time precede the table. One highlighted postfix star follows the complete relative tier chain; the row's structured offer supplies multiline Price Promotion/model/discount/end/resume help. No numbered footer, native duplicate title or routine catalog/source caveat. Unitless ratios distinguish the Copilot-credit basis from Credits/reference USD and billing/native quotas |
| Sessions/detail, Token Mix, active-hour | Shared sort and intrinsic metric help remain. No retained-source/as-of/refresh caveat or finite progress footer on the loaded Sessions catalog. The retired Reports date form has no help surface |
| Accounts | Shared Watch subscription help retains exact native-money/pace/billing facts and genuine provider restrictions/auth failures; usable retained quotas have no passive source aria or timed refresh captions |
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

FR000641 scoped delta: ratio Capacity/Remaining, theoretical Monthly Capacity and
estimated Web pace expose their unrounded Decimal calculation in intrinsic value help.
Mini appends only its primary Capacity/current Remaining estimate to the existing
Capacity/reset facts. Provider-confirmed figures do not get a before-rounding claim.
Server-prepared help follows live identity, mode and unit; `quota-estimates.md` in the
Web journal records the precise rounding rule, exception and verification limits.

Analysis retains canonical linked-session evidence (including links without requests) in
the revisioned analysis cache. Shared `prompt_index.prompt_windows` resolves own-session
visible/synthetic boundaries; `TraceEntry.logical_prompt_id` survives cache round trips.
Ambiguous/missing parent boundaries remain unknown, never request-time inference.
`reports/prompt_costs.py` retains private source/session/prompt identity sets and groups canonically attributed
requests by session/model/effort/tier and values categories at each request's actual catalog
tier. Unknown counters never become fabricated zero. `application/prompt_costs.py`
combines those unrounded parts by producer role/provider/model/effort/tier before
exporting at most 24 groups, honest omitted cost/calls, full distinct-model count and
preformatted Credits/USD text, distinct prompt counts and boundary completeness only;
raw child identities/text never reach these groups. Missing request evidence cannot claim a full Calls sum;
the browser never prices, allocates aggregate cost or reacquires source data on hover.
`test_prompt_cost_detail.py` owns causal scopes, same-model links, model-only switches,
concurrent/nested work, partial telemetry/pricing, tiers, corrections and bounded detail.
`probe_help_values.cjs` adds real delayed value/PiP flows and both-table cost/unit checks.
`probe_cost_groups.cjs` checks grouped backend wire data, conditional accessible model
stars, Calls/header-only Mix, 241 virtual seconds of stable Full/Mini totals and Loading.
Full Watch footer keeps Context/warning first and Total CCost second with unchanged math.
