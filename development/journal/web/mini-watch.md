# Mini Watch and finished history

Source revision: 4d7eca5a1f073a405a62dfeb2d93fdfa6b1410c6
Checked revision: 4d7eca5a1f073a405a62dfeb2d93fdfa6b1410c6
Last checked: 2026-11-09
Status: current

## Summary

FR 000642 / v80.222 replaces the two Mini tables with one **Activity | Session |
CCost (Total) | Ctx** table. These are delivery-working-tree observations against
the base above, not a fresh audit of every older Mini feature. Full Watch retains
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
