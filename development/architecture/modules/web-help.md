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

FR000695 (v81.39): `control-focus.js`, not the tooltip controller, owns per-document
input modality for buttons, links, checkbox/radio filters and intrinsic help targets.
Pointer ownership gates only the extra focus outline; native focus, keyboard cues,
Popover dismissal, pinned help and true selected states are separate. Mini explicitly
installs the same controller on its own document. The source-shaped same-element
Tab → pointer reproduction and native PiP/route matrix are in
[Models isolation evidence](../../journal/web/models-isolation.md).

FR000694 (v81.38): `application/effort_help.py` alone formats semantic selected/effective
facts as `default (level)`. Only `value_cell=True` adds the marker and one source-sensitive
line; ordinary Model/CCost/Calls/Mini/Comparisons Model/Stats podium never reuse that
copy. Watch's Effort span is retained by `metricValue`; Session detail uses its existing
protected-row lifecycle. Comparisons separates value-cell context from ordinary
contributor provenance. Evidence is bounded to 24 distinct facts per group with an
honest overflow marker, never a silently chosen conflicting default. Visible values,
generic headers, benchmark filters and native selections stay unchanged.
`test_default_effort_help.py`, `probe_web_help.cjs --effort-defaults` /
`probe_default_effort.cjs` and `probe_effort_live.py` own regression/acceptance evidence.
`probe_web_live.py --effort-tooltips` separately observes recorded selections through
active Watch or one already-discovered pinned session detail, without certifying
Earlier history. Its exclusions and unobserved results are not tooltip PASS.

FR000653 scoped update (v81.2): Mini Ctx help has separate Next and Δ paragraphs,
then independent threshold/price guidance. `analysis/context.py` retains a complete
prompt-local pair independently of current history membership, with epoch/model/input
guards; `reports/prompts.py` retains richer comparable adjacent anchors. Live exports
the canonical short unavailable/provisional explanation, never browser subtraction.
Historical visible Next remains session-scoped and its delta prompt-scoped, explicitly
not necessarily the same timestamp. Running source revisions refresh existing help
and focus; exact zero is 0, unsupported comparisons N/A. No new acquisition or layout.

- Answer “What am I looking at?” first, in plain English. A simple field needs one
  sentence, not a standard-size card. Do not lead with internal implementation names.
- One concept gets one compact, natural sentence. Two or more distinct concepts
  get separate short paragraphs separated by one blank line (`\n\n`). Let CSS
  wrap naturally, never insert arbitrary hard line wraps or a long formula dump.
- Example: `Reference-price ratio to the cheapest comparable model (1.0x).\n\nUses
  the same recent token mix for every model and price tier; not task performance.`
- Apply this to all new/edited help, not a bulk rewrite of unrelated tooltips.
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
  Mini has separate Session, CCost and Total headings. CCost explains the represented
  prompt; Total explains the entire session including attributed linked subagents.
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
  HTML injection, storage, request or dependency. The sole structured exception is
  `ContextHelp.runningDuration(before, duration, after)`: privately branded text parts,
  rendered as TextNode / fixed running-color span / TextNode, never interpreted HTML.
  Live fragment updates retain text/selection identity; non-running help returns to plain text.
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
- FR000683 (v81.31): one controller-owned self-scheduling timeout revalidates an
  **open hover** about every **1000ms** against its exact connected `pointerTarget`
  or panel's current `:hover`, document visibility and window lifetime. Negative
  hover evidence uses the existing 150ms transfer grace. Pending 600ms openings
  also revalidate target/hover; timer tickets reject obsolete callbacks. Unsupported
  hover queries are inconclusive, never perpetual permission to remain open.
  A monotonic **30-second pointer-idle lease** bounds even falsely retained CSS hover.
  Only trusted pointer entry/movement/down inside the label/panel renews it; no
  stored coordinates, focus, selector poll, `refresh` or Live redraw can do so.
  With no OS-wide cursor API, truly stationary reading may expire too: intentional
  re-entry can reopen, and deliberate keyboard/pinned help has no hover lease.
  Close/Escape/actions, owner changes, replacement, hidden/pagehide and PiP teardown
  cancel exactly the owned watchdog; closed/focus/pinned states do no recurring work.
  [Evidence and physical-OS limitation](../../journal/web/contextual-help.md#fr-000683-bounded-hover-watchdog-2026-11-12).
- No links/buttons or focus trap inside tooltips. Interactive advanced help uses
  native `details/summary` or a suitable nonmodal disclosure. Critical status stays
  visible outside hover help.

## Whole-application audit inventory

FR000665 scoped delta (v81.15): Mini Total is an intentional no-help value, including
N/A and Loading. Only its heading explains the whole-session scope, in one sentence.
CCost retains compact prompt details and the running Duration cue; Session combines
the full title and direct prompt number/25-grapheme preview. The existing server's
prefix-free `account_ccost` token supplies Mini Total after the no-priced-work guard;
global formatting, raw values and completeness stay unchanged.
[Verification and limits](../../journal/web/mini-watch.md#quiet-total-and-direct-session-help-fr000665).

FR000628 scoped delta (v80.208): actual reference-CCost N/A text is a shared help
target, not a blanket rule for noncost N/A. Watch merges reasons into rich details;
Mini retains stable independent prompt/session spans, with details on CCost only.
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
| Full Watch: all ten active/historical headings | Shared buttons; explicit I/C/W/O, concise CCost directs to value details, exactly two Model bullets, concise Effort without N/A tautology, Ictx versus next context |
| Watch: Started/Finished, Model, Calls, CCost cells | Clock text reveals real dates; accessible model star and help expose causal linked agents even for one shared model. Main-only model switches retain help without a star. Model/CCost omit tier prose without changing tier grouping/rates; Calls copy is unchanged. CCost shows only the total; value help starts with independent I/E amounts, then retains all grouped category/child-prompt counts, qualified missing evidence and one total. Unknown I/E never becomes zero from total rounding. Token Mix remains header-only; no preview popups or generic noncost N/A help |
| Watch: session Context/CCost and price warning | Concise shared context/cost help; severity and canonical threshold remain visible |
| Watch: daily summary, account Today, primary/secondary quotas, exact reset | Global Today label, amount and prompt count remain plain semantic text. Account Today and native quota-summary help remain. Unknown Capacity/Monthly Capacity rows and their help targets are absent. Known values have distinct concise explanations plus native facts, without raw arithmetic/rounding. Ratio period Capacity and every numerical monthly equivalent use leading `~`; native amounts do not. Display-only first-letter normalization also applies to help/ARIA |
| Watch: activity and Earlier Sessions | Native disclosures retain full lists/counts; expanded activity cues explain all-call totals, red outcome subsets, missing evidence and direct skill failures without repeating lists |
| Mini: table headings | Activity / Session / CCost / Total / Ctx; CCost keeps its prompt/pricing definition. Total says exactly: The entire session’s reference cost, including attributed linked subagents. Active-next versus historical-last-valid-next context remains distinct |
| Mini: session title/cost and prompt/history status | Session help reveals the full title and direct `Prompt #N: excerpt` line (unknown number stays unavailable), using the existing bounded 25-grapheme preview. CCost alone retains prompt model/effort/duration/calls and linked/mixed/pricing/outcome help, including the yellow running Duration fragment and open-help updates. Total stays plain selectable text without help, tabindex, native title or prompt details. History uses its actual representative. No row-wide popup, unsafe HTML, detailed I/C/W/O or raw prompt retrieval |
| Mini: Today, freshness, Earlier Sessions, quota bars, return-to-tab | No global Today or Earlier Sessions help, table-level replacement or progress-bar popup. Loaded rows and certified empty history refresh silently, with no timed refresh warning. Keep useful return action help with immediate activation dismissal. Critical host/auth/source failures stay actionable, not observation logs |
| Mini: subscriptions | Primary-window Capacity, then Next reset; applicable raw Capacity/current Remaining estimate help follows. Select canonical unit/provenance and reset tokens; no secondary or unrelated CCost prose. Warnings remain visible; Full Watch/Accounts retain richer help |
| Models: reference checkboxes and multi-sort | Four semantic label-only definitions preserve click/keyboard/Shift actions and accessible sort names. Relative Price List Cost has two compact paragraphs: reference ratio, then shared recent token mix rather than task performance. Internal `relative_cost`, tiers and sample semantics are unchanged |
| Models: independent coding benchmark | Five sortable intrinsic header targets; Model value help identifies that configuration's actual Coding Client/version/source row; Relative Task Cost value help gives Harbor USD per attempted task including failures. Dynamic native Effort multiselect has keyboard/touch/outside/Escape dismissal. Missing versions/efforts are not inferred; no promotions or benchmark-driven New clock |
| Models: price refresh and promotion help | Explicit price action and genuine fetch time precede the table. One highlighted postfix star follows the complete relative tier chain; the row's structured offer supplies multiline Price Promotion/model/discount/end/resume help. No numbered footer, native duplicate title or routine catalog/source caveat. Unitless ratios distinguish the Copilot-credit basis from Credits/reference USD and billing/native quotas |
| Sessions/detail, Token Mix, active-hour | Shared sort and intrinsic metric help remain. Compact Export Sanitized JSON owns action-style native sanitization/review/snapshot/save help; activation and programmatic picker-focus restoration leave it dismissed. No separate export helper/idle caption; operational status remains. No retained-source/as-of/refresh caveat or finite progress footer on the loaded Sessions catalog. The retired Reports date form has no help surface |
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

FR000641's raw calculation help remains for ratio Remaining, estimated Web pace and
Mini's primary Capacity/current Remaining detail. FR000654 intentionally replaces only
shared-card Capacity/Monthly Capacity help with one explanatory sentence and native facts;
canonical unrounded Decimal calculations and estimate precision are unchanged.
Provider-confirmed figures do not get a before-rounding claim.
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
