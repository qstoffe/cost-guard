# FR 000550 — Finer-grained loading progress on the Web Models page

## Owner request and priority

The owner requested this improvement on **2026-11-02**, with **low priority**. When the Web Models page loads, its progress indicator appears to jump to roughly **35%**, then **55%**, remain there for a long time, and suddenly finish. The owner wants more frequent, useful percentage updates through the remaining work to 100%, where feasible.

Permanent identity: **000550**. Ready priority: **000900**, after the currently queued FR000549, FR000547 and FR000544. This is a small Web loading-feedback improvement, not a request to redesign Models or optimize the entire startup pipeline.

Improve the existing bar and concise status line by reporting finer real work progress. Preserve the minimal loading layout and successful-result behavior established by FR000535 and the subsequent unified Models route.

## Feasibility and inspected cause

Inspected main: **`7703e141cec502e1c11aee91ef395975ac3d4b12`**. The source supports a practical improvement using the existing progress channel. The owner's exact timings and 35%/55% sequence were not reproduced against their local data.

- `src/web/assets/app.js::overviewProgress` maps broad phases to fixed percentage bands: history 30–55, projection 55–70, quotas 70–90, availability 90–95, and finalizing 95–99. A phase with no usable total stays at its starting value; `Math.max` prevents backward movement. Repeated work in an already-consumed phase band cannot advance the bar.
- The actual Normal report used by `#/models` does not follow that assumed phase order. `src/reports/service.py::_build_dashboard` samples history, announces projection, checks availability during model comparison, then obtains quotas and loads their separate period history. An early availability event can therefore move the estimate ahead of substantial later quota/history work, which the monotonic clamp then hides.
- `src/reports/acquisition.py::RootAcquisition.analyze` reports history without counts. `prepare` has counted analysis updates but cache checks and batch loading are less granular. `src/reports/sampling.py::recent_sample_roots` may stop early once its sample cutoffs are satisfied, so the number of roots ultimately needed is not a known fixed workload from the outset.
- `WorkProgress` and `ProgressEvent` already carry phase/completed/total. `ReportApplication` forwards approved phase/count metadata, and `ReportJobs` transports and coalesces it. The browser consumes both job polling at roughly 500 ms and progress events. A new transport or more provider polling is unnecessary.
- The Normal path does not currently emit a finalizing event covering final report projection/packaging. The existing browser code correctly reserves 100% for receipt of a successful complete acquired report.

This is principally a progress-instrumentation and mapping problem. Merely animating the existing coarse milestones or adding decimal places would leave it unresolved.

## Required behavior

### Track meaningful work throughout this load

Use existing work boundaries and countable units to produce more intermediate updates during the longer Models-loading stages. Suitable opportunities include completed cache/session analysis units and model/report preparation batches where the work is actually performed. Add only the callbacks/metadata needed for useful feedback.

Make the overall estimate reflect the actual Normal-report workflow, including repeated history passes, separate account-period history and work that overlaps in the background. Give distinct stages/substages appropriate progress ownership so completing an early pass does not exhaust the percentage range needed by later work. Do not serialize independent work simply to make the bar easier to calculate.

Where a reliable denominator exists, derive progress from completed units. Report completion after the unit finishes. Where the amount of work is discovered incrementally or sampling can stop early, use an honest bounded estimate or completed-work status; do not scan extra history merely to discover an exact denominator.

Use a proportionate shared progress extension if needed, updating the application's approved event mapping along with it. Preserve the existing safe phase/count boundary; source paths, session IDs and raw provider/debug messages do not belong in the browser's progress display.

### Keep the display responsive and honest

- Retain a monotonic 0–100 bar and one short meaningful status line. Keep the existing approximate presentation when the global percentage is stage-weighted rather than measured.
- Aim for visible whole-percentage updates in smaller steps during measurable work, using the existing bounded delivery cadence. There is no requirement to display every integer, add decimals, or hold a fast load open to animate all steps.
- Reserve progress room for genuine later preparation. Do not simply move today's long stall to 95% or 99% while known substantial work remains.
- A blocked operation with no intermediate observations can legitimately pause at its current estimate with a truthful stage label. Do not advance solely because time passes or claim an exact remaining time.
- Keep burst handling/coalescing bounded so extra progress callbacks cannot delay the report, block control/cancellation, or flood the UI. Stale or duplicate observations from polling and events must not move the bar backward or overwrite a newer load's progress.
- Reach **100% only when the complete successful report has arrived and is ready to show**, then use the existing transition to the Models table. Errors, timeout, offline/authorization failure, cancellation or partial acquisition must retain their established truthful behavior.
- Preserve the existing accessible progress/status semantics and minimal layout. Optional visual interpolation must respect reduced motion and follow an already observed value.

No changes are requested to the Models data, filters/sorting, account calculations, snapshot semantics or CLI progress presentation. Shared backend instrumentation may benefit other consumers, but must preserve their behavior.

## Acceptance and focused verification

1. **Representative slow Models load:** exercise the actual Normal-report progress path through the Web job boundary and browser using a bounded slow fixture with enough real units to expose intermediate work. The long countable portions produce several distinct intermediate percentages; later quota/history/preparation still has room to advance. The bar no longer effectively consists of a few coarse milestones followed by completion.
2. **Actual stage order:** cover initial sampling, comparison/availability, account completion, account-period history and final preparation as applicable. Repeated history passes, nested callbacks and parallel completion do not freeze the global estimate merely because an earlier phase reached a higher fixed band.
3. **Known versus unknown work:** counted stages reflect completed units; early-stopping samples and unknown/blocking I/O remain honest. No fabricated denominator, clock-driven progress, premature 100% or extra scan/fetch is introduced.
4. **Fast and cached loads:** cached, empty and short workloads may skip unnecessary intermediate values and finish promptly. Progress does not delay a ready report, change the result or disturb existing cache/batching and source/provider request behavior.
5. **Lifecycle and presentation:** keep monotonic progress for the current job across polling/events, proper reset for a genuinely new load, and existing failure/partial behavior. In a browser, confirm the concise line, accessible value, completion transition and no noticeable layout churn. Navigation to an already captured Models result must not start acquisition just to replay the bar.

Extend the relevant existing checks, especially `development/tests/test_application_reports.py`, `test_startup_progress.py`, `test_web_runtime.py`, `test_web_views.py`, and `development/tests/integration/web_minimal_overview.py`. That browser fixture currently supplies a hand-written phase sequence; retain its useful UI coverage, but also verify observations generated by the real Normal workflow so an incorrect phase-order assumption is caught.

Record which operations remain inherently unmeasurable between start and finish. A small before/after progress observation from the representative fixture is sufficient evidence; no permanent telemetry system, benchmark suite or full-provider live-testing requirement is introduced.

## Delivery scope

This FR adds finer loading feedback specifically for **Web Models**. Reuse the existing job lifecycle, polling/events, source caches and concurrent acquisition. Avoid additional source/provider requests, an always-growing progress log, or a broad performance rewrite.

Creating the FR is backlog-only: publish this document and advance the permanent-identity counter without product code or release/version changes. Implementation follows the normal repository delivery process.
