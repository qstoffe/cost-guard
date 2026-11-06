# Mini Watch and finished history

## FR 000591 — owner re-scoped and returned to Ready, 2026-11-06

The owner explicitly approved the reduced click/open-fit approach and withdrew the
hands-free Live/SSE window-height requirement that had caused the 2026-11-05 On Hold.
FR000591 retains its identity and is now Ready priority 000187 (after FR000602,
before FR000597). Default Mini Watch opens at about 650 outer DIPs wide, sized to
fit actual visible content **plus two complete running-prompt rows** with no
vertical scrollbar where the work area permits. Earlier Sessions pointer/keyboard
activation grows to show expanded content and collapses/shrinks back to a compact
two-row baseline; normal passive Live updates do not resize native PiP.
Best-effort independent position/size preferences remain, using **Fit on open**
instead of misleading **Auto height** language. Native permission limits,
screen caps and manual/remembered window control are acknowledged.

The older On Hold section below remains dated historical feasibility evidence,
not the current status. FR000597 is separately clarified to use actual shipped
Settings fields and not depend on FR000591 being completed first. This is backlog
and journal publication only: no runtime code, product tests, version, release
or ordinary completion progress was changed.

## FR 000591 — On Hold feasibility, 2026-11-05

Fresh installed **Chrome 156.0.8078.80** and **Edge 156.0.4314.58** opened genuine
Document PiP in disposable strictly headless profiles through browser-input clicks.
Native `resizeTo` (+61 height) and `resizeBy` (-47 height), from both opener and PiP,
all threw `NotAllowedError`: the method requires user activation in document
picture-in-picture. Both transient activation states were inactive before and within
each call; every evaluation explicitly used `userGesture:false`. All **eight**
before/after measurements remained **531×280 outer / 509×235 inner**. Native APIs
were unmodified. This measures an API blocker, not physical Windows geometry.

[Chrome raw results](mini-auto-height-feasibility/chrome.json),
[Edge raw results](mini-auto-height-feasibility/edge.json), and
[standalone diagnostic](mini-auto-height-feasibility/probe.cjs) preserve the evidence.
The diagnostic takes absolute browser/output paths, uses only Node built-ins and a
minimal local fixture, and closes its owned browser/server. No real source, provider,
personal browser state, visible desktop or shared OpenCode service was touched.
The freshly read [specification §6.8](https://wicg.github.io/document-picture-in-picture/#resizing-the-pip-window)
corroborates the activation requirement; opening consumes activation too. Live
observers/timers do not grant it. Eligible-click fitting plus scroll therefore
cannot fulfill this FR's principal hands-free Live-resizing goal.

**Decision Delegate, not the owner**, first authorized an **FR 000591-only,
measurement-only exception** to the FR's browser-automation prohibition, constrained
to hidden genuine PiP input, unmodified APIs and verified absent activation. After
the measurements, the same delegate directed **only FR 000591 On Hold**, not partial
implementation or delivery. The original specification and local implementation
branch are retained. Release requires an explicit owner-approved click/open-fit plus
scroll fallback with disclosed geometry limitations, or an approved alternative
capable of hands-free resizing. No requirement waiver or future-task authority exists.

Independent position/size combinations, native vertical lock and physical
DPI/monitor/work-area behavior remain **UNVERIFIED**; no broad acceptance matrix was
run. No product edits, product tests/validator/live probe, version/release work,
Complete move or progress increment accompanies this development-only hold.
Architecture/user guides need no update: shipped behavior is unchanged.
The hold rationale and release prerequisite are preserved with the
[intact held FR](../../backlog/on-hold/000591-mini-watch-position-and-auto-height-sizing/HOLD.md).

## FR 000583 — v80.164, 2026-11-05

Base `30736ab6`, later backlog-only default `8147b1f9` retained. Mini's disclosure
now measures newly introduced vertical overflow directly in pointer/native-keyboard
activation. Expanded CSS can use the added space; one height-only request includes
flex-shrunk account space and a small rounding margin. Achieved bounds, not a
successful API return, enable collapse restoration. Native manual size changes
invalidate restoration; no data/render timer resizes, reopens or moves PiP.
`resizeBy(0, delta)` avoids the one-pixel width drift reproduced with `resizeTo`
at fractional scale. Both tables replace pipes with parenthesized cost at the
same natural-width, right-aligned edge. Placement modes/persistence are unchanged.

The original Watch source was freshly executed in the deterministic DOM harness:
`retrying` rendered `Retrying prompt refresh; retained contents are not current.`;
`refreshing` added `(refreshing; retained total)` beside cost `4583`. Both paths
now remain quiet during brief refreshes, including the equivalent top source retry
message. Empty status paragraphs are hidden. Cost help retains source provenance;
30 continuous seconds of retry/refresh produces meaningful delayed/not-current
guidance. Recovery resets these presentation-only clocks; unavailable/partial,
host/auth/connection and canonical lifecycle/accounting states are not suppressed.

### Verification and limitations

- Local Full: **141 bounded units, 1659 passed tests, one platform skip, zero
  failures, 89.9s**. An earlier concurrent Full/browser run failed the unrelated
  872-root fixture's catalog-count assertion (four versus two/three); after reading
  its real-time hint-expiry-sensitive assertion, the complete unchanged suite was
  rerun without browser load and passed. No test, timeout, cap or dependency weakened.
- Working-tree validator: **11 passes, zero failures**, six existing advisory
  prose/Python design warnings. No release archive generated.
- Actual hidden **Chrome 156.0.8078.80** at scales 1 / 1.5 and **Edge 156.0.4314.58**
  at 1.5: **113 layout cases, 18 grouped checks per run**, shipped HTTP/auth/CSP/SSE.
  Pointer and Enter activation grow once, preserve width and restore bounds without
  accumulated drift; e.g. at 1.5 outer **560×300 → 560×388 → 560×300**, inner
  **538×255 → 538×342 → 538×255**, expanded session **159/159px** viewport/content.
  Fit/existing-scroll/horizontal-only, manual native/CDP bounds, real absent user
  activation, unsupported/refused/no-change and simulated short-work-area partial
  clamps preserve disclosure/scrolling. SSE/history changes never resize. Native
  placement/reload/process restart, Classic/Web light/dark, units, title ellipsis,
  sticky headings, narrow windows and one EventSource continue to pass.
- Five actual Watch DOM refresh cycles preserve exact card heights and prompt/session
  figures for active/history cards. Virtual 30-second delays, unavailable source and
  recovery show truthful statuses. This is synthetic browser evidence, not an outage
  injected into the user's running service.
- Read-only installed V2: session-cost report parity for four requests/all priced,
  zero fresh valuations/cache writes/inference; one owner/two streams, three accounts,
  14.1498s and no remaining owned threads/processes or cleanup failures. One history
  batch failed and Daily was unpublished: this probe does **not** prove complete
  history/Daily health. Shared OpenCode and the ordinary checkout were untouched.
- An **additional exploratory scale-2** run stopped in the existing placement test,
  before new feature checks: browser clamped the requested 500×340 to 436×296.
  It is **not a scale-2 PASS**. Required Chrome/Edge actual-PiP and fallback checks
  above passed; no physical monitor, manual-drag/native-frame, touch hardware,
  screen-reader or macOS acceptance is claimed. No requirement/test exception was
  requested or granted.

[Compact browser measurements and full per-unit test report](../../architecture/governance/verification/watch-disclosure-refresh/).
Owner/module docs updated in place; no acquisition, valuation or layer-boundary change.

## FR 000579 — v80.159, 2026-11-04

Base: `34522ecb25a8aee0629f456068ddc02671de2aac`; later default additions were
backlog-only and retained. **Fresh reproduction, before design:** in hidden Chrome
156.0.8078.80, the owner naturally reported light and Mini dark. Both had Web selected
and the expected shared/Mini stylesheets, but owner/mini backgrounds were respectively
`#eef2f8` / `#0c1422`; ink, panels, headers and quota roles disagreed too. Attribute
copying alone was insufficient. Classic's forced-dark roles matched both documents.
[Before/after computed facts and Classic comparison](../../architecture/governance/verification/mini-web-theme/reproduction.json).

The Mini controller now applies the effective theme before styles/content and copies
the owner's computed custom properties only for Web. Content `color-scheme` follows
the owner's media result. Settings and owner media-change events resynchronize directly,
without another publication, report refresh or live connection; close/replacement
removes the listener. Classic clears every inherited Web override and retains its
original CSS. Web-only canvas/quota-panel/empty/scrollbar rules reuse semantic roles,
not a duplicated hardcoded palette. Main Web, compact grid/geometry, native controls,
valuation and acquisition are unchanged. Module/user docs updated; no boundary/flow change.

### Verification and limits

- **PASS:** new VM palette assertion first failed against old production; opening,
  owner-media-only changes, Web/Classic round trips and listener release/reopen pass.
  [Full local suite](../../architecture/governance/verification/mini-web-theme/full-tests.txt):
  140 bounded units, four workers, **92.1s**, zero failures.
- **PASS:** [validator](../../architecture/governance/verification/mini-web-theme/validation.txt),
  11 passes, zero failures, six existing advisory prose/Python design warnings.
  No assertion, cap, deadline or dependency weakened.
- **PASS:** hidden actual Document PiP in [Chrome 156.0.8078.80](../../architecture/governance/verification/mini-web-theme/chrome.json)
  and [Edge 156.0.4314.58](../../architecture/governance/verification/mini-web-theme/edge.json),
  emulated device scale 1.5, shipped HTTP/auth/CSP/SSE, **108 layout cases each**.
  Owner and PiP preferences are deliberately opposite: all owner roles, actual canvas,
  table/header/help/controls/status/quota colors, text contrast, semantic scrollbars,
  media-only updates and Default/Classic/Web round trips pass. Keyed rows/disclosure,
  keyboard focus/popovers, standard compact/native-API narrow resizing and one SSE remain.
  Prior pipe-alignment/units/density/independent-scroll/sticky/retention/lifecycle cases pass.
  [Compact light/help](../../architecture/governance/verification/mini-web-theme/chrome-theme-owner-web-light-560.png),
  [narrow dark/help](../../architecture/governance/verification/mini-web-theme/chrome-theme-owner-web-dark-280.png).
- **PASS:** exact Classic baseline, all computed properties on **15 representative
  elements**, sampled tokens, stylesheet URLs and inner dimensions; identical synthetic
  content/browser before and after. This compares app-controlled content, not native frames.
- **PASS:** [read-only installed V2](../../architecture/governance/verification/mini-web-theme/mini-source.txt),
  64 coherent publications, one running prompt, three accounts/two period costs,
  four known-finish history cards, **26.068s**, owned close **0.151s**. No inference
  or shared OpenCode stop/mutation.

The integrated browser was disconnected; owned hidden browsers provided adequate
app-content evidence. System preference is emulated and narrow windows use the native
PiP resize API, not physical manual dragging/OS settings. Native chrome recoloring is
out of scope; actual OS frame rendering, screen-reader speech and macOS pixels remain
unverified. No task/test exception requested or granted and no physical proof claimed.

## FR 000578 — v80.158, 2026-11-04

Base: `57f2505fcf9f7365a8ce4eb28e23f894d21c7770`. Both first headers now reuse
the row's two-region grid: Session stays left, `| Total CCost` stays right, and
each row uses `| amount`. Header tracks retain both labels' intrinsic minima;
row suffixes use their own natural text width rather than a header-sized block.
Only session titles ellipsize. One physical first column, canonical display/cost
scope, focus/hover/click help, other metrics and shared scrolling remain intact.
There is no acquisition, accounting, SSE, window-geometry or full-Watch change.

### Verification

- **PASS:** local Full, **140 bounded units, zero failures, 91.6s**, four workers;
  **1663 tests passed, one standard Windows platform skip** (zsh/PTY unavailable;
  native macOS CI owns shell execution). [Per-unit report](../../architecture/governance/verification/mini-session-alignment/full-tests.json).
  The new VM heading/separator assertions first failed against old production code.
  Both tables cover actual zero/loading/unavailable/partial/retained cost states,
  full canonical title/ID, concurrent prompts, disclosure/row identity and units.
- **PASS:** working-tree validation: 11 passes, zero failures; six existing advisory
  prose/Python design warnings. No dependency, assertion, cap or timeout weakened.
- **PASS:** actual hidden [Chrome 156.0.8078.80](../../architecture/governance/verification/mini-session-alignment/chrome.json)
  and [Edge 156.0.4314.58](../../architecture/governance/verification/mini-session-alignment/edge.json),
  emulated device scale 1.5, shipped HTTP/auth/CSP/SSE and real Document PiP.
  Each run records 91 layout cases, including 54 new width/font/zoom/theme/unit combinations:
  560/800/280 outer-width requests (browser clamps permitted), 100/150% root font or 125% CSS zoom,
  Classic/Web light/dark and Credits/USD. Rectangles/ranges prove both cell edges,
  natural suffix width, title-only ellipsis, full header/cost visibility, flexible
  space, fallback IDs and unchanged row identity. Extreme narrowing/CSS zoom pans the region,
  not the page. Existing keyboard disclosure/title popover, sticky headers, shared
  vertical scrolling, live updates, reopening and single-EventSource checks pass.
  [Light screenshot](../../architecture/governance/verification/mini-session-alignment/chrome-web-light.png)
  inspected: Session flush left, pipe/full total flush right in each first cell.
  Initial probe failures were causal test selectors now matching the reused header
  classes, a new matrix not restoring disclosure state, and mouse checks aiming beneath
  a sticky header after focus scrolling / leaving pointer modality for a later keyboard
  outline check. Selectors are now TD-scoped; the matrix restores its input state,
  pointer targets use the painted visible cell intersection and a real Tab restores
  keyboard modality. Native hidden hover/click/title-help checks pass; no product workaround.
- **PASS, limited scope:** [read-only installed V2 probe](../../architecture/governance/verification/mini-session-alignment/live-probe.txt),
  `probe_web_live.py --watch-cards --session-cost`:
  four requests/all priced, independent report parity, zero fresh repository
  valuations, cache writes false, no inference. One acquisition owner, two streams,
  three accounts, one active/one history card; 13.9005s, owned close 0.1053s,
  zero pending owned threads/processes or cleanup failures. One history-batch read
  error and no Daily publication were observed: full history/Daily completeness
  is **not** established. Shared OpenCode and running Web Beta were untouched.

Architecture module and current user guide updated in place. This presentation-only
FR needs no new boundary or broader journal assessment. No requirement/test exception
was requested or granted. Physical Windows DPI/native chrome, manual OS input,
actual browser page zoom and screen-reader speech were not exercised; CSS zoom/enlarged font and
headless DOM/accessibility evidence are not those proofs. No release ZIP/tag/Release.

## FR 000576 — v80.156, 2026-11-04

Base: `c905df332071c5eff69f6aed8654d2c73f7f1372`. Three Web Settings dropdowns
retain symbolic Default versus explicit choices independently of effective values.
The canonical config enums resolve `default` against shipped defaults before regular
consumers; the nested sentinel bypasses retained legacy `webTheme`. The preserving
JSONC/atomic-write owner and HTTP guards are unchanged. API responses expose
`webSettings`, `webSettingsChoices` and `webSettingsDefaults`; UI labels derive from
the last, not hardcoded default names. Failed saves restore confirmed intent;
an unconfirmed first read cannot enable settings writes or Mini opening.

Mini requests the unchanged 560×250 DIPs with initial placement on first opening
per opener/host nonce, then permits browser-native bounds reuse for Remember last.
Standard always prefers initial placement. No geometry getter, persistence or native
window-management bridge is added to production. A mode switch never touches open
PiP. Reload/navigation/new tabs start standard, even while the server lives; this
is deliberately a live-opener scope, not cross-tab/server-wide geometry retention.
The reload test proves our explicit first-open request, not independent cache clearing.

### Verification

- **PASS:** local Full, **140 bounded units, zero failures, 83.4s**, four workers;
  **1659 tests passed, one standard platform skip** (zsh/PTY on Windows, macOS CI owns
  shell execution). [Per-unit report](../../architecture/governance/verification/mini-placement/full-tests.json).
  Config tests cover unsupported enums, legacy precedence, missing/default/explicit
  intent, future changed defaults and independent pinning. Settings tests retain
  JSONC bytes/comments, authenticated allowlists, Origin/CSRF/body validation,
  stopping/editor conflicts, no-create reads, honest rollback and focus.
- **PASS:** working-tree validator: **11 passes, zero failures, six existing advisory
  prose/Python design warnings**. No dependency, cap, timeout or assertion was weakened.
- **PASS:** final actual hidden [Chrome 156.0.8078.80](../../architecture/governance/verification/mini-placement/chrome-placement.json)
  and [Edge 156.0.4314.58](../../architecture/governance/verification/mini-placement/edge-placement.json),
  **emulated scale 1.5**, shipped HTTP/auth/CSP/SSE and real Document PiP. Native CDP
  bounds were changed to `(80,90,500,340)` and both position/dimensions returned after
  app-close and `Window.close()`/pagehide. Standard reset to the original lower-right-like
  bounds each time; current-window bounds remained unchanged when selecting modes.
  The 560×250 request retains width/height in both modes. Initial 700×400 test bounds
  hit the browser's 634×362 work-area maximum; the final probe uses supported 500×340
  bounds and at most two DIPs of scale-rounding tolerance, not a product workaround.
- **PASS:** a real Python fixture subprocess exits/restarts using the same disposable
  user-config directory and browser profile. New nonce/random-port origin, persisted
  explicit Theme/CCost/mode, standard first opening and later remembered bounds are
  checked. Opener reload on the original same host also starts standard and then
  remembers. Browser local/session storage stays empty. No geometry file/setting exists.
  VM independently checks a changed host nonce in the same controller, canceled/rejected
  opens, delayed callbacks, first-open flags, next-opening mode changes and native closes.
- **PASS:** three real selects and exact option order/labels, Default and explicit saves,
  immediate Theme/USD propagation to open Mini, single EventSource, historical table,
  keyboard/scroll, narrow windows, light/dark layouts and host stop remain verified.
  [Settings screenshot](../../architecture/governance/verification/mini-placement/chrome-placement-settings.png)
  inspected: one column, all three controls readable. Rendered-headless proof is not physical DPI proof.
- **PASS, limited scope:** read-only installed V2 `probe_web_live.py --watch-cards`,
  one acquisition owner, two streams, three accounts, one active/two history cards;
  **7.0461s**, owned close **0.2511s**, no pending owned threads/processes or cleanup
  failures. One history-read error was observed and Daily was not published; this
  check does **not** claim Daily/history completeness. Shared OpenCode/running Web
  Beta were untouched; no inference or real-user settings write.

Architecture overview/module/code map and current user guides updated in place;
no acquisition, accounting, CLI, connection, CSS/layout or process-owner change.
Product metadata advances to v80.156; no release ZIP/tag/Release is produced.

### Decision Delegate-approved verification and scope exception

On 2026-11-04 the foreground **Decision Delegate**, after read-only inspection of
the FR/controller/probes/restart fixture/lifecycle tests, authorized **FR 000576 only**:
omit fresh physical Windows-150% manual move/resize, native-X clicks, frame/display-edge
measurements and monitor/work-area changes, and accept remembering only within the
same live opener and server instance. Reload/navigation/new tabs begin standard.
The decider was **Decision Delegate, not the user**; no visible-desktop permission
was granted and no visible probe ran. Reason: adequate hidden real Chrome/Edge API/cache
evidence avoids disruptive reassurance or unsupported native geometry workarounds.

**UNVERIFIED:** physical DPI/frames, manual/native-X interaction, monitor transitions
and untested browsers/platforms. CDP bounds changes are not manual Windows dragging;
`Window.close()`/pagehide is not a physical X click. Historical native measurements
remain historical. The decision required Full, validator and normal exact-HEAD GitHub
checks; it waived no functional failure, security/Git protection or other requirement,
and grants no future-FR authority. Completion is limited to this documented scope,
not a claim of full physical acceptance.

### Decision Delegate-approved queued ARM CI exception

The same foreground **Decision Delegate**, not the user, explicitly narrowed the
normal exact-HEAD-check condition for **FR 000576 / PR 159 only**. On original HEAD
`1ef72a4b4763b5cfea5bc8fb379e01cd25026406`, [run 41903154630](https://github.com/qstoffe/cost-guard/actions/runs/41903154630)
passed common Linux (Full/validator/rendered browser), Windows2025 and Intel macOS15.
At 20:13:27Z, ARM `native (macos-15)` job `126830653328` was still queued since
20:05:03Z with no assigned runner, no conclusion and no observed failure. Fresh
main protection/rules reads showed no required contexts/rules; nothing was bypassed.

The delegate permitted merge while that ARM job is **queued, unassigned and the sole
missing check**, and extended this precise exception to the reporting-only successor
recording this paragraph/completion, with unchanged product/tests/config/workflow and
effective base. **All other checks must succeed on that successor's exact HEAD**;
original successes are not successor PASS. If ARM starts, its bounded execution must
finish; any failure, timeout, unexpected cancellation or other missing result requires
repair or renewed consideration. No manual cancellation/rerun, runner/workflow change,
force/protection bypass or future-FR waiver is authorized. Normal automatic CI
supersession from this reporting push is not evidence of failure concealment.

Reason: the missing native AppKit/launcher/lifecycle check does not own the changed
settings/PiP behavior; local plus Linux/browser, Windows and Intel-macOS evidence is
adequate without indefinite unassigned-runner waiting. **ARM-native execution remains
UNVERIFIED and the queue cause unknown**, not an established outage. Later CI outcomes
belong in the PR/run/final handoff; no additional reporting commit/CI loop is required.

## FR 000574 — v80.154, 2026-11-04

Base: `7df4a6a9a8c826f537970c4348c872bdb8fb4381`. Mini consumes the existing
`session_summary.cost/context` and canonical ascending `history_cards`, without
changing the server projection, valuation/cache, lifecycle or acquisition owners.
The first cell's grid reserves a nonshrinking full-session-cost suffix and only
ellipsizes the title. Focus/hover/click exposes the complete title and cost scope
in a native top-layer popover. The neutral Earlier Sessions disclosure starts
collapsed per PiP document, retains its choice across publications, and puts up to
three newest eligible session-distinct rows above running prompts in one bounded
scroll region. Accounts retain independent scrolling; opening remains 560×250 DIPs.

### Verification

- **PASS:** final local Full, **139 bounded units, zero failures, 84.9s**, four workers;
  [per-unit report](../../architecture/governance/verification/mini-session-tables/full-tests.json).
  **1653 tests passed; one standard platform skip**: macOS zsh/PTY execution unavailable
  on this Windows host (native macOS CI owns that test).
  The initial Full overlapped both browsers and real-source work and failed an existing
  872-root catalog-count assertion (4 versus 2/3) in the two-second catalog-reuse path.
  A focused run passed that individual case but its whole file exceeded the default
  25s focused-run timeout; the final standard Full, with its unchanged 240s unit bound
  and no competing probes, passed the scale class in 30.74s. No product/test deadline,
  assertion, source behavior, dependency or budget was weakened. Contention is the
  observed association, not a claim that the historical timing sensitivity is repaired.
- **PASS:** working-tree validation, **11 passes, zero failures, six existing advisory
  prose/Python design warnings**. Focused Mini has seven tests, including whole-session
  versus prompt/current-session-context scope, concurrent totals, units and partial coverage.
- **PASS:** final hidden [Chrome 156.0.8078.80](../../architecture/governance/verification/mini-session-tables/chrome.json)
  and [Edge 156.0.4314.58](../../architecture/governance/verification/mini-session-tables/edge.json),
  **emulated device scale 1.5**, shipped HTTP/CSP/auth/SSE and actual Document PiP.
  Zero/one/three/five eligible sessions, zero/one/twelve running prompts, newest-three
  ordering, no active/history duplicates (VM), full-cost visibility, metric minima,
  partial/unknown/zero/retained states, focus/row identity, Enter/Space disclosure,
  real Ctrl+Home/PageDown region scrolling and visible full-title focus popover pass.
  Expanded Classic/Web light/dark, enlarged font, native-API narrow resizing and
  no page overflow are checked; screenshot inspection caught generic section-card
  styling, now fully reset (including shadow). Sticky headings remain table-scoped,
  every running row is reachable, toggle never changes PiP dimensions, reopen
  collapses history, and exactly one EventSource remains. An initial probe race
  accepted the prior three-row publication during a five-history update; waiting for
  the actual source history count fixed the probe without weakening expected IDs.
  [Expanded light](../../architecture/governance/verification/mini-session-tables/chrome-web-light.png),
  [dark](../../architecture/governance/verification/mini-session-tables/chrome-web-dark.png),
  [narrow](../../architecture/governance/verification/mini-session-tables/chrome-earlier-narrow.png).
- **PASS:** read-only installed V2 `probe_web_live.py --watch-cards --session-cost`:
  stable session **4 requests/all priced**, independent report parity, fresh repository
  valuations **0**, cache writes **false**. One acquisition owner, two streams, three
  accounts, **13.204s** overall, owned close **0.1302s**, no pending owned threads/processes
  or cleanup failures. No model inference or shared OpenCode stop/mutation.

Architecture: module contract/code map updated in place; no boundary/flow change.
User guides distinguish full-session, prompt, daily and native-period costs. Existing
cache/correction/compaction/child/provisional/no-op tests retain semantic ownership.

### Decision Delegate-approved verification exception

The foreground **Decision Delegate** approved an **FR 000574-only** exception,
conditional on final Full/validator/browser and normal PR verification: omit fresh
physical **Windows-150% PiP rendering/native-chrome observation** and actual
**screen-reader speech**. Hidden real PiP tests use **emulated device scale 1.5**;
font enlargement is not browser zoom or physical Windows scaling. Actual OS DPI/frame
rendering and assistive announcements remain **unverified**. Historical native
measurements are context, not fresh proof of the changed tables. Adequate hidden
layout/input and installed-source evidence did not justify disruptive reassurance.
No visible probe ran and no desktop permission was granted. Functional behavior,
failing tests, CI and Git protections were not waived; no future-task exception applies.

## FR 000571 — v80.151, 2026-11-04

Base: `711e45b21ef6c9d5ff84f02653205f2a0efdea56`. Mini passes its already-formatted
CTX display token directly to the cell, without adding `~` or stripping source
characters. The estimate tooltip/table accessible description and N/A remain intact.
Mini's initial/loading/observed daily heading and full Watch's visible/accessible
daily heading are now **CCost Today**. No acquisition, accounting, Token Mix, full
Watch context, layout/CSS, geometry, window control or SSE ownership change.

- **PASS:** new VM assertions first failed against the old CTX prefix and daily
  accessible name, then passed after the presentation-only fix. Mini covers grouped
  values, numeric changes, zero, N/A, missing context and source-owned characters;
  existing currency, retention, rollover, outcomes and focus/identity checks remain.
  Full Watch pins all four Token Mix categories/order plus partial/retained/unavailable
  and loading daily headings, numeric values and accessible name.
- **PASS:** local Full, **138 bounded units, zero failures, 90.5s**, four workers.
  Working-tree validation: **11 passes, zero failures**, six existing advisory
  prose/Python design-budget warnings; caps, assertions and dependencies unchanged.
- **PASS:** [headless Chrome 156.0.8078.80](../../architecture/governance/verification/mini-watch-labels/chrome.json)
  and [Edge 156.0.4314.58](../../architecture/governance/verification/mini-watch-labels/edge.json),
  emulated scale **1.5**, shipped HTTP/CSP/SSE and real Document PiP. Both check CTX
  text/updates/unknowns, tooltip/table meaning, daily loading text and full-Watch
  visible/accessible name, intrinsic/narrow scrolling, alignment, themes/units,
  retained states, keyboard behavior, reopen and exactly one EventSource. The new
  initial-context assertion first assumed N/A; the fixture actually projects `120k`.
  Correcting that independent expectation required no production change.
- **PASS:** read-only installed **V2** Watch/Daily probe: 568 observed requests,
  11 initiating prompts, complete pricing and reconciled category costs; prompt-count
  completeness was **false**, preserved rather than overstated. Two active/two history
  cards, three accounts, single acquisition owner; **14.5121s**, owned close **0.1076s**,
  no pending owned threads/processes or cleanup failures. Shared OpenCode was untouched;
  no model inference or running Web Beta mutation.

Architecture assessment: no boundary/flow update; current Watch module wording and
user guides updated. Browser evidence is synthetic/headless, not physical OS geometry,
native chrome, screen-reader or physical macOS proof; those surfaces were not changed.

### Decision Delegate-approved CI exception

The **Decision Delegate** explicitly authorized FR 000571 / PR 154 delivery without
completed `native (macos-15-intel)` verification while it remains queued without a
runner and is the sole missing check. On implementation/tested SHA
`0fbd02a09a8fb794f69e2da3ace0ff0aa4678c6b`, [run 41874147908](https://github.com/qstoffe/cost-guard/actions/runs/41874147908)
passed common Linux (Full/validator/browser), Windows 2025 and macOS 15 ARM. Intel
job `126728878795` stayed queued after eight minutes of foreground waiting and a
fresh read; no failure or outage was established. Fresh default protection/rules
reads showed no required checks or branch rules; none were changed or bypassed.

Reason: the missing job tests unchanged native launchers/lifecycle/AppKit/compilation,
not Watch rendering; local Full/browser plus the three passing CI jobs provide
adequate task-specific proof. **Intel-native behavior remains unverified**, not PASS.
The delegate specifically authorized correcting this journal/completion report even
though a reporting-only push retriggers CI, extending only the queued Intel exception
to that successor; all other checks and normal exact-HEAD merge guards remain.
No failed check, force/protection bypass, workflow edit, cancellation, duplicate rerun
or future-FR exception is authorized. If Intel starts, allow bounded foreground
completion; if it passes no missing-result exception is needed at merge. Any failed
check requires renewed consultation with changed evidence. No owner question/hold.

## FR 000570 — v80.150, 2026-11-04

Base: `ce7859fcb8df3fe713c85519a7739242fc60fe6c`. Mini's independent document now
adds one `rel=icon`, `type=image/x-icon` link to the existing absolute same-origin
`/favicon-cg1.ico` before its stylesheets. No new artwork, route, dependency,
native bridge, acquisition owner, CSP exception or browser/OS grouping change.
Normal-tab/tray branding and the 560×250-DIP opening/controls remain unchanged.

### Native feasibility, before implementation

An owned disposable **Chrome 156.0.8078.80** profile, synthetic shipped loopback
HTTP/SSE and hidden helpers ran on **Windows build 26300, actual DPI 144 / 150%**.
No zoom/display settings or personal browser state were changed. Read-only,
exact-browser-PID `WM_GETICON` queries succeeded for all three PiP icon sizes.
On the **same HWND**, adding the link changed the generic globe to recognizable
CG; immediate attachment during the API's enter event and reopening gave identical
CG icon pixels on a new HWND. Class fallback icons and the normal Chrome window
were unchanged. Borrowed HICONs were not destroyed or modified. Browser resampling
means the canonical ICO's rendered pixels need not equal the browser's HICON hash.

- [Baseline native large icon](../../architecture/governance/verification/mini-watch-icon/native/baseline-459438-large.png)
  → [same-window CG icon](../../architecture/governance/verification/mini-watch-icon/native/delayed-link-459438-large.png).
- [Native frame](../../architecture/governance/verification/mini-watch-icon/native/delayed-link-459438-frame.png):
  origin/security, return and close controls intact; raw height **437px**, DWM-visible
  height **428px**. This frame capture is not a taskbar or Alt+Tab screenshot.
- [Raw results and all linked native captures](../../architecture/governance/verification/mini-watch-icon/native/result.json).
  Retained probe sources describe the owned-PID method; they are experiment records,
  not an automatically authorized native check. Native visible runtime was **4.551s**.
  The probe's `streams: 0` counts matching owner-document DOM, **not SSE connections**.

### Final-controller regressions

- **PASS:** local Full, **138 bounded units, 88.4s**, four workers. Working-tree
  validation: **11 passes, zero failures**, six pre-existing advisory prose/Python
  design-budget warnings; no caps, assertions, product deadlines or dependencies changed.
- **PASS:** real installed **V2** read-only acquisition, **seven coherent publications**,
  two running prompts, three accounts/two available primary-period costs, two known-finish
  cards; **9.567s**, owned close **0.126s**. No inference or shared OpenCode stop.
- Focused Mini VM, HTTP/favicon/CSP and Windows shared-icon regressions passed.
  VM checks the exact absolute link, independent per-window nodes, reopen and unchanged
  owner head alongside existing race, policy, geometry, theme and retained-data cases.
- Final shipped controller, **without candidate injection**, passed real **headless**
  [Chrome](../../architecture/governance/verification/mini-watch-icon/browser/chrome.json)
  and [Edge 156.0.4314.58](../../architecture/governance/verification/mini-watch-icon/browser/edge.json)
  at **emulated scale 1.5**. Both fetch the ICO through the favicon loader on initial
  open/reopen and preserve styles/CSP, normal-tab icon, controls/API identity, geometry,
  hidden-opener updates, terminal lifecycle and **exactly one EventSource**. Headless
  document captures and emulated scale are not physical native proof.

### Scoped Decision Delegate verification exception

The **Decision Delegate**, not the owner, authorized the crucial finite Chrome-only
native feasibility probe after non-disruptive alternatives could not establish native
adoption. After independently reading its JSON and four images, the same delegate
approved protected delivery **with an FR 000570-only verification exception**:
omit actual **taskbar-preview, Alt+Tab and grouping observation** because the proven
native-icon change and narrow link-only fix do not justify disruptive shell interaction.
Unused visible authorization ended; final code is checked only through hidden browsers.

**Verified:** Chrome's native small/large PiP HICON adoption at actual Windows 150%.
**UNVERIFIED:** actual shell taskbar-preview/Alt+Tab rendering and grouping, native
Edge and macOS. Shell caching/browser/OS-specific representation remains uncertain;
untested platforms are not declared unsupported. This is **delivery with an approved
verification exception**, not unconditional primary/full acceptance PASS. No behavior,
failing-test or future-FR exception was granted; legitimate continuation retains this
scope unless superseded. No shared desktop input, taskbar hover/Alt+Tab invocation,
unrelated-window capture or native-window mutation occurred.

## FR 000569 — v80.149, 2026-11-04

Base: `99e8940206177a2dc46c525a7babb67fc9ec2e71`. Mini-only presentation policy;
full Watch, accounting, polling, one-SSE ownership and 560×250-DIP opening are unchanged.

- Auto-layout metric columns contribute full intrinsic nowrap minima; their 1% width
  preference prevents taking spare space. Zero-intrinsic Session/empty spans leave
  the remaining width to Session, whose heading still sets its minimum. Only session
  titles ellipsize; insufficient native viewport width scrolls the prompt region.
- Controller-owned presentation retention survives closing/reopening Mini. Coherent
  prompt publications, Daily's actual `observed_at_ms` and each native quota's own
  observation clock independently detect ten continuous minutes without usable data.
  Repeated snapshots/retries cannot reset them; pricing incompleteness is not itself
  an operational warning. One muted notice replaces short-lived orange warning spam;
  definitive host/auth/identity failures remain immediately actionable. Numeric unknowns,
  restriction/exhaustion and prompt outcome colors remain truthful.
- Partial prompt reads retain unmatched rows, while individually valid card corrections
  still apply; an observed empty set removes rows normally. Failed quota reads retain
  usable native values. Canonical null Daily clears retention on rollover. Additive
  presentation-only `daily_usage.day_end_ms` uses configured timezone/DST to expire
  yesterday's Total Today even without a new publication; no usage is extrapolated.
  Tooltips/accessible descriptions retain observation times and partial/retained state.

### Executed verification

- **PASS:** final local Full, **138 bounded units, 82.9s**, four workers; focused
  Mini/lifecycle/historical regressions: 15 tests, 7.068s. Initial Full failed two
  lifecycle units because the new day-end projection called a display formatter that
  intentionally maps epoch dates to `unknown`. Direct configured-timezone date
  conversion fixes the cause; new zero/negative-epoch and 23/25-hour DST cases pass.
  No assertion, product deadline or test requirement was weakened.
- **PASS:** working-tree validator, 11 checks, zero failures; six existing advisory
  prose/Python design-budget warnings. No hard caps, dependencies or archives added.
- **PASS:** real headless Chrome **156.0.8078.80** at emulated scales **1 and 1.5**,
  and Edge **156.0.4314.58** at **1.5**. Shipped HTTP/CSP/auth/SSE and real Document PiP
  verify default opening, metric growth/shrink, long titles, N/A/approximation/partial
  strings, empty colspan, centered headings, semantic data alignment, sticky/independent
  scrolling, real native-API narrow resizing, Credits/USD, Classic/Web light/dark,
  keyboard focus, hidden-opener updates, retained/empty/recovery/terminal behavior and
  one EventSource. Each measured metric width matches the maximum header/cell DOM
  Range width plus padding/borders within **1.1 CSS px**. Narrow large metrics scroll
  internally without document overflow. VM clocks cover 599999/600000ms, unrelated
  healthy lanes not hiding Daily failure, genuine recovery, no fabricated initial
  values and disconnected configured-day rollover.
- **PASS:** read-only real installed **V2** acquisition: three coherent publications,
  one running prompt, three accounts/one primary-period cost, two known-finish cards;
  **4.442s**, owned close **0.114s**. No model inference/shared OpenCode stop.
- Retained synthetic evidence: [Chrome raw layout/check results](../../architecture/governance/verification/mini-watch-quiet/mini-chrome-final.json),
  [Edge results](../../architecture/governance/verification/mini-watch-quiet/mini-edge.json),
  [Edge dark viewport](../../architecture/governance/verification/mini-watch-quiet/mini-edge-web-dark.png).
  These screenshots were inspected and are **headless document captures**, not native
  Windows frame or physical monitor proof.

### Scoped Decision Delegate exception

The **Decision Delegate**, not the owner, approved omitting the actual physical
Windows-150% portion of acceptance criterion 2 **for FR 000569 only**, valid through
same-task continuation unless superseded. System DPI was independently read as
**144 (150%)**, but browser device scale **1.5 was explicitly emulated**, not native
physical proof. Real headless layout/native-API checks are adequate for these
presentation changes; additional visible proof is reassurance, not crucial enough
to justify desktop disruption. The delegate explicitly said **do not run the visible
native probe**. No earlier FR 000565 permission was reused; no future blanket exception
or desktop authorization is granted. Physical PiP rendering/native chrome, minimized
restoration and screen-reader speech remain **unverified**, not PASS. Functional
content-fit, alignment, scrolling and accessible-description requirements are **not
waived**, and **no failing-test exception** was granted.

## FR 000565 — v80.145, 2026-11-03

Base: `6c99e65cc9e4dc0dccd9d2302f50fbd89392a8d9`. Only Mini presentation changes;
the full Watch layout, accounting, acquisition and one EventSource remain unchanged.
The right, non-clickable header reads the exact full Watch `daily_usage.total` and
`prompt_count`, including pre-Watch activity, through existing unit display tokens.
Missing pricing is N/A, real zero stays zero, partial coverage and retained/not-current
states remain explicit. Corrections and the next canonical local day replace values.
All five headings are centered; title data stays left and numeric data right. The
compact header overrides full-page header padding/background, preserving readable
health text and independently scrollable prompt/account regions at reduced height.

### Native physical geometry, not requested-height proof

Executed on this workstation's actual **Windows DPI 144 / 150%**, installed
**Chrome 156.0.8078.80**, with an owned disposable profile and synthetic loopback data.
No display settings or personal browser state were changed. Genuine browser zoom was
set/read through Chrome's own `settingsPrivate` default-zoom API, not CSS/pinch/DPR
emulation. Fresh profiles have no per-origin override. `visualViewport.scale` was 1.
The visible native PiP HWND inherited the owner page title, not its document title;
the helper identifies a new visible HWND in the launched browser's exact PID.

| Case | Requested height (screen DIPs) | Browser zoom | DOM innerHeight (CSS px) | DOM outerHeight (screen DIPs) | DPR | GetWindowRect / capture height (physical px) | DWM visible height (physical px) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Unchanged baseline | 450 | 100% | 451 | 492 | 1.5 | 738 | **729** |
| Unchanged baseline | 450 | 80% | 562 | 492 | 1.2000000477 | 737 | **728** |
| Corrected first open | 250 | 80% | 312 | 292 | 1.2000000477 | 437 | **428** |
| Corrected first open | 250 | 100% | 250 | 292 | 1.5 | 437 | **428** |
| Corrected first open | 250 | 125% | 201 | 292 | 1.875 | 438 | **429** |
| Corrected first open | 250 | 150% | 167 | 292 | 2.25 | 438 | **429** |
| Reopen, dense/warnings | 250 | 80/100/125/150% | 312/250/200/166 | 292 | as above | 437 | **428** |

Native measurement runs per-monitor-DPI-aware. Baseline client geometry was
841×727 physical px; corrected 100%-zoom client geometry was 839×426. Win32 client
area includes browser-drawn PiP chrome, not just the document. At baseline 100% zoom,
451 CSS px × DPR 1.5 = 676.5 physical document pixels; the 729px visible frame adds
about **52.5 physical pixels** of native chrome/frame. At corrected 100% zoom,
250×1.5 = 375 physical document pixels, plus about **53** = 428 visible pixels.
GetWindowRect/capture includes an additional 9px invisible bottom resize border.
Rounding explains roughly 1px variation; it is not subtracted to manufacture a pass.
Even the larger raw capture bounds remain <=438, safely below 470.

This reproduces and explains the owner's ~725–730px report. Chromium's opening
request is in **screen DIPs**, independent of page zoom; zoom changes CSS innerHeight
and DPR together, while the physical footprint stays stable. The measured 150%
scale plus native chrome, not an unexplained 450→730 API enlargement, causes it.
250 DIPs was derived from those native measurements, not relabeled as 250 physical px.

Window-only `PrintWindow` captures were visually inspected: full origin/security,
return and close controls, frame, content and bottom boundary are present; not a
blank/cropped DOM image. Retained synthetic evidence, all including raw native bounds:

- [Before, 863×738 physical pixels](../../architecture/governance/verification/mini-watch-geometry/baseline-150-scale-100-zoom.png)
- [After, 861×437 physical pixels](../../architecture/governance/verification/mini-watch-geometry/compact-150-scale-100-zoom.png)
- [Reopened warnings at 150% page zoom, 863×437 physical pixels](../../architecture/governance/verification/mini-watch-geometry/compact-150-scale-150-zoom-warnings.png)

Each corrected native batch measured initial open before any resize, then manually
enlarged the owned PiP to 700×600 through a new test user activation, closed and
reopened with six long-title prompts, four subscriptions and retained/source/quota
warnings. Reopening honors 560×250 with `preferInitialWindowPlacement:true`, not the
last manual size. A bounded 20ms native sampling loop observed no oversized opening
frame; sampling is not an assertion of every unsampled compositor instant. Header,
warning line, sticky headings and independent scroll areas remain readable without
document/horizontal overflow, including 150% browser zoom. Manual resizing is free.

### Executed regressions and limits

- **PASS:** final local Full, all 136 bounded runner units, **290.0s**, one worker
  without simultaneous browser/native probes. All original assertions are intact.
- VM/Python regression: full Watch/Mini exact daily parity despite visible-row totals
  differing, Credits/USD, known zero, unavailable pricing, partial data, loading,
  retry/source/offline/auth/stale states, canonical day replacement/corrections,
  separate non-navigating daily metric, keyed rows, lifecycle races and settings.
- Real headless Chrome and Edge **156.0.4314.58**: served CSP/assets, one SSE,
  centered headings and semantic data alignment, separate canonical daily header,
  sticky/independent scrolling, Classic/Web light/dark, currency, focus/keyboard,
  narrow resize, hidden-opener updates, terminal/empty/recovering/native close/reopen.
  Chrome emulated device scales 1/1.5/2 pass layout/lifecycle; higher-scale browser
  clamps may scroll even five/three rows. Virtual screen size scales with DPR so
  tests do not accidentally change available logical screen size. This is **not**
  actual Windows 100% or 200% native outer-window proof. In particular, a 250-DIP
  request can exceed 470 physical pixels at higher OS scaling; no universal cap is
  claimed and no platform support was silently removed.
- Read-only installed V2 acquisition: 80 coherent running publications before Daily
  became available, one running prompt, five known-finish history cards, three
  accounts/one primary-period cost; **28.282s**, owned close **0.106s**. No inference
  or shared OpenCode stop. This is not a WebHost shutdown or OS restoration test.
- The initial concurrent Full run failed one pre-existing 872-root historical-report
  catalog-count assertion (4 rather than allowed 2/3); a focused run with the default
  25s harness timed out after its first large test passed. A subsequent isolated run
  with a 120s per-file bound passed all historical-report tests in **25.71s**. The
  source has real-time catalog-hint expiry; concurrent native/browser probes changed
  runtime load. That is a timing sensitivity, not a proven causal source defect, and
  no assertion, source timeout or product behavior was weakened to hide it.

### Decision Delegate authorization and diagnostic exception

The active Decision Delegate authorized the crucial, finite **visible own-profile
Chrome/PiP measurements only**, after integrated Electron lacked Document PiP and
headless geometry could not establish physical acceptance. Helpers remained hidden;
CDP touched only owned targets, with no shared mouse/keyboard/clipboard, personal
profiles, login, display-setting changes or unrelated foreground cycling. Owned
windows closed between batches and while editing. This was **not owner desktop
permission** or future blanket authority.

An attempted minimal open then automatic resize was rejected by real Chrome:
`NotAllowedError: resizeTo() requires user activation in document picture-in-picture`.
Opening consumes activation. The approach was removed, not bypassed; the mock now
throws on any automatic resize so it cannot falsely approve this again. The final
implementation uses one direct 250-DIP request, no post-open resize or new permission.

After the native baseline and actual 80%/100% zoom results, the **Decision Delegate**
explicitly replaced the FR's personal-profile original-zoom inspection requirement
with controlled genuine **80/100/125/150% browser-zoom verification on the same
150%-scaled workstation**. This superseded the earlier withholding of that exception.
The owner's original personal-profile zoom remains **unknown**, not verified; the
470-physical-pixel cap at actual 150% OS scaling was **not waived**. This exception
applies to FR 000565/same-task delivery only unless superseded. Actual alternate
Windows scales, macOS/Linux native frames, minimized restoration, OS z-order and
screen-reader speech remain unverified, not PASS.

## FR 000561 — v80.141, 2026-11-03

Implementation base: `5a2fe691ba8c8bd5701b4beada8863d50930754c`.

### Current ownership and edge cases

- `WatchCapture.history_row` chooses the exact supported latest terminal prompt;
  capture also keeps its bounded context anchor when it falls outside the six most
  recent starts. `WatchCards` ranks membership and display by that finish, not
  catalog activity/start. Unknown-ended sessions fill spare slots before known
  finishes with stable identity ordering and an unknown clock. No usage is deleted.
- `live_projection` exports the canonical terminal timestamp; display owns localized
  Finished tokens and full date/time/UTC offset. The new DST regression found that
  the dependency-free Windows Stockholm fallback lost autumn fold identity. It now
  preserves the repeated hour and offset without changing observed terminal times.
- Mini renders shared focal identities and display tokens directly, never aggregate
  counts as rows, source reads or lifecycle guesses. Rows/cells and provider-aware
  account identities stay keyed across SSE/units/reordering. Final metrics remain
  visible for shared terminal grace; success/abort/error/unknown endings stay distinct.
- Mini's independent five-prompt/three-account scroll areas use a sticky header,
  title ellipsis and thin primary native Used bars. Cost attribution/completeness is
  accessible without a visible cost approximation glyph. Healthy Live text and the
  custom frame/close are removed; health/freshness and native identity guards remain.
  The old canonical running aggregate remains available, with no accounting change.
- Session-current continuation guidance remains under its existing owner; it is
  not reconstructed from the historical representative's old context. A transient
  implementation change broke that existing footer regression and was removed.

### Executed evidence and limits

- **PASS:** final local Full, 133 files, 75.2s. Validator: 11 passes, zero failures,
  six advisory warnings (existing README/Web guide/history and three Python design
  budgets); no hard-cap changes. No archive or model inference.
- **PASS:** final headless Chrome **156.0.8078.80** and Edge **156.0.4314.58** using
  owned fresh profiles, shipped HTTP/CSP/assets/authorization/SSE and disposable
  settings. Actual request initially grants **560×450**; five prompt/three one-line
  subscription rows have no outer or internal overflow. Native resize yields
  **538×405**, still fitting 5/3, with **9.75px** thin bars. Rows 6/4 scroll independently;
  account counts 1/2/3/4/6, long labels, 125% fonts, narrow native resize, sticky
  headers, Classic/Web light/dark, Credits/USD and keyboard activation pass.
- Native API close/replacement, Watch toggle/reload to Off, retained navigation and
  return-to-existing-tab pass. Actual hidden opener/visible PiP SSE updates preserve
  completed prompt-local metrics, then empty/recovery/host-stopped warnings, with
  exactly one EventSource. VM tests cover cancel/reject/races, source/auth/offline
  states, canonical ordinals, deduplication, row identity, abort/quota/error/unknown,
  partial costs, Unlimited/near-100/exhausted bars and provider-aware reordering.
- **PASS:** installed V2 read-only probe: three coherent publications, one running
  prompt, two correctly ordered known-finish history cards, three accounts/one
  available period cost; **7.83s**, owned close **0.089s**. Shared OpenCode untouched.
- Earlier failures were repaired: cost test expectations now follow existing integer
  CCost rounding; default 800×600 headless screen clamped PiP. The final test explicitly
  uses a synthetic **1920×1080** screen, not `--window-size` (which overrides popup
  geometry). Initial and native-resized dimensions are independently measured.
- **Unverified:** physical native close/return chrome, minimized OS restoration,
  always-on-top/z-order/OS geometry, screen-reader output and macOS. Browser automation
  is real hidden Chromium with CDP test activation, not physical clicking. No external
  desktop interaction or security-relaxing flag was used. Small browser/OS bounds
  may force internal scrolling. No scoped exception is claimed or reused for this FR;
  the specification explicitly requests evidence within safe available limits.

## Historical FR 000544

Date: 2026-11-03. Implementation base: `dd9507f5561dcc9e624baa64f07dd4555f84391b`.
Product: v80.131. These observations apply to this feature, not every desktop/browser.

## Ownership and reusable findings

- `watch/running.py` aggregates one canonical focal population before immutable
  Live export. Concurrent prompts in one session remain separate; duplicates,
  compaction, contextual/history rows, placeholders and terminal grace are excluded.
  Count, prompt-only CCost and maximum canonical duration share completeness/price
  state. Partial empty acquisition is unavailable, not a fabricated complete zero.
- Mini consumes the existing app-level connection, health and settings, independently
  of the Watch DOM/route. Its document has only external registered styles and safe
  text DOM; no CSP/auth exception or second acquisition/connection is introduced.
  Pending requests are cancellable but cannot be duplicated; closed/replaced window
  identity prevents late callbacks from clearing a newer On state.
- A visible PiP timer checks freshness only. Repeated progress events or identical
  HTTP snapshots do not advance its Live epoch; no local timer extrapolates duration.
  Backend capture failure also freezes retained card duration. Theme switching avoids
  transitional low-contrast Mini controls; Web light/dark follows each document's media.
- FR 000552 already delivered complete native-month history admission and indexed
  current-quota rebinding. Mini reuses that lane and quota-object association, not
  Today/30-day cost or a new scan owner. Estimate/partial attribution survives in the
  compact line and accessible period/attribution tooltip; unavailable cost preserves
  a known percentage. Native-period regression owners remain unchanged.

## Executed checks

- **PASS:** Full deterministic suite, 127 files, 58.1s, including Mini's Python/Node
  lifecycle and DOM cases. `validate_package.py --working-tree`: 11 checks, zero
  failures, four existing design-budget warnings. Hard caps unchanged. Existing
  oversized Web help was shortened and new Mini help put in its own cohesive page;
  history entries were compacted to retain the existing byte budget.
- **PASS:** Installed headless Chrome **156.0.8078.76** and Edge **156.0.4314.58**,
  each with a fresh owned profile and no browser-security feature flags. The bounded
  `integration/probe_mini_watch.cjs` + `serve_mini_watch.py` uses actual Document PiP,
  shipped HTTP/CSP/assets, one-use browser authorization, real SSE and disposable
  Settings. User activation is CDP test activation, **not physical clicking**.
  Checked opening, actual owned API window, keyboard summary focus/activation,
  user-activated native resize, existing-owner Watch return while keeping Mini open,
  route navigation, exactly one EventSource, Credits/USD, Classic/Web light/dark,
  six primary-only account lines/long names, no horizontal page overflow, native API
  replacement/close, custom close, reopening and main reload to Off.
- **PASS:** The same real-browser runs explicitly observed the main document
  `hidden=true` and PiP document `hidden=false`. Real SSE publications still updated
  count/cost/maximum as the 20-minute prompt ended (2/4/20m → 1/1.25/10m), acquired
  zero, source recovery and terminal host-not-live states. This is real hidden-page
  behavior, not proof of Windows minimization or OS z-order.
- **PASS:** Deterministic VM cases additionally cover rapid/rejected/delayed opening,
  cancellation, old close callbacks, policy/unsupported contexts, owner pagehide,
  auth/host identity/offline/retained states, stale epochs despite duplicate snapshots,
  partial/estimated/missing account cost and independent keyed DOM. Source regression
  tests carry the quota-ended child prompt through the canonical capture path into
  a non-running Mini aggregate; removed child history remains honestly partial.
- **PASS:** `integration/probe_mini_source.py` against the real installed **V2** source:
  three coherent aggregate publications, one actual running prompt, complete running
  count/pricing, three accounts, one available primary-period cost; others remained
  truthfully unavailable. Acquisition 25.858s, direct owned acquisition close 1.363s.
  No inference or shared OpenCode stop. This does not establish complete real monthly
  account attribution/valuation where the provider/source lacks evidence.

## Failed check and scoped Decision Delegate exceptions

The earlier broad `probe_web_live.py --watch-cards --daily` is **FAIL** overall:
it observed valid V2 cards, daily reconciliation (1002 requests, 49 initiating prompts,
incomplete causal attribution explicitly retained, complete pricing), one engine,
two test subscribers and three accounts, then raised **`web_shutdown_timeout`** in
owned-host cleanup. Previous account-period verification recorded the intermittent
failure before Mini. Nested deadlines and waiting workers suggest a mechanism,
**not an established root cause**. The successful direct acquisition close above is
not a passing WebHost shutdown test and does not resolve that risk.

On 2026-11-03 the **Decision Delegate**, not the user or worker, authorized protected
delivery **for FR 000544 only**, valid through same-task continuation unless superseded:

1. Omit physical native X/return-control interaction, actual Windows minimized-opener
   restoration/minimized-window tests, and OS z-order/geometry proof. Screen-reader
   behavior remains untested; accessibility requirements are **not** waived. Adequate
   non-disruptive real headless browser/native-API/hidden-document and source evidence
   makes external desktop disturbance unnecessary. **No visible desktop action was
   authorized or performed.** Integrated browser access failed `browser.disconnected`.
2. Deliver without repairing unrelated host lifecycle or requiring the broad failed
   probe to pass first, while retaining its FAIL and unresolved shutdown risk. No
   runtime requirement, source truth, new-test failure or Git protection is waived.

No blanket future exception or full physical/native acceptance is claimed. Main
focus requests may not restore a minimized OS window; native return-to-tab remains
available and may close PiP. Browser-owned security chrome/geometry are never hidden.
The user help reports those limits rather than promising a frameless tooltip.
