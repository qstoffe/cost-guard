# FR 000564 completion — 2026-11-03

Delivered in v80.144: completed and running CLI/Web per-prompt Token Mix now share
the canonical projector's all-call I/C/W/O coverage rule. Missing counters never
form an implicit zero or a silently partial-known denominator. Unsupported completed
rows show `N/A`; active rows show `running`. Fully known half-up/Output-residual
rounding, reasoning inclusion and all accounting/context metrics are preserved.
Session-table Total mix also stays unknown for incomplete contributing rows, without
changing its independent incoming/extra CCost diagnostics. The Watch-only guard is
removed; no browser math, acquisition change or model call is introduced.

The exact FR 000558 completed-partial CLI/Web discrepancy is closed; that task's
historical delegate exception is neither reused nor treated as a retroactive failure.
No new requirement/test exception was requested or applied.

Verification: baseline-red reproduced four completed-partial CLI assertion failures;
focused coverage/projection/presentation and LiveConnection/DOM tests pass, including
numeric→unknown→corrected numeric→terminal unknown, stale-event rejection, reconnect,
terminal freeze and long-lived retained captures. Final Full: **136 files, 1,612 passed,
one platform skip, zero failures/errors**, 93.5s. Skipped: macOS zsh/PTY execution on
Windows. Package validation: 11 passes, zero failures, six advisory size warnings.

Read-only real V2 Watch/detail/SSE probe passed: five known mixes, one owner, two
advancing streams, frozen detail, zero tracked workers remaining on close; no model
calls or shared OpenCode stop. No natural call-count/mix transition or incomplete
category observation was seen, so those real-source transitions remain unverified;
controlled fixtures prove them separately. Daily cancellation observations are not
a complete Daily campaign or proof of zero untracked OS helpers.

Policy, before/after examples, evidence and limits:
[journal](../../../journal/web/watch-prompt-tables.md),
[sanitized results](../../../tests/evidence/watch-prompt-tables/token-mix-coverage.json).
Current user docs, report contract, version history and ordinary progress are updated.
