# Mini Watch and finished history

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
