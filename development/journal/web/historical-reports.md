# Historical date report acquisition

FR 000563; Windows/Python 3.14, 2026-11-03. Pre-repair product baseline:
`f737a3f44f8d61fcf433062e7b89aa946fb23bf9` (v80.142).

## Causal evidence and scope

The original FR 000555 run remains FAILED: 120 seconds, history 868/872;
there is no retained per-operation trace proving precisely where that old run
spent every second. The new instrumented real baseline completed the same fixed
2026-10-25 report in 101.811s with 880 eligible roots (the live catalog had grown).
It spent 75.600s hydrating 914 session trees, 11.688s in six full catalogs,
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
