# Web Watch terminal reconciliation

## Follow-up: capture starvation under revision churn

2026-11-02 · FR 000551 · v80.129

At v80.128 (`d57760e7cd9c9070c3b9ee20f13fd2155f0ba620`), six observed
running roots and four capture slots exposed a separate post-FR000546 defect.
Catalog changes reset `CardSession.last_ms` to -1. Constantly changing early
session IDs repeatedly won the timestamp/ID sort; later retained running cards
never acquired fresh lifecycle evidence, even when their own revision stabilized.
The first bounded scheduler regression never admitted its last two roots.

Real current-V2 HTTP fixtures then reproduced CLI=False/Web=True for a stopped
sixth root while the other five roots changed revisions: quota failure without
usage, interruption with zero usage, and an abandoned `tool-calls` continuation
without an idle/final/abort row after the existing continuation grace elapsed.
Each went through isolated capture, retained history, cards and immutable export;
the equivalent fresh CLI/report root was already not running. These are new
failing regressions, not a restatement of the earlier quota fixture.

`watch/cards.py` now orders eligible work by successful admission turn. Revision
changes, failures and rejected generations cannot reset that queue position.
The existing active/history rotation and four-worker cap remain. This changes
acquisition fairness only: no inactive/age/cost/quota-based retirement, canonical
continuation change, provider loop or browser-only lifecycle filter.

Regression coverage includes rejected-generation fairness, source-to-card stop
transitions, frozen duration/known usage, once-only grace, cold reconstruction,
Session detail and actual exported-stage JavaScript rendering/reload. Existing
partial/outage, missing-child/idle, later-work and stale-publication protections
remain required. Verification results belong to the task completion.

The owner's exact prompt and installed Web/CLI versions remain unknown. The
ordinary checkout's read-only Web diagnostics returned `not_observed`; that is
not evidence of an outdated or stopped host. The baseline real V2 cards/detail
probe passed (first rows 3.33s, one owner/two streams), demonstrating liveness,
not reproduction of the owner's incident. A probe interrupted by the OpenCode
server restart has no verification result. The foreground Decision Delegate
directed bounded starvation characterization and then normal delivery; it
authorized no scope/test exception or desktop interaction.

## Original terminal reconciliation

2026-11-02 · FR 000546 · v80.125

## Reproduced mechanisms

Canonical current-V2 HTTP fixtures, through actual isolated CardWorkers capture,
retention, WatchCards and immutable export, reproduced three defects:

- A child previously observed active disappears from a complete source tree.
  Retaining that session object made a freshly persisted quota terminal stay
  running in Web, while the fresh report correctly stopped it.
- An idle terminal omitted on a later refresh removed the same assistant's
  normalized terminal evidence and resurrected that attempt.
- Delayed same-generation rows/totals replaced a newer terminal capture.

The same fixtures also showed that the card export omitted the normalized quota
cause. It now exports that allowlisted cause and the page displays it.

## Ownership and guardrails

V1 transaction/V2 complete pagination plus revision brackets certify snapshot
completeness. Shared observed-history analysis keeps retained usage but uses
the fresh complete tree for lifecycle. Absent data from an unproven partial read
does not establish an end; the retained card is partial/unavailable and omitted
rows do not advance their last-observed clock. Persisted ends stay on assistant
identities, not a prompt-wide terminal lock: real later attempts/tools/children
and background work remain possible. Session detail reuses the same owner.

Complete zero-call/compaction reclassification keeps observed Web history without
claiming success or fabricating a source end. Observation grace starts once,
separately from execution; final activity counts survive without live indicators.
The shared adaptive cadence, bounded workers and 60-second continuation grace
are unchanged. Mini Watch is not implemented here; it must consume this same
server-owned card lifecycle rather than adding an age/quota heuristic.

## Evidence and limits

The new regression file covers missing/zero/positive usage, cold/repeated
reconstruction, terminal grace/history, partial/outage/recovery, reclassification,
retained active children, delayed publications and legitimate subsequent work.
Existing card tests cover concurrent focals and old generations. Actual check
results are recorded in the task completion, not inferred from this test route.

A read-only real V2 installation probe published cards/full totals, shared two
SSE streams on one live owner and verified Session detail/freeze. Owned workers
closed; the shared OpenCode service was not stopped. This does not reproduce the
owner's historical quota incident: no affected session/snapshot/version was
provided, so its exact cause remains unknown. No inference, model switch,
production prompt intervention or quota-based termination was performed.

A supplementary `--watch-cards --daily --detail` real-source probe later hit
`probe_daily_timeout`: no Daily publication within 120 seconds, and detail was
not reached on that run. The cause is unknown; live Daily liveness is not PASS.
Shared-source diff inspection found only completeness flags, no added waits or
retries reachable from Daily. Do not diagnose source churn from this result.

The foreground Decision Delegate authorized a scoped test/workflow exception:
successful supplementary Daily acquisition and a baseline comparison are not
delivery prerequisites for this lifecycle FR. Today preservation and causal
failures remain mandatory; Full, validation, the primary cards/detail probe and
actual PR checks must pass on the normally reconciled base. This is the
delegate's decision, not user approval or a broad Daily waiver.

The same Decision Delegate separately permitted paced foreground CI queries
because GitHub checks have no session notification channel. Only this narrow
interpretation of the earlier no-timers instruction was reconsidered: no
background watcher, scheduled retry, automatic merge or time/poll-count waiver;
actual current-head checks must pass. The user did not grant this exception.

A later integrated-browser synthetic DOM check rendered `Aborted · quota limit`
with terminal error class, no running rows, hidden running indicator and no
console errors. It confirms supplied-state rendering, not source truth or
physical/native-browser paint. The owned fixture was stopped afterwards.
