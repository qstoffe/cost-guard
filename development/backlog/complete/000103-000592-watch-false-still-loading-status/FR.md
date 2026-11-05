# FR 000592 — Web Watch: remove false “Still loading Watch data” when Live is updating

## Owner observation

**Owner-approved executable Ready Feature Request, 2026-11-05.** On the full **Watch** page, the notice **“Still loading Watch data; check source availability.”** remained visible for several minutes **while running prompt/session cards visibly continued to receive new data and new running sessions appeared**. This is misleading and distracting. A delayed account/history component must not make an otherwise active Watch display announce that Watch itself is stuck.

**Separate priority before the Sessions overhaul (FR000593).** This FR is a narrowly scoped status-truth/UX bugfix, not a generic overhaul of Live acquisition or source retries. During this authoring action, publish only the FR; do not change product code/tests/docs/version.

## Current code paths to examine (main at authoring)

- `src/web/assets/watch.js::View.update()` derives `initialDelayed` from **`cards_state === loading || history_state === loading || !view.accounts`**, then can set `this.empty` to **“Still loading Watch data; check source availability.”** after a threshold, even with a nonempty `active_cards` stream. These phases have different owners and do not prove global Watch freezing.
- `src/web/assets/app.js::show()` has another 30-second fallback with the **same exact message** when **`liveValue?.view` is missing**. Audit both so the identical misleading notice cannot survive via a second path.
- `src/web/assets/live.js`, the host-state banner and Watch state projections already distinguish **connected, source retrying, source unavailable, authorization loss, offline/terminal and retained observations**. Preserve this more authoritative status system instead of duplicating it inside a healthy prompt area.

The owner observed the UI while it was genuinely updating. Investigate with real Live/DOM state to determine which branch fired; do not claim that a source was unavailable simply because a timer elapsed.

## Required behavior

1. **Do not show the generic “Still loading Watch data; check source availability.” warning anywhere on full Watch.** Remove the redundant elapsed-time fallback(s). If there is no initial usable data yet, use an unobtrusive ordinary startup/loading placeholder or no body text, not a persistent failure warning based on an unrelated sublane's delay.
2. **If prompt data is advancing, Watch is not globally frozen.** New/updated running cards, changing prompt counters/durations or arrival of new sessions must not coexist with a page-level “Watch data still loading” warning solely because **Earlier history**, **accounts/quota**, **daily summary**, or another independent component is loading, absent, slow or unavailable. Localize any materially useful component-specific warning to that component, only when truthful.
3. **For genuinely failed/paused connection or source**, continue to show the existing accurate, actionable host/source state, e.g. reconnecting, source unavailable, retained—not-current, terminal authentication/host errors. Retained frames must not be misrepresented as actively updating. Don't suppress real errors just to keep the view quiet, and do not relabel missing/partial data as successful empty values.
4. Keep **“No running prompts”** only when an actually observed, healthy result establishes none; do not replace loading/unknown with a false empty success. A stale/historical snapshot alone is not a fresh-running view.
5. Component updates, tab navigation, reconnect and old/new Live publication sequences must not resurrect the removed notice, flicker broad loading banners or reset existing usable card DOM/selection/scroll. Preserve the shared one-publisher SSE and distinct source/accounts cadence; don't add new polling or provider calls.

## Acceptance criteria

1. Reproduce a case with **active cards updating** while one or more of **`history_state=loading`**, absent/`loading` accounts, daily pending or partial source evidence persists **for several minutes**. **No** “Still loading Watch data; check source availability.” text appears, and the active cards continue to update.
2. Both original message paths (the initial `app.js` fallback and Watch's `initialDelayed`) are removed or made nonmisleading; no duplicate hidden alternative restores the same warning.
3. No false “No running prompts” during uncertain acquisition. Healthy confirmed empty state remains quiet/accurate; real source disconnect, failed acquisition, auth loss, host shutdown and reconnect/retention states still provide **correct**, reasonably concise feedback at their respective UI owners.
4. Focused JS/DOM and browser tests cover long-running independent history/accounts delays, active card arrivals and updates, initial empty/loading, partial/retained data, source interruption/recovery, theme variations and route changes. Verify that unchanged Live data does not acquire a fabricated progress state.

**Boundary:** author only this Ready FR and update the backlog identity watermark, without implementing it now.
