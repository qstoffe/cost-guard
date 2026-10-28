# Completion — FR 000527

Implemented for Cost Guard v80.110, 2026-10-29, from base `7d625fda623477ccafd7c9f606fbb92f3e014f0a`.

Existing historical model and publisher tables now include absolute Tokens alongside Prompts, Calls, I/C/W/O shares/category CCost and total CCost. Canonical deduplicated attribution and existing per-request valuation are unchanged. Known-category subtotals include reasoning exactly once, use compact K/M/B display and distinguish partial `?`, unknown `N/A` and complete zero. Web sorts exact raw integer strings, not labels; narrow CLI history uses labeled metrics without dropping columns. No new scan, provider call, default report section or automatic Web capture is introduced. FR 000521 publisher semantics and FR 000526 configured CCost units are preserved.

## Verification

- Full suite: 116 test files passed, zero file failures, 55.7 s / four workers.
- Working-tree validator: 11 checks passed, zero failures, four existing soft design-budget warnings. Hard caps unchanged.
- Canonical model/publisher reconciliation, child/subagent history, partial/unknown telemetry, exact large volumes, narrow CLI and deterministic Web DOM sorting covered.
- Read-only real-installation `--token-mix --ccost-unit credits` completed with exit 0 in 491.188 s after a separate cold attempt timed out at 300 s (not PASS). Overall/model/publisher volume fields were present. This is not a clean cold benchmark or browser-visual proof.

Detailed [evidence and limits](../../../architecture/governance/verification/historical-token-volumes.md) remain outside this immutable specification bundle. Original FR.md is preserved byte-for-byte; no attachments were supplied.

## Knowledge and dependencies

Updated the current report contract and journal evidence route. Architecture boundaries: **no-update**; acquisition, pricing, accounts and publisher identity retain their owners. No new dependency, model inference, service restart, ZIP or GitHub Release. Deep-history latency and deleted/pruned-history limitations remain explicit; browser/mobile visual acceptance was not claimed. No new cross-repository proposal is published.
