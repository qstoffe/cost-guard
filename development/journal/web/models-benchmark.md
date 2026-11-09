# Independent Models benchmark — FR000652

Date: 2026-11-09. Scoped v81.1 implementation on base `a5d12cc`; not a whole-Web
revalidation. Existing GitHub reference math, token sampling, promotions, Watch,
CLI and accounting are unchanged.

## Source and meaning

- Harbor's [official documentation](https://github.com/harbor-framework/harbor/blob/main/docs-mintlify/harbor-hub/leaderboards.mdx)
  explicitly documents unauthenticated public leaderboard display on other websites.
  This supports attributed aggregate display/cache, not unlimited mirroring rights;
  no benchmark task artifacts are bundled. The Terminal-Bench
  [leaderboard schema](https://github.com/harbor-framework/terminal-bench/blob/main/leaderboard/leaderboard.yaml)
  and live API were checked before designing the adapter.
- Fixed POST `https://api.harborframework.com/functions/v1/leaderboard-read`, package
  `terminal-bench/terminal-bench`, name `4-0-0`, page size 100. Board UUID
  `9f966760-00f1-424e-90f5-c964fb6f6091`, dataset UUID
  `1922072f-a433-429a-8929-350d5e1bcf02`. The
  [official board](https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4)
  remains 4.0 even though the public landing page promotes 4.1.
- Live source: 35 unique official rows on one complete page; 33 positive complete
  costs, one explicitly partial cost, one published zero. Cheapest positive:
  `72.14 / 330 = 0.2186060606060606060606060606` USD per attempt. This is a dated
  observation, not a bundled model list or perpetual expectation.
- USD/Task includes failed attempts. Partial numerator never divides by full trials;
  zero stays zero without a relative ratio. Source accuracy is 0–100. All distinct
  official row IDs/configurations survive, including medium/high/xhigh/max/low
  efforts and different clients. API client versions are currently not published;
  the UI says so rather than deriving a version from submission-only metadata.

## Ownership and recovery

`src/benchmarks.py` owns frozen typed aggregates, finite numeric/schema/edition/
pagination/identity checks and fixed verified HTTPS. Acquisition has a 5-second
socket timeout, 20-second total read budget, 10-page/1,000-row/2-MiB cap and no
redirects/auth/cookies/local metadata. Duplicate fields/rows, inconsistent board
definitions/pages, invalid dates and numeric underflow cannot publish a full snapshot.
Only needed aggregate fields survive into IPC/cache, not upstream user IDs.

`src/web/benchmark.py` reuses a separate `ReportJobs` instance under the existing
host tick/close owner: one coalesced optional child, 25-second job cap, 24-hour
freshness and 10-minute-to-6-hour backoff. Terminal children are still reaped during
the quiet freshness period. Atomic `cache/terminal-bench-4-v1.json` publication is
independent of pricing, source reports and canonical cache identity. A failed update
retains last-good values and their actual timestamp; no snapshot is a benign local
unavailable state. HTTP reads demand/retained prepared values, never upstream I/O.

`application/benchmark.py` prepares precise raw sort keys and full-edition positive
normalization. Only exact publisher/model identity and a unique reference release
date reuse `model_is_recent` (UTC ages 0–6 days). Anthropic's exact Claude brand-prefix
difference is the only admitted label equivalence; known official publisher URLs
qualify joins. Ambiguous/unmatched identities remain visible without lime. Benchmark
dates, new efforts/clients and first sightings cannot renew New. Promotions remain
only in reference pricing. Browser `benchmark.js` retains independent six-column
sort/DOM state; USD stays USD and tiny positive values cannot display as exact zero.

## Verification and repaired failures

- Local Full run: 179 isolated file entries, 176 passed, three failed on affected
  old source/help expectations and prohibited USD grouping commas. Causal repairs
  passed targeted `test_web_views`, `test_web_display` and `test_ccost_migration`
  reruns. This is **not** a claim that the original Full run passed. The new
  benchmark file was subsequently added explicitly to Quick/Full runner selection.
- Current focused runs: benchmark/Models 15 tests passed; after extra hardening
  fixtures, benchmark 10 passed. The current CI-runner/runtime/price-refresh/tier
  group passed all 91 tests. Existing overview, reference/Watch/account/source and
  lifecycle tests also ran in the preceding Full matrix.
- Validator: zero failures, seven existing advisory size warnings; layout,
  syntax/import/layers, hard budgets and v81.1 consistency passed.
- Hidden Chrome/Edge Models layout artifacts `scratch:/models-chrome.json` and
  `scratch:/models-edge.json`: six cases each, light/dark at 360/1366/1920, including
  Classic/Web and 100/125% zoom, independent sorting, intrinsic help and horizontal
  pan. Current toolbar/input artifacts `scratch:/models-refresh-chrome.json` and
  `scratch:/models-refresh-edge.json`: PASS, nine interaction checks and 247 layout
  records each. Native CDP Enter/Space sort benchmark independently; Escape closes
  compact help; no price fetch follows sorting/hover. Reference refresh, retry,
  filters, focus and touch remain covered. The initial added hover check failed
  because it ignored intentional post-sort help suppression; the probe now leaves
  focus/hover before re-entry, without changing production help behavior.
- Real installation `probe_web_live.py --models --refresh-prices`: PASS in 97.05s;
  true upstream price observation, Normal/full Models, one Live owner/two streams,
  pinned Watch catalog, zero inference and no owned workers at exit.
- Earlier cold benchmark host probe was unavailable after 30.92s; insufficient
  diagnostics leave its original cause unknown. A separate actual cold lane then
  fetched 35 rows successfully. A warm HTTP probe served those 35 rows but failed
  its final guard with two unrelated in-flight account-quota threads; it was not
  overall PASS. Existing acquisition explicitly permits bounded in-flight provider
  HTTP after its short close join. The short benchmark probe can now observe exact
  in-process workers' natural exit for up to 45 seconds, keeping the zero-owner
  assertion and product shutdown contract unchanged.
- Fresh real `--benchmark --benchmark-cold`: PASS, 35 rows, fetched timestamp
  `1794254373005`, one V2 Live owner/two streams, source view 0.834s, total 3.306s,
  maximum local HTTP 0.027s, zero owned threads/processes, no cleanup failures.
  Cold mode ignores only this probe host's in-memory cache; the last-good disk file
  remains protected. No retirement wait was needed in this successful run.

## Limits

No physical desktop, screen-reader or macOS acceptance is claimed. Integrated
browser was disconnected; permitted hidden installed Chrome/Edge supplied rendered
evidence without desktop interference. Browser reports use synthetic source data;
separate real HTTP/spawn/source probes establish installation behavior. Existing
probe text about a prior split-verification Delegate decision is historical, not a
new exception for this task. No new waiver, model call, dependency, release ZIP,
tag, GitHub Release or shared OpenCode stop was used. Remote checks/merge truth
belong to the delivery PR, not this local evidence snapshot.
