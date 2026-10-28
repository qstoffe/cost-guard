# Model/publisher workload-profile evidence

Source revision: b788aa556cc12a50fc2909968fc7fdea19e1bebf
Checked revision: b788aa556cc12a50fc2909968fc7fdea19e1bebf
Last checked: 2026-10-28
Status: current

## Scope and deterministic checks

FR 000521 changes comparison profiles and historical publisher grouping, not account/billing/quota semantics. `development/tests/test_workload_mix.py` proves 0/1/10/99/100/>100 model prompts; 0/40/90/100 publisher coverage; 10/90 and 10/40/50 blends; short/no-history priors; mixed publishers; repeated/clone entries; complete-telemetry eligibility; reasoning; exact identity/manufacturer aliases; tier/reference changes; older-than-global history; revision/deletion reuse; filtered/fail-open historical reconciliation; and shared CLI/application projections. Existing suites retain child/compaction, partial-price, null/zero-rate, sorting, cancellation and finite-result coverage.

Full suite: **1,389 tests passed, zero skips/failures/errors across 114 files** (57.2 s, four workers). Working-tree validator passed its 11 checks; four existing design-budget warnings remain, with no hard-cap increase. Node DOM assertions exercise model provenance and both historical tables using shared frozen display tokens. Existing responsive table-scroll, sort/filter/CLI-order and finite-job tests pass. No browser/desktop automation or visual mobile acceptance was performed; DOM/CSS evidence is not a screenshot claim.

## Reproducible performance

Windows workstation, Python 3.14, standard library, synthetic 1,000 roots / 20,000 prompts, no network/accounts/model calls. Same model-free runner and fixtures for extracted base `c7c98ce3426f5b11393a4dec9a9584ed8d219001` and candidate above. Cold is an empty disposable cache; warm is median of three fresh services sharing cache; refresh is one same-service repeat. These are observations, not universal latency targets.

Run `python development/tests/integration/benchmark_workload_mix.py`; `--source-tree <verified-base-extraction>` selects the comparator without switching the working tree.

| Mode | Base cold / warm / refresh (s) | Candidate cold / warm / refresh (s) | Hydrated roots base → candidate |
| --- | --- | --- | --- |
| Normal | 0.0708 / 0.0216 / 0.0058 | 30.7186 / 0.0635 / 0.0316 | 5 → 1,000 |
| All Models | 0.0690 / 0.0237 / 0.0063 | 32.2399 / 0.0454 / 0.0273 | 5 → 1,000 |

The cold regression is material and explicit: exact sparse/untried-model evidence requires history beyond the generic five-root window. It is not silently truncated to global latest-100. Per-root compact samples rebuild through canonical cached analysis and release deep hydrated roots. An initial implementation still rebuilt all compact roots on warm reports (~2.1 s); revision- and exact-membership-validated stable-root aggregates removed that repeated work. Unstable roots remain excluded from stable reuse; changed/deleted roots invalidate proofs. No source-private ledger or second analyzer was introduced. Warm repeats hydrate no additional roots in this benchmark. Source revisions and catalog/analysis dependencies govern reuse; warnings retain the existing 15-minute observation window.

## Real installation and limits

Read-only `python cost-guard.py --all-models` against the registered local OpenCode installation completed with **exit 0**, 15.986 s, producing actual model/tier ratios. An earlier cold probe exceeded a 240-second harness limit; its interrupted result is not PASS or a completed cold timing. A subsequent traversal completed; PowerShell's stderr redirection misleadingly returned a shell error, so a direct subprocess return-code capture established success. The measured 15.986 s run benefited from acquired cache and is not a clean cold baseline. No shared OpenCode service was stopped and no model inference ran.

Deleted/pruned history cannot be reconstructed. Publisher grouping depends on trustworthy catalog metadata; ambiguous/missing manufacturers stay unverified. Profiles personalize workload estimates rather than proving same-task economics or billing. Physical desktop/mobile visual acceptance remains unverified; no promotion of Web Beta or latency guarantee is implied.
