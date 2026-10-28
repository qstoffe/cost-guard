# Historical absolute token-volume evidence

Base revision: 7d625fda623477ccafd7c9f606fbb92f3e014f0a
Observed: 2026-10-28–29, local Windows workstation, Python 3.14.

## Semantics and deterministic proof

FR 000527 extends the existing canonical TokenMix aggregation, not acquisition or valuation. The model and publisher renderers expose the same Python totals and display primitive. Known-category subtotals retain observed tokens from partially reported requests; complete totals/shares remain unknown when any category is missing. Reasoning is included once. Complete zero, partial zero and wholly unknown telemetry remain distinct. CCost still uses the configured display unit and original request-level valuations.

`test_token_mix.py` covers incomplete categories, reasoning, empty/zero and exact large integer sums. `test_token_mix_economics.py` reconciles canonical deduplicated child/subagent history with model totals. `test_workload_mix.py` reconciles model/publisher/overall totals and preserves availability, publisher identity, mixed-prompt counts and revision/deletion behavior. `test_web_remaining.py` checks CLI/application display parity and narrow 50/80/120-column history metrics. Its Node VM asserts Tokens in both tables, exact raw sorting of adjacent integers above JavaScript's safe integer range despite identical compact labels, partial/unknown ordering and keyboard-scroll container preservation. Existing configured-unit tests cover CCost isolation. No new dependency, API, model inference or automatic deep scan is introduced.

## Real installation

Read-only `python cost-guard.py --token-mix --ccost-unit credits` used the registered local installation. The initial cold attempt exceeded its 300-second bound and was terminated by the owning subprocess wrapper: **not PASS**, no completed cold timing. A second bounded attempt using the partially populated disposable cache completed with exit 0 in **491.188 seconds**, 3,742 output characters, Tokens cells, the overall Total Token Mix heading and the publisher heading. Stderr was present but its contents were not retained or classified; no account credentials, source content or raw output are retained here. This proves report completion/visible fields, not a clean cold benchmark or a latency guarantee. No shared OpenCode service was stopped.

Final `python development/tools/run_tests.py --suite full`: **116 files passed, zero file failures**, four workers, 55.7 seconds. `python development/tools/validate_package.py --working-tree`: **11 checks passed, zero failures**, four existing design-budget warnings (README and three unrelated runtime owners). Existing hard caps were preserved by concise documentation, not increased.

The preexisting deep-history scan remains slow on this installation; no speedup is claimed. Web uses the same immutable application export; deterministic DOM evidence is not real-browser/mobile visual acceptance. Deleted/pruned history cannot be reconstructed. No ZIP or GitHub Release is created.
