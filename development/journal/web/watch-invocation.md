# Full Web Running invocation disclosure — FR 000632

2026-11-08 · v80.207 · base `7eff2c84ca9f35ca69d41b0b45aea5aee2a5c890` plus this FR diff.
Scoped feature evidence, not a whole-application architecture or performance audit.

## Boundary and lifetime

`watch/invocation.py` opts in only from Web card capture. It copies supported small
scalar inputs from `tool_input`, never whole part/state/output/metadata. Unknown,
nested, content-bearing, secret-pattern and oversized fields are withheld and
qualified. String length is checked before screening; all serialized candidate
input is bounded before publication. Safe strings retain quotes and actual newlines.
Freeform screening is conservative and cannot promise to identify every private value.

Opaque identities include source type/generation/instance and canonical physical
call identity; revisions include call update time and filtered content/qualification.
Duration publication reuses capture-derived values. No new provider read, endpoint,
service, command execution or persistent input storage is introduced. `cards.py`
withholds detail while catalog generations await verification; application/browser
also suppress terminal, unverified or unavailable/retained live detail.

Source normalization adds original part/call identities to `BackgroundActivity`.
Unknown registry evidence and conflicting origins supply no disclosure link. Watch
requires one running job and one scoped physical original call; kind names are never
identity. Aggregates and absent links show unavailable, not a foreground command.
Running status foreground uses `--watch-running` for both sources; this supersedes
only FR000584's old background gold/brown decision. Ordinary activity/outcomes retain ink.

## Reproducible evidence

- Final `run_tests.py --suite full`: all 171 files passed, 2102 tests, zero failures,
  119.4 seconds. One existing macOS zsh/PTY skip on Windows. A final source-identity
  namespace regression distinguishes canonical call IDs from otherwise equal part IDs.
  Earlier execution: 170/171 files initially passed.
  New card test failed due to a mismatched fixture capture/projection clock, corrected
  only in the fixture. `--pattern test_watch_cards.py`: 25/25 passed afterward. This
  earlier attempt was not a clean Full PASS; the subsequent clean Full is above.
  Initial obsolete paragraph assertions were changed to assert the same short
  summary plus the new honest unavailable note; affected suites now pass.
- `test_watch_invocation.py` is admitted in Quick/Full, covering legacy/current input,
  privacy/huge values, scope/deduplication/corrections, background matching/ambiguity,
  and bounded 100-card Live/replay publication without re-derivation on duration ticks.
- `validate_package.py --working-tree`: 11 passes, 0 failures, 7 advisory warnings.
- Integrated browser disconnected. Permitted hidden Edge 156.0.4314.58 ran
  `serve_watch_summary.py --tool-outcomes` with `probe_watch_tool_outcomes.cjs`
  and `probe_watch_invocation.cjs`: Classic/Web light/Web dark × 1366/360px, 6 cases.
  Actual native keyboard/mouse/touch interaction, selected-text/focus/node/scroll
  retention over 8 duration updates, identity/revision/source/aggregate invalidation,
  long unbroken wrapping and text injection checks passed. Expanded/collapsed images
  were inspected. This is synthetic browser evidence, not native desktop/real secrets.
- Real V2 `probe_web_live.py --tool-invocations`: 1 bounded live detail observed,
  one producer/two verified advancing streams, 0 probe model calls, no cleanup failures
  or remaining owned workers, shared OpenCode untouched. Source view 0.846s,
  overall 39.1074s including observation/streams/cleanup; not a benchmark claim.

## Inconclusive ancillary check and decision

The first broader `--watch-cards --tool-outcomes` attempt overlapped a product version
edit. Normal SourceGuard shutdown invalidated it (connection reset), not PASS.
The frozen-source attempt retained Earlier loading 933/2972 at 90 seconds, with no
pre-cleanup source/runtime errors and advancing Live publications. It did not reach
subsequent real tool-outcome assertions. Its cause and whole-history health remain
unresolved; no timeout/requirement/assertion was weakened to manufacture success.

**Decision Delegate**, after inspecting the FR/probe/tests, approved a scoped
verification exception for FR000632: focused active-invocation live evidence plus
deterministic/rendered checks are adequate; success of the unrelated full Earlier
probe and a 300-second retry are not required. No product acceptance was waived.
It also accepted the earlier Full execution plus targeted fixture correction.
The subsequent identity-namespace source regression triggered a fresh clean Full,
superseding that earlier Full limitation. The unrelated live-probe exception remains
a scope decision, not exhaustion or proven history health.

Live background correlation, complete Earlier history, physical desktop,
screen-reader, Firefox/Safari and macOS observations remain unproved. No unrelated
history-performance repair or On Hold was justified solely by that ancillary cap.
