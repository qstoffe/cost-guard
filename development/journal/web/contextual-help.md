# Shared Web and Mini contextual help

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
