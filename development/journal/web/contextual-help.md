# Shared Web and Mini contextual help

## FR 000683: bounded hover watchdog (2026-11-12)

Base `c33e761`, product v81.31. The shared `help.js` controller now owns one
self-scheduling timeout only while a visible panel has hover ownership. Each
1000ms check revalidates the exact connected label or panel's browser `:hover`,
document visibility, window lifetime and target identity. Negative evidence uses
the existing 150ms transfer allowance. Opening revalidates after 600ms; obsolete
opening/watchdog tickets cannot affect a replacement or re-entered target.

A monotonic 30-second pointer-idle lease supplies the independent finite bound:
polling, stale CSS, focus, synthetic movement and Live refresh cannot extend it.
Only trusted pointer interaction on the label/panel renews the lease. This is a
deliberate compromise, not OS cursor detection: a browser can retain stale hover
and has no general external-window mouse-position API, so truly stationary
mouse-only reading may also expire after thirty seconds. Intentional re-entry
can reopen; keyboard focus and deliberate passive click/touch pins have no hover
lease. Close, Escape, actions, owner/target changes and document/PiP lifecycle
cancel the owned timer. No host/request work, new dependency or Mini cadence.

Verified safety scope:

- Deterministic virtual clock/hover tests pass with every exit/move/blur event
  absent, including ARIA restoration, hidden Popover, one watchdog and zero timers
  after close. Stale-true and inconclusive selectors both expire at thirty seconds;
  genuine pointer input keeps reading alive, and panel transfer retains its grace.
  Live refresh/synthetic input/focus cannot renew hover. Focus/pin survive sixty
  virtual seconds with no watchdog. Opening races, old callbacks, exact labels,
  removed labels, hidden/closed windows, teardown and separate/reopened documents
  are covered in the registered `test_web_help.py` owner.
- Owned hidden **Edge 157.0.4341.46** and **Chrome 157.0.8103.51** pass
  `probe_web_help.cjs --hover-watchdog` through shipped HTTP/CSP/SSE and actual
  Document PiP. Window-capture interception suppresses native trusted pointer exit,
  leave, outside movement and blur before any controller handler. Silent exits
  during the delay produce no popup; open Mini return/header/quota and Full Watch
  help close in about **1.15–1.20 seconds**, with ARIA/Popover cleanup and no Live
  resurrection. Neither hover selector nor production timer is mocked there.
- Each browser also passes 24 label/padding/theme/zoom cases (Classic/Web light/
  dark, wide/narrow, 100/150%), transfer/re-entry, lingering mouse focus, real
  mouse/touch/Enter/Space action dismissal, deliberate keyboard help and passive
  touch pin/outside dismissal. No browser runtime errors. A development iteration
  exposed keyboard ownership loss during pointer-presence updates; renewal no
  longer changes input modality, and incidental entry after keyboard focus has a
  deterministic regression. Final browser runs pass without weakening assertions.

Final gates and scope-limited delivery decision:

- Local Full: **185 isolated groups, zero failures, 150.9s**, four workers.
  Working-tree validation: **11 passes, zero failures, seven advisory warnings**;
  no budget/baseline changed. Those passes do not supersede the separate failed
  integration probes below.
- The broader Edge Mini invocation is **FAILED**, with 122 layout observations
  and nine completed check groups before its Duration/Total-heading hover abort.
  Already-confirmed scope includes theme/activity/width/density, configured time,
  current Mini help and source-shaped context flows. `manual-only` independently
  **PASSES** 25 layouts, both sizing modes, real pointer/Enter/Space/touch Fit,
  immediate help dismissal, narrow panning, remembered reopen and one SSE.
  Remaining duration cases after the first abort and the intervening
  history-readiness subprobe are **NOT RUN**, not a full Mini PASS.
- Focused `help-only` reproduces a mixed touch/keyboard → Total-heading mouse
  opening failure in both named browsers. Trusted pointer AND mouse events arrive,
  yet native hover is false at 600ms, so the opening guard cancels. Geometry/hit
  test, synchronous PiP/opener native reads, quiet no-CDP observation, explicit
  touch setup, fixed two-point motion and pre-entry compositor capture do not
  resolve it. A bounded trace finds hover becomes true only after a natural Mini
  render's next frame; that is correlation, not an established cause. Temporary
  instrumentation was removed, original failing assertion retained; intentional
  keyboard cases now actually send Tab. The [non-executable Suggestion 000684](../../backlog/suggestions/000684-mini-help-mixed-input-hover-opening/SUGGESTION.md)
  preserves the reproduced gap, attempts, uncertainty and future acceptance.
- **Decision Delegate authorizes partial acceptance**, excluding reliable hover
  opening for that precisely reproduced mixed-input path. The independent finite
  orphan fix and tested keyboard/touch alternatives remain useful; no accounting,
  security, source-integrity or data-loss consequence or blocked Ready dependency
  was identified. Whole-FR On Hold would unnecessarily withhold the verified safety
  correction. This is the Delegate's decision, **not owner approval**, not a claim
  of full acceptance and not permission to execute the Suggestion.
- Real-installation `probe_web_live.py --watch-cards`: **FAILED** with
  `probe_watch_cards_timeout` at 90s; history was loading, **872/3149** checked.
  Source V2, one Live owner, advancing publications/346 HTTP Live reads and an
  independently published daily result were observed. Full history certification
  is **UNVERIFIED**. Final elapsed 91.5798s, pending work empty, zero owned
  processes and `cleanup_failures: []`, but two native quota-provider waiters
  remained in the final thread snapshot.
- Distinct basic `probe_web_live.py`: verified V2, one owner, two streams,
  advancing verified stream IDs and stable origin in 1.1708s, but **FAILED** with
  `probe_owned_workers_remaining` (two provider HTTP/usage waiters). No owned
  processes/pending work/cleanup failures. Cancellation surfaced one history-batch/
  advance error in that short teardown. These positive source observations are
  **not full-probe PASS**; natural retirement of the two waiters is **UNVERIFIED**,
  not a proven persistent leak. The Python probe does not execute changed help JS;
  provider calls can outlive their bounded close join.
- **Decision Delegate minor verification exception:** full history certification
  and zero-worker teardown proof are excluded for this browser-only FR. No source/
  provider repair or separate proposal is authorized/needed for that caveat. Exact
  outcome codes/counts above remain visible; no acquisition failure was hidden.

**UNVERIFIED:** physical Windows PiP → browser chrome → another app pointer travel
and native OS blur delivery. Headless target switches emit no native blur; the
existing explicit blur injection proves its handler only. The original intermittent
incident and its exact OS trigger are not claimed reproduced. This FR explicitly
permits that physical evidence gap; no user/delegate exception is used. No visible
desktop action, inference, shared OpenCode stop, ZIP, tag or GitHub Release.

Earlier grouping/capacity follow-up: **FR 000620 / v80.200**, recorded below. The FR 000582
inventory and evidence here are historical; removed preview/row/freshness cues are
not current UI recommendations. Current writing/placement policy lives in the module contract.

## FR 000620: logical prompts and shared capacity comparison (2026-11-07)

Base `928f227`. Shared canonical `prompt_windows` now resolves each physical request's
own-session parent to a real logical prompt, including supported synthetic continuations.
Missing/ambiguous boundaries remain unknown; no call/agent/time heuristic substitutes
for a child prompt. The revisioned analysis cache retains the identity. Report parts
deduplicate private source/session/prompt sets per model/effort/tier, and the bounded
Web group exports only count/completeness. Subagent cost sections begin with that count
or a qualified lower bound/N/A; main sections do not gain the bullet. Same-model linked
work opens Model help, with unreported fields honest. Only Model/CCost tier prose is
removed; tier valuation/grouping, Calls help, numeric I/E and CLI totals remain intact.

One Python Decimal calculator supplies factual period Capacity and a separate
standardized 30-day comparison. Numeric extrapolations are always guesstimates;
unprovable recurrence/duration/reference basis, stale/expired/inactive/contradictory or
incomplete evidence yields N/A with a reason. An optional explicit source-verified
reference limit supports a genuinely compatible fixed weekly capacity without
guessing conversion from money, requests, tokens or similarly named credits. No adapter
fabricates that evidence. Monthly native windows keep one original Capacity line.

The existing AccountCards component is the full-size contract on both Watch/Accounts,
not two similar renderers. Responsive same-row peers reserve an empty aria-hidden,
unfocusable monthly spacer only beside an actual extra primary Capacity line. A grid
ResizeObserver and membership/period updates recalculate this without destroying
unchanged progress/help nodes. Each real secondary quota has its own monthly line;
no fake secondary rows. Mini's compact two-fact quota help and layout remain unchanged.
Full Watch Today retains cost/count, completeness and source indicators without daily
Token Mix categories; canonical mix data and other surfaces retain their original data.

Evidence and limits:

- Final local Full: 155 isolated files, zero failures/errors, 105.3s, including the
  added independent daily-export preservation case. One existing zsh/PTY test is
  skipped on Windows; native macOS CI owns that execution.
- Working-tree validator: 11 passes, zero failures, six existing advisory prose/design
  warnings; no cap/baseline was increased.
- Hidden Edge `156.0.4314.58`: shared-route parity and conditional primary alignment
  passed 96 width/zoom/theme/scenario combinations (360/800/1280/1920, 100/125%,
  Classic/Web light/dark, mixed 3+, single/all-monthly and period changes). Ordered
  text, primary/secondary help/lines, ARIA and no horizontal overflow were checked.
  Account identity/focus/selection, one SSE, no route jobs and stale/empty/recovery
  passed in the final complete Accounts driver together with actual Document PiP
  quota compatibility, Used/Remaining/USD, idle/ratio updates and terminal host SSE.
  The final v80.200 light/1200 screenshot was inspected.
- Watch-only shared-help audit passed in hidden Edge with actual Document PiP:
  same-model linked effort help, prompt-count-first category bullets, both tables,
  retained hover/keyboard/touch/Escape behavior, bounded long groups and 241 virtual
  seconds of stable totals. This is not an unrelated report-route audit.
- Existing probe assumptions were repaired, not waived: current separate Mini
  headings/paired-cost targets and compact two-fact quota help replace retired
  selectors/copy. Alignment measurements now wait two animation frames after viewport
  changes. The expanded Accounts driver explicitly restores its Remaining/USD
  prerequisites after the compact subprobe restores defaults; all assertions remain.
- Read-only real V2 installation: three accounts, one Live/account-refresh owner,
  advancing publication, ten initiating daily prompts / 402 requests, complete pricing
  and reconciled category costs; 14.7421s total, no final owned threads/processes or
  cleanup failures. The probe initiated no model calls and left shared OpenCode running.
- Integrated browser was disconnected; the Decision Delegate authorized bounded
  normal-guarded hidden Edge discovery/execution, not a permission grant or test waiver.
  The normal invocation ran without an approval prompt. No visible desktop/login or
  personal browser profile was used. Browser synthetic groups prove child cases;
  the live observation is not proof of every provider, child boundary or quota duration.
- Headless input/layout is not physical OS, assistive-technology, macOS or other-engine
  proof. No requirement/test exception, ZIP, tag or GitHub Release is introduced.
  Compact durable evidence: `development/architecture/governance/verification/web-capacity-620.json`.

## FR 000601: grouped request detail and stable totals (2026-11-06)

Base `7d80b4d`; consumes the already-delivered canonical V2 subagent attribution.
`reports/prompt_costs.py` retains unrounded individual valuations by original
session/model/effort/actual price tier; `application/prompt_costs.py` sums those parts
by main/subagent role and provider/model/effort/tier before exporting 24 groups.
Contributing-session counts deduplicate nested sessions, independent roles never merge,
and same-name provider identities are visibly qualified when ambiguous. Missing category
telemetry remains N/A, unpriced costs remain unavailable/partial, and omitted groups
retain exact group count/known subtotal/calls. No residual allocation, repeated per-agent
totals, browser pricing, hover acquisition or per-cell Token Mix popup is added.

The model popup requires two actual provider-qualified model identities; unknown
identity is not a second model. Same-model child participation keeps its accessible star.
Calls shares cost grouping and reports a reconciled total only with complete request
evidence. Value-help spans now survive advancing row publications, updating their source
content without duplicating keyboard handlers or tearing down an open hovered tooltip.
600ms hover, focus/touch, Escape, unit formatting and shared viewport clamping remain.

Session freshness/scheduling ownership and cache limits are described in
[the session summary findings](watch-session-summary.md#fr-000601--stable-evidence-gated-totals-2026-11-06).
No new causal child parser or cost engine is introduced; CLI/billing/account totals and
canonical physical-request arithmetic remain unchanged.

Verification and limits:

- Local Full passed **148 files, zero failures, 92.7s**, four isolated workers.
  Working-tree validation passed all **11 checks**, zero failures, six existing
  advisory prose/design warnings; no cap or baseline was raised.
- Owned headless **Chrome 156.0.8078.80**, shipped HTTP/assets/CSP/SSE and actual
  Document PiP, passed the explicit `probe_web_help.cjs --watch-only` audit.
  Both Full tables aggregate two child sessions and Calls, suppress same-model
  help while retaining the accessible star, and retain an open hovered value
  through ten advancing row publications. Full/Mini known totals stay quiet
  through **241 virtual seconds**, other-prompt updates, disclosure and re-entry;
  unknown totals show Loading in both. Thirty backend groups export 24 plus six
  explicitly omitted groups (known omitted cost 150, total 750). All eight
  active/history × 1280/360 × 100%/150% zoom long-scroll cases stayed in bounds.
  Classic/Web light/Web dark Watch and Mini screenshots were visually inspected.
- Read-only actual-installation `probe_web_live.py --watch-cards --prompt-cost
  --session-cost` passed on V2: four physical requests matched canonical CLI raw
  cost/category sums and independent session-report valuation. A fresh repository
  replay valued zero requests and wrote no cache. One owner/two streams/three
  accounts, stable run origin and advancing stream IDs were observed; 14.6399s
  elapsed, with no final pending work, owned threads/processes or cleanup failures.
  This prompt had no linked agents; canonical synthetic/nested tests, not this
  observation, establish multi-agent behavior.
- The earlier broader help command failed on the unrelated Sessions route with
  “Live session source unavailable”: the synthetic help host has no live Sessions
  catalog owner. The default broad audit remains intact; the explicit Watch-only
  PASS is not a whole-application report-route or report-process lifecycle PASS.
- Native blur was unavailable in headless Chrome (`native:false`); injected blur
  proves the handler only. No physical desktop, screen-reader, macOS or other
  browser-engine proof is claimed. The owner's original private incident was not
  independently reproduced; its exact original cause remains unproven. No
  requirement/test exception was requested or granted, no paid inference ran,
  and the shared OpenCode service was not stopped. No ZIP/tag/Release was made.

Compact durable evidence:
`development/architecture/governance/verification/web-cost-groups-601.json`.

## FR 000590: direct values, delayed hover and attributed cost detail (2026-11-05)

Base `d947355`; delivery incorporates the later documentation-only main updates.
Standalone help cues are removed, genuine unknown-data question marks preserved.
Intrinsic visible labels/values own passive help; action cursors/selection and native
disclosures remain. Shared opening is 600ms, distinct from 150ms exit grace, with
event-driven pending cancellation and existing focus/pinned/PiP isolation.

Canonical causal links survive analysis caching even without request usage. Immutable
report detail groups original session/provider/model/effort, with each physical request's
actual reference-price tier and known category contributions. The bounded application
projection exports 24 groups, omitted cost/calls and honest missing usage/pricing;
unit-formatted text does no client repricing or aggregate allocation. Per-agent combined
totals supplement multiple model/effort subtotals. I+E and CLI/accounting remain unchanged.
Linked-agent stars, exact clock help, provenance-qualified Capacity and two-row
Context/Total CCost summaries share active/historical behavior. Mini retains one first
column with different Session and Total CCost help.

Actual owned headless **Chrome 156.0.8078.80** checks passed:

- Shared help through shipped HTTP/CSP/SSE and real Document PiP: delayed/flyover/re-entry,
  keyboard/touch/actions, panel transfer, removal/exit/suppression, both Watch tables,
  scoped account/daily text, distinct Mini headings and units. Classic/Web light/dark,
  1280/360 widths and 100%/150% CSS zoom; rich detail wraps/scrolls within bounds.
- The new long-detail zoom check initially caught viewport overflow. Top-layer geometry
  now converts effective CSS zoom for both bounds and coordinates; deterministic and
  real-browser regression checks cover it. Rich-cost screenshots in all three themes
  and the Mini scoped-heading screenshot were visually inspected.
- Full Mini browser suite: actual PiP placement/reopen/restart, theme-role/contrast,
  primary/secondary quotas, verified/inferred/unknown Capacity and immediate units/
  orientation in Watch/Accounts/Mini, session edge alignment, selection/scrolling,
  user disclosure resize, retained/live updates and one SSE.
- Full Watch browser suite: **12 cases**, three themes and 2560/1920/1366/360 widths;
  footer severity/icon/contrast/focus-safe transitions, quotas, units, layout/zoom,
  selection, canonical I+E and 100-card behavior. Old native-title, cue and combined
  heading assumptions in existing browser owners were updated, not assertions weakened.
- Route keyboard-help inventory now intentionally enters keyboard mode and includes
  passive values: Models 6, Sessions 5, detail 8, Accounts 2, Date 8, Token Mix 18;
  active-hour and Settings retain visible/native disclosure guidance.

Read-only real-installation `probe_web_live.py --watch-cards --prompt-cost --daily`
passed: V2, one owner/two streams/three accounts, advancing sequence/stable run origin,
one active/two historical cards. An observed four-call prompt matched raw CLI cost,
I+E and one group's category sum. No linked agents were observed in that real prompt;
deterministic fixtures establish multi-agent/nested/multiple-effort behavior. Daily
1523 requests/75 prompts had complete cost/category reconciliation but incomplete
prompt attribution. One history-batch/advance failure was observed during recovery;
the coherent daily result subsequently published. Total 14.7233s; final pending work,
owned threads/processes and cleanup failures were empty/zero. No inference or shared
OpenCode stop occurred.

Headless focus switches emitted no native window blur (`native:false`); injected blur
tests only prove the handler. No physical desktop, screen-reader, macOS or other-engine
proof is claimed. In-memory report fixtures are UI evidence, not finite-report-process
lifecycle proof. No model inference, shared-service stop, release ZIP, tag or GitHub
Release is used; no verification exception has been requested or granted for this FR.

Final local Full suite passed **144 files, zero failures, 89.4s**, four workers;
the eight new cost-detail tests are explicitly registered in Quick and Full.
Working-tree validator passed all **11 checks**, zero failures, six existing advisory
prose/design warnings; no cap or baseline changed. `git diff --check` was clean.
Compact durable evidence: `development/architecture/governance/verification/web-help-590.json`.

## Historical FR 000582

FR 000582, 2026-11-05, product v80.163. Implementation base: `02c6800`.

## Ownership and content audit

`src/web/assets/help.js` owns one text-only, noninteractive manual Popover per
document. Weakly held triggers supply static text or current-state functions.
`app.css` owns line preservation, viewport wrapping and semantic theme colors.
Watch, Mini and report renderers integrate it without acquiring or calculating
data. The complete surface inventory and future writing/interaction patterns are
in `development/architecture/modules/web-help.md`.

Rewritten help distinguishes prompt/session/day scopes, I+E reference cost from
I/C/W/O tokens, main-model labels from linked-subagent contributions, and native
quota from CCost/billing. Unknown and partial evidence stays explicit. Exact
titles, previews and dates use adjacent cues rather than breaking text selection.
Real disclosures and critical visible warnings stay persistent; there are no
overlapping native-title/custom explanations. The shipped-asset audit found no
remaining explanatory `title` or `aria-description`; document/route/session title
data is not a tooltip API.

## Confirmed browser evidence

`integration/probe_web_help.cjs` passed with owned fresh headless profiles in
Chrome **156.0.8078.80** and Edge **156.0.4314.58**. Both use shipped HTTP/assets,
CSP and SSE plus actual Document PiP, not a separate-window facsimile. Classic,
Web light and Web dark passed focus, hover, Escape/suppression during updates,
pointer transfer, touch pin/outside-dismiss, semantic help cursors and viewport
bounds. Screenshots were inspected: line breaks, compact Mini help and theme
contrast were readable. Full Watch was 1280×900; the default PiP content viewport
was 518×231, with help inside its bounds. Mini 150% text enlargement passed.

The same probe exposed verbatim long/hostile title data without HTML execution,
partial pricing, retained-state notes, full preview/date reveals, and rendered
Models, Sessions, session Snapshot, Accounts, Date reports, Token Mix, active-hour
and Settings. Focusable report-help counts were 6/5/8/0/8/18/0/0 respectively;
zero means the surface uses persistent text/native disclosures instead of custom
help, not that the report was skipped.

The broader Chrome `integration/probe_mini_watch.cjs` passed: actual PiP opening,
placement/reopen/restart, theme-role/contrast parity, Used/Remaining quota mode,
Earlier Sessions and scrolling, intrinsic metric widths, session-total edge
anchoring at 560/800/280 widths, enlarged fonts/CSS zoom, retained-state updates,
hidden-opener SSE, native API replacement and terminal host state.

## Causal repairs and limits

- Existing VM/browser tests assumed native `title`, repeated row ARIA, or direct
  heading text. Tests now exercise the shared helper and retain metric, suffix,
  lifecycle and selection assertions; the normal suite includes `test_web_help`.
- An open Mini prompt-status cue initially refreshed before its data changed.
  Refresh now runs after drawing the complete update; a deterministic regression
  verifies an already-open cue changes without refocusing.
- Browser hit tests now prevent automatic focus scrolling and wait for the old
  Popover to close before testing a visible target below sticky headers. Resize
  assertions wait for the viewport and help geometry to settle.
- The reused finite-report cancellation fixture deliberately sleeps for Token Mix
  and fails Date. Its Models process also remained `running` in this Node-hosted
  audit despite successful direct and isolated-process reproductions. That hang's
  cause is **not established**. No product acquisition/lifecycle fix is claimed.
  `fixtures/web_help_reports.py` instead supplies immediate in-memory jobs over
  canonical synthetic report services for this UI-only audit. The existing
  cancellation owner/default mode is unchanged; this probe is not report-process
  proof.
- An earlier load-overlapped Full run saw an unrelated historical 872-root test
  request four catalogs instead of two/three. Catalog hints use real two-second
  reuse windows at report start and message brackets. A subsequent focused case
  passed unchanged; load/timing causation remains unproven.

Read-only real-installation `integration/probe_web_live.py --watch-cards --detail`
passed: V2 source, one owner/two streams/three accounts, advancing sequence and
stable run origin, retained detail/frozen pages, zero owned threads/processes or
cleanup failures. It never stopped the shared OpenCode service.

No physical desktop, screen-reader, Firefox/Safari, macOS or other-engine proof is
claimed. Structural ARIA and actual Chrome/Edge keyboard/touch behavior are
verified; in-memory synthetic reports are not a replacement for source evidence.
No live inference, dependency, preference default, accounting, source acquisition,
quota arithmetic, CLI, release ZIP, tag or GitHub Release change is included.

## Final local gates

`py -3 development/tools/run_tests.py --suite full` passed **141 files, zero
failures**, four isolated workers, 86.1 seconds, including the unchanged historical
scale cases. No browser probes ran concurrently. The earlier catalog-count
failure was not reproduced or hidden by a weaker assertion.

`py -3 development/tools/validate_package.py --working-tree` passed all **11
checks**, zero failures. Six existing advisory prose/design warnings remain
(Web guide, README, VERSION_HISTORY, context, ReportService, Watch coordinator);
no hard cap or baseline was raised. `git diff --check` was clean.

## FR 000587: quieter help and ownership-aware exit (2026-11-05)

Base `a7b41c1`; product v80.168. Keep actual Mini column headings (including two
separated Session/Total CCost concepts), remove all routine row/header/disclosure
cues, preserve selectable full titles and accessible outcomes. A single subscription
cue groups real primary/additional quota periods, native amounts/limits, resets and
concise server-formatted reference caveats. Confirmed partial/unavailable/stale and
authentication information remains meaningful without observation logs.

Full Watch removes prompt-preview popups in both tables. One far-right daily cue
explains all three daily metrics; duplicate usage/Capacity explanations consolidate
at Capacity. Exact prompt/reset dates, additional-model facts and meaningful account
attribution remain; header copy is shorter, while the useful CCost I+E grouping stays.
The [module inventory](../../architecture/modules/web-help.md) records the wider
kept/removed/consolidated/repositioned decisions, including other report/settings views.

The original controller tied hover lifetime to `activeElement`: mouse-owned focus
could strand help. Before the fix, actual hidden Edge document exit emitted
`pointerout:null`/`pointerleave:null` while the help remained open. The shared owner
now distinguishes hover/keyboard-focus/pinned, covers document/window exit and
outside movement, preserves trigger-to-panel grace, and dismisses actions immediately.
One bounded exit timer cannot be postponed by repeated outside movement; there is
no polling, second framework or new acquisition. Updates do not resurrect help.

Actual **Edge 156.0.4314.58** shipped-HTTP/CSP/SSE + Document PiP results:

- Shared-help probe PASS: Mini return action/heading/quota and full Watch heading/
  daily cue close after real CDP pointer travel beyond the document with lingering
  mouse-owned focus. A document-only exit also covers a deliberately missed trigger
  leave. Keyboard ownership survives pointer exit. Real mouse/touch/Enter/Space
  returns to the existing Watch and immediately closes help without focus/Live reopening.
- Classic/Web light/dark, focus/Escape/touch pin/outside-dismiss, panel transfer,
  150% Mini text, hostile/long title text, both tables and all report/settings routes PASS.
  Daily cue has one direct card parent, no overlap/page overflow, and zero edge gap
  at 1280/360 widths and 100%/150% CSS zoom. The layout check caught and repaired a
  later generic cue margin overriding the original auto-margin rule.
- The complete Mini probe PASS: both tables/long title selection, sticky headers,
  560/800/280 widths, fonts/CSS zoom, theme/unit/quota variants, newest-three history,
  independent scroll regions, user disclosure resize, retained/live updates and one SSE.
- Fresh screenshots of the Mini two-part heading and full Watch/daily placement
  were inspected. These are synthetic content, not physical desktop captures.

**Decision Delegate verification exception, FR 000587 only:** the foreground
delegate explicitly reconsidered acceptance 9 and the actual-browser/PiP wording.
It waived only physical pointer travel into native browser chrome/another app and
native blur proof where headless emitted none. No visible desktop action was
authorized or required: adequate actual PiP reproduction/regression does not justify
desktop disruption. All five attempted headless target-focus switches emitted no
native blur; the probe separately records **`native:false`** and injects a window
blur event to verify the handler. This is **synthetic handler evidence**, not native
event-delivery proof. Physical OS-pointer/browser-chrome/other-window checks were
**not performed**. Native OS event delivery, focus and monitor behavior remain
unverified; no physical, screen-reader, other-engine or macOS PASS is claimed.
This decision was made by **Decision Delegate, not the user**, and grants no future waiver.

Full deterministic suite PASS **142 files, zero failures, 87.0s**, without a competing
browser matrix. An earlier overlapping run hit the historical 872-root catalog TTL
assertion (four reads vs allowed two/three); no causal source change or weaker
assertion was made. The unchanged subsequent Full passed; load/timing causation is
not established. Initial Full also passed (90.7s). The exception did not waive tests.

Read-only actual-installation `probe_web_live.py --watch-cards --daily` PASS: V2,
one owner/two streams/three accounts, observed active/history cards, coherent daily
category cost reconciliation and advancing stream IDs. Owned workers closed with
no cleanup failure; shared OpenCode remained untouched. Validator PASS all 11
checks with the six existing advisory budgets. No cap/baseline/dependency, inference,
runtime restart, release ZIP, tag or GitHub Release change.

Compact portable evidence: `development/architecture/governance/verification/web-help-587.json`.

## FR 000589: undecorated text-only header help (2026-11-05)

Base `9ad321b`, integrated default `f63e175`; product v80.170. Shared help buttons
have intrinsic text width and no underline or hover background. The generic button
hover rule excludes passive help and sorting-help actions; text alone changes color.
Mini replaces its full-width combined Session/Total CCost button with two intrinsic
buttons in the same edge-anchored grid. Useful help, question marks and unrelated
link/semantic-threshold decoration remain. No accounting/acquisition change.

`ContextHelp.heading` separates the pointer label from an existing sort action.
Pointer entry/leave, movement fallback and positioning use the label; original
focus, ARIA descriptions and click actions stay on the button. Models updates its
retained label rather than replacing the hover target. Empty action space still
sorts but never opens help or highlights text/background. The prior shared
hover/focus/pinned owner, exit grace, suppression and document cleanup are unchanged.

Actual hidden **Edge 156.0.4314.58** and **Chrome 156.0.8078.80** help probes PASS:
24 Running/Earlier main/PiP header cases per browser across Classic/Web light/dark,
wide/360px and 100%/150% CSS zoom, plus sortable Models/Sessions. Computed label
and text widths match; left/right padding and Mini's empty middle track have no
help cursor, popup or text/cell background change. Text-to-padding exit, genuine
re-entry, panel transfer, fast document exit and no refresh resurrection pass.
The same probes preserve keyboard focus/ARIA/Escape, touch pin/outside-dismiss,
date/cue help, exact hostile text and all report/settings surfaces. Real mouse
clicks outside sorting labels still sort. Fresh main/Mini screenshots were inspected.

The initial probe used Chromium's small default virtual screen. At 150% zoom a
readable Mini popover covered the purported padding point, so that coordinate was
actually over the panel and correctly retained help. The fixture now declares its
1920×1080 virtual screen and tests exposed padding with a taller real PiP viewport;
the existing compact viewport/clamping checks remain. No product geometry fix,
physical pointer proof or guessed failure cause is claimed.

The complete Edge Mini probe also PASS: sticky headers/scrolling, selectable long
titles, natural suffix edges, 560/800/280 widths, enlarged font/CSS zoom, theme/unit/
quota variants, disclosure resize and unchanged one-SSE ownership. The read-only
real-installation `probe_web_live.py --watch-cards --daily` PASS: V2, one owner/two
streams/three accounts, one active/two history cards, coherent daily category costs,
advancing IDs, zero owned threads/processes and no cleanup failures. The shared
OpenCode service was not stopped.

Full suite PASS: **143 files**, **1,687 passed tests**, zero failures/errors, **89.5s**;
one existing macOS zsh/PTY case is skipped on Windows. Working-tree validator PASS
all **11 checks**, with the six existing advisory budgets; no caps/baselines changed.
No user/delegate verification exception was requested or applied. Headless native
blur delivery was unavailable (five switches per browser); synthetic blur-handler
checks are not native blur evidence. Physical desktop/browser-chrome pointer,
screen-reader, macOS and other-engine acceptance remain unperformed/unverified.
The FR's actual-browser/PiP geometry is exercised by real CDP pointer input, not a
DOM-only fake. No inference, dependency, release ZIP, tag or GitHub Release change.

Portable summary: `development/architecture/governance/verification/web-help-589.json`.
