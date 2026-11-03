# FR 000554 — completion

Implemented in v80.134 (2026-11-03): theme-aware icon/text warning emphasis,
independent five-second source/card/daily retry confirmation with truthful retained
observations, distinct browser reconnect messaging, and ascending display of the
five most recent eligible historical sessions. Original specification preserved.

## Cause, policy and evidence

Card failures discarded classification and immediately became unavailable; daily
failures immediately warned and could wait a minute to retry. Watch also conflated
browser reconnect with source failure. These paths were reproduced in focused tests;
the owner's exact local intermittent occurrence was not reproduced. Existing healthy
SSE rotation fix remains intact; CLI acquisition/calculations are unchanged.

Retryable failures with retained evidence get one five-second monotonic confirmation
window (existing source retry interval), never extended by further failures. Existing
publications evaluate the deadline, normally every second; in-flight bounded reads
can delay publication. Initial/non-retryable/auth errors have no grace. Retained
contents explicitly are not current; only relevant successful source evidence clears
failure. Daily retry uses its existing single background lane, not another loop.

- Full suite: 127 files, zero failures; working-tree validation: 11 passes, zero
  failures, six advisory prose/design warnings, unchanged budgets.
- Hidden fresh-profile Chrome: nine Classic/light/dark × 1920/1366/360 cases,
  108 severity/theme transitions and cleared-warning checks passed. DOM/Python tests
  cover selection-before-order, deterministic ties/new eligibility, collapsed updates,
  failure confirmation, retained freshness, sustained failures and recovery.
- Read-only real V2: one owner/two streams/three accounts, four-capture bound,
  one row/card, reconciled 1,263-request daily totals and 55 known prompts (incomplete
  attribution). Daily result 11.242s; owned workers closed, shared OpenCode untouched.

Detailed findings/limits: `development/journal/web/watch-summary.md`.
Architecture owner facts and current Web guide updated. No model calls, runtime
installation/restart, ZIP, tag or GitHub Release. No requirement/test waiver.

## Limits

First live attempt timed out during daily wait/owned shutdown amid edits; cause not
established. Stable-source repeat passed. Integrated browser disconnected, so hidden
Chrome supplied rendered proof. No physical-input, screen-reader, suspension or
macOS acceptance, or claim that every connection problem is fixed.
