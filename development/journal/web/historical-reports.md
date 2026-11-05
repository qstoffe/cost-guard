# Historical date report acquisition

## Scale-fixture clock determinism — 2026-11-05

During FR 000588 verification, the unchanged 872-root correctness test passed one
Full run and failed another with four catalog calls against the old two-or-three
bound. Its two-second production catalog-hint lifetime depended on elapsed test
execution and a later revision observation. Load-induced expiry is supported by
the source, but the exact fourth call in that run was not traced.

Decision Delegate explicitly authorized a test-only repair: replace only the V2
module's local `time` binding for this synthetic build/revision-observation context,
freeze monotonic catalog age and retain real perf_counter metrics. No global clock,
production TTL, deadline or algorithm changes. All 872 prompt/request/revision/
message/context and exact 12.20800-cost assertions remain. The fixture now requires
exactly three catalog calls. Traced fake-wire stacks identified initial catalog,
revision lookup and mandatory after bracket: mocked `_client` defers endpoint
initialization, and provenance's first endpoint read clears the initial complete
catalog before revision lookup. Three is fixture-specific, not a general requirement
for an incomplete recent catalog. The delegate's initial exact-two directive was
explicitly superseded after this investigation; the first controlled attempt failed
that mistaken expectation, not a correctness assertion. Focused historical-report
and source-history tests passed afterward. Full/validator remain required, not waived.

FR 000563; Windows/Python 3.14, 2026-11-03. Pre-repair product baseline:
`f737a3f44f8d61fcf433062e7b89aa946fb23bf9` (v80.142).

## Causal evidence and scope

The original FR 000555 run remains FAILED: 120 seconds, history 868/872;
there is no retained per-operation trace proving precisely where that old run
spent every second. The new instrumented real baseline completed the same fixed
2026-10-25 report in 101.811s with 880 eligible roots (the live catalog had grown).
It spent 75.600s hydrating 914 session reads, 11.688s in six full catalogs,
3.571s reading cache, 0.507s analyzing and 4.022s projecting. These timings are
nested, not additive. Actual source reads, including child trees and consistency
rechecks, dominate; this is not Daily's former per-root catalog amplification.

V2 deep-date acquisition previously performed every independent tree read
serially. A production-report/production-V2 controlled 872-root regression gates
the first source reads: baseline cannot reach four independent reads before the
gate is released; candidate can, with no more than four submitted trees. The
separate correctness case retains 872 prompts/requests, 872 revisions and exactly
12.20800 canonical CCost credits. Its complete request results agree before and
after. Fixture setup corrections (clone fingerprint timestamps, credit conversion
and expiry of the initial catalog hint) were not product regressions.

The explicit synthetic latency model charges 140ms per root's independent reads:
serial work alone is 122.08s; four lanes require 30.52s plus actual catalog-bracket
charges. This is a causal work model, not an observed source SLA or replacement
for real HTTP/live evidence. Many-root scale checks run in Full; small actual-HTTP,
source-failure, application-progress, cancellation and browser-text checks run in Quick.

## Implementation and safety

Only date detail opts into the observed V2 batch. At most four futures/tree reads
exist at once; shared normalization/diagnostics remain serialized. Every returned
root still passes the existing before/after revision check; only unstable roots
retry, with no new retry allowance. All batch workers join before return/error.
Existing single-snapshot, Watch/Daily batching, accounts and transport read
cancellation are unchanged. The Web process still enforces 120s and 8 MiB.

Safe progress distinguishes cache, before-catalog, unverified completed tree reads,
after-catalog and analysis. A completed read count is not a verified report.
Timeout retains phase/count and gives CLI guidance; no partial result is silently
promoted to success. The deterministic deadline test first reaches actual blocked
V2 HTTP reads, then triggers the existing deadline without a 120-second sleep.
The real process is reaped and the failure retains its progress and absent result.

## Observed failure and practical limits

The first candidate live run reduced hydration to 36.232s but FAILED consistency
after 46.471s: one root continued changing through the unchanged retry bound.
The report's final stage was `revision_changed`, not a timeout. Concurrent worker
editing/source churn overlapped this run; no individual private root is exported.
It is retained as a failed run, not completion evidence. Host close took 0.1357s,
with zero residual owned threads/processes. The probe now also prints typed
application errors, rather than losing them behind a null job-level error.

Slow I/O, large histories and continuously changing roots remain unsupported as
a universal 120-second success guarantee. Explicit source/timeout failure is
required in those cases. No deadline extension, source truncation, provider/model
inference, shared-service restart, external installation or native desktop proof
is part of this repair. Final campaign commands/results are in the FR completion.

## Final verification and scoped exception

The final ordinary real campaign passed on implementation `de6a645`: fixed date
30.448s (880 roots, 912 session reads, 21.242s hydration), Daily 3.594s,
Normal/All-models/Sessions 5.903/2.468/2.346s. Detail, two SSE streams, retained
Live owner and deep Token Mix cancellation passed. Max authenticated HTTP was
0.2347s; host close 0.0934s; zero residual owned resources in that campaign.
Cache warmth and ambient load differ from baseline; this is not a controlled
3.34x universal speed claim. Deterministic gating supplies the causal comparison.

The experimental same-interpreter CPU/JSON competing campaign exceeded the
shell's 180-second deadline with an empty output file. Its product outcome,
actual CPU overlap, responsiveness and process-tree cleanup are **unverified**.
Own-session tool metadata confirmed only tool completion with `timeout: true`,
not OS process termination. No supported retained PID/handle or shell ID was
available. No other-session process/scratch inspection, guessed kill or shared
service operation was used. The continuous CPU-load flag was experimental and
removed before delivery, not rerun until green. Synthetic `run_cycle(competing=True)`
adds SSE/report cancellation but does not itself start the CPU worker; it is not
substitute real CPU-overlap evidence.

**Decision Delegate, 2026-11-03, scoped to FR 000563:** explicitly waived the
remaining real competing-load acceptance and its unavailable cleanup census,
after the supported ownership recovery yielded no handle/termination evidence.
This superseded the delegate's earlier no-exception-yet decision. It is not user
approval, does not authorize broad process discovery or interference, and grants
no future blanket exception. The delegate directed no further live-load campaign
or ownership search for this obstacle. Delivery therefore does **not** establish
successful date completion under that intended CPU load or leak-free cleanup of
the timed-out invocation. No subsequently proven interference has been observed.
