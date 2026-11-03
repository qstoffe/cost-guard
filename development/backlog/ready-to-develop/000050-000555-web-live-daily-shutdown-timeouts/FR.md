# FR 000555 — Find and fix intermittent Web Watch Daily and WebHost shutdown timeouts

## Owner decision, priority and required outcome

**Owner-approved executable FR, 2026-11-03.** Permanent identity **000555**; Ready priority **000050** (medium-high, ahead of optional further Web expansion).

The owner requests a **root-cause fix with stronger-than-usual acceptance requirements** for recurring broad live-probe failures in Cost Guard Web. The requested result is not a prettier log, a longer timeout, or a single green rerun. Both the Daily-publication failure and the owned WebHost-shutdown failure must be investigated and resolved according to the evidence, even if they turn out to have different causes.

**Successful outcome:** the existing full Watch live flow can acquire and publish truthful Daily data, keep cards and streams coherent, and terminate its *own* WebHost/workers within the existing bounded lifecycle. Required end-to-end runs pass repeatedly, including a controlled contention case, without losing relevant diagnostic evidence or touching the user's shared OpenCode service.

This FR authorizes focused fixes in production or the test harness **only after establishing which layer is responsible**. An external-source delay, fixture defect, lifecycle deadlock and probe measurement defect must not be conflated.

## Observed evidence, not yet a diagnosis

Multiple recent, completed FRs explicitly retain failures:

- **FR000546 and FR000547:** broad live probes with --watch-cards --daily (sometimes --detail) reached probe_daily_timeout after a 120-second Daily wait; some also reported web_shutdown_timeout during cleanup.
- **FR000549:** broad --watch-cards --daily --reports failed a short /api/live request during the Daily wait and then hit owned-host shutdown timeout.
- **FR000551 / PR #129:** a real-source run reached cards/detail but shutdown timed out while Full tests were concurrently active; its later serial run passed. No root cause was established.
- **FR000552 / PR #130:** the first live run reconciled Daily and cards but failed WebHost shutdown; the subsequent diagnostic rerun passed, without proving the cause.
- **FR000544 / PR #131:** the broad Mini Watch run acquired valid live data but failed during WebHost close; direct acquisition close passed separately and does not prove host shutdown.
- **FR000554 / PR #134:** the first source run timed out during Daily wait/cleanup amid edits; stable-source repeat passed. The cause remains unknown.

The current development/tests/integration/probe_web_live.py uses a **120-second Daily-publication deadline** and per-request /api/live timeout. src/web/host.py::WebHost.close asks the owned serving thread to join for **10 seconds** and raises web_shutdown_timeout if it is still alive. Its serving-thread cleanup includes ReportJobs.close, LiveRuntime.close, EventHub close and HTTP server close. Those are **inspection starting points, not identified culprits**.

Some later runs have passed. Those successes are valuable controls, but do **not** invalidate earlier failures. Do not claim that every failure has one common root cause or that the current Web UI itself is necessarily defective.

Related completed changes must be preserved: FR000546/551 terminal lifecycle and fair card acquisition, FR000547/549/552 native-period and Daily semantics, FR000544 Mini Watch, FR000554 availability smoothing, FR000553 proportionate verification.

## 1. Establish exact failure ownership and causality

1. Inspect and map the actual start, acquisition, Daily computation/publication, /api/live polling, SSE clients, ReportJobs, source-workers and WebHost stop/close paths. Distinguish **(a)** no Daily publication, **(b)** blocked/slow authenticated HTTP request, **(c)** host closing late, and **(d)** cleanup failures after the primary error. These can be separate bugs.
2. Collect **bounded, monotonic phase timings** and sanitized state for both success and failure. At minimum identify the last completed operation and elapsed wait for Daily acquisition/projection/publication, selected pending work, HTTP response, jobs close, LiveRuntime close, EventHub close, server close and WebHost thread join. Identify owned process/thread/task counts before and after; record the first failure as well as cleanup failure. Use existing diagnostics, focused probe switches or temporary test-only instrumentation as appropriate; do not add permanent personal telemetry.
3. Reproduce the diagnosed failing mechanism **against the baseline behavior** using a deterministic, causally connected test of the real production owners; establish a failing pre-fix outcome and passing post-fix outcome. Where the intermittent real-source symptom itself cannot be forced safely, combine observed real phase evidence with a deterministic injection of the **same demonstrated blocking mechanism**. An arbitrary sleep or fabricated error unconnected to the source path is not adequate.
4. **Reach a supported root-cause conclusion for each failure class.** It is acceptable to show that one is entirely a probe/harness error and another a product bug, or that both share one proven mechanism. It is not acceptable to relabel unknown cause as fixed because a rerun happens to pass. Explain earlier successful serial reruns and failures under contention as far as the evidence permits.
5. Do not let probe cleanup hide the triggering exception. If Daily fails and close also fails, report **both**, with phase, source scope and time, preserving the primary failure. Test reports must distinguish an incomplete/no-data source, slow source, true product failure and harness assertion error rather than manufacturing PASS.

## 2. Fix at the owning boundary — without weakening behavior

1. Correct the identified production/harness mechanism. In-flight Daily/report work, source delays, polling/SSE readers, concurrent Full or other verification activity, cancellation and late completions must not leave the owned host uncloseable or starve valid Daily publication indefinitely.
2. Shutdown must be **bounded, repeatable and idempotent**. Normal stop, failure stop and stop while a Daily/report/source read is pending must close the host's *own* workers/threads/sockets and leave no test-owned orphan, blocked join or second acquisition owner. Existing 10-second WebHost serving-thread join remains the maximum acceptance bound; no simply raising it or adding hidden waits/retries to pass.
3. Preserve canonical **Daily totals, attribution/completeness, partial/unavailable status, account-native periods, card lifecycle, retained freshness and SSE identity/sequence semantics**. A missing or delayed Daily result must not be falsely converted to an empty/successful result. Mini Watch and normal Web Watch must still share one Live acquisition owner.
4. Keep actual provider/source problems visible and classified; do not mask them with CSS suppression, unconditional success, endless retry, swallowing exceptions or automatically restarting the host/Shared OpenCode. A genuinely unavailable source may produce a truthful, explicit unavailable outcome, never a fabricated Daily pass.
5. Maintain existing process identity, loopback/auth/CSRF, bounded capture and source security, normal Stop/Exit, Windows/Web startup and CLI behavior. Do not change quota/account/pricing semantics, introduce provider polling, modify credentials, infer model output, or touch user history.
6. **Do not change the 120-second Daily probe deadline, 10-second host join, request timeout or live test gating as a substitute for diagnosis.** Any necessary test-only timing adjustment must be causally justified and preserve an equally strict observable bound; no weaker acceptance or unconditional skip is authorized by this FR.

## 3. Mandatory regression and repeatability evidence

Acceptance requires **all** the following, not merely a subset:

1. **Before/after reproduction:** at least one pre-fix RED / post-fix GREEN deterministic regression for each established, distinct Daily/HTTP and shutdown failure mechanism. If one root cause explains multiple symptoms, prove both manifestations. Exercise actual production lifecycle and probe behavior where appropriate; pure mocks of already-successful output are insufficient.
2. **Controlled failure matrix:** verify delayed/nonresponsive acquisition, pending/failed Daily, HTTP timeout, stop while cards/Daily/report are active, one or two SSE subscribers, cancellation and repeated close. Assert no deadlock, truthful errors, preserved primary plus cleanup diagnostics, bounded close and no owned-resource leak. Include both otherwise healthy serial use and deliberate overlapping work similar to the observed contention.
3. **Repetition:** run the relevant end-to-end deterministic harness **at least 10 consecutive cycles under ordinary/serial conditions and 10 under controlled competing workload**, with zero timeouts, inconsistent Daily values, stuck owned workers, false PASS or cleanup failures. Repetition is supplementary to causal testing, not a substitute for it.
4. **Actual integration:** on an authorized, read-only **real OpenCode V2 source with eligible Daily history**, run the **full** existing probe_web_live.py --watch-cards --daily --detail path **three consecutive times**, each obtaining actual coherent Daily publication, cards, SSE continuity and **successful owned-host shutdown**. Also complete at least **one** bounded real-source run including concurrent reports or equivalent representative competing work. Retain phase timings. Do not pass this requirement using a synthetic-only browser fixture, direct LiveRuntime.close, or the shorter Watch-cards-only path.
5. **Production time bounds:** on all applicable successful test conditions, Daily appears within its unchanged **120-second** probe bound, each authenticated HTTP request respects its existing limit, and owned WebHost shutdown completes within the unchanged **10-second** join bound. A genuinely inaccessible real source is an explicit **unverified/blocked** result, not acceptance.
6. **Normal verification:** execute applicable focused and full product tests, package validation and platform-specific checks for touched code. Preserve the current FR000548/553 proportional CI setup; no broad new recurring validation framework. Report every failing, skipped, unavailable or not-run requirement accurately. Mac-native or physical-desktop acceptance is not implied by Windows/headless evidence unless changed code requires it.
7. **Reviewable completion evidence:** record baseline and final commit, fault classifications, root-cause chain(s), exact test commands, number of repetitions, pass/fail counts, elapsed time and resource cleanup observations, failures encountered along the way, source limitations and remaining risk in the normal PR and COMPLETION.md. Sanitize identities, account data, source paths and credentials.

## Completion is deliberately blocked if the gap remains

This owner's **acceptance conditions take precedence over a desire to empty the queue quickly**:

- If either failure class is still unexplained, only a lucky rerun exists, a required causal regression is missing, the full real-source integration cannot run, or owned-host cleanup still times out, **do not mark FR000555 Complete or describe it as fixed**. Retain it in Ready while actively investigating, or place it On Hold with the concrete missing prerequisite if genuinely blocked. Preserve partial work/evidence and report why.
- Neither an implementation worker nor Decision Delegate may silently replace the mandatory real-source/causal tests with narrower checks, reclassify FAIL as PASS, or grant itself a candidate-specific waiver of these explicit acceptance requirements. **Only a new explicit owner decision can change that scope.** Delegate help with diagnosis and ordinary technical choices remains allowed.
- A fix may consist solely of correcting the probe/harness **if the evidence proves both observed categories are harness-owned**. No gratuitous production rewrite is required. Conversely, a harness-only change is insufficient if a production lifecycle bug remains.
- No claim of a universal guarantee against arbitrary future provider outages is requested; the FR instead requires a proven causal repair and repeatable bounded behavior under the defined conditions.

## Safe execution and limits

All live acquisition is **read-only**. Use only the test's own WebHost/processes, temporary files and browser sessions. **Never stop, restart or reconfigure the user's shared OpenCode service; do not exhaust a quota, trigger model calls, alter sessions, credentials or user data.** Do not operate the visible desktop without separate authorization. Use focused bounded runs and avoid running a high-cost repetitive real-source campaign without evidence that it is necessary; deterministic repetition takes the bulk of the load.

No new UI feature, release migration, monitoring service, separate history index, global timeout increase or permanent telemetry architecture is requested. Implementation may touch src/web/host.py, src/application/live.py, src/web/jobs.py, the Watch acquisition path and/or development/tests/integration/probe_web_live.py as the established cause requires. Update affected architecture, journal, runbook and version metadata only as required by actual functional changes.

## Initial references

- [FR000547 completion](../../complete/000060-000547-watch-table-surfaces-native-quotas-and-quiet-refresh/COMPLETION.md)
- [FR000551 completion](../../complete/000061-000551-web-watch-stopped-prompts-still-running/COMPLETION.md)
- [FR000552 completion](../../complete/000062-000552-web-version-and-watch-subscription-cards/COMPLETION.md)
- [FR000544 completion](../../complete/000063-000544-mini-watch-floating-status/COMPLETION.md)
- [FR000554 completion](../../complete/000066-000554-watch-warning-connection-and-history-order/COMPLETION.md)
- [Host lifecycle source](../../../../src/web/host.py)
- [Real-source probe](../../../../development/tests/integration/probe_web_live.py)

**This authoring delivery adds only the executable FR and permanent ID bookkeeping. It does not diagnose the runtime issue, claim a test PASS, change product code or install the Web app.**
