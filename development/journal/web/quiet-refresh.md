# Web-wide quiet refresh — FR000634

Date: 2026-11-09. Product: v80.212. Scope: presentation and safe browser lease
recovery, not new source acquisition, accounting or inference. This assessment
updates the affected Web/help module notes, not the whole architecture map.

## Decision and owners

The owner-approved FR requires **visually and accessibly silent ordinary refresh
after useful content exists**. It supersedes earlier presentation preferences for
as-of strips, retained-source help and timed refresh warnings. Initial missing
content, certified empty states, intrinsic per-metric uncertainty, explicit actions
and genuine authorization/host/provider failures retain their distinct semantics.
No delegated requirement/test exception was used for this FR.

- `app.js`, `index.html`, `app.css`, `cached-reports.js`: remove the shared passive
  refresh strip rather than hiding it; preserve report cadence/observation state.
  Quiet host-source retry also clears stale hidden banner text. Terminal host and
  authorization recovery remains a single app-owned surface.
- Reports freeze optional `ModelPromotion` facts for the actual model/offer;
  application exports only model/description/through/resumes. `render.js` puts
  one highlighted ` *` after the full relative tier chain and binds multiline
  ContextHelp to that row. No numbered Web footer or native duplicate title;
  CLI grouping/notes, rates, expiry and valuation are unchanged.
- Full/Mini global Today uses canonical `daily_ccost`, plain label/value/count,
  no help or passive source aria. A same-day missing refresh retains the usable
  amount; the configured `day_end_ms` still expires yesterday in disconnected Mini.
  Other prompt/session/account-specific cost semantics remain independent.
- Watch/Accounts retain usable card/track DOM without timed refresh prose.
  New incomplete native observations, restrictions, exhaustion and actionable
  provider/auth failures remain. A failed read cannot erase verified values.
- Earlier history keeps canonical five Full/three Mini membership and source/epoch
  producer safety; populated rows or certified empty states have no refresh footer.
- Sessions removes the finite loader and age-based hiding. One reopen per poll
  handles `catalog_expired`; without proof of old membership it safely returns to
  latest, preserving sort intent and synchronizing URL/epoch/rows/pager. Pending
  global sorts retain the previous actual header/order/pager. Initial nonusable
  responses cannot permanently pin an empty table. Late generations demote only
  their own interest. Detail retains complete usable history quietly.

## Lifecycle inspection and regression matrix

| View | Checked behavior and retained boundary |
| --- | --- |
| Models | Initial finite loader remains; loaded running/queued/delayed/scheduled/failed refresh preserves DOM/focus, no as-of strip/hidden status. Price action remains local, with factual fetched time. Filter/sort/tier/promotion mapping remains canonical. |
| Token Mix | Initial acquisition remains; loaded retained refresh has no source/catalog caveat. Intrinsic token/price semantics and exact sort remain. |
| AI Stats | Shared passive strip removed without changing FR000633 calculations, period cards or fun-first help. Retained route/period behavior stays with its existing owner. |
| Comparisons | Initial acquisition and acquired no-match remain distinct; loaded retained refresh removes partial-history/as-of process captions, not matching/population logic. |
| Full Watch | First missing/failed acquisition remains meaningful. Retained cards, daily and Earlier rows stay quiet through independent history/accounts/daily/partial delays, including virtual three-minute updates; focus/selection/disclosure/panning and real changes remain. |
| Mini/PiP | Actual hidden Document PiP, no global daily help, stable Earlier membership/AX and fit. Canonical day expiry, observed empty, offline/auth/host recovery remain. |
| Accounts | Shares Watch cards and one SSE, no route report jobs. Retained retry, native quota restrictions/idle/empty/recovery, route parity, Settings unit changes and actual host-stop SSE checked. |
| Sessions | Hour-old 50-row catalog remains visible, no bottom progress; expired first/older pages with nondefault sort reopen safely, pending sort keeps actual order. Controlled API fixture drives shipped route/DOM; backend acquisition has separate tests/probe. |
| Session detail | Retained complete history, row identity/selection, pinned chunks, running corrections and source-status silence; initial loading and actual missing/archive remain distinct. |
| Settings | No polling refresh surface added. Retained route DOM remains stable; explicit saves and actual readonly-save rollback/retry checked. Native options, theme/narrow/CSS zoom matrix, actual browser zoom 200%, keyboard/touch and capability-disabled fallback pass. No source/pricing computation moves here. |

`probe_web_help.cjs --quiet-refresh` passed **97 cases** in hidden Chrome
156.0.8078.80: nine-route DOM/AX matrix at 360/1366/1920 in Classic/Web light/Web
dark; finite-report retained refresh/failure, visibility changes and navigation;
Full/Mini daily help absence; controlled catalog expiry on offsets 0/50; detail
retention and terminal authorization surface. Nine additional promotion cases use
native keyboard focus, hover, Escape, touch and outside-dismiss, with exact multiline
model/discount/end/resume copy, trailing multi-tier star and viewport bounds.

`probe_watch_presentation.cjs` passed six theme/width cases, including the shared
quiet/loading helpers, retained numbers/heights, three virtual minutes per independent
lane, advancing actual values/new cards, focus/selection/scroll and terminal ink.
Final deterministic Full: **174 isolated files/2,134 tests, zero failing files**,
132.7 seconds, four workers. One platform skip: macOS zsh/PTY unavailable on this
Windows host. Package validation: zero failures, 11 passes, seven existing advisory
prose/module-size warnings; no hard cap/baseline increase.

Task-owned evidence: `scratch:/quiet-refresh-final.json`,
`scratch:/watch-presentation-aligned/browser.json`, `scratch:/full-tests-delivery.json`.
These are local evidence locators, not shipped user data or portable artifacts.

## Other completed evidence and limits

The earlier resumed work completed and read actual PASS artifacts for Models
refresh (240 toolbar states plus control actions), six Models layout cases,
Accounts route/quota/Settings/host-stop checks, and Mini Fit at scale/zoom 1 with
actual hidden PiP and history AX. Evidence includes `scratch:/models-refresh.json`,
`scratch:/models-layout.json`, `scratch:/accounts-live.json`, `scratch:/mini-fit.json`.
The final continuation also reran Accounts after the last quota-presentation change:
`scratch:/accounts-live-final.json` reports PASS, including Settings persistence and
actual host-stop SSE, not merely a successful PowerShell pipeline exit.

The preceding read-only real-installation `probe_web_live.py --models --daily --sessions`
completed successfully with one shared Live owner, two streams and three accounts;
no model calls or shared OpenCode stop. Sanitized observations: 2,985 catalog roots,
first page about 0.088 s, scalar indexing observed 0 to 22 (requested global metric
sort still pending); detail two rows/one chunk about 1.81 s; daily 313 requests/nine
prompts with complete prompt/cost flags and reconciliation; normal Models about
81.9 s, all-models about 2.88 s. Owned threads/processes and cleanup failures were
zero at exit. One internal daily-history error was counted despite overall probe
success; this is not a proven new defect or complete owner-incident diagnosis.

Synthetic browser replies do not prove real catalog acquisition, completed global
indexing, a full-history oracle, physical desktop/macOS/Finder, screen-reader use,
natural arrival latency or every possible source failure. Zoom evidence is split
between the existing Models toolbar, Accounts and Mini/help probes; it is not every
route at every zoom. Other older browser probes adjusted for removed surfaces were
not all rerun. No paid inference, new dependency, source/credential/config mutation,
CSRF/auth relaxation, release ZIP, tag or GitHub Release was introduced.

## Harness corrections and failed intermediate runs

Intermediate Full failures were investigated, not reported as final PASS. Removed
UI text expectations were updated while preserving numeric, membership, security
and recovery assertions. Quota arithmetic cases use separate synthetic account
identities rather than treating independent stale cases as fresh observations of
one retained account. The late second-account stale case also exposed and fixed a
remaining passive caption when useful numeric quota data already existed.

Browser fixture repairs: price-fetch coalescing now holds/releases synthetic work
explicitly; route driving uses actual hashes; Sessions capability is explicitly
synthetic and its epoch obeys the shipped 32-hex route grammar; current-day Watch
fixtures use a current configured UTC day; promotion touch targets are measured
after touch emulation, and a real Tab event restores keyboard input modality.
Those failed driver attempts did not establish a product fault or acceptance PASS.

The separate Settings probe initially required an entire long, stacked option
description to fit in a narrow 200%-zoom native picker. It now proves that both
ends are reachable in the existing native scrollport (short descriptions remain
fully bounded), without document overflow. At actual browser zoom, native keyboard
focus/Space replaces the CDP pointer-coordinate mismatch that opened the neighboring
quota picker. No Settings product behavior changed. The final
`scratch:/settings-keyboard.json` reports PASS, including real readonly-save failure
rollback, retry and native fallback. These are driver repairs, not a waived test.

A later Full run passed the changed Web/accounting surfaces but hit a Windows
`PermissionError` reading the temporary registration during the unchanged batch
restart test's atomic replacement. That test now serializes its synthetic endpoint
read/replacement with the same local lock; it still executes the real source path
and requires `SourceConcurrentChangeError` for identical-metadata generation change.
No production discovery/retry/authorization behavior was changed or assertion broadened.
The old help-lifecycle probe also still targeted the now-deliberately plain global
Today label; that obsolete target was removed, not restored as a tooltip.
Its corrected `--watch-only` run saved PASS before the host restart notification;
the saved artifact was read, not rerun. The final Full process also survived that
restart and its completed JSON and zero-failure summary were read without replay.
