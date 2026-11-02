# FR 000554 — Refine Watch warning emphasis, source availability feedback and history order

## Owner request and outcome

On 2026-11-03 the owner requested three coordinated improvements to the **Web Watch page**:

1. An approaching-price-threshold warning should have a gold/orange warning triangle and ordinary foreground text. Once the threshold is exceeded, the triangle and the whole warning text should remain gold/orange as today.
2. Brief, intermittent **Source unavailable** messages should not flash aggressively during otherwise continuing use. Investigate the responsible state/connection path and make the presentation appropriately stable while keeping genuine outages visible.
3. **Earlier Prompts** should read chronologically like Running Prompts: oldest at the top, newest at the bottom.

This is one focused Watch improvement. The source-availability observation is not yet a reproduced root cause; the owner perceives CLI Watch as smoother, which is a comparison to investigate rather than proof that Web uses a defective connection mechanism.

## 1. Severity-specific warning emphasis

Apply the following styling to the existing context/price warning beneath each applicable prompt table:

| Canonical severity | Warning triangle | Remaining warning text, including associated values |
| --- | --- | --- |
| Approaching price threshold | Existing gold/orange warning color | Normal theme foreground text |
| Price threshold exceeded | Existing gold/orange warning color | Existing gold/orange warning color |

Use the theme's normal body-text role for approaching text: gray/white in the dark/Classic themes and the corresponding readable foreground in the light theme. Do not hardcode a pale color that becomes unreadable on a light background. Keep the current warning color rather than introducing a new severity palette.

Drive this from the existing canonical severity, not English text matching or a duplicate browser threshold calculation. Keep the warning's wording, numeric meaning, placement immediately beneath the table, and accessible textual meaning. A severity change or theme switch must update the icon and text correctly; a cleared warning must clear normally. Scope the styling to these Watch warnings, preserving unrelated quota, source-error and other-page styling. CLI warning behavior and threshold/CCost calculations are unchanged.

## 2. Stable, truthful source-availability feedback

The owner reports short appearances of **Source unavailable** that disappear again after a few seconds. Inspect the actual Watch locations that can show this or equivalent text: per-card status, the active/earlier area, Total Today and any relevant connection presentation. Do not assume all occurrences have one cause.

Trace a representative transition through existing source/acquisition, card/daily projection and browser connection evidence. Distinguish:

- Browser to CostGuard HTTP/SSE connection loss or reconnection.
- CostGuard to OpenCode source acquisition/read/poll failures.
- A failed individual card or daily refresh while other data remains available.
- Normal refresh, pending work and initial loading.

Compare the relevant CLI acquisition/recovery behavior where useful. Fix an erroneous transition or avoidable acquisition failure at its existing owner if that causes the flash. If a genuine brief retryable condition still needs presentation smoothing, use a small, bounded confirmation/recovery policy grounded in the existing cadence and freshness model. Document the chosen condition and finite detection bound; this FR does not prescribe an arbitrary universal delay or another polling loop.

Keep existing valid observations visible through routine refresh and transient recovery. Do not replace values with fabricated zero/empty results, claim that retained data is fresh, or let a browser heartbeat/progress event stand in for a successful source observation. Ordinary transient refresh/reconnect should not repeatedly announce a source outage when the evidence does not justify that meaning. Recovery should clear the relevant status on appropriate successful evidence.

A persistent source outage must still produce a visible, meaningful warning within the defined finite policy. Repeated failures must not restart a grace period forever. Preserve decisive handling of authentication failure, host-identity change, terminal stop and other non-retryable conditions. Browser/host failures must retain their proper meaning instead of being relabelled as OpenCode source failures. Do not conceal the problem with blanket CSS suppression, unconditional success or automatic browser/host restarts. Preserve bounded selected-source recovery, acquisition limits and useful existing diagnostics.

## 3. Earlier Prompts in ascending chronological order

Keep the existing selection of the **five most recent eligible distinct historical sessions**, with the latest actual prompt shown for each, excluding active/recent cards according to the existing lifecycle rules. Change only their final display order to **oldest first, newest last**, matching the chronological direction of Running Prompts.

Select the recent set before ordering it for display. Sorting all sessions ascending and then taking five would incorrectly select the oldest history and does not satisfy this request. Use the displayed prompt's canonical timestamp/order semantics consistent with the active cards, with deterministic ties. Do not order by formatted clock text, title, fetch completion, or when a card happened to enter the history section.

Preserve that order on first load, subsequent updates, reconnection and collapsed/expanded history. Newly eligible or refreshed history must enter its appropriate chronological position without duplicates or obsolete running cards. Retain existing one-row cards, history limit, disclosure/focus behavior and normal page scrolling; no new sort control, forced auto-scroll or layout redesign is requested.

## Acceptance and proportionate verification

1. **Warning emphasis:** approaching shows only the triangle in gold/orange, with the remaining text in normal foreground; exceeded colors both. Verify severity transitions and Classic/Web light/Web dark readability using the existing rendering/DOM and focused browser checks. Threshold values and unrelated warnings retain their meaning.
2. **Transient behavior:** demonstrate the identified refresh/recovery sequence through the relevant actual state owners. Normal refresh and short recoverable conditions do not cause unjustified Source unavailable flashes, content resets or disruptive layout churn. A rendering test with an arbitrarily pre-cleared error alone is insufficient to establish the fix.
3. **Real failure and recovery:** focused cases cover sustained source unavailability, browser/host reconnect as a distinct condition, retained-data freshness, and recovery. A persistent problem is shown within the documented finite bound; repeated failures cannot defer it indefinitely. Preserve existing authentication/identity/stop protections without adding a broad new acceptance matrix.
4. **History selection and order:** with more than five eligible sessions and at least one active/recent exclusion, the selected set remains the five latest eligible historical sessions and is displayed oldest to newest. Cover a newly eligible item, changed source order, equal-time stability and collapsed/expanded updates through existing fixtures.
5. **Evidence:** report the actual cause established for the flicker, the chosen state/timing policy and executed checks. If the owner's exact local occurrence cannot be reproduced, retain that uncertainty and demonstrate the corrected relevant path without claiming that every connection problem is fixed. Use focused existing tests and bounded browser/reproduction work; no permanent new telemetry framework, broad live-provider campaign or release gate is requested.

## Inspected source and related work

Baseline: `b7937ffa69c1eae902b408b3ecd030421b7547a6`. Reconcile normally with later Watch changes; do not rewrite other FRs or historical requirements.

- `src/web/assets/watch.js::Card.update` currently renders the icon and warning text as one string and exports `data-severity`. `View.update` also maps a non-fresh overall state to a connection/source message; card and daily messages have their own inputs. `src/web/assets/app.css` currently gives the entire warning its warning color. `src/reports/watch_context.py` already supplies canonical severity.
- `src/watch/cards.py::historical_ids` selects recent history descending, and `project` currently emits that same order. Active cards already sort by canonical start order ascending. Preserve recent-set selection while changing historical display order.
- Existing connection owners include `src/web/assets/live.js`, `app.js`, `src/application/live.py`, `src/watch/acquisition.py`, `web_coordinator.py`, `card_workers.py` and the shared CLI coordinator. Source recovery and browser transport are distinct; an observed UI difference alone does not establish which failed.
- Preserve the source-versus-host and freshness distinctions documented in [Web connection verification](../../../architecture/governance/verification/web-connection.md). FR000532 addressed an earlier Web connection-flapping case; inspect its current evidence when relevant instead of assuming the old cause has returned.
- FR000551 owns the remaining stopped-prompts-shown-running defect; FR000552 owns subscription cards/version display; FR000544 owns Mini Watch. They remain separate scopes. Integrate shared Watch edits normally without making those FRs prerequisites for this presentation/status correction.

This authoring request publishes only the FR and permanent identity bookkeeping. Implementation follows the repository's ordinary delivery process; no runtime installation/reload is part of authoring.
