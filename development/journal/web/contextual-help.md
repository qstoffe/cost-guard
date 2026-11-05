# Shared Web and Mini contextual help

Current selective follow-up: **FR 000587 / v80.168**, recorded below. The FR 000582
inventory and evidence here are historical; removed preview/row/freshness cues are
not current UI recommendations. Current writing/placement policy lives in the module contract.

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
