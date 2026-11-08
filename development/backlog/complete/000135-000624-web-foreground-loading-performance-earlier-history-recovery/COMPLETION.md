# FR 000624 — completion and scoped acceptance

## Delivered scope

Candidate **v80.204, 2026-11-08**, PR [#220](https://github.com/qstoffe/cost-guard/pull/220).
The original FR and owner clarifications remain intact. This report records scoped
acceptance, not universal performance or a fabricated all-PASS experiment history.
The PR/default branch own actual merge status; this report does not claim a merge.

- Healthy finite acquisition/proof stays meaningfully pending without elapsed-work
  failure fallbacks or forced Retry. Genuine I/O/auth/schema/source-identity faults,
  cancellation and cleanup retain bounded, typed behavior. Actual SQLite BUSY/LOCKED
  Stats checkpoint contention now backs off and automatically recovers; unknown,
  READONLY and other storage failures are not disguised.
- V2 scoped authoritative brackets, exclusively owned reusable readers, bounded
  canonical batches, compact shared guidance and qualified cache reuse reduce work
  while preserving complete global Earlier proof and report populations.
- Foreground-first finite admission/promotion retains original jobs/checkpoints;
  all useful defaults continue warming. Full/Mini independently own authenticated
  history demand, including visible PiP with a hidden opener. Verified identity/
  model/context fields do not wait unnecessarily for cost/guidance.
- Current main remains the supported source distribution. No release, tag or ZIP;
  historical v80.0 is untouched. The ordinary checkout/shared OpenCode service was
  neither switched nor stopped; work used the isolated FR branch.

## Baselines, controls and results

Full route/resource tables, failed experiments and exact scopes:
[recovery](../../../journal/web/foreground-recovery.md),
[retained/promotion/idle](../../../journal/web/foreground-performance.md), and
[cold/untouched](../../../journal/web/foreground-cold-warm.md).

B0 is pre-dispatcher `41c4ead868d62e955ba693ab9c50bbcbe04323af` (v80.196);
B1 is pre-implementation `684c5785d045ba9651282bcb586369c0b17cda74` (v80.203).
Measured B2 Windows product-byte digests are `b2415ba7…` for retained180/original
cold36 and `299dd9c63cb406730a2edc24e323db20ee3e42ae4e378a8a74e1ed737b77c5bc`
for repaired current work. Journals retain full digests and the narrow four-file
failure-only Stats timing carry-forward decision; old trials were not rerun on the
repaired build. Implementation is committed at `19f774718c67b2ca448bfd3892466452dd7150ae`;
the portable test-only CI repair is `027e9cef451be49485698e9214867b09ec7ea07e`.

Synthetic 550 roots/two prompts, fixed valid Stockholm day/quota inputs, independent
winners, same raw source, isolated caches/hosts/Chrome156 profiles, normal limits,
all six arm orders: retained60/arm; cold30 planned attempts/arm/profile; untouched30
hosts/arm. p50 is ordinary median; empirical p95 is nearest rank (60→57,30→29,29→28),
not population-tail confidence. Later routes benefit from earlier warming.

| Usable endpoint, seconds p50 / p95 | B0 | B1 | B2 | Interpretation |
| --- | --- | --- | --- | --- |
| Retained Models | 3.787 / 4.115 | 3.532 / 3.874 | 1.940 / 2.115 | 1.952× B0 median; preferred2× missed |
| Cold-recent Models | 14.629 / 15.999 | 14.057 / 15.058 | 5.968 / 6.611 | 2.451× B0 median |
| Cold-cutoff Models | 12.010 / 13.324 | 2.806 / 3.309 | 1.542 / 1.972 | 7.790× B0 median |
| Cold-recent Token Mix | 2.614 / 2.826 | 2.639 / 3.132 | .962 / 1.111 | B2 materially faster |
| Cold-cutoff Token Mix | 2.711 / 3.111 | 7.666 / 8.388 | 2.771 / 3.014 | B0 median target missed; +59.111ms/+2.18% |
| Cold-recent AI Stats navigation | 4.229 / 4.694 | .938 / 1.601 | .951 / 1.077 | B1 navigation median slightly better |
| Cold-recent Models-entry→AI | 21.468 / 23.168 | 17.680 / 18.462 | 7.930 / 8.588 | Separate whole-entry clock improves |
| Cold-recent Comparisons | 5.042 / 5.912 | 3.182 / 3.732 | 2.192 / 2.531 | No slow-sample removal |
| Retained certified history, host clock | UNPROVEN | 43.519 / 44.230 | 5.732 / 6.058 | 7.59× B1 median |
| Cold-recent certified history, host clock | UNPROVEN | 42.785 / 43.822 | 7.684 / 8.179 | 5.568× B1 median |
| Cold-cutoff certified history, host clock | UNPROVEN | 42.710 / 43.455 | 7.598 / 8.251 | 5.621× B1 median |
| Untouched qualified Token Mix entry | 2.601 / 3.111 on-demand | .071 / .074 | .072 / .075 | Different B0 contract |
| Untouched qualified AI entry | 4.356 / 4.754 on-demand | .070 / .086 | .070 / .076 | No prior browser acquisition |
| Untouched qualified Comparisons entry | 4.984 / 5.871 on-demand | .160 / .203 | .168 / .211 | B2 qualified-entry p95≤1s |

B0 provisional history/identity convergence is **not** correctness-equivalent
certification. Accounts and Sessions membership, both AI clocks, warm categories,
maximum values, exact per-route n and B1/B0/B2 ratios remain in the linked tables.
Accounts cutoff capture changed from arbitrary text size to visible semantic
identity/heading/quota: pooled descriptive results are not unchanged-endpoint proof.

Fixed cold/untouched accounting: **267 completed + two failed + one interrupted =
270 planned slots**; all90candidate journeys completed. Cold-recent B0=29complete/
1failure and B1=29complete/1interrupted; cutoff B0=29complete/1failure. Unreached
routes, absent final validation and unknown interrupted block closure remain missing;
no replacement,300s imputation, benign-censoring assumption or invented planned p95.

| Cold-recent whole-attempt resource p50 / p95 | B0 | B1 | B2 |
| --- | --- | --- | --- |
| Owned CPU s | 38.516 / 42.938 | 32.094 / 34.594 | 18.562 / 19.906 |
| Sampled peak WS MiB | 139.844 / 145.754 | 172.957 / 175.434 | 134.328 / 138.000 |
| Logical read MB | 192.997 / 195.455 | 140.165 / 142.729 | 131.514 / 135.582 |
| Logical write MB | 31.786 / 32.735 | 32.918 / 33.616 | 33.958 / 34.421 |
| Source MB | 258.055 / 261.624 | 269.649 / 272.168 | 67.685 / 68.451 |
| Catalog requests | 5029 / 5109 | 5295 / 5346 | 1269 / 1284 |
| Per-journey maximum Live gap s | .468 / .523 | .418 / .468 | .334 / .415 |

Candidate also makes1,100scoped root GETs+1,100child-page requests/journey; hydration
was not eliminated. Logical counters include network/cache, not physical-disk wear.
Idle n3/arm: open/closed CPU medians B0=13.57/13.93%, B1=14.72/14.20%,
B2=11.33/10.99%; max WS90/94/64MiB. Closed requests/h3084/3083/3110;
bounded open Comparisons refresh raises B1/B2 traffic. Some unvisited scalar keys
remained pending; this is not all-scalar-warm proof. Qualified untouched preparation
still takes B2~34.3s after Models, not instant warming.

## Real source and native responsiveness

One serial-first current-build observation: **2,961/2,961 roots**, missing0,
2,965reference hydrations. Independent preparation224.655s; product first verified
certificate**125.831s**, zero competing reference refreshes. That exact frozen
certificate independently matched epoch, complete membership, every revision and
winner identity/prompt/finish/order in0.676s (126.527s from host start). Full5/Mini3
shipped DOM/finish/order, actually hidden opener, visible headless PiP and independent
demand passed; post-browser revalidation128.169s. During acquisition350Live
publications/maxgap1.254s; all owned resources closed, total353.012s.
Evidence: `scratch:/real-history-oracle-6/result.json` and its provenance file.

The earlier412.349s result included concurrent reference work. The new result
supports contention contribution, not isolated causation across changed builds/
workloads. Retained caches and preparation may warm storage: **no OS/application-
cold proof, real B0/B1 ratio or real p95**. Earlier real inconclusive runs remain so.

Native production `WatchCoordinator.run_forever`/120-column `WatchRenderer` ran to a
bounded memory sink, with normal deferred history/adaptive cadence/hints and native
account requests/observation logging disabled as Diagnostics. First frame2.118s;
30s lead,189.173s genuine owned Web loading and30s recovery.418native render/status
completions during load: observed gap p95/max1.205/4.560s, poll p50/max1.007/4.557s,
maximum poll-completion gap12.101s. Recovery render gap max1.017s. No source recovery
or runtime fault; controller/native/Web workers and readers closed. This establishes
observed application-loop responsiveness with a temporary delay, not zero impact,
native B0/B1 regression statistics, physical terminal/keyboard or OS responsiveness.
Evidence: `scratch:/native-watch-responsiveness/{result,summary}.json`.

## Verification and changed keyboard/PiP coverage

- Final completion-tree local Full: **168 files, zero failures,116.9s**,
  `scratch:/completion-full-output.txt`; post-portable-repair Full112.9s and
  previous final-harness Full122.6s also passed.
  Focused reference/oracle13tests pass, including RED-before-implementation protection
  against unverified/later-certificate substitution; portable profiler tests6pass.
- Package validator: **zero failures, seven advisory warnings,11passes**, v80.204;
  `scratch:/completion-validator-output.txt`. No hard cap, baseline or assertion raised.
  `git diff --check` passes.
- Actual Full disclosure uses native browser Enter; current real Full/Mini identity
  and hidden-opener demand pass. Mini-focused Chrome156 Enter/Space expansion AND
  collapse pass DOM/aria and actual authenticated `/api/interest` HTTP200/90s lease
  checks before the30s timer can hide a missing callback. Close withdraws demand;
  reopen is collapsed with a new document lease; exactly one EventSource.
- The broad legacy Mini probe **FAILED before keyboard** on remembered geometry:
  it expected remembered bounds while default size was fit-on-open. Decision Delegate
  inspected intended sizing and the newer fit probe; no product placement repair or
  additional sampling required here. Placement is not called PASS. First focused
  attempt also failed because the old synthetic host did not expose dispatcher
  capability; adding the real isolated lease registry corrected the harness, not
  the product. Final focused evidence is `scratch:/focused-mini-keyboard-2.json`.
- Initial hosted run [42504809117](https://github.com/qstoffe/cost-guard/actions/runs/42504809117)
  failed one Linux profiler-test assertion: forbidding `Path.anchor` also forbade `/`
  in valid relative module paths. The repair checks the exact relative module, excludes
  the absolute repository root, and rejects absolute/traversal paths. Product unchanged;
  failure preserved, no manual rerun. Native jobs/browser had passed on that run.
- Repaired run [42505234346](https://github.com/qstoffe/cost-guard/actions/runs/42505234346),
  head `027e9cef451be49485698e9214867b09ec7ea07e`: **all four jobs SUCCESS**.
  Linux Full168files/2074tests/2053passed/21platform skips/0failures/0errors;
  validator exit0, common regression170.38s. Actual headless Chromium141 browser
  smoke PASS12.85s. Native Windows2025, macOS15 ARM64 and macOS15 Intel succeeded.
  Native CI covers APIs/launchers, not physical desktop/default-browser proof.
  Final cumulative-head CI/protection state remains authoritative at merge.

Core executed commands (isolated clone; real/native runners and controls in journals):

```text
py -3 development/tools/run_tests.py --suite full
py -3 development/tools/validate_package.py --working-tree
git diff --check
node development/tests/integration/probe_mini_watch.cjs <browser> <new-output.json> 1 --history-demand-only
```

## Attributed decisions, exceptions and remaining limits

Decision Delegates explicitly accepted these **measured scopes**, not blanket FR
waivers: retained Models1.952×preferred2× miss (~47ms); cutoff Token Mix materially-
faster-than-B0 median target missed (+59.111ms/2.18%); separate AI navigation/whole-
entry clocks; logical-write increases (retained+.817MB/2.77×primary, recent+6.83%,
cutoff+12.07%, untouched~8.28%) with lower CPU/source/WS; bounded idle logical-read
growth; finite AI promotion evidence; Earlier promotion **no material acceleration
observed**, accepted by Astra Decision Delegate because history already uses its
demonstrated safe maximum. None authorizes weaker proof or greater worker capacity.

The final verification Decision Delegate accepted the exact-first real-loading observation and
qualitative native-loop tradeoff above. Physical tray/default-browser/window-placement/
Finder/Gatekeeper/OS-accessibility checks were **not performed under Decision Delegate
exception**, because those native owners are unchanged; headless/CI is not OS proof.

Knowledge helper failed before writes on inherited leaf/router limits and later
`INDEX_LIMIT`. Decision Delegates approved bounded manual consolidation/replacement
of the prepared journal leaves, with exact hash/HEAD checks, byte-exact recovery
backup, unchanged budgets and no unrelated routing migration. Latest replacement
was12,258bytes≤12,288. Ancestor route-count/hierarchy nonconformance remains; helper
execution is not PASS. No credentials, private prompt/title/winner identities, raw
session exports or scratch logs were published.

The exact private historical terminal incident was not reproduced as one definitive
cause. Controlled RED/GREEN demonstrates concrete failure/recovery mechanisms and
current large-real-source success. Static Live publication gaps are not active-input
latency; sampled working sets may miss peaks; logical I/O is not physical disk.
No universal speed, reliable population-tail bound or unmeasured native guarantee.

Ordinary delivery progress advances73→74 only with this PR's actual merge;
existing maintenance milestones/deferred learning remain unchanged. The source
version/date/history/current README were reconciled against latest main80.203.
