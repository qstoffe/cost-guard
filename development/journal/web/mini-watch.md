# Mini Watch and finished history

Source revision: 217e835d5d16734f5333b690cfa649b5de1be350
Checked revision: 217e835d5d16734f5333b690cfa649b5de1be350
Last checked: 2026-11-09
Status: current

## Shared pointer/keyboard focus (FR000695)

v81.39 installs the main Web's modality owner on the actual PiP document, including
same-element return/Fit/help actions. Native hidden input verifies pointer resting
styles, keyboard rings and same-window route return. Exclusive PiP-to-owner window
focus transfer is **UNVERIFIED**: both tested headless browsers report both documents
focused without distinguishing focus/blur events. This is not physical OS-window
proof or a replay of the owner incident. [Detailed evidence/limits](models-isolation.md).

## Persistent session Ctx (FR000690)

Scoped v81.35 delta against `bd74062349614c7e6a7fd0c21fb7257c621a607f`,
checked locally 2026-11-13. This supersedes FR000666's destructive missing-permission
rule, not its cross-session safety or the earlier sections' evidence scopes.

`analysis/session_context.py` resolves **pending / ready-current / invalidated**
from the already acquired root, canonical `ContextEpochs` and session continuation.
Full analyzed history can seed a legitimate previous anchor even outside the card
slice or without a known current model. Compaction events (including not-yet-analyzed
triggers), boundaries, known provider/model conflicts and removed active anchors
are positive invalidation; prompt start, Stop/error and missing telemetry are not.
Source instance/generation/observation epoch, canonical root and actual boundary
digests qualify compact guidance. `CardSession` retains only the last-good compact
context, without another source watcher/history read. Pending retention never copies
old price guidance into an unknown new model. Current numeric evidence replaces it
immediately, including equal numbers and supported post-boundary anchors.

Mini consumes session summaries and retains supplementary observations in the
Controller, not prompt/DOM rows. Independent history owner/scope changes no longer
erase Ctx. Close/reopen and a fresh Mini use the legitimate source summary; no
browser storage, timer grace, expensive refresh or context arithmetic is added.
Full Watch's footer **was affected** and now receives the same prepared session
observation, with pending provenance in help. Sessions catalog **was affected**:
scalar summary algorithm 4 uses the same observation and labels carried context.
Prompt Ictx/Δ, cost, effort, other warnings, selection, geometry and cadence retain
their existing owners and meanings.

Evidence:

- Final local Full: **186 bounded groups, 2323 passed tests, zero failures, 155.6s**;
  four native macOS zsh/PTY tests skipped on Windows. Package validator: **11 passes,
  zero failures, seven existing advisory warnings**; no cap/baseline/dependency change.
  An intermediate Full run caught old historical rows leaking into an active refresh
  placeholder. Retaining only session Ctx while preserving empty prompt membership
  repaired that causal regression; focused card/guidance/context and final Full passed.
  The earlier failed run remains `scratch:/full-final.json`; final is
  `scratch:/full-repaired.json`.
- RED source-shaped V2 normalization → analysis/capture/Live → original renderer:
  **230k → N/A → N/A → 235k**. The first new-prompt publication has null prompt-local
  raw Ctx and no `context_handoff`; the second is still pending. Replaying the same
  publications through the fix gives **230k → 230k → 230k → 235k**. The original
  Mini VM also failed the one-frame missing-permission oracle before implementation.
- Focused source/VM/footer/catalog cases cover unknown/partial/retrying/unverified
  observations, Stop/error, rapid repeated prompts, a predecessor outside captured
  rows, explicit compaction/reset/move/model boundaries, source replacement,
  removed membership, equal-number replacement, remount/reopen and older publications.
  Existing broader context/child/concurrency/Watch regressions remain registered.
- Actual hidden **Chrome 157.0.8103.51 Document PiP** and shipped HTTP/CSP/SSE:
  source-shaped sequence passed with **0.5s / 5.1s** pending gaps, yellow new prompt
  while raw Ctx is null, real timer draws, unchanged row, bounded width, focus/AX,
  delayed hover/touch, history-owner change, invalidation controls, close/reopen and
  exact raw **230000** current replacement. Full Watch footer asserts the same values.
  The additional **touch → Tab/focus → Escape/blur → outside → one mouse arrival**
  Ctx sequence also passed without guard/timing changes or retry-until-PASS.
- Independent unchanged history-readiness probe passed actual Full/Mini DOM/AX
  loading, silent refreshing/failure, source switch and unchanged popup size.
  Independent lifecycle/Fit run passed **25 layouts**, four theme/scheme combinations,
  Credits/USD, narrow/wide windows, pointer/Enter/Space/touch Fit, both sizing modes,
  remembered reopen, scroll, one SSE and no storage/passive native resize.
- Read-only installed **V2** probe passed real context export/formatting, one Live
  owner, two coherent advancing streams and cleanup (**zero owned threads/processes**,
  shared OpenCode untouched). It saw one supported running context and **zero natural
  handoffs**: the owner's rapid real transition is **NOT VERIFIED**, not a production
  handoff PASS. Earlier history stayed loading; one background history batch/advance
  error was recorded, not certified as completed history.

### Scoped verification exception

The additional broad PiP portfolio remains **FAIL**. Its first failure was an old
Duration fixture injecting `row.model` while current model help uses prepared
recorded-model tokens; the fixture was corrected to inject the same literal unsafe
text into that prepared help, preserving its escaping assertion. The next run
reproduced the already documented **Total-heading mixed-input hover does not open**
(Classic/light/Credits, hovered and focused window, hidden help panel). Later Duration
variants after that assertion were **NOT RUN**, not passed by isolated checks.

**Decision Delegate** explicitly authorized an **FR000690-only minor verification
exception**, after the mixed-input **Ctx**, unchanged history-readiness and independent
Fit/lifecycle checks above passed. Rationale: isolate the known unrelated Total defect
without expanding into general hover/watchdog repair; no original Ctx acceptance is
waived. The failed assertion remains enabled. The defect and unrun later Duration
scope remain unverified/unresolved; no whole-portfolio PASS is claimed. Existing
[Suggestion000684](../../backlog/suggestions/000684-mini-help-mixed-input-hover-opening/SUGGESTION.md)
owns that follow-up; no duplicate proposal or owner approval is implied.

Raw local evidence: `scratch:/context-mixed-order.json`, `scratch:/history-isolated.json`,
`scratch:/manual-isolated.json`, `scratch:/mini-full.json` and
`scratch:/mini-full-repaired.json`. No paid request, source write, visible desktop
interaction, ZIP, tag or GitHub Release. Physical OS frames/work areas, macOS pixels
and screen-reader speech are not tested or changed. Final Full/validator results are
recorded in the completed task report; earlier successful checks are not retroactive
PASS for the failed broad portfolio.

## Relative Activity ages (FR000672)

Scoped v81.22 delta against `2fd4375360ca0ebf1d100fc2af270f3fb9486163`,
checked locally 2026-11-10. Earlier sections retain their own evidence scopes.

`mini.js::activityLabel` reads the selected absolute start/finish, its prepared
configured-local date/clock and the current configured-zone date from the existing
`ReportView.timestamp` helper. Same-day OR under-12-hour events retain their clock;
older values floor absolute milliseconds into h/d/30-day m/365-day y buckets.
Missing/invalid timestamps remain unknown; future timestamps keep their supported
clock. Missing configured-day evidence conservatively retains the prepared clock,
never substitutes the browser zone. Exact date/offset help and the running-only
triangle remain on the existing value wrapper. Selection, history age eligibility,
keys, source acquisition, CSS, opening measurement and native Fit are unchanged.
The already-existing five-second Controller render supplies the current instant.

Verification:

- Local Full: **182 bounded groups, zero failures, 153.2 s**. Focused Mini also
  passed. Controller VM cases independently assert exact 12h/24h/48h/30d/60d/365d/
  730d boundaries and their preceding milliseconds, flooring, lowercase units,
  same configured date even after 20+ hours, midnight, configured/browser date
  mismatch, both DST changes/repeated 02:30 offsets, invalid/missing/future time,
  all five old-history slots, terminal/unverified/resumed rows and sole-timer ticks.
- Package validator: **11 passes, zero failures, seven existing advisory warnings**;
  no budget, baseline or dependency changes.
- Hidden Chrome **157.0.8103.39**: full native Document PiP portfolio **131 layouts
  passed** at 100% zoom/DPR 1; focused Activity **24 layouts passed** at 125% zoom/
  DPR 1.5. Clock and relative tokens retain exact focus/hover/touch help under
  en-US/sv-SE and New York/Tokyo browser zones; four Classic/Web light/dark themes,
  Credits/USD and narrow/wide windows remain nowrap, aligned and unclipped.
  Multi-year/100+ day history and a running relative token fit without native
  width growth. Synthetic time crosses 24h on the existing callback with the same
  row, focused help and serialized source view, no render fetch/new timer/resize.
  The first full run's test-only reference-equality assertion rejected an identical
  retained HTTP snapshot; checking unchanged serialized source values corrected
  that harness assumption. The entire portfolio then passed; product code was not
  changed for that repair. Raw: `scratch:/mini-full-100.json` (failed assertion),
  `scratch:/mini-full-100-repaired.json`, `scratch:/mini-activity-100.json`,
  `scratch:/mini-activity-125.json` and its synthetic `-activity.png` screenshot.
- Relevant real-input seam **PASS**: authenticated installed V2 produced a verified
  running prompt within **1.169 s**. An independent Python datetime oracle matched
  the selected absolute start, configured-local clock and exact date/UTC offset;
  unchanged flags/time/display fields passed through the Mini Controller seam at
  actual observation time, including the running cue, exact help and sole timer.
  Owned host close **0.146 s**, immediately **zero owned threads/processes**; no
  natural-retirement wait needed. Only sanitized assertions/counts were exported.
  Raw: `scratch:/real-activity-result-repaired.json`; task-specific harness stays
  in scratch, with no source payload/identity publication.
- Earlier installation checks remain **not PASS**: `scratch:/live-probe.json`
  reached the 90 s operational history cap while **488/3103** roots were checked;
  the source remained healthy and no provisional history escaped, but completed
  real-history proof was inconclusive. `scratch:/live-basic.json` verified V2/one
  owner/two streams but failed its remaining-worker assertion: one native Claude
  quota worker was still waiting after host close. The first narrow scratch run
  passed the independent timestamp oracle but failed its VM harness's relative
  fixture import; the import was repaired and synthetically checked before the
  successful real-input run. Raw: `scratch:/real-activity-result.json`.
- Decision Delegate authorized the bounded Activity-specific alternative, then
  confirmed ordinary delivery/progress 122 with **no acceptance exception**:
  completed installation-wide history and naturally observed aging are not extra
  acceptance requirements for this presentation-only change. No broader history
  rerun, backend repair, Suggestion or hold was warranted. Original failures above
  are not erased by the narrower success.

Integrated browser was disconnected; permitted hidden Chromium supplied rendered
evidence. These checks do **not** verify completed real-history enumeration, natural
age transitions, physical desktop/work-area frames, macOS or screen-reader speech.
No paid inference, source writes, shared OpenCode stop, ZIP, tag or GitHub Release.

## Running Activity indicator (FR000671)

Scoped v81.21 delta against `bfb164e87913cb53f45e6dec84b5f902b8ab916d`,
checked locally 2026-11-10; earlier sections retain their own evidence scopes.

Mini's existing `running` selection deliberately includes execution-unverified
work. The decoration therefore requires the represented nonhistorical prompt's
`in_progress` plus absence of execution uncertainty and success/abort/error flags.
Every draw replaces its text from these facts; keyed rows retain no independent
running latch. The separate span is `aria-hidden`, noninteractive and unfocusable;
the existing time wrapper still owns date/offset hover/focus/touch help. A compact
glyph fits inside Activity's existing header width. No lifecycle inference, source
call, new control, native minimum, opening measurement or Fit change is introduced.

Verification:

- Local Full: **182 bounded groups, zero failures, 145.0 s**. Focused Mini:
  **13 tests passed**. Extended fixtures cover simultaneous
  running sessions, same-row running/terminal/history/next-prompt updates,
  unverified and contradictory terminal flags, unknown times, removed/replacement
  sessions, source correction, rejected older snapshots and repeated draws.
- Package validation: 11 passes, zero failures, seven existing advisory warnings;
  no hard cap/baseline/dependency change.
- Actual hidden Chrome 157.0.8103.39, 125% zoom/DPR 1.5: 16 lifecycle/color and
  24 Activity/layout cases passed, including four themes, Credits/USD, narrow
  native PiP, immediate terminal cue removal, decorative accessibility, stable
  focus, hover/touch help and full date/offset invariance. Activity remains nowrap,
  unclipped and header-aligned within its existing 57.3 CSS-pixel metric width.
- The complete native PiP portfolio passed **131 layouts** in the same Chrome at
  100% zoom/DPR 1, including measured opening sizes, sticky headings, five-row
  internal scrolling, selection, help/AX, source transitions, explicit Fit,
  remembered size and no passive resize. The glyph remains inside the Activity
  header minimum; opening/Fit calculations and native width were not increased.
  [Synthetic running Web-light sample](../../architecture/governance/verification/mini-running-671/web-light.png)
  and [Classic-dark sample](../../architecture/governance/verification/mini-running-671/classic-dark.png)
  retain the compact rendering. Raw reports: `scratch:/mini-chrome-100-full.json`,
  `scratch:/mini-chrome-125-lifecycle.json`, `scratch:/mini-chrome-125-activity.json`
  and `scratch:/full-tests.log`.
- Read-only installed V2 probe: 62 coherent publications, one running prompt,
  three accounts and five quota projections, 22.882 s; owned acquisition closed
  in 0.087 s and shared OpenCode was untouched. No historical rows were observed:
  synthetic cases supply terminal/history evidence, not a real-source transition.
- Integrated browser was disconnected. The first headless Edge attempt timed out
  at `Browser.getVersion`, before rendering; this is not an Edge PASS. The working
  hidden Chromium route supplies native PiP evidence without desktop interaction.

No paid inference, source writes, release ZIP, tag or GitHub Release. Physical
desktop/work-area frames, monitor transitions, macOS and screen-reader speech are
not tested or changed. No acceptance exception or deferred scope has been needed.

## Same-session Ctx handoff (FR000666)

Scoped v81.16 delta against `eaa7cb93b5699b6887b169b6455bf27e55af6fe1`,
checked locally 2026-11-10. The earlier headers/sections retain their own scope.

- Existing session guidance and prompt context share canonical invalidation and
  cannot always supply a numeric value while the next prompt has no bound model.
  The old `waiting for comparable request context` detail also covers invalid data;
  it is not sufficient permission for browser carry-forward.
- `watch_capture.mini_context_handoffs` therefore exports only permission to retain
  an exact earlier prompt/token pair. It requires complete nonretained capture,
  proven active current/prior history, no current root request, no compaction since
  the prior anchor, no retired boundary, no incompatible known provider/model, and
  a supported predecessor projection. An unbound new model stays pending, not a
  fabricated comparable measurement. Fresh verified Watch cards alone export it.
- Mini's row owns only its last displayed source token/raw identity. The handoff
  must match both; missing permission clears it. Historical seeding additionally
  requires matching prompt/session context, never merely a numeric summary. New
  source/host identity and row removal reset retention; old publication timestamps
  are rejected before identity/observation changes. No arbitrary delay, storage,
  request, context arithmetic, delta reuse, Full Watch or layout change.
- Retained help says `previous same-session estimate; current prompt pending
  refresh`; fresh same-number evidence removes that qualification immediately.
  Δ always comes independently from the current prompt.

Verification:

- Local Full: **181 bounded groups, zero failures, 142.6 s**. Focused Mini was
  rerun after final fixture/late-publication adjustments: **13 tests, zero failures**.
  VM cases include repeated draws, several prompts, fresh equal values, separate
  sessions, missing first context, zero, authoritative unknown, unverified work,
  source correction, removal/reappearance, host/source changes and history resumption.
- Package validation: **11 passes, zero failures, seven existing advisory warnings**;
  no cap/baseline/dependency changes. No ZIP, tag or GitHub Release.
- Integrated browser capability check found no Document PiP on its blank document.
  Owned hidden **Edge 157.0.4341.42**, zoom/DPR 1, then passed actual Document PiP
  with shipped HTTP/CSP/SSE. Raw synthetic V2 evidence passes through normalization,
  analysis, capture, verified cards and Live: **172k → 172k → 175k**, repeated SSE/
  timer draws, focused help/AX provenance, independent Δ, late snapshot rejection,
  tool continuation, genuine reset/model/move/inactive/unverified invalidation, and
  a newly opened Mini with no retained value. Reproducer:
  `node development/tests/integration/probe_mini_fit.cjs <edge.exe> <owned.json> 1 1 context-only`.
  Summary retained as `scratch:/mini-context.json` for this worker.
- Read-only real installed V2 `probe_web_live.py --context-deltas`: one known running
  context, zero handoffs observed, one acquisition owner, two verified streams,
  sequence advancing, first usable row 1.115 s; owned threads/processes zero after
  cleanup, shared OpenCode untouched. This verifies real export/formatting, **not**
  the owner's original incident or a real new-prompt handoff. Earlier remained
  loading; one history-batch/advance failure was recorded, not claimed as history PASS.
- Initial probe failures were fixture defects, not waived acceptance: root and
  invocation replacements now agree; the canonical estimate includes the prompt's
  two-token growth. Partial current telemetry can still legitimately yield the
  existing provisional `172k`, which must replace retained help rather than be
  forced to N/A. Deterministic raw assertions now pin fresh/unverified fixture states.

Limits: no paid model calls, source writes, physical desktop/work-area test or
instrumental reproduction of the private incident. No acceptance exceptions or
deferred product scope were needed; headless PiP proves the changed rendering path.

## Quiet Total and direct Session help (FR000665)

Scoped v81.15 delta against `b22cfc98fa123ac50d4a201bb92eafe8c6c236d7`,
checked locally 2026-11-10. The earlier revision header/sections retain their
historical scope. The runtime change is confined to `mini.js`:

- Total's span is normal selectable text: no `ContextHelp.value`, `help-value`,
  tabindex, title, popover binding or `totalCostHelp` construction. Its factual
  accessible amount label remains. Header help is exactly one sentence.
- `drawCost` reuses the existing server-prepared `account_ccost` token from the
  same canonical whole-session cost object. Its `known_ccost` input includes the
  existing linked-subagent scope. The existing no-priced-request guard converts
  that token's dash to Mini's N/A; null pending/unavailable summaries remain distinct.
  No backend change, prefix stripping, client arithmetic or missing-cost invention.
  Ordinary `known_ccost`, raw cost, completeness, CCost and other views are unchanged.
- Session help keeps the full title/stable-ID fallback and reuses `promptPreview`
  for `Prompt #N: excerpt`; missing number/preview cases stay explicit. No new
  prompt retrieval. The CCost help construction and Duration highlight are unchanged.

Fresh evidence:

- Local Full: **181 bounded groups, 2,243 passed tests, two skipped, zero failures,
  133.1 s**. Both skips are existing macOS zsh/PTY checks unavailable on Windows.
  The focused Mini group passed all 12 tests. Projection/VM cases cover partial
  versus complete Credits/USD, known/empty zero, wholly unpriced N/A, pending and
  unavailable summaries, corrected subtotals, running/grace/history rows, preserved
  canonical fields, direct preview labels, grapheme boundaries and literal HTML text.
- Package validation: **11 passes, zero failures, seven existing advisory warnings**
  (README/Web-guide/version-history prose and four module design budgets). No cap,
  baseline or dependency change; no release ZIP or GitHub Release.
- Real headless **Edge 157.0.4341.42**, zoom/DPR 1: the full PiP fit probe passed
  **127 layouts**, including Classic/Web light/dark, Credits/USD, 650/280 widths,
  lifecycle/SSE handoff, selection, scrollbars, Fit, viewport bounds and one SSE.
  New assertions preserve CCost focus/delayed-hover/touch help and its ticking
  yellow Duration/selection, including terminal/unverified/history/replacement
  transitions. Total is skipped by Tab, has no focus/click/touch help and does not
  open after a 700ms hover (beyond the shared 600ms delay). Total remains selectable;
  the exact header definition opens by focus/hover/touch. Corrected/unknown/zero
  Total values update the same row, including at narrow native width.
- Real headless **Chrome 156.0.8078.80**, 125% zoom/DPR 1.5, overlay-scrollbar
  configuration: the complete help/source-context/Duration matrix also passed.
  This is a targeted second-browser run, not another 127-layout run.
- Read-only installed V2 `probe_mini_source.py`: **36 coherent publications**, one
  running row, three accounts, five quota projections, 14.298 s. Owned acquisition
  closed in 0.086 s; shared OpenCode was untouched. No historical cards were
  observed, so synthetic tests supply historical transitions, not a real-history claim.
- Two initial fixture failures were repaired, not waived: oversized Total inputs
  now populate the reused subtotal token; synthetic help pins its own publication
  until source-driven checks begin, avoiding replacement by normal live refresh.
  An initial unit fixture also inherited old display-unit tokens; making its inputs
  explicit and retaining the established wholly-unpriced N/A expectation fixed it.

[Synthetic Web-light sample](../../architecture/governance/verification/mini-total-665/web-light.png)
retains the rendered five-column layout. Detailed execution reports were
`scratch:/full-tests.json`, `scratch:/mini-edge-verified.json` and
`scratch:/mini-chrome-help.json`; this section retains their useful outcome facts.
The integrated browser was tried and disconnected; owned hidden browsers supplied
real Document PiP evidence without external desktop interaction. Physical Windows
frames/work areas, monitor transitions, macOS and screen-reader speech were not
tested or changed. No paid model calls, acceptance exceptions or deferrals.

## Unused scrollbar gutter (FR000660)

Scoped v81.10 delta against `0da05445ee574952d268fa8d8502cdc2b8fb5b0d`,
checked locally 2026-11-10. The only runtime behavior change removes
`scrollbar-gutter: stable` from `.mini-prompts` in `mini.css`. `overflow: auto`,
the five-row viewport, sticky cells and all other tables/styles remain unchanged.
There is no scrollbar hiding, fake left padding, new resize handler or redesign.

Fresh browser evidence, not a visual assumption:

- Local Full passed **181 bounded groups, zero failures, 152.3 s**. Two native
  macOS zsh/PTY tests skipped on Windows; no all-platform PASS is claimed.
- Package validation passed **11 checks, zero failures, seven existing advisory
  prose/module budget warnings**. No hard cap or structural baseline was raised.
- The new regression failed against original CSS: a non-scrolling three-row table
  reserved **15 CSS px**, with **7.5 px left / 22.5 px right** outer insets. The fix
  gives **7.5 / 7.5**, and six/ten rows still consume the authentic 15 px scrollbar.
  Returning to five/one rows releases it without resizing the native window.
- Four complete real Document PiP runs passed **127 layouts each (508 total)**:
  headless Edge 157.0.4341.42 with classic-width scrollbars at 100%/125% zoom,
  Chrome 156.0.8078.80 with actual zero-width overlay scrollbars at 100% zoom/DPR 1
  and 125% zoom/DPR 1.5. The new matrix measures body/main/region/table rectangles,
  client/offset/scroll widths, computed gutter and independent document scrollbars;
  it covers Classic/Web light/dark, 0/1/3/5/6/10→5→1 rows, reachable last rows,
  sticky headers, non-overlapping accounts and unchanged native bounds.
- Paired before/after screenshots reapply just the original `stable` declaration
  in the same PiP, then restore shipped CSS, at unchanged native dimensions.
  All four theme/color combinations at 100%/125% are retained. The original-code
  red run also captured the original shipped declaration directly.
- Existing width/fit/theme/activity/help/AX/history checks passed in every run:
  compact metric minima and flexible Session, narrow horizontal panning without
  document overflow, too-short document scrolling, Fit on open/Remember last,
  manual resize/reopen, pointer/Enter/Space/touch Fit, selected tooltip text and
  retained focus, one SSE and no passive native autosizing or geometry storage.
  One exploratory test read the non-sticky `thead` rectangle instead of its sticky
  `th`; correcting that test observer repaired it without a product change.
- Rechecked `tableWidth`, `scrollbarWidth`, `OpeningMeasure.read` and explicit
  `FitSize` height measurement. The measured opening allowance is authentic
  scrollbar width, not the persistent CSS reservation. Removing the latter gives
  Session the recovered width at identical requested/achieved native bounds.
  No measured over-reservation requiring a JavaScript change was demonstrated;
  **`mini.js` is unchanged**. Full Watch, Models and other table gutters are untouched.
- Read-only actual-installation `probe_mini_source.py` passed on V2: **20 coherent
  publications**, two running rows, three accounts, 7.756 s; owned acquisition
  closed in 0.117 s. It observed zero historical cards, so synthetic tests supply
  row-transition/history evidence, not an invented real-source transition.
  No model calls or shared OpenCode stop.

[Compact measurements and paired screenshots](../../architecture/governance/verification/mini-gutter-660/summary.json)
retain the public synthetic evidence. Raw runs remain `scratch:/mini-edge-full.json`,
`scratch:/mini-edge-125.json`, `scratch:/mini-chrome-overlay-full.json` and
`scratch:/mini-chrome-overlay-125.json`. Integrated browser was tried but disconnected;
owned hidden browsers supplied the actual browser proof without desktop disruption.
Physical desktop/work-area frames, monitor transitions, macOS and screen-reader
speech were not tested or changed; no acceptance exception or deferral is claimed.

## Value-help additions (FR000645)

Scoped v80.225 delta on `0997b8b9e0b9e592db29153a7bceb85d9efba13a`,
checked locally 2026-11-09. Earlier sections and their revision header retain their
historical scope, not a fresh audit of unrelated behavior.

`mini.js` selects the existing displayed next-context token once for both cell and
help. The delta is the chosen prompt's prepared token, never a subtraction of rounded
context values. Historical help names the prompt scope and potentially later session
estimate. Canonical session warning text/cost/refresh notes remain untouched, including
exceeded thresholds. All row help refreshes after the coherent row update through the
existing root `ContextHelp.refresh`, preserving target identity/focus.

Session help adds only the selected row's existing `prompt.preview`, normalized to one
line and trimmed at 25 `Intl.Segmenter` graphemes. Truncation adds one ellipsis; absent,
non-prompt or unsupported previews add nothing. The unsupported-Segmenter fallback
omits the optional hint safely. No raw content acquisition, logging/cache, new endpoint,
layout/column/visible-value, lifecycle or Full Watch change was introduced.

Fresh evidence (not inferred from earlier results):

- `test_mini_watch.py` passed 10 tests, including active/history projection tokens.
  `mini_help.cjs` covers independent next/delta owners, zero/signed/unknown/source-format
  cases, no/approaching/exceeded/pending/refreshing/unavailable warning states,
  history/resumption/concurrent representatives, full title/ordinal, 25-boundary,
  combining marks/family/skin-tone emoji, whitespace/controls/ellipsis and literal HTML.
  An initial expected HTML-like snippet counted 27 rather than 25 characters; fixing
  that fixture expectation repaired the exploratory failed test, not product code.
- Local Full passed **179 files, zero failures, 124.8s**. One existing macOS shell test
  was skipped because zsh/PTY is unavailable on Windows; no all-platform PASS is claimed.
  Package validation passed **11 checks, zero failures, seven advisory warnings**
  (existing prose/module budget debt). No caps or structural baselines were raised.
- Integrated OpenCode browser smoke loaded shipped assets in an isolated real-DOM
  fixture and confirmed the expected labels/preview, four columns, unchanged visible
  next value and no native titles. This was not native PiP or interaction proof.
- `probe_mini_watch.cjs` passed in owned **headless Edge 157.0.4341.42**, DPR/zoom 1:
  **91 existing layouts** plus `probe_mini_help.cjs`'s real PiP Tab focus, delayed hover,
  touch, Escape, literal HTML, live preview/delta/warning updates and active→history
  source handoff while help remained open. Focus/row identity and table geometry stayed
  stable. Existing four-theme, Credits/USD, scroll/Fit/history checks also passed.
- Extended `probe_mini_source.py` passed against real **V2**: three coherent captures,
  one running row with bounded preview and both prepared context-help tokens, three
  accounts, **1.569s**. Owned acquisition closed in **0.112s**; shared OpenCode was
  untouched. No model calls. It observed **zero historical cards**: history correctness
  comes from deterministic and synthetic PiP cases, not a claimed real transition.

Compact durable summary: [mini-help-645.json](../../architecture/governance/verification/mini-help-645.json).
Raw local test/browser artifacts remain session-local (`scratch:/full-tests.json`,
`scratch:/mini-browser.json`), without personal prompt text or bootstrap capabilities
in this publication. Physical desktop/work-area, macOS and screen-reader behavior
were not verified; none changed here. No acceptance waiver or substantial deferral.

## Historical foreground correction (FR000643)

v80.223 fixes a category-versus-outcome regression: `View.drawSessions` previously
colored every successful representative green, including certified history. It now
checks the existing `historical` category first. Historical rows always inherit the
theme foreground; active/grace rows retain running/yellow, success/green and
abort/error/red. Outcome accessibility is unchanged. Server grace eligibility,
duration, source acquisition, selection, ranking, CCost and Full Watch are unchanged.
No timer, CSS palette, setting, badge or warning was added.

Verification against the source revision above, in this delivery working tree:

- A new cold-success-history assertion failed on the original code and passed after
  the guard. `mini_sessions.cjs` covers neutral old success/failure, same-node grace
  handoff and consecutive/concurrent resumption. `mini_watch.cjs` checks source
  membership handoff, accessible outcomes and retained/repeated retry publications.
- Local **Full: 179 bounded test files, zero failures, 170.3s**. The new browser-only
  fixture initially used a DTO-only `has_error` field; correcting it to canonical
  `watch_error` repaired that failed exploratory browser run, not product behavior.
  Package validation passed **11 checks, zero failures, seven advisory warnings**.
  No budget/structural baseline was raised. Backlog-only updates through `7334126`
  were fast-forwarded before delivery; they changed no tested runtime surface.
- Owned **headless Edge 157.0.4341.42**, real Document PiP and shipped HTTP/CSP/SSE,
  passed **91 layouts** through `probe_mini_watch.cjs`: 12 new lifecycle/color cases
  plus the existing 79-layout width/density/Activity/help/AX/history/Fit matrix.
  The new `probe_mini_theme.cjs` covers Classic/Web light/Web dark × Credits/USD ×
  650/280 widths. It asserts computed row and all four value foregrounds, cold five
  successful histories, same-node running → success → history, abort/error → history,
  repeated/retained SSE, reopen, unverified work and proof invalidation/arrival.
  Full Watch historical classes stay neutral and running/success classes unchanged.
  A final 12-case color-only supplement also passed explicit unit and theme switches
  while historical rows remained mounted, without losing their neutral foreground.
  Membership changes are **synthetic canonical source publications**, not observed
  natural terminal transitions in the personal installation.
- The read-only actual-installation `probe_web_live.py --accounts` passed: V2,
  three account cards, one owner, two coherent advancing streams, stable run origin,
  **6.0313s**, zero remaining owned threads/processes and no cleanup failures.
  No model calls or finite jobs were started; shared OpenCode was untouched.
- Earlier real-source exploratory checks remain **FAILED**, not retrospective PASS:
  `--tool-invocations` observed no invocation in its bounded window; `--watch-cards`
  lost the owned HTTP host after about 75s (history completion inconclusive).
  A concurrent version-file edit could have triggered the existing source guard;
  the shutdown reason was not captured, so this explanation is unproved.
  The default probe passed continuity subchecks but failed its immediate final
  owned-worker assertion with one Claude quota worker still awaiting a response.
  Delegate source inspection found deliberately nonblocking 0.2s joins and bounded
  provider work; it directed the distinct `--accounts` run above, which passed its
  final cleanup gate. No cleanup assertion or provider deadline was suppressed.
- Decision Delegate assessed these scoped presentation checks as sufficient, with
  the successful relevant live check and normal final validation: **no acceptance
  waiver**, Suggestion or hold. The extra probes do not prove private history
  completeness or real-source lifecycle colors. The integrated browser was tried;
  its initial embedded page exposed no Document PiP API. The owned headless route
  supplies the actual PiP evidence without external desktop interaction.

Physical desktop/work-area frames, monitor transitions, macOS pixels and screen-reader
speech remain unverified. These are not changed by this foreground correction.
See the completed FR report for final validator/delivery evidence. Raw local outputs:
`scratch:/mini-regression.json`, `scratch:/mini-colors-final.json`; public compact
evidence is under `development/architecture/governance/verification/mini-history-643.json`.

## Unified table baseline (FR000642)

FR 000642 / v80.222 replaces the two Mini tables with one **Activity | Session |
CCost (Total) | Ctx** table. These are delivery-working-tree observations against
base `4d7eca5a1f073a405a62dfeb2d93fdfa6b1410c6`, not a fresh audit of every older Mini feature. Full Watch retains
its per-prompt active cards and independently certified five historical sessions.

`src/web/assets/mini.js` selects one representative per canonical session ID from
already-acquired cards. A genuinely running focal prompt beats an unfinished
execution-unverified candidate; the latest start/event-ID wins within that class.
Every distinct active session survives. The latest finished terminal-grace and
certified history candidates compete for `max(0, 5 - active sessions)` places after
active IDs are excluded. Final order is Activity ascending with stable identity
ties; unknown finishes sort conservatively, not as newest. History proof/retention
stays server-owned. Browser code performs no acquisition, pricing or identity merge.

One keyed row survives history-to-running promotion and chronological movement.
Atomic DOM `moveBefore`, or focus restoration in its fallback, preserves a focused
help target during reorder. Activity uses the representative's actual start or
supported finish. `src/application/display.py` exports `start_date_time` separately
with the configured local UTC offset; old date/time tokens retain their format.
Prompt CCost and independent whole-session CCost remain separate. Duration remains
in CCost help; historical-only Ctx comes from session summary, active/grace Ctx from
the focal prompt. No Duration column or Earlier disclosure remains.

The table reserves five styled body-row metrics plus its header and any horizontal
scrollbar. A sixth/tenth distinct active row scrolls internally; header and accounts
remain outside. Measurements may change this internal viewport, never native bounds
on a passive publication. Opening width measures compact non-Session columns, aims
for Session about 1.6 times their sum, and takes the larger complete actual/reference
header need. Explicit Fit remains activation-checked, one-shot and height-only;
native clamps preserve ordinary scrolling. Remember/manual sizing stays browser-owned.
The existing authenticated Mini history lease is needed below five active sessions,
released at five-plus and withdrawn on close; there is still one EventSource.

Current guides, Settings help, module contract and test map describe the unified
layout. Superseded two-table/disclosure test branches were removed rather than kept
as conflicting executable specifications. Architecture boundaries did not change.

## Evidence

- Reproduce deterministic coverage with
  `py -3 development/tools/run_tests.py --suite full` and
  `py -3 development/tools/validate_package.py --working-tree`.
  Final Full completed **179 bounded files, zero failures, 148.5s**, including the
  final Settings-help changes. Validator passed **11 checks, zero failures, seven
  advisory size warnings**; no budgets or structural baselines were raised. Earlier
  Full runs exposed the expected new-start-token golden change before correction.
- `development/tests/fixtures/mini_sessions.cjs` pins 0/1/3/4/5/6/10 active counts,
  ten prompts in one session versus distinct sessions, actual latest prompt/cost,
  event-ID ties, running-over-unverified priority, sequential completion/resume,
  grace/history competition, sparse/unknown/pending/certified history and independent
  CCost/Ctx. `test_watch_cards.py` verifies five server candidates remain after two
  running and one terminal-grace exclusion. Display tests distinguish repeated
  Stockholm 02:30 +0200 and +0100 for starts and finishes.
- Actual **headless Edge 157.0.4341.42 Document PiP**, owned disposable profile and
  synthetic shipped HTTP/auth/CSP/SSE: full normal-zoom and 150%-zoom/device-scale2
  runs each passed **79 layouts**; the earlier 125%-zoom/device-scale1.5 matrix also
  passed. `probe_mini_fit.cjs <absolute browser> <absolute output> <scale> <actual
  browser zoom>` runs width, density, Activity help/interaction, DOM/AX history
  readiness and explicit Fit. It records requested and achieved bounds separately.
  Pointer/Enter/Space/touch and manual-size close/reopen are exercised; `manual-only`
  is an optional final scope argument. Device scale is emulated, not Windows scaling.
- Ordinary system-font reference: request **550x480**, achieved **566x522 outer /
  550x480 inner**, columns **58.234 / 335.328 / 89.391 / 37.047 CSS px**, Session/other
  ratio **1.816**, measured table gutter **15px**, complete header and no page overflow.
  Ten active/six accounts: **566x509 outer**, **156px** table viewport / **283px**
  content, internal vertical scrolling and no document vertical overflow. A zero-row
  opening reserves **151px** table capacity without fake session rows.
- The scale2/150%-zoom exploratory run initially failed a test that always demanded
  shrinking from a requested large window. Achieved native bounds were actually below
  the fit target. The corrected assertion distinguishes a real tall baseline from a
  short native clamp. The original full run remains FAIL, not retroactively PASS;
  the final full rerun passed with **18 native-limited density cases and eight
  native-limited Fit activations**, asserting reachable scrolling, not full fit.
  Both final matrices also passed four oversized paired-cost layouts: exact separate
  prompt/session amounts survive narrow region-local horizontal panning.
- `probe_mini_watch.cjs <browser> <output> 1 --history-demand-only` passed after its
  compatibility-runner rewrite. Eight authenticated transactions returned HTTP200:
  history enabled initially, disabled at five, enabled at one, disabled at six,
  enabled at three, withdrawn on close, enabled for a new reopened-document lease,
  withdrawn again. Hidden opener/visible PiP and one EventSource were observed.
- Read-only actual installation `probe_web_live.py --tool-invocations` passed:
  V2, one owner/two coherent advancing streams, three accounts, invocation scalar
  evidence, no model calls, about **15.987s** total. Owned cleanup succeeded; the
  shared OpenCode service was untouched. History/Daily completeness is not proved
  by this targeted source probe; deterministic/browser history proof is separate.

Compact final results and commands:
`development/architecture/governance/verification/mini-activity-642.json`.
Scratch artifacts are local working evidence, not public artifact URLs. GitHub CI
and merge truth belong to the PR/run, not an invented all-platform PASS here.

The integrated browser returned `browser.disconnected`; the permitted owned hidden
route supplied app-content evidence without external desktop interaction. Normal
and high-zoom screenshots were inspected; the latter shows native-limited height
with reachable document scrolling, not full-fit proof. Physical OS frames/work-area,
monitor transitions, manual OS dragging, macOS pixels and screen-reader speech remain
**unverified**, not PASS. No requirement/test exception was requested or granted for
FR000642; historical exceptions below are not reused. No inference, personal profile,
shared desktop input, ZIP, tag or Release was used.

### Retained historical findings

This note consolidates the old append-only log. Its complete dated observations,
per-task decisions and artifact links remain in
[the pre-FR642 journal](https://github.com/qstoffe/cost-guard/blob/4d7eca5a1f073a405a62dfeb2d93fdfa6b1410c6/development/journal/web/mini-watch.md).
They are historical evidence, not current two-table geometry or fresh test results.

- FR000561 owns supported terminal representatives and Stockholm fold identity.
  FR000569/621 retain independent observation clocks, honest retained/empty data and
  symmetric value help. FR000608 owns independent prompt/session costs. These source,
  help and accounting responsibilities survive the new Mini-only selection policy.
- FR000591's original passive automatic-height goal was placed On Hold after actual
  Chrome/Edge `resizeTo`/`resizeBy` raised `NotAllowedError` without activation.
  The owner later replaced that goal with click/open fitting. Opening consumes
  activation; timers/publications never grant another native resize permission.
- FR000565 measured actual Windows DPI144/150%: requested screen DIPs, CSS pixels,
  physical frame pixels and native chrome are not interchangeable. FR000570 proved
  Chrome native CG HICON adoption, **not** taskbar/Alt+Tab/grouping behavior. Their
  specific delegate-authorized visible work and exceptions grant no future permission.
- FR000544's broad Web-host shutdown probe failed `web_shutdown_timeout`; its
  delegate permitted that task's scoped delivery without claiming the risk fixed.
  Later direct acquisition cleanup passes were not retroactive WebHost shutdown PASS.
  Older queued-native CI exceptions applied only to their named PR/HEAD successors.

## Next investigations

No additional product scope is created by this delivery. Future physical-platform
or accessibility work needs its own relevant task and permission. Preserve native
clamp measurements rather than replacing them with requested geometry or promising
exact OS bounds. Broader historical-performance drivers updated for this layout are
not claimed executed merely because their selectors changed.

## Rejected hypotheses

- Multiple running prompts are not multiple Mini sessions; equal titles are not
  identity. Mini must not sum focal costs or truncate distinct active roots to five.
- A successful resize API request is not proof of achieved fit. High-scale native
  clamps can make explicit Fit grow instead of shrink; scrolling is honest fallback.
- Replacing help-bearing sample spans with plain text undermeasures normal rows.
  Preserve real cell structure when measuring five-row reserve and horizontal gutters.
- Ordinary `insertBefore` reordering can lose focused time help. Stable keys alone
  do not preserve focus across a DOM move; actual browser regression found this.
- A close withdrawal built before clearing the active window can falsely keep
  historical interest true. Clear ownership before the demand controller closes.
