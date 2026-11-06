# Suggestion 000604 — Preserve actionable causal windows when Session Learning context is fitted

Origin method: **session-learning**, Cost Guard maintenance milestone 50, 2026-11-06.
Origin repository: **Cost Guard**, base `dd27df2a77206a615f212877ae4d6d7470ebab8f`.
Proposed implementation owner: **OpenCode Toolkit / shared-repo Session Learning**,
especially `skills/shared-repo/scripts/session_learning.py::fit_context` and its
focused Python regressions. This is an unprioritized proposal for human review,
not an approved FR, implementation, or permission to change the installed Toolkit.

## Observed problem and impact

A supported newest-eight repository-scoped sample exported successfully. The
extractor marked seven observations relevant, but every retained relevant
projection was INCONCLUSIVE. Its final fitting step reduced each to one first
event: four contained successful scratch-bootstrap calls, two contained Resume
instructions and one contained an interruption message. The actual failure,
applicable authority and subsequent recovery/outcome were not retained together.
Signal counts and tentative work groups cannot establish incident causes.

The historical assessment was explicitly deferred, not declared clean or complete.
A delegate-authorized single metadata request to reconnect one original hashed
identity did not find its target in that bounded page. It stopped before private
message retrieval, without substitution or additional exports. Recovery remains
possible in principle, but the discarded session-to-window association made this
particular bounded attempt unsuccessful. This does not prove sessions were lost
or establish why the directory-scoped page no longer included that identity.

## Source-backed mechanism and confidence

Toolkit source was checked at
[`1a144f8d6e1d8385ec76ea9cd3c490504595f892`](https://github.com/qstoffe/opencode-toolkit/commit/1a144f8d6e1d8385ec76ea9cd3c490504595f892).
The installed analyzer's Git blob hash exactly matched current source blob
`8f614467c555620dd724d400f39efc8d76d4b693`; no installed release version is inferred.

In `fit_context` (lines 399–432 at that revision), the initial narrowing greedily
keeps chronological events up to a per-session allowance, irrespective of whether
the candidate and its follow-up survive. The final batch fallback takes only the
first event of the first retained window. A window beginning with authority or a
successful preceding call can therefore lose the incident itself. This mechanism
is directly observed; underlying historical task defects, independent incident
counts and avoidable human interventions remain unknown.

Long instructions, overlapping windows, conservative scrubbing and genuine input
size pressure are plausible contributors, not reasons to relax privacy or claim
causal completeness. The existing honest INCONCLUSIVE result is correct; the
proposed improvement concerns evidence usefulness, not changing that verdict.

## Smallest useful change to consider

Fit a coherent candidate/authority/recovery window rather than arbitrary first
events. Where the existing allowance cannot contain one, retain a bounded,
private supported recovery association and clearly identify what is missing,
instead of spending the remaining context on unrelated successful bootstrap text.
Compare this with simply removing redundant overlapping context before adding
another helper, preflight or state mechanism. Do not increase the eight-session,
24,000-character, per-export size or time limits as part of this proposal.

Any supported locators must remain confidential and ephemeral, never a published
session index, durable cursor, owner registry or cross-repository discovery route.
No raw export retention, additional export authority or automatic retry loop is
proposed. The analysis may still correctly remain INCONCLUSIVE.

## Existing coverage and semantic comparison

Completed Toolkit FR 000375 repaired per-export size limits, sequential disposal
and nonblocking partial failures. Its retained requirements already call for
useful bounded projections, but its completion is not proof of multi-session
candidate preservation. At the checked revision,
`development/tests/session_learning_test.py::test_context_overflow_retains_scrubbed_partial_cause_not_false_completion`
checks the bound, INCONCLUSIVE, prior authority and secret removal in a long
single-session fixture; it does not assert that the candidate and recovery remain
together after the multi-session fallback. These tests were read, not run here.

Targeted available planning names and that completed specification/completion
revealed no separate candidate-preserving fitting delivery. Cost Guard's pending
UX tasks and its two parked Web migration suggestions address different problems;
its rejection inbox was empty. This is a targeted comparison, not a claim that
all historical or external plans have been semantically audited.

## Readable regression and protected negative behavior

Use synthetic exports with long initial authority, successful bootstrap calls,
a distinct failing tool response, a recovery attempt and a known outcome. Combine
enough observations to trigger both per-session and batch fitting. Within the
unchanged allowance, retain at least one coherent actionable window, or honestly
report insufficient capacity with a usable bounded private recovery association;
do not call an isolated bootstrap event useful causal coverage.

Keep wrong-repository/identity rejection, exact export threshold, sequential raw
disposal, secret scrubbing, Stop and explicit authorization boundaries. Unknown
authority, missing outcomes and truncated evidence must never become PASS,
NO_SUGGESTION, a recurrence count or completed progress. Prove no confidential
locator or raw transcript enters a suggestion, report, Git or durable cache.

## Publication exception and uncertainty

`repository_contract.py priority --stage suggestions` failed with CONTENT_INVALID
(bounded regular UTF-8 document validation). The exact failing document/condition
was not identified; a Complete-body failure is not established. The Decision
Delegate authorized this one manual next-watermark allocation, with names-only
collision checks and atomic publication of this proposal plus watermark 604.
The helper remains failed, not PASS. No helper repair, promotion, implementation,
product tests, measured savings or verified historical task outcomes are claimed.
