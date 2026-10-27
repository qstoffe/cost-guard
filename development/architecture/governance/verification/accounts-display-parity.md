# Accounts CLI / Web parity

FR 000490; observed 2026-10-27 on Windows, Python 3.14 and Node 24 / headless Edge.
Implementation baseline: `cfd07a8ee1247dd147e7bb94a8a0e9fc3727f568` plus this FR's candidate.

## Inventory and ownership

CLI Normal uses `account_capacity_parts` / `account_ccost_lines` in `src/presentation/accounts.py`:
identity/plan, native quota name/window, percentage/unlimited/unknown, Remaining, reset,
Pace, native balance/billing, billed today/month, Today/local-month CCost and Copilot
Unaccounted usage. Watch reuses these primitives with its own rolling/Today scopes,
compact reset labels and recovery ownership; it is not the Accounts page's source.

Accounts now reuses `overviewAccounts` cards and semantic light/dark styles from the
shared visual/display FRs. Each quota owns a known-only remaining bar, native amount
and money equivalent, reset/status/window. Billing and attribution/error notes stay
visible; observed time and used amounts expand in native details. Missing bills show
N/A, not zero. Classified method errors get readable text; private provider-authored
reason/warning payloads remain excluded, with a visible generic warning flag instead.

The unchanged CLI reset algorithm moved to `src/display.py`; terminal accounts re-exports
it. Application display traverses only frozen allowlisted DTOs, inheriting report
`now_ms` for reset tiers/timezone. No application→presentation import, formula, source
scope, account cadence, privacy permission, acquisition owner or in-browser edit changed.
Overview/Models/Accounts continue sharing the cached Normal observation. Watch remains
compact and never gains Normal billing/month totals. Journal: no-update; module/code-map
routes record the reusable owner facts without a duplicate chronological entry.

## Deterministic and browser proof

`test_web_accounts.py` / `fixtures/account_views.py` feed equivalent canonical Normal
projections to CLI and immutable Web export. `integration/web_accounts.cjs` checks rendered
cards for available, blocked, unlimited, missing, partial/inactive, rate-limited and stale
states; distinct native/rounded values, CCost scopes, USD, reset, Pace/no-workdays,
Unaccounted usage, attribution warnings and private/raw-code exclusion. Existing terminal
quota/reset and display regressions cover the shared formatter's unchanged CLI behavior.
The bounded Quick/Full runner now includes the new account tests.

Reproduction for the explicit synthetic browser test: start
`python development/tests/integration/serve_web_accounts.py`; then
`node development/tests/integration/probe_web_accounts.cjs <explicit-Edge-or-Chromium> <owned-output.json>`.
The output parent must already exist **outside the repository**; profiles/screenshots are
test artifacts, never source/package input. Stop only this fixture with its loopback
`http://127.0.0.1:18749/stop`, or its five-minute bound expires. No product host/login/source
is involved. Node 22+ supplies the WebSocket test transport, not a runtime dependency.

Final browser checks: PASS for 1200px/360px × light/dark, seven cards, no document overflow,
correct theme tokens, and progress counts `[2,1,0,0,0,0,1]` (unknown/unlimited never zero bars).
Real Chromium key dispatch verifies Enter opens, Space closes, and Tab advances to the
next disclosure with visible focus in all four cases. Captures were inspected for desktop
light and narrow dark wrapping/status/focus. The desktop-pane click helper failed with
`UnknownVizError`; its key calls did not establish input proof. The isolated headless
test is the verified equivalent, not a claim of physical input or screen-reader acceptance.

## Real-installation observation and limits

Final repository verification: `py -3 development/tools/run_tests.py --suite full` PASS,
111 files, zero failures (46.9s); `py -3 development/tools/validate_package.py --working-tree`
PASS, zero failures, four existing design-budget warnings, no hard-cap changes. The first
full run found two causal fixture issues: an older DOM assertion expected the now-replaced
raw authentication code, and generated screenshots inside `ci-results` entered the package
validator scan. The assertion now pins readable text **and absence of the raw code**;
captures/profiles moved outside the repository before rerun. No gate/assertion was weakened.

Read-only `integration/probe_web_live.py --reports`: real V2, one live owner, two streams,
three accounts, preserved run origin and advanced sequence. The Normal HTTP job correctly
failed `result_too_large`; no limit was raised or provenance discarded. The owned host
closed through its existing finally cleanup; shared OpenCode was not stopped.

A separate direct Normal facade acquisition succeeded with three available accounts / four
quotas. To classify the limit independently, the **same canonical input** was formatted
with both the verified base `src/application/display.py` and this candidate's formatter:

| Measurement | Bytes |
| --- | ---: |
| Base compact Normal result | 8,683,533 |
| Candidate compact Normal result | 8,683,732 |
| Request identity vector alone | 8,403,281 |
| Unchanged HTTP result ceiling | 8,388,608 |

This establishes an existing history/provenance-size limitation, not an account layout
regression; added reset/window tokens account for 199 bytes. Reproduction uses one
`src.web.composition.application(ReportRequest(ReportKind.NORMAL)).execute(...)`, retaining
the canonical record passed to `projection.with_display`, formatting it once with the
base formatter and once with the candidate, then measuring compact JSON with the same
request identity vector. Print only byte/count/status facts, never account/session payloads.
Follow-up proposal deferred here: design bounded Normal provenance delivery separately;
do not silently omit evidence or bypass the 8 MiB contract in a presentation FR.

Integrated real-history browser Accounts could not be validated through that oversized
HTTP result. Synthetic browser/keyboard proof is not physical keyboard/mouse, assistive
technology, native macOS or end-to-end real-provider browser acceptance. No inference,
credential inspection, private captures or unrelated shared-system writes occurred.
