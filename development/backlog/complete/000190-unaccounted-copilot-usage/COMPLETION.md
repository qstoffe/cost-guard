# FR 000190 completion — Copilot Unaccounted usage

Implemented in Cost Guard v80.78 (2026-10-26).

## Delivered behavior

- Normal Accounts Overview adds one signed `Unaccounted usage` row per Copilot account, including `—` when comparison is unsupported or incomplete.
- Uses existing native used-credit evidence minus canonical deduplicated period-index CCost. A provider-reported fixed reset at 00:00 UTC on the first day establishes the supported calendar billing month. Unsupported/expired bounds never become guessed intervals.
- Acquires the earlier native start only within the existing normal-report account scope. The local-month CCost line, Watch scopes/performance, other providers, quota/Pace and billing remain independent.
- Requires complete required-start acquisition, priceability and unambiguous existing account attribution. Keeps Decimal precision, negative values and established zero; provider aliases and model publishers follow existing grouping. No new credentials, endpoint, poller, ledger or valuation engine.
- Usage documentation explains residual uncertainty, signed magnitude rounding and why neither positive nor zero proves whether reviews were free.

## Verification

- Focused account-period regressions passed; the new nine-test synthetic/model-free module covers native parser evidence, unknown/partial pricing/history, signed decimal rounding, fork deduplication, aliases, separate accounts, UTC/local boundaries, independent DST and report-only rendering/acquisition.
- Full local suite: 94 test files passed, zero failures (32.8 seconds). An initial README hard-cap failure was repaired by shortening current-version prose without raising any limit.
- Working-tree package/source validator: zero failures; existing design-budget warnings remain. No product ZIP, tag or GitHub Release was generated.
- Headless normal report against the real local OpenCode installation exited 0 and displayed exactly the Copilot reconciliation row alongside the unchanged local-month CCost. This is a functional smoke observation, not verification of GitHub billing accuracy or of every provider's health. No model inference, credential changes or service restarts.
- The first live-report wrapper failed only while printing Unicode through Windows' legacy encoding after the report itself exited 0; an explicit UTF-8 rerun succeeded.

## Knowledge, privacy and dependencies

Updated the existing Reports source contract and its focused-test route. Architecture boundaries are unchanged: adapters supply native evidence, analysis owns period valuation, reports derive the residual and presentation formats it. Journal assessment: **no-update**; no new reusable investigation or performance claim warrants a journal entry.

The selected FR is preserved byte-for-byte by Git; this bundle contains only FR.md and this authored completion report, with no private prompts, credentials, raw provider payloads or live account amounts. No unfinished cross-FR dependency, foreign change or stash was found in the isolated clone. Retention prunes nothing; exact native maintenance and identity state are included in this delivery.
