# FR 000559 — bounded delivery

2026-11-03 · v80.139

Fixed a demonstrated current-code defect: failed/interrupted runs before an
assistant response, including synthetic continuations separated by system notices,
were losing persisted terminal evidence. Shared source/causal analysis now ends
the correct attempt; retention preserves its end, duration and known history.
Newer genuine work remains eligible. No browser-only filter, arbitrary age cutoff,
quota polling, usage invention or shared OpenCode restart was introduced.

## Verification

- New regressions failed on v80.138 before the fix. Corrected Full: all 133 files
  passed (75.7s); prior terminal/fairness protections remain covered.
- Six native V2 roots, actual isolated/four-slot scheduled captures: quota abort
  without final usage, generic failure, interruption, catalog churn, retained
  known CCost/calls, CLI/Mini equivalence, partial/complete omissions, stale results,
  grace/history, cold reconstruction, detail and genuinely later live attempts.
- Fresh headless Edge 156 actual DOM with shipped SSE/presenters: active→aborted→
  history, frozen 3s, usage unchanged, running count 6→5, reload/reconnect/stale
  duplicate-active rejection. No model requests or physical desktop test.
- Existing read-only real V2 cards/detail probe passed: one owner/two streams,
  first rows 4.927s, four captures, consistent detail/freeze, zero surviving owned
  threads/processes. Shared OpenCode untouched. Optional Daily was not tested/PASS.
- Working-tree package validation passed, zero failures/six advisory budget
  warnings; hard caps unchanged. Product v80.139, release date and current docs
  updated. Journal/architecture updated at their existing owners.

## Evidence limits and explicit exception

A live-source candidate matches the reported 20:09 CET start and Sonnet 5.5/Low,
but its identity is not owner-confirmed. Baseline current code classified it as
running; corrected code yields terminal Error with unchanged usage. Its verified
later failure is `provider.no-route`, **not proven quota exhaustion**. Frozen
8,137,033ms reaches that later failure, not a verified original quota-stop time.

Owned authenticated WebHost status reported v80.139; worker CLI v80.138→v80.139,
OpenCode source 2.2.5. Known ordinary-checkout CLI is v80.66; that does not establish
the owner's invocation. Ordinary Web diagnostics were `not_observed`; integrated
browsing was disconnected. Historical host/CLI versions and the exact original
browser disappearance/reappearance mechanism remain unknown.

The **foreground Decision Delegate**, not the user, authorized this FR's bounded
delivery/Complete without confirming the exact incident identity, historical
WebHost/CLI versions/browser state, original quota event/time or precise historical
intermittence mechanism, and waived conclusive explanation of that particular
mismatch. Reason: a distinct inspected current-code defect plus live-source and
canonical/actual-DOM evidence justifies delivering the useful fix. This does not
establish the reported incident fully solved and grants no broader test/access or
future-task waiver. Unavailable historical checks and optional Daily are not PASS.

Detailed findings: `development/journal/web/watch-terminal-lifecycle.md`.
