# Mini Watch — FR 000544

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
