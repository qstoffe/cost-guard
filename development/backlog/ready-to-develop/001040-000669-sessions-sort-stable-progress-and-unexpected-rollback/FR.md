# FR 000669 — Sessions: three-tier sorting progress and no unexpected rollback

**Owner-approved Ready Feature Request, 2026-11-10.** Permanent identity **000669**, Ready priority **001040**, following existing Ready FR000668 (001030). **FR-only backlog publication:** create this Ready FR and atomically advance `development/backlog/identity-state.json` highWatermark **668 → 669** in one `main` commit. This authoring step does **not** implement code, run product tests, change versions/releases or modify other FRs.

## Owner observation and desired outcome

The recently completed **FR000664** introduced a useful centered progress bar and status for expensive **Cost Guard Web → Sessions** global sorting. The owner wants to **retain** it, but the current changing stage/count status competes in one place and feels visually jumpy: it is hard to tell **what overall operation is being performed**, **how much has finished**, and **what the system is doing right now**.

Use **three distinct, stable locations** around the existing determinate progress bar:

1. **Above the bar — stable overall task:** `Sorting sessions by CCost` (or `Loading CCost sort…`). This identifies the **requested** column/sort and remains in place throughout that operation. For page navigation say `Loading Sessions page 2`. It changes only on an actual new intent/terminal outcome, not on each index step.
2. **Immediately below the bar — progress/count:** e.g. `Indexed 154 of 3,090 sessions (5%)`. Reflect the authoritative completed/total index count, continuously updating without restarting the row's text layout. For page navigation use real page readiness (e.g. `Prepared 18 of 50 sessions`, or the actual shorter last page).
3. **Second line below the bar — current work/status:** e.g. `Checking cached session summaries…`, `Reading source metadata…`, `Retrying one session summary…`, `Waiting for source…`, or `Source changed; revalidating keys…`, **only when the source can prove that operation**. This may change much more frequently than the other two lines, without moving or blinking them.

Illustrative layout, not observed measurements:

```text
                 Sorting sessions by CCost
              ━━━━━━━━━━━░░░░░░░░░░░ 5%
                  Indexed 154 of 3,090 sessions
                  Checking cached summaries…

                            Cancel
```

Make the heading, count and work text short, centered and legible in the existing visual style. No marquee, arbitrary clock-driven percentage, flashing/recreated progress component, oversized progress panel or constantly shifting content height. Preserve the standard 0–100% determinate bar; show 100% only when the requested sort/page is actually qualified and applied. Progress/count should be meaningful in source/epoch context, not a cosmetic animation.

### A separate observed correctness problem

While sorting by **CCost** over the large Sessions catalog, the owner saw roughly **one minute of work** reach approximately **5%**. Then, *without the owner pressing Cancel*, the pending operation apparently disappeared and the page displayed the previously applied **Last activity** ordering. The owner does not know why. It may correlate with a running prompt/session update, but that is **a hypothesis, not a confirmed cause**.

Clicking CCost again began a new visible sort, yet progress appeared to resume from previously accumulated backend work. The owner wants the failure/rollback behavior investigated: a long operation should **not silently give up and look as if the user requested Last activity**. Reuse valid indexed work on retry; do not unnecessarily repeat expensive work.

## Verified code facts, likely seams to investigate

The following are checked against the repository at FR publication, not an instrumented reproduction of the owner's particular event.

- `src/web/assets/sessions.js::View` currently creates one `ReportLoading.View` with a progress bar, percent and **one changing stage string**. `pendingNavigation()` repeatedly calls `showProgress(`Indexing CCost (X of N sessions)…`, label)`, combining work identity and count rather than separate stable heading/count/current-work slots. `ReportLoading.View` is shared with other routes; prefer a narrow **Sessions-owned composition/extension** so Models/Session detail/finite report loading do not change unintentionally.
- `src/application/session_catalog.py::page()` returns requested/applied sort, `pending_sort`, generation, `progress.phase/status/completed/total/reason/failed/waiting/pinned/metrics`, plus indexed/available and page_ready. It does **not currently expose a trustworthy fine-grained 'what this worker is doing now' stage**. If such an update is wanted, add only safe bounded host-owned source-backed stage information with clear provenance. Do not infer detailed activity from a ticking browser timer.
- In `sessions.js::pendingNavigation()`, each changed `progress.generation:phase:total`, or a decrease in completed count, is treated as a **rebase**. After **eight rebases** the UI calls `failNavigation('concurrent_source_change')`. It also fails after **45 seconds without an increasing completed count**, on server-reported failure, and on a 15-second unresponsive HTTP request. `failNavigation()` should render Retry/Cancel alongside an error; **no reason is confirmed for the owner's disappearance**.
- `SessionCatalog.observe()` increments `generation` when root membership/metadata or revisions change, not just when the selected global sort's key set is materially invalid. A frequently updated **running root/prompt** may be a source of churn. Examine whether harmless activity updates can unnecessarily rebase the expensive sort, reset UI progress or exhaust the eight-rebase threshold. **Do not** globally ignore meaningful revision/identity changes; stale sort keys cannot be considered qualified.
- `sessions.js::configure()` and route/hash navigation retire a previous generation and can reset the operation; `cancelNavigation()` deliberately returns to last applied sort/page. Check whether unexpected hashchange, navigation reconfiguration, lease expiry/recovery or stale replies could mimic an automatic Cancel/rollback, alongside source failures and index timeouts.
- Completed FR000664 explicitly documented limited real-source observations: `3,090` roots, only `0→75` indexed in `39.315s` and a requested CCost sort still pending; the synthetic `3,217`-root warm-cache proof was fast but **not** evidence that cold 3,000-root sorting works to completion in a live source. The newly observed longer failure needs targeted investigation, not a claim of already-resolved behavior.

## Requirements

### A. Three independently updating status regions

1. Keep stable, visibly separated **overall task above progress**, **exact completion count below**, and **momentary source-backed stage below that**. Current requested sort/direction/page context must remain correct through queued/indexing/waiting/revalidation/apply/failed states. No `Last activity` as the heading while the user is awaiting CCost.
2. Keep `percent` and progress counts tied to the **same authoritative source/index generation** and scope. Preserve normalized 0–99 while pending, real last-page denominator, deterministic restart/revalidation on genuinely invalidated source, 100 on applied. If a legitimate restart is necessary, say so explicitly, retain reusable valid facts and avoid visually implying it completed.
3. Reserve enough layout height for changing details; use fixed structural nodes and text replacement without recreating the bar or shifting stable label/count/Cancel. Coalesce rapid identical stage updates or apply a small display-only throttle when necessary, not arbitrary work delays. The current-task line may change quickly but should remain readable instead of flashing.
4. Preserve keyboard/focus/touch access to Cancel/Retry. Announce meaningful phase changes/failures to screen readers without narrating every individual indexed root or every frequent stage tick. Keep Classic/Web light/dark, narrow widths and browser zoom legible.

### B. Investigate and fix apparent automatic sort termination

5. **Reproduce the owner's CCost sort** with a cold/partially indexed large catalog and at least one **continuously running/changing session**. Trace the exact user sort intent, hash/location history, controller generation, flight/AbortSignal, lease/token/epoch, requested/applied sort, index/source generations, count/rebases, progress/failure reason, fresh activity/revisions and all success/failure/cancel UI transitions. Determine whether this is source churn, eight rebases, 45-second 'no progress', a genuine source failure, a 15-second request timeout, catalog expiry, route navigation, or another cause. Do not present a hypothesis as established without evidence.
6. **Do not abandon a valid sort because of unrelated Live/prompt updates.** Distinguish global sort membership/key invalidation from routine running activity that leaves already qualified scalar keys reusable. If a *real* source revision requires some revalidation, invalidate only what is justified, continue or rebase transparently, and preserve valid cache work; never publish a globally mis-sorted first page to mask a long wait.
7. If work is **still making real source-backed progress**, even slowly, keep the pending sort alive under the established bounded workload. A lengthy single-root read, legitimate stall or uncertain source must be distinguished from demonstrable terminal failure using truthful progress/attempt/failure facts. Review the eight-rebase and 45-second protection in light of actual large-source measurements; do not just remove all safeguards or extend timeouts indiscriminately. Every operation must eventually complete or give an explicit, actionable terminal failure/retry state.
8. **Never silently revert to Last activity or another old sort.** Until a new global sort is qualified, preserve the previously applied view as recoverable, but clearly distinguish `requested CCost (pending/failed)` from `Last activity (applied)`. On genuine failure keep an obvious, persistent error with a reason and **Retry / Cancel**; explicit Cancel restores the last applied sort/page/hash/focus/scroll. Do not quietly clear pending intent, let a hashchange impersonate a user Cancel, or allow an obsolete response to overwrite a newer request.
9. A second attempt must **reuse valid cached/indexed scalar keys** and make that continuation understandable in counts/progress. A retry must not falsely inherit a complete count from a different source generation. Preserve host resource bounds, source authorization and the existing no-unbounded-scan rule; no paid inference or automatic teardown of a user's OpenCode session.

### C. Scope and compatibility

10. Target the Sessions catalog's progress UI/operation lifecycle and the minimum source-backed progress/state changes required to fix the reproduced issue. Preserve existing real full-catalog sorting, deterministic ties, unknown-last ordering, 50-per-page epochs, Last activity/Name speed, and other reports' loading components.
11. Coordinate with **Ready FR000667** (new global sortable **CTX** column): the stable header and progress breakdown must work with **all current metric sorts and CTX when implemented**, without requiring duplicate status logic in that future column. Do not prematurely implement or rewrite FR000667.

## Acceptance and required implementation-time verification

- **Display contract:** with a seeded 3,000+ session pending CCost sort, show a stable **`Sorting sessions by CCost`** line **above** progress; live **`Indexed X of N sessions`** below; separate **current operation** detail below. Across at least 20 distinct work-phase/count updates, verify the first two lines retain their semantic slots and stable geometry while the last may change; no extra native progress track, spurious 100%, or misleading screen-reader chatter.
- **Live-source churn case:** while global sort has reached a nonzero count (e.g. around 5%), repeatedly update a different running session's activity/metadata and produce several source generations. The request must **remain pending and correct**, or show a justified explicit revalidation (not fail purely because eight ordinary prompt updates arrived). The final sorted first page must be globally correct or a real failure must remain visibly actionable. Include a case with genuinely invalidating changes to verify appropriate failure/restart and no invalid ranking.
- **Long-running / recovery cases:** test slow progress beyond one minute, one slow root, source waiting, recoverable failures, 15-second request interruption, genuinely stalled 45-second window, server terminal failure, lease expiry and stale generation replies. If a request cannot finish, verify a persistent reason plus Retry/Cancel and **no unannounced Last activity rollback**. Retry preserves only valid reusable work; explicit Cancel restores previous sort/page/hash/focus/scroll and withdraws interest safely.
- **Behavioral parity:** warm cached sorts and page changes still finish quickly without a loading flash; no extra work is triggered merely by rapid stage redraw. Test CCost, Model, Prompts, Duration, Activity/Name and CTX when separately delivered under FR000667; full-catalog membership/paging remain correct across source changes.
- Extend `development/tests/fixtures/sessions_navigation_vm.cjs`, `development/tests/fixtures/sessions_navigation_browser.cjs`, `development/tests/integration/serve_web_sessions.py`, `development/tests/test_web_session_catalog.py` and relevant real-browser Sessions navigation probes. Include source-backed tests from the installed V2 source if safely available, without paid model calls or exposing private transcripts. Document exact observed cause, progress semantics, and remaining limitations in `development/journal/web/sessions-navigation.md` and `docs/web-beta.md` when implementing; run the repository's normal relevant checks then, not during FR publication.

**End state:** The user always sees **what is being sorted**, **how much has finished**, and **what is happening right now** in separate stable places. A legitimately slow CCost sort continues transparently; a genuine failure stays explicit and recoverable rather than unexpectedly resembling a silent return to Last activity.
