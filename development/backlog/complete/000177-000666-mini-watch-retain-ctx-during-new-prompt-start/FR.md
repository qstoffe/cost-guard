# FR 000666 — Mini Watch: retain the last valid Ctx value while a new prompt starts

**Owner-approved Ready Feature Request, 2026-11-10.** Permanent identity **000666**; Ready priority **001010**, following the current Ready queue. **Backlog publication only:** create this FR and increment `development/backlog/identity-state.json` highWatermark **665 → 666** together in one documentation-only commit on `main`. Do not implement product changes, run product tests, modify release/version files, or alter unrelated backlog items during publication.

## Owner observation and desired behavior

In **Cost Guard Web → Mini Watch** (Document Picture-in-Picture), an existing session's **Ctx** column can already display a useful numeric context estimate. When the owner submits **another prompt in that same session** and it begins executing, the Ctx cell briefly changes to a loading/placeholder indicator for the first seconds, before showing the new running prompt's context. This visible flicker is distracting.

**Desired behavior:** If Mini Watch already has a **valid, displayed Ctx value for that same session**, leave that value visible **while the new prompt's Ctx is still pending**, and replace it promptly once a new valid estimate becomes available. Do not briefly replace useful context with a spinner, `Loading…`, blank, or `N/A` just because the representative prompt changed. No extra UI controls or new columns.

Example (illustrative values, not a recorded trace):

| Moment | Visible Ctx |
| --- | --- |
| Prior prompt in session A, supported Ctx | `172k` |
| New prompt in **session A** starts; no fresh estimate yet | **`172k` remains visible** |
| First supported new prompt estimate arrives | `175k` |
| Another session B, without any prior Ctx | Existing truthful pending/unavailable presentation; **never `172k`** |

The owner's report is a visual observation; the exact placeholder and root cause have not been instrumentally reproduced in this authoring step.

## Existing code and likely transition

- `src/web/assets/mini.js::View.drawSessions()` currently chooses the **active** row's Ctx with `ReportView.display(item?.live_context, 'watch_next_context_tokens')` and writes it each draw; **historical-only** rows use `card.session_summary?.context`. A new active prompt may temporarily have no prepared next-context token, leading to a placeholder.
- `mini.js::Observations.update()` already retains certain prompt facts keyed to `[session_id, focal_id]`, so that retention does not necessarily bridge the **new focal prompt** within an otherwise unchanged session. The rendered row itself is keyed by `session_id`.
- Investigate whether the existing canonical Live/session projection provides a suitable still-valid same-session next-context estimate before introducing a new Mini-only retained presentation value. This is a focused display continuity change, **not** permission to invent context calculations or rewrite the upstream estimator.

## Requirements

1. **Same-session handoff:** Across previous prompt → new running prompt, preserve the most recent supported **visible next-Ctx estimate** associated with the same canonical root session only **while the new prompt's value is genuinely pending**. New valid/current source evidence must replace it promptly, even if the number is unchanged. Avoid placeholder flashes across successive SSE, HTTP refresh and timer renders.
2. **Truthful fallback semantics:** Distinguish transient not-yet-available data for a newly starting prompt from an **authoritative** unavailable/invalid context state. Do not freeze an old number forever when the source establishes that no comparable current next-context estimate is valid. Where a retained value is shown, any Ctx help/accessible description must not falsely attribute it to a measurement of the new prompt; briefly identify it as a previous same-session estimate pending refresh if necessary. Keep **Δ Ctx** prompt-specific: never copy the previous prompt's delta as the new one's.
3. **Identity and invalidation:** Never carry a value across different session/root IDs, a host/source identity change, removal, or a known incompatible context epoch. Respect compaction, reset, model/context boundary, execution-unverified or other established source validity rules; do not bypass real invalidation to maintain a cosmetic number. A first prompt with no valid earlier context continues to show the established honest pending/unavailable state. Avoid accidental reuse from historical-only rows when a session resumes unless their context is actually eligible for the same continuing session.
4. **Preserve source and formatting:** Reuse existing source-prepared Ctx display and established estimation/rounding, including legitimate `0` and `N/A`. Do not parse the formatted `172k` string, sum prompt contexts, calculate token deltas in JavaScript, persist browser-local values, invent a refresh request, or introduce an arbitrary delay. Continue to update Ctx during ongoing model/tool calls as soon as credible new values exist.
5. **Small scope:** Target Mini Watch's Ctx presentation/retention and, only if truly necessary, the narrow Live projection/state contract that distinguishes pending from invalid. Leave full Watch, account summaries, CCost/Total, Activity, Session, table layout, PiP geometry and shared context arithmetic unchanged. Do not change unrelated existing Ready FRs.

## Acceptance and verification when implementing

- Start with a session A that already shows Ctx `172k`; inject a new prompt in **A** with initially pending context, then fresh `175k`. Across all intermediate Mini renders assert **`172k → 172k → 175k`**, not `172k → N/A/Loading… → 175k`. Check hover/focus Ctx help against each state, including truthful Next Ctx and independently prompt-scoped Δ Ctx.
- Test several new prompts in one session, repeated/late SSE snapshots, a tool-call-heavy running prompt, completion then resumption, a newly opened Mini, a first-ever session without a prior number, two concurrent sessions, and a row disappearing/reappearing. Values must never leak across session keys or host changes.
- Inject a **genuine unavailable** context transition, compaction/reset/incompatible model epoch and other established invalidation cases. The Mini must drop invalid carry-forward appropriately, not conceal an actual unknown indefinitely. Ensure historical-only context still uses its established session-level meaning.
- Add focused cases to the existing Mini fixture/browser tests (e.g. `development/tests/fixtures/mini_sessions.cjs`, `development/tests/integration/mini_watch.cjs` and/or `probe_mini_watch.cjs`) plus source-projection tests if a source-state distinction changes. Verify the real Document PiP rendering path where feasible, without paid AI requests; update `docs/web-mini-watch.md` to describe the transient Ctx handoff and its limits.

**End state:** A familiar session's useful Ctx number stays steady while its next prompt starts, then updates naturally with fresh evidence. The display never borrows another session's context or masks a genuinely invalid estimate.
