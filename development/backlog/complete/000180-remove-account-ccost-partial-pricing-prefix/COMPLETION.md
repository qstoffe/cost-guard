# FR 000180 completion — plain account CCost

Implemented in Cost Guard v80.77 (2026-10-25), from default revision `3929f5645fa48db02526efd06a3c466943fff8e9`.

## Delivered behavior

Account CCost now uses the ordinary upward-rounded known priced subtotal for both complete and partial values: 37.2 displays as 38, 0.15 as 0.2, and 0.01 as <0.1. Report today/month, rolling quota parentheses, Watch and text-only fallbacks share this formatter. Unknown/wholly unpriced scopes remain `—`; acquired empty periods remain `0`. Internal Decimals, priceability counts, attribution, acquisition, native quotas and global/prompt/session/Token Mix partial markers are unchanged. Usage documentation explains that missing prices may understate complete reference valuation without adding account prose or warnings.

## Verification

- Focused account-period suite: PASS, 18 tests. Added partial subtotal coverage across report/Watch, ANSI/plain, narrow/wide, both rolling windows and compact/text-only fallbacks; retained internal incomplete evidence and global marker assertions.
- Full repository suite: PASS, 93 test files, 0 failures, 34.4 seconds. First run exposed README hard-cap overflow from the release note; shortened that note without changing budgets and reran the full suite successfully.
- Working-tree product validator: PASS, 11 checks, 0 failures, four existing design-budget warnings (README and context/service/coordinator modules). No ZIP, tag or GitHub Release generated.
- Read-only local Windows Diagnostics: selected healthy OpenCode V2 2.1.4; normal report succeeded with 24 comparison rows, and headless Watch initialization/poll/render at 120 columns reported zero overflow lines. Simulated macOS checks: 14 PASS, not native execution. Diagnostics validation was explicitly skipped because Full and the product validator ran separately above. V1 remains an unsupported legacy schema; V2 supplied the live evidence. No claim that live history happened to contain partial pricing; partial acceptance is deterministic.
- No paid model calls, credentials/auth writes, login automation, database mutation or OpenCode service restart. Private diagnostic output remains outside the repository; only this sanitized summary is committed.

## Knowledge, dependencies and retention

Architecture assessment: no boundary or dependency changes; updated only the existing Reports contract's stale account marker description. Journal assessment: no-update, no new reusable operational finding. Source/tests remain authoritative.

No unfinished cross-FR dependency or unfamiliar clone change/stash is required for recovery. Original FR preserved byte-for-byte, with no attachments. Native transaction advances ordinary count to 8; identity high-watermark remains 180; retention prunes nothing. Failed or unmerged work is not delivery.
