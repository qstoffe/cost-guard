# FR 000544 — Add Mini Watch with live running metrics and primary subscription usage

## Owner goal, priority and dependencies

Provide a compact, persistent floating view of CostGuard while the owner works in another application. The Watch page opens and closes this **Mini Watch** explicitly. It shows how many prompts are actually running, their combined current CCost, the longest current running duration, and each subscription's primary Used percentage with CCost for that same quota period.

The owner approved this separate feature on 2026-11-02 after discussing Document Picture-in-Picture and the meaning of its metrics. Permanent identity: **000544**. Ready priority: **000120**. The related page cleanup is **FR000545** at 000110; the running-state correctness fix is **FR000546** at 000100.

Implement on top of delivered FR000542/FR000543. **FR000546's terminal-lifecycle parity is a correctness prerequisite**: Mini Watch must not publish an inaccurate running count by inheriting the reported stuck quota-ended prompt. Coordinate with FR000545's final Watch layout and terminology; consume shared projections instead of copying its card renderer. No change to the delivered FRs' archived text is needed.

This FR includes the compact window, its lifecycle, authoritative aggregate data and same-primary-period account CCost. Automatic opening on minimization, completion toasts, quota alerts, native desktop applications and a redesigned Sessions page are outside this request.

## 1. Explicit on/off control and window ownership

Add a compact Watch-page control labelled **Mini Watch: Off** or **Mini Watch: On**, reflecting the actual window state. It is a small page action; do not restore the removed Watch heading, refresh/cancel toolbar, next-refresh banner or other old top-of-page content.

- An explicit user click while Off requests one Document Picture-in-Picture window. Show On only once it actually opens.
- A click while On closes that window. Both the browser's native close control and a small close affordance inside Mini Watch return the page control to Off.
- A rejected, unsupported or cancelled open request leaves the state Off and provides a concise explanation. Rapid repeated clicks, delayed close callbacks and open/close races must not create duplicate windows or leave a phantom On state.
- Track the window actually owned by this document. Respect browser PiP replacement/ownership behavior; do not promise independent always-on-top windows for every tab.
- In-app navigation away from Watch keeps Mini open and updating. Returning to Watch shows its actual state. Closing or reloading the owning document ends the Mini session. A subsequent load must not reopen it automatically or restore On from a saved preference.

Use runtime feature detection for the desktop **Document Picture-in-Picture API**, a secure context and any relevant browser restrictions. The loopback Web Beta deployment should work under the browser's secure-context rules. Do not assume that all desktop browsers implement the API, or that video Picture-in-Picture is equivalent.

For unsupported/disabled browsers, present an unavailable control with a short reason. Do not silently substitute a regular popup and call it always-on-top. No browser flags, extension, notification permission or native helper is required by this FR.

## 2. Compact appearance and returning to Watch

Render a dedicated, compact HTML view with rounded interior corners, restrained spacing and the current CostGuard theme. Use sensible initial dimensions and allow the browser/user to resize it. It should feel like a small status card, not a duplicate full Watch page. Keep the main summary visible and allow content to remain usable with long account names or more accounts.

The browser owns the outer window chrome, origin indication, native close/return controls and final geometry. Rounded card contents are achievable; a completely frameless tooltip, arbitrary desktop positioning and identical OS window behavior are not promises of this web feature. Do not hide or work around browser identity/security UI.

Make the main summary/header area an accessible action that requests focus of the **existing owning CostGuard tab/window** and selects Watch when appropriate. A supported user-initiated focus action should leave Mini Watch open. The internal close control must not also trigger this focus action. If the browser/OS cannot restore a minimized opener, handle that limitation honestly and retain usable native return-to-tab behavior. If a native return action closes PiP, synchronize Off normally.

Use the current effective theme and Credits/USD setting in both documents. Changes in the main app must update Mini without reopening it. Cover Classic and Web's light/dark appearances, keyboard focus, meaningful accessible names and readable contrast.

## 3. Three precisely scoped running metrics

The compact summary contains these fields, with equally clear shorter presentation acceptable where space requires it:

| Label | Definition |
| --- | --- |
| **Running prompts** | Number of distinct canonical prompts currently in progress. |
| **Running CCost** | Sum of the accumulated prompt CCost of those currently running prompts, each counted once. |
| **Longest running** | Maximum current duration among those running prompts, never their summed duration. |

For two running prompts at 10 and 20 minutes, show **2** and **20 minutes**; the cost is the sum of those two prompts' current costs. When the longest prompt ends, the displayed maximum may decrease. When any prompt ends, its cost immediately leaves Running CCost; this is not an all-time or Watch-run cumulative total.

Use a **backend-owned aggregate** from one coherent observation of canonical prompt state and valuation:

- Deduplicate by actual session/prompt identity, such as `(session_id, event_id)`. Concurrent prompts in the same session remain separate prompts.
- Include only genuinely `in_progress` focal prompts. Do not count historical cards, contextual earlier rows, source placeholders or terminal cards still displayed during their highlight/grace period.
- Sum current prompt CCost, not full-session totals, Total Today, account costs, formatted strings, or the existing Watch-run `run_ccost`.
- Use canonical prompt duration and its existing running-time semantics. Do not replace it with time since Mini opened or a new sum of tool durations.
- Publish count, cost and maximum together. Missing pricing or pending acquisition must not appear as a complete zero; express partial/unavailable data with existing concise conventions. Do not expose a raw **Provisional** label.
- A successfully acquired empty running set shows count **0**, a genuine zero cost in the selected unit, and **—** for Longest running. Retained terminal values must not remain in these fields.

The existing Web `active_count` includes pending empty card placeholders at the inspected baseline and is not automatically an exact count of known running prompts. The existing active card list also includes terminal grace. Reuse or extend the canonical projection deliberately; do not derive these metrics from rendered card count.

## 4. One compact primary-usage line per subscription

Below the running summary, show each subscription/account once using its existing disambiguated name, its stable **primary Used percentage**, and parenthesized CCost in the effective display unit. For example, the structure is:

**<Subscription name> · <percentage>% used (<same-period CCost>)**

This shows **used**, not remaining. Do not include reset countdowns, secondary weekly/model windows, observation detail boxes or explanatory paragraphs. Preserve meaningful account distinctions when two accounts have the same provider/plan. The period and cost meaning can be made clear through a concise accessible label/tooltip without expanding the card into the full account view.

Reuse FR000543's provider-aware, stable primary selection: an explicit adapter primary first, with the established monthly Copilot and account-scoped five-hour provider defaults. Do not switch to whichever window is most depleted, and do not substitute weekly when the expected primary is temporarily unavailable.

### The parenthesized cost covers the same primary quota period

The owner accepted the recommendation that this is **same-period CCost**, not universally CCost Today. A five-hour primary gets that actual quota interval's CCost; a supported monthly primary gets that actual native month/billing interval's CCost. Include relevant usage before Watch or Mini opened.

This is new scope acquisition/projection work, not just a label change:

- Reuse canonical request valuation, account attribution, request deduplication and period indexes. Acquire enough history for the complete relevant period, including earlier days of a native month.
- Use the provider's verified period boundaries and reset semantics. Never substitute Today, an arbitrary trailing 30 days, or the configured local calendar month for a different native interval.
- Existing `monthly_quota_window` supports known fixed UTC calendar months with the native reset at day 1, 00:00. Reuse that support where valid. An arbitrary billing date or absent boundary remains unavailable until supported by authoritative data; do not invent it.
- A duration-based trailing lookback marked uncertified by existing helpers must not silently become an exact native quota-period amount.
- Keep the quota observation's period identity tied to the cost scope. When the native window resets, an old-period cost must not accompany a new-period Used percentage while background work catches up.
- Preserve genuine unknown/partial/estimated attribution. Do not multiply a quota percentage by an assumed budget to fabricate CCost, duplicate provider costs across ambiguous accounts, or arbitrarily split a global total.
- A known Used percentage may coexist with unavailable cost. Keep the usable percentage and show a truthful unavailable cost instead of dropping the row or displaying zero. Preserve canonical unlimited and exhausted quota semantics.

The current CLI fallback to Today for a monthly component without a duration does **not** meet this Mini requirement. This FR does not need to change that CLI presentation; it must supply an explicit correct Web Mini scope.

## 5. Reuse live ownership, health and efficient acquisition

The inspected app already owns one authenticated live connection per tab and retains the latest publication across in-app routes. Implement an app-level Mini controller/subscriber and an independent Mini DOM using that data and its health events.

- Do not move the main Watch DOM into PiP. Both views must remain usable and retain their own rendering/focus state.
- Do not open a second EventSource, auth bootstrap, Watch engine, provider polling loop or separate per-Mini acquisition owner.
- Extend the process-owned projection and bounded shared period-cost acquisition/cache as needed. Opening, closing, resizing or navigating Mini must not repeatedly scan complete session histories. Do not block live prompt updates on account history enrichment.
- Keep the visible Mini updating while the main browser window is hidden/minimized or another app is focused. Do not make its rendering depend exclusively on a throttled hidden main-document animation callback. Any local elapsed-time presentation must obey canonical lifecycle and freshness; pricing and lifecycle remain authoritative backend data.
- Reopening immediately renders the latest available publication and its current health. Connection loss, source failure, auth expiry, host identity change or shutdown must not leave stale values looking live or a duration growing indefinitely without trustworthy state.
- Preserve last-known valid figures through ordinary refreshes and identify stale/unavailable state concisely when appropriate. Keep first acquisition distinct from a real empty running set.

Respect the existing same-origin/CSP model. The inspected CSP allows same-origin scripts/styles and connections, not arbitrary inline code. Use safe DOM/text construction, existing asset registration and an external same-origin Mini stylesheet or equivalent permitted styling. No CSP relaxation, copied auth tokens, bootstrap credentials in window URLs/storage/markup, or independent sign-in flow is needed.

## Inspected baseline and implementation pointers

Source inspection used main `389f9881bc4e00e4c0cbd0f6245fe2af86e037c2`; reconcile against the intervening deliveries when implementing.

- `src/watch/cards.py`, `web_coordinator.py`, `models.py`: focal identities, running/grace distinctions and coherent aggregate ownership.
- `src/application/live_projection.py`, `display.py`: typed server projections, current unit formatting and display tokens.
- `src/application/watch_accounts.py::primary_quota`, `src/reports/accounts.py`: stable primary selection and account scope projection.
- `src/analysis/period_ccost.py`: native quota/month boundaries, `history_start` coverage and `PeriodCCostIndex`; monthly history is not enabled by default.
- `src/web/assets/app.js`, `live.js`, `watch.js`, `settings.js`: app-level connection, health, route ownership, toggle and setting propagation.
- `src/web/http.py`, `src/web/security.py`, `src/application/live.py`: registered assets, CSP, session and process ownership.

Primary browser references: [Chrome's Document Picture-in-Picture guide](https://developer.chrome.com/docs/web-platform/document-picture-in-picture), [the Document PiP specification](https://wicg.github.io/document-picture-in-picture/), and [MDN's Document Picture-in-Picture reference](https://developer.mozilla.org/en-US/docs/Web/API/Document_Picture-in-Picture_API). Use runtime detection and record actual tested desktop browsers; support is not a promise for every operating system/browser combination.

## Acceptance evidence

1. **Toggle/window state:** a real supported desktop browser opens one Mini on click; a second click, native X or custom close returns Off. Rejection, rapid clicks, stale callbacks, native return/replacement, main reload and close leave correct ownership/state. No automatic open on minimize/reload and no notifications are introduced.
2. **Return to app:** the summary action focuses the existing CostGuard owner and selects Watch while keeping Mini open when supported. In-app navigation does not terminate Mini or create another connection. Record actual minimized-window restoration behavior rather than claiming headless tests prove every OS interaction.
3. **Correct aggregate:** exercise two durations of 10/20 minutes, concurrent prompts in one session, partial acquisition and unavailable cost. Count each genuine running prompt once, sum only its cost, and show the maximum duration. A terminal/grace card leaves all three aggregates immediately; fresh zero running is distinct from unavailable.
4. **Quota termination:** the source regression from FR000546 produces the same non-running truth in Mini and full Watch. Mini adds no independent timeout or frontend lifecycle workaround.
5. **Same-period subscription data:** verify native five-hour and supported monthly windows, pre-Watch history, multiple/disambiguated accounts, missing boundaries, partial attribution and reset races. Monthly cost includes earlier days; no Today/30-day fallback or old-period/new-percentage combination is mislabeled as correct.
6. **Live health and efficiency:** while the main page is hidden/minimized, Mini continues receiving correct visible updates. Reconnect, source failure, shutdown, auth/host changes and reopening preserve honest freshness. Opening multiple times adds no EventSource/acquisition owner or unbounded repeated scan.
7. **Presentation:** both themes including Web light/dark, live Credits/USD changes, long account names, resizing and keyboard use remain readable. No reset/secondary-window clutter, full-page toolbar, raw Provisional label or false frameless guarantee appears.
8. **Unsupported browser:** feature absence/rejection has a concise truthful control state; no regular popup is advertised as equivalent always-on-top behavior.

Use proportionate existing Web/live/account-period tests plus real-browser evidence for browser-owned behavior. Update Web Beta help with the supported interaction and limitations. These are this feature's acceptance cases, not new permanent release gates. This backlog publication itself changes no product code or version.
