# Web table scroll investigation — FR 000529

Base: `a554d312fecc7d7db31ae6aebe7819418c18c11c`; Windows, 2026-10-30.
Status: complete automated browser run passed; physical-device limits remain explicit.
The [fresh measurements](web-table-scroll-2026-10-30.json) retain the baseline,
complete candidate run and registered-suite outcome without private payloads.
The colleague's original browser, route and physical device remain unknown.

## Source-bound causes and repair

1. Session-detail polls captured the first row's document position **before** HTTP
   and compensated through `window.scrollBy` in `finally`, even on unchanged/error
   responses. Internal wheel movement during the await was mistaken for a layout
   change and moved the document. Capture now occurs immediately before an actual
   DOM update, after HTTP, over the visible row relative to `.table-scroll`.
   Compensation changes that container's `scrollTop`, not the document.
2. Internal browsing did not disable Live follow; only window scroll/focus did.
   Scrolling away from the internal bottom now disables follow.
3. Host-health checks rebuilt all frozen finite reports except Overview.
   `app.js` now retains the DOM for any unchanged report/search/current output.
   Health is not a new frozen observation. Detail's `attach` also avoids replacing
   an already-connected root with itself, preserving native focus/scroll.

There are no wheel/key handlers, overflow removal, valuation, source/provider
acquisition, security, SSE limits or frozen snapshot calculation changes. Native
scrolling, sticky headers and existing 50-row paging remain. No Web promotion.

## Reproducible browser setup

`development/tests/integration/web_table_scroll.py --approved-browser --output <json>
--screenshots <directory>` requires separately approved browser use/provisioning.
Use the repository's CI-pinned Playwright 1.56.0 and matching Chromium; the observed
headless version was 141.0.7390.37. No product dependency or automatic gate was added.
`--skip-layout-matrix` is a focused diagnosis, explicitly identified in its output,
not full layout acceptance. `--baseline-session <file>` injects only baseline
session.js read from the base commit to isolate the former response race.

The harness uses the shipped WebHost, HTTP/security, authenticated EventSource and
assets. Only application jobs/detail observations are synthetic; no providers,
personal browser/profile, model calls, actual user sources or shared host are used.
Long-list fixtures duplicate 125 rows/cards for layout stress, not total-value
assertions. The session fixture has 120 canonical prompts and 50-row pages.
All owned browser/server work is closed in `finally` and closure is recorded.

Decision Delegate authorized session-isolated Playwright/Chromium discovery,
official dependency provisioning and this bounded loopback testing because no
integrated browser tools were exposed in the current session. This is not a claim
that the previously connected browser was disconnected or authentication failed.

## Measured checks

- Actual pending HTTP + native injected wheel: table 500→850, document 578.
  Baseline session.js then moved the document to 228. Candidate retained 578/850.
  This is a real-browser source-bound reproduction, not proof of the colleague's
  exact historical cause or a complete old-host replay.
- The 1000px/360px matrix covers Watch, Models, all Models, Sessions, deep Token
  Mix, date reports, Snapshot/Live detail and Accounts (18 view/width cases).
  Table wheel advanced 350px with stable document; PageDown/PageUp moved ±453px
  and arrows ±40px. Accounts scroll the document instead (page keys ±700px).
  Last rows/cards were reachable; sticky headers, focusable regions, filters,
  horizontal input, page overflow and boundary chaining were asserted.
- Explicit host resync retained finite-report DOM, selection, focus and offsets.
  Actual synthetic SSE publications verified Watch idle/changing rows, visible
  anchor, canonical nodes, horizontal/document offsets, selection and disclosure
  focus. These are real browser/transport checks, not actual source acquisition.
- Snapshot/Live first/middle/latest paging retained 50 rows and the whole-session
  summary. Detail selection/focus deferred revisions, release applied the pending
  revision, Freeze retained its revision, resizing worked, and reduced-motion
  transitions remained disabled. Stable-controls growth retained document and
  horizontal offsets with visible-anchor drift below 1px.
- Screenshots were inspected for readable narrow left/right columns and focus
  rings, alongside numeric sticky/overflow checks. They are browser raster proof,
  not OS/default-browser or physical-device proof.

## Native anchoring versus an unrelated jump

An initial blanket document-offset assertion failed: the existing new-activity
button label expanded controls by 47.25px at 360px; native document anchoring moved
the page 47px while the same connected row drifted only 0.25px. Focus, selection
and horizontal offset survived. This is distinct from the old unrelated 350px
response jump. The original failed run is not relabeled PASS.

Decision Delegate directed anchor-aware checks, not a production control redesign
or FR waiver: controls expansion must explain document movement by its measured
height change while preserving the visible row/focus/selection. With controls
already stable, document/horizontal offsets must stay fixed and inner adjustment
must compensate preceding-row growth. Geometry-neutral updates retain all raw
offsets. The focused rerun passed: growth moved inner scroll to 1647 while document
900 and horizontal 100 stayed fixed; visible-anchor drift was -0.25px.

## Regression and verification limits

`web_session.cjs` covers the pending response, changed visible geometry, horizontal
retention, internal-follow cancellation and idempotent detail attachment.
`web_views.cjs` covers frozen-report heartbeat DOM retention. Both new attachment
and finite-view regressions failed before their respective causal fixes.
The final full registered suite passed 115/116 test files (54.2 seconds).
`test_launcher_feedback.py` failed four Windows PowerShell 5.1 subcases: scripts
were disabled (`SecurityError` / `UnauthorizedAccess`), exit 1 rather than 9009/17.
The corresponding pwsh.exe coverage passed; intended 5.1 behavior remains
unverified, not proven pre-existing. Decision Delegate approved only this narrow
exception, conditional on relevant Web/browser checks and validator passing.
No policy or unrelated test was changed or circumvented. Package validation:
11 passes, zero failures, four existing design-budget warnings. Release notes
were shortened to preserve unchanged hard caps rather than weaken the validator.
Two registered tests also skipped their symlink cases because Windows did not
permit creating test symlinks (`test_macos_app.py`, `test_web_lifecycle.py`).

The [2026-10-29 integrated-browser measurements](web-table-scroll-browser.json)
remain historical partial evidence: 16 layout/14 trusted-wheel cases, detail and
Watch fixture retention, but inconsistent keyboard cases and unavailable native
capture. That run's full suite passed 116 files and its real-source read-only
probe observed one owner/two streams, three detail rows, frozen consistency,
normal/all-models/sessions/date reports and cancelled explicit deep history.
Those observations are not fresh long-list or physical-device proof.

Physical mouse/touchpad/touch, assistive technology and the colleague's original
installation are not verified by this headless environment. Automated trusted
browser input over synthetic observations must never be called full physical-device
acceptance. Earlier harness failures (old-route readiness, rapid document reloads
retaining SSE slots, fractional final scroll pixels and an already-latest disabled
Next button) were corrected in the harness, not masked by production input handlers.
