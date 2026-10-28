# Shared global Relative CCost — FR 000534

Date: 2026-10-29. Product: v80.111. Base: `1b0fd64375bfc10c6653dda86dea41e2d0c1eb88`.

## Implementation and independent expectations

`ReportService` retains `latest_prompts` → `_relative_usage` → `normalized_average_token_mix`; every comparison row/tier now consumes that global pooled mix. Warning-first acquisition and model-table acquisition share the same sample semantics and existing 15-minute observation window. Neither calls deep `comparison_samples`. The retained historical evidence infrastructure and explicit historical Token Mix path are not deleted.

`test_workload_mix.py` independently prices 90 cache / 10 output at .59/.38/.37/.49 USD/M across four models, then reconciles the 1.59/.59 target tier multiplier. Identical-price/untried models compare equally. Global sample cases cover 0/1/99/100/121 prompts, different model/publisher jobs, DTO provenance and warning-first acquisition with 100 older target-model prompts outside the global window. Existing sampling, attribution, unknown/zero-rate, tier, publisher, absolute-token, display-unit and Web DOM tests remain in the full suite.

The first full run exposed obsolete assertions requiring deep comparison hydration and README/history hard-cap overruns. Expectations were updated to the approved global scope, not relaxed to arbitrary bounds; prose was consolidated without raising caps. Follow-up runs caught a test indentation mistake and an obsolete injected-sample ratio; both were repaired. A new warning-first fixture initially overlapped its roots' prompt times; separating the roots by a day fixed the fixture, not production sampling.

## Real-installation probe

Executed `py -3 cost-guard.py --all-models` against the installed OpenCode V2 source, read-only, without stopping the service or calling models. It exited zero and rendered the actual 100-completed-priceable-prompt global comparison explanation and model/tier table. Dashboard usage independently showed 100 priced prompts. Raw session progress/output was inspected locally and not published; its disposable report was removed. This proves headless report acquisition/rendering, not browser pixels, physical mobile accessibility, actual billing or latency improvement.

## Verification

- Focused workload/presentation run: 25 tests passed after the final fixture/expectation repairs.
- `py -3 development/tools/validate_package.py --working-tree`: zero failures, four design-budget warnings; hard caps unchanged.
- Final `py -3 development/tools/run_tests.py --suite full`: zero failures, 116 files, four workers, 52.1 seconds. Includes the final warning-first fixture and presentation repairs.

## Knowledge and limits

Updated analysis/report contracts and the performance journal: old milestone-40 deep-scan timings describe a superseded policy, not current performance or an equivalent-work speedup. No architecture-boundary/diagram change, dependency, background acquisition, model evaluation, release ZIP or new permanent gate. No cross-repository suggestion was published. Browser visual/native acceptance was not run; deterministic DOM/source and headless live evidence have distinct scopes.
