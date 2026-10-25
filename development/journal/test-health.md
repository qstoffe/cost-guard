# Test system health

Source revision: 86e4a2dab9393bb634e2247c4278e1be2de50190
Checked revision: 86e4a2dab9393bb634e2247c4278e1be2de50190
Last checked: 2026-10-25
Status: current

## Summary

Scheduled Test Health assessment at ordinary milestone 5. No test-system rewrite is justified by the inspected evidence. Retain bounded, isolated per-file execution, responsibility-owned fixtures and distinct deterministic versus real-installation evidence. Corrected the code map's removed `test_step10_release_hardening.py` route to existing fault/launcher tests. No runtime, test, fixture or runner behavior changed; no product version update.

This is a source-based maintenance assessment, **not a fresh passing-suite claim**. The development-only workflow intentionally runs no product tests, validator, Diagnostics, live probes or release gates. No model inference was requested. Current execution time, flakiness and paid-suite cost are unmeasured.

## Evidence

Reproduce the static inventory with the installed maintenance skill's `maintenance_evidence.py inventory --repo-root .` and `python development/tools/code_inventory.py --json`. Neither imports the application. At the source revision above, the whole-tree maintenance inventory examined 314 text files (158 source/config, 118 test-related, 38 documentation); 17 binary/over-1-MiB files were excluded from text analysis. Git internals/ignored runtime state are outside that inventory. There were zero exact-byte duplicate groups; this does not establish absence of semantic duplication. AST inventory covers 138 runtime modules, 12 development tools and 110 test-tree Python modules, including the 16 fixture modules counted once.

`development/tools/run_tests.py` lists 90 Quick files and three Full-only files, exactly matching all 93 top-level `test_*.py` files, without stale entries or duplicates. AST inspection found 1,202 syntactically named test methods, not an executed test count. Quick defaults to four workers and a 25-second per-file timeout; Full schedules its three slow files first with a 240-second timeout. Pattern/profile defaults use one worker. Each file gets a fresh unittest subprocess, test mode and UTF-8 output. Full-only package-negative, Diagnostics and parity/performance files retain different responsibilities, not three interchangeable gates. Profiles are focused selections, not claims of exhaustive area coverage.

Ten static test-to-test import edges remain, matching the bounded debt already described in PERFORMANCE.md. Their consumers are `test_model_pricing_presentation.py`, `test_runtime_errors.py` (two edges), `test_token_mix_economics.py`, `test_v2_synthetic_attribution.py`, `test_v784_regressions.py`, `test_watch_lifecycle.py`, `test_watch_subtotals.py` (two edges), and `test_watch_tool_activity.py`. This is coupling, not proof of repeated test execution: importing a test module does not itself run its tests. Twenty test files contain text reads and nine mention subprocesses; these are investigation leads, not failure classifications. No measured new fanout, repeated setup failure or recurring implementation blockage was available to justify a cross-file fixture migration this cycle.

Representative source and test risk mapping:

| Critical outcome | Source owner | Inspected protection |
| --- | --- | --- |
| Source readiness has a deadline; auth/schema errors never trigger readiness retries | `src/sources/read_recovery.py` | `test_connectivity_reliability.py`: virtual clock, bounded retries, auth/schema denials and sanitized errors; fake V2 service fixtures exercise HTTP separately |
| Account replacement never resurrects stale identity or sends incompatible credentials | `src/accounts/openai_subscription.py` | `test_openai_account_switch.py`: synthetic read-only SQLite/auth byte comparisons, gated late responses, explicit forbidden-request callbacks, recovery and secret exclusion |
| Period valuation retains provenance and does not duplicate ambiguous account totals | `src/analysis/period_ccost.py` | `test_account_period_ccost.py`: independent expected Decimal values, aliases, DST/month boundaries, partial pricing, clone deduplication and no-revaluation sentinel |
| Watch retains daily published accounting through enrichment/deletion and resets at local midnight | `src/watch/today_ccost.py` | `test_watch_today_ccost.py` and account-period tests: explicit clocks, clone/step identity, midnight/DST and history publication |
| Disposable cache supports concurrent access without becoming authoritative history | `src/cache/database.py` | `test_cache.py`: on-demand/rebuild, independent generations and concurrent reader/writer cases |
| Comparison and token-mix sampling preserve independent eligibility/cutoffs | `src/reports/sampling.py` | `test_report_sampling.py`; code-map routes retain focused sampling and report tests |
| Software faults are fatal/sanitized, distinct from expected CLI/interrupt failures | `src/runtime_errors.py` | `test_runtime_errors.py`: seeded exception families, private sentinel exclusion, process guard and recovery/deduplication checks |
| Package negatives and Diagnostics privacy are detected without mutating the real installation | Development validator, Diagnostics and `fixtures/package_copy.py` | `test_foundation.py`: deliberately broken disposable copies and owning-check assertions; `test_rc2_public_diagnostics.py`: redaction and already-running-service/cold-start separation |

Read `test_foundation_quick.py`, `test_step9_parity_performance.py`, fixture ownership routes and PERFORMANCE.md as well. The earlier expensive nested full-validator pattern has already been replaced by focused negative checks; the retained positive validator subprocess protects composition. Simpler alternatives considered: one monolithic unittest process would discard file isolation/hard timeouts; deleting the Full tier would discard package-negative and parity risks; a universal fixture module would mix independent owners. None is justified by current evidence. Existing string-based wiring checks are more refactor-sensitive than outcome assertions, but are not grounds to remove the only wiring guard without first establishing equivalent behavioral coverage.

Recent committed completion reports are historical evidence, not newly executed receipts. FR 000150 records 93 Full files passing in 81.0 seconds with four workers, plus focused account checks and a validator pass; it describes an obsolete blanket-401 assertion repaired to protect quota-versus-model authentication. Current source has explicit method classification and forbidden-request tests, so that historical failure is not treated as an outstanding regression. FR 000140 records 93 passing files and independent account-period/Watch coverage. Historical PERFORMANCE.md records prior fixture extraction (43 to 33 to 18 to 10 import edges) and 151-to-32-second Full scheduling improvements under earlier conditions. Those timings are not comparable to a fresh benchmark here. GitHub Actions query returned HTTP 200 with zero runs; there is no CI timing/failure history to correlate. No private session exports were accessed.

## Next investigations

When product changes next require execution, inspect actual per-file durations/failures before changing suite selection or timeout policy. Prefer migrating a legacy import edge into its existing responsibility-owned fixture when that area actually changes, preserving unique negative cases. Characterize wiring behavior before replacing source-text assertions. No negative-fixture or before/after execution experiment was performed this cycle because no tested mechanism changed. No runtime-health, native macOS or live quota-support conclusion follows from this audit.

Architecture assessment: **no-update** to module contracts/overview/diagrams; no ownership or dependency boundary changed. Journal assessment: retain this bounded baseline and fix only the stale navigation route. The native maintenance transaction advances Test Health to milestone 5; identity reservations stay unchanged and retention prunes nothing. There are no pending FRs or cross-FR dependencies at the assessed default. No raw inventory, credential, session content, machine path or diagnostic export is published.

## Rejected hypotheses

- Test count alone proves excess: rejected; independent source, attribution, lifecycle, privacy and package risks remain distinct.
- Exact-byte duplicate absence proves a healthy suite: rejected; semantic duplication and flakiness need stronger evidence.
- Historical quota 401 proves model login failure: rejected; current method/resource compatibility is distinct from model authentication, and real token-sharing quota support remains unavailable as documented.
- A documentation/state-only audit needs another Full run or version bump: rejected by the active development-only workflow; historical passes remain explicitly attributed.
