# FR 000160 completion — compact account CCost and actionable Codex quota hint

Implemented in Cost Guard v80.76, 2026-10-25, from default revision `632bfbc287997b6aa14ec29b134e78548c30855e`.

## Delivered behavior

- Identified token-sharing accounts explain separate model/quota authentication and name Codex browser (legacy) / Codex device code (legacy) as options to try for now, with no promise of quota availability. Both report and Watch show the advice once; API keys do not supply Codex subscription quota. Legacy, methodless, unknown, expired and HTTP-rejection handling remain distinct; no auth writes or identity fallback.
- Account-only formatting uses `0` for observed empty acquired scopes, `—` for unknown/unpriced scopes and downward-rounded `≥…` for priced partial lower bounds. Global/prompt/session partial markers remain unchanged. Acquisition supplies its existing observed range; empty input or account-attribution capability alone never establishes zero. Multiple-account ambiguity and invalid window anchors stay unknown.
- Normal reports keep today/month numeric values, place rolling amounts on existing quota rows (textual without a percentage) and remove explanatory note rows, duplicate rolling rows and the account footer. Watch retains daily placement before Remaining and no monthly comparison row. Existing scope acquisition, valuation, resets, capacity and refresh cadence remain unchanged.

## Verification

- Full deterministic suite: PASS, 93 test files, 0 failures (52.8 seconds). Targeted period and OpenAI-method suites also passed. Initial full-run failures were obsolete presentation expectations and the README hard cap; expectations now assert the requested behavior and README wording was shortened without raising any cap.
- Working-tree product validator: PASS, 0 failures, 11 checks; four nonblocking design-budget warnings (README, existing context/service/coordinator modules). No release ZIP built.
- Real local Windows installation: read-only Diagnostics selected healthy OpenCode V2 2.1.4, built a normal report with three accounts, and exercised headless Watch startup/history/publication/polling. Zero free-flowing overflow lines at 80/120/160 columns. Full validation inside the first Diagnostics invocation timed out; no owned process remained. Retried collection with validation skipped because the separate complete Full/validator commands above establish product verification, not because an interrupted suite passed.
- Additional bounded real-source acceptance: report and actual Watch account projection/history rendered in ANSI/plain at 80/120/160 columns; all six combinations passed width, no-question-mark, no-footer/prose, retained today/month, and no-Watch-month assertions. The acquired empty Copilot day displayed zero. Diagnostic OpenAI observation was a current legacy WHAM HTTP 200 with returned native quota, not token sharing; token-sharing method guidance remains deterministically fixture-tested, not live quota retrieval.
- No paid model calls, login automation, token refresh, credential writes, OpenCode database mutations or shared-service restart. Private Diagnostics ZIP/raw output stays outside the repository; only this sanitized summary is committed.

## Knowledge, dependencies and retention

No new module or architecture boundary: existing report/account/presentation owners remain authoritative. Update the affected report contract and OpenAI journal in this same delivery to describe acquired-zero evidence and retire the now-stale lack-of-live-legacy-success limitation; unrelated knowledge remains unchanged.

The FR relies on the already-completed period-accounting and auth-method work without changing their routing/valuation responsibilities. No unfinished cross-FR dependency, unfamiliar change or stash was found in the isolated clone. Native transaction advances ordinary count to 6, identity high-watermark stays 160 and retention prunes nothing. The original FR is preserved byte-for-byte and has no attachments.
