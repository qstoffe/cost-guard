# Stopped parent, outstanding linked subagents — FR000708

2026-11-14 · v81.52 · base `a8623ec67ab85f41d22a5e0be544e58b6a7d8bcf`.

## Reproduction and cause

The owner report was not a captured live interruption trace. A sanitized synthetic
native V2 service reproduced three distinct failures before production edits:
closed delegation plus executing child, quiet child without an assistant, and
superseded cancelled parent plus executing background child. Three of four initial
tests failed RED; the unrelated-child negative already passed.

`causal.py` combined parent cancellation/supersession with tree execution and used
one terminal cutoff across parent/child messages. Child activity also required an
open delegation window. A tool's completed/aborted launch could therefore exclude
an already-running child and its late completed request. Parent success/error
flags could also leak into a tree that still had outstanding work.

## Ownership and lifecycle

- `ChildLinkIndex` retains validated physical calls, parent-session ancestry and
  launch times. A crossing assistant or acknowledged child turn awaiting its first
  assistant binds that execution beyond the tool return; cold reconstruction binds
  the subsequently completed physical request too. A later invocation/independent
  turn bounds extensions. Existing in-window request multiplicity is preserved;
  an unrelated assistant starting after a closed completed launch stays unallocated.
  For an unambiguously newly created child, its first turn may arrive after the
  launch acknowledgement; that creation-qualified fallback never applies to an
  older reused child. A separate RED→GREEN regression covers this delayed turn.
- `child_activity.py` separately qualifies descendant activity from fresh native
  status, scoped message/tool evidence and owned background activity. It never
  fetches source history. Open accounting windows alone are not active proof;
  native status cannot borrow a displaced child invocation or resurrect a durable
  owned end. Complete process-local inactivity with an unfinished owned attempt is
  Unverified, not a globally proven completion or another server's execution.
- Parent cancellation/failure/success and terminal time remain separate facts.
  `subagent_active` projects normal tree RUNNING while aggregate terminal flags
  remain off. The final owned end restores the parent's real Aborted/Error outcome.
  Abort reason is retained rather than erased while a child runs.
- Scoped child terminal proof, including a user attempt ended before any assistant,
  extends the existing causal-tree elapsed duration without inventing a priced
  request. It does not reopen the parent tool, infer ongoing parent model requests,
  alter billed/reference CCost or redefine active-AI time.
- Source retention, generation/epoch rejection, acquisition scheduling, terminal
  grace and recent/history owners are unchanged. Analysis/scalar caches advance to
  algorithms 22/8. No source mutation, model call, interrupt, resume or restart.
- Added lifecycle fields exposed a causal 100-card payload failure. Multi-call
  Live DTOs now omit redundant legacy singular invocation detail when the same
  call is already in the plural list. Single-call compatibility and the original
  input/event/replay budgets remain unchanged; the stress regression now includes
  cancelled-parent/active-subagent facts.

## Decision Delegate clarification

The Delegate's initial advice proposed one shared visible representative per root.
Existing `test_watch_cards.py` explicitly requires 100 concurrent per-prompt Full
Watch cards in one root and independent per-prompt terminal grace. After inspecting
that evidence, the same Delegate superseded its earlier population recommendation:
preserve Full's individual focal cards and aggregate counts; preserve Mini/PiP's
existing per-session representative preference. The FR's “existing one-card” rule
applies where it actually exists, notably Mini. Cross-surface parity means shared
lifecycle facts, not identical populations. No acceptance-test waiver, Suggestion
or hold was authorized or used.

A newer genuinely running prompt can represent the root in Mini without inheriting
the older prompt's child costs. If the newer prompt ends while that child continues,
the older running prompt can represent it again. All causal rows retain their own
identity/usage in Full/detail and CLI.

## Verification

- Focused source/analysis/abort/attribution, duration, coverage/cost detail,
  Watch/detail/catalog/CLI and invocation-budget regression run: **86 tests passed**.
- Synthetic native source → isolated Watch capture → publication → Full DOM and
  actual Document PiP: **6 Chromium cases passed**, three themes × wide/narrow,
  five observations each (running, parent stop, repeated child activity, terminal
  grace, Earlier). Assertions cover running styling/ARIA, retained cancellation,
  no reopened parent delegation, final Aborted, no duplicate Mini row, frozen final
  duration and cold presentation reconstruction.
  Evidence: `scratch:/stopped-parent-browser-final/results.json`.
- Package validator: **0 failures**, 11 checks passed, 8 existing/advisory budget
  warnings. Product version/date/readme/history agree on v81.52 / 2026-11-14.
- Full suite passed all **199 groups**, 0 failures in 183.5 seconds, before the
  additional delayed-first-turn edge was added. On continuation, the earlier final
  background process was absent and its output unavailable; no result is claimed.
  A retained final-byte Full rerun passed **199/199 groups**, 0 failures in
  **166.6 seconds** (`scratch:/final-full.log`).
  The final edge/ownership focused run passed **48 tests**;
  invocation-detector plus stopped-parent suites passed **36 tests**.
- Clean real-installation `probe_web_live.py --tool-outcomes --watch-seconds 90`:
  **PASS**, authenticated V2, one Live owner, two verified streams, sequence
  advancement, source guard unchanged, one observed activity card with five
  failed-call details; zero generated model calls. First rows arrived in 1.649
  seconds. Owned workers closed and shared OpenCode stayed untouched.
- A broader stable-tree `--watch-cards --tool-invocations` observation was
  **INCONCLUSIVE**, not PASS: the unrelated global Earlier proof reached 452 of
  3251 roots within 90 seconds, while 197 publications/208 captures advanced with
  no source errors. No all-history claim is made.
- A first narrow invocation probe inspected only legacy singular details, which
  this change suppresses for multi-call publications. Its negative was therefore
  **INCONCLUSIVE—detector mismatch**, not demonstrated natural inactivity. On the
  Delegate's instruction, `invocation_observations.py` now validates actual plural
  DTO shape, retains running/verification/privacy/size checks, falls back to legacy
  singular details and deduplicates physical identities. The existing stress
  fixture checks 1000 published identities and a duplicated singular fallback.
- Corrected stable-tree `--tool-outcomes --tool-invocations`: **two published live
  invocation details verified**, one native command and timeout label preserved,
  one observed card/five failed details, one owner/two streams, source unchanged,
  no model calls. First rows arrived in 2.198 seconds. The final immediate cleanup
  assertion nevertheless failed because one account-quota daemon thread was still
  in an unrelated HTTPS read; zero child processes and no cleanup-operation
  failures were reported. All Live/HTTP/card/source-event workers had ended. The
  probe process then exited, ending its residual daemon thread. This whole command
  is **NOT PASS**; its successful publication assertions and teardown gap are
  distinguished, not averaged into a green result.

The initial Full run found a pre-response-child duration omission and two causal
regressions (over-clipped in-window child requests and expanded 100-card payload).
Those were repaired; no tests/caps were weakened. An initial read-only live run
verified V2/authenticated single-owner publication but correctly stopped when this
worker edited three source files during the run. That run is **not PASS** and is
not an authentication/source-access failure. Its owned cleanup completed; a stable
tree reruns above supply independent evidence.

The browser sequence is synthetic, not a live stopped-parent reproduction. Real
installation checks must remain read-only; no owner session was stopped or new
paid inference generated for this feature. Native macOS UI/OS behavior is outside
this lifecycle change. No ZIP, tag or GitHub Release is produced.

## Scoped live-verification exception

The active Backlog Decision Delegate (`ses_e25bbc26dffeKsfh1u0sN97S7e`)
authorized delivery after final-byte Full/CI and normal gates, accepting only the
corrected probe's immediate teardown assertion failure. It inspected
`AccountAcquisition.close()`: the shared 200 ms join budget intentionally permits
an in-flight provider HTTPS read to remain daemonized, discards post-close results,
and has an existing nonblocking-close regression. This observation does not
establish a regression caused by FR000708.

No further live rerun, unrelated quota/shutdown refactor, Suggestion, hold or owner
question is required by that decision. This is not an overall probe PASS or a
blanket cleanup waiver: that command exited 1 with one quota daemon and zero owned
processes; its subsequent process exit ended the thread but proves neither graceful
HTTP completion nor natural retirement latency. The two verified published
identities remain useful evidence. The first singular-only negative and broad
Earlier observation remain INCONCLUSIVE; the actual owner interruption remains
NOT REPRODUCED. Synthetic lifecycle/browser acceptance is independent evidence.

## Architecture

`development/architecture/modules/CODE_MAP.md` and the affected Web guide were
updated. Ownership remains source → domain → analysis → reports/application →
presentation. No architecture-wide revalidation or new acquisition/retention
framework is claimed.
