# Mini Watch and finished history

Source revision: 217e835d5d16734f5333b690cfa649b5de1be350
Checked revision: 217e835d5d16734f5333b690cfa649b5de1be350
Last checked: 2026-11-09
Status: current

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
