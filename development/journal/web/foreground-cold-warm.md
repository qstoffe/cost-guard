# FR 000624 — cold and untouched warming measurements

Source revision: bdc0494df6acfda2e09060bd42319195c003d416
Checked revision: bdc0494df6acfda2e09060bd42319195c003d416
Last checked: 2026-11-08
Status: current

## Summary

Fixed plans are reconciled, not all-PASS: **267 completed journeys + two failed + one interrupted = 270 slots**. All90candidate journeys completed. [Build provenance/retained evidence](foreground-performance.md) and [correctness/mechanisms](foreground-recovery.md) separate synthetic timing from real correctness and final delivery.

## Evidence

### Setup and accounting

550synthetic roots/two prompts, independent Full5/Mini3 winners,100Models prompts,550Sessions/11pages, positive complete quota. Chrome156, Windows Python3.14/pythonw, serial execution, isolated application caches/hosts/profiles; normal warming/limits, no controlled locks/navigation detours/competing producers. All6arm permutations×5 =30planned attempts/version/profile. Recent metadata and10%recently touched old roots (cutoff-effective) are separate inputs, not population models or OS/disk-cold proof. Later routes share warming, not eight independent cold launches.

Cold-recent asof1794138824106; cutoff1794145124642; untouched1794149339093. Each uses raw reset=asof+9,000,000ms, duration18,000s, fraction.75, Europe/Stockholm; real clocks and successful end/day/window validation. No expired-input refresh or failed-slot replacement. Candidate recent=12measured b2415ba7+18repaired299dd9c; cutoff/untouched=30repaired299dd9c each. Prior limited four-file timing carry-forward does not turn old runs into repaired reliability samples.

| Plan | B0 complete/failed/interrupted | B1 | B2 |
| --- | --- | --- | --- |
| cold-recent | 29/1/0 | 29/0/1 | 30/0/0 |
| cold-cutoff | 29/1/0 | 30/0/0 | 30/0/0 |
| untouched-recent | 30/0/0 | 30/0/0 | 30/0/0 |

All slots attempted; no unattempted replacements. Cold r13-B0 Stats never ready by300s; underlying natural cause unproved, end validation absent. Cold r29-B1 lost its processes/results; outcome and source-block closure unknown. 49other completed results in that segment retain individual closure checks; new source closure cannot repair old missing lifetime totals. Cutoff r16-B0 failed generic Accounts text>100 at exactly100characters; no end validation, Sessions/Mini unvisited. Do not infer its precise historical cause from later diagnostics.

p50 ordinary median; p95 empirical nearest rank ceil(.95n), n=30→rank29, n=29→rank28. Cells show **n; p50/p95/max seconds**. Observed routes from failed journeys remain, explicitly without final validation. Missingness is not assumed random; no300s/infinity/imputed latency or hypothetical rank bounds. Planned-denominator p95 is unavailable when a route is missing; even n30observations with one unvalidated journey are not unqualified acceptance. B0 history values are independent identity convergence, **UNPROVEN**, never certified.

### cold-recent usable time

| Endpoint | B0 | B1 | B2 | B1/B0 median | B2/B0 median |
| --- | --- | --- | --- | --- | --- |
| Models | 30; 14.629/15.999/16.306 | 29; 14.057/15.058/15.147 | 30; 5.968/6.611/6.891 | 0.961 | 0.408 |
| Token Mix | 30; 2.614/2.826/2.910 | 29; 2.639/3.132/3.382 | 30; 0.962/1.111/1.139 | 1.009 | 0.368 |
| AI Stats navigation | 29; 4.229/4.694/4.805 | 29; 0.938/1.601/1.715 | 30; 0.951/1.077/1.118 | 0.222 | 0.225 |
| Models entry→AI usable | 29; 21.468/23.168/23.519 | 29; 17.680/18.462/19.453 | 30; 7.930/8.588/9.009 | 0.824 | 0.369 |
| Comparisons | 29; 5.042/5.912/5.951 | 29; 3.182/3.732/3.794 | 30; 2.192/2.531/2.639 | 0.631 | 0.435 |
| Full Earlier route | 29; 21.470/22.324/22.435 | 29; 21.734/23.198/23.816 | 30; 0.046/0.053/0.055 | 1.012 | 0.002 |
| Accounts* | 29; 0.014/0.021/0.021 | 29; 0.021/0.021/0.021 | 30; 0.020/0.020/0.029 | 1.484 | 1.454 |
| Sessions page2 membership | 29; 0.139/0.147/0.147 | 29; 0.139/0.154/0.154 | 30; 0.147/0.160/0.161 | 1.002 | 1.053 |
| Mini Earlier | 29; 0.083/0.090/0.118 | 29; 0.084/0.103/0.105 | 30; 0.089/0.099/0.102 | 1.004 | 1.070 |
| History host clock† | 30; 39.488/40.555/40.697 | 29; 42.785/43.822/43.880 | 30; 7.684/8.179/8.540 | not equivalent | not equivalent |

### cold-cutoff usable time

| Endpoint | B0 | B1 | B2 | B1/B0 median | B2/B0 median |
| --- | --- | --- | --- | --- | --- |
| Models | 30; 12.010/13.324/13.504 | 30; 2.806/3.309/3.389 | 30; 1.542/1.972/2.082 | 0.234 | 0.128 |
| Token Mix | 30; 2.711/3.111/3.145 | 30; 7.666/8.388/8.542 | 30; 2.771/3.014/3.027 | 2.827 | 1.022 |
| AI Stats navigation | 30; 4.184/4.705/4.743 | 30; 2.712/3.250/3.278 | 30; 0.948/1.083/1.146 | 0.648 | 0.227 |
| Models entry→AI usable | 30; 19.002/20.721/21.260 | 30; 13.172/14.372/14.573 | 30; 5.235/5.937/6.193 | 0.693 | 0.275 |
| Comparisons | 30; 4.953/5.802/6.403 | 30; 3.251/3.813/5.842 | 30; 2.199/2.503/5.952 | 0.656 | 0.444 |
| Full Earlier route | 30; 23.839/25.441/25.449 | 30; 25.834/26.727/26.873 | 30; 0.047/0.352/0.497 | 1.084 | 0.002 |
| Accounts* | 29; 0.014/0.021/0.021 | 30; 0.021/0.021/0.021 | 30; 0.020/0.021/0.021 | 1.435 | 1.420 |
| Sessions page2 membership | 29; 0.132/0.154/0.154 | 30; 0.133/0.147/0.147 | 30; 0.141/0.154/0.154 | 1.002 | 1.064 |
| Mini Earlier | 29; 0.078/0.097/0.104 | 30; 0.083/0.096/0.096 | 30; 0.089/0.097/0.097 | 1.064 | 1.143 |
| History host clock† | 30; 39.112/41.008/41.497 | 30; 42.710/43.455/43.696 | 30; 7.598/8.251/9.374 | not equivalent | not equivalent |

*Accounts cutoff methods differ: old generic-length completed samples B0n15/B1n16/B2n16; new semantic visible identity/heading/quota samples n14/arm. Pooled numbers above are descriptive, **not an unchanged-endpoint acceptance claim**. Cold-recent uses the old method throughout. †Certified B1/B2 history median improves5.568×recent/5.621×cutoff; B0 cannot supply a correctness-equivalent ratio. Models improves2.451×/7.790×B0median.

**Target miss:** cutoff Token Mix B2median2.770506s vsB02.711395s =+59.111ms/2.18%; p95/max improve modestly. **Materially faster than B0 median target missed; scoped exception accepted by Decision Delegate**, 2026-11-08. This replaces the older +48ms scope, not exact parity/statistical-equivalence proof. Keep candidate Comparisons5.952s cutoff maximum; no slow-sample removal.

### Untouched initial warming and entry

30hosts/version, three correlated entry observations/host; **n30/route**, not90independent trials. B1/B2wait passively after Models until all three exact default host publications qualify, then visit each for the first time. Checkpoint≤1s, unvisited/unacquired client state, exact publication match, no new logical job/heavy report acquisition. B0 has no dispatcher: its rows are separate on-demand timings, not qualified host-warm equivalence.

| Endpoint, n; p50/p95/max seconds | B0 on-demand | B1 | B2 |
| --- | --- | --- | --- |
| Models initial | 30; 14.112/15.345/16.244 | 30; 13.037/15.128/16.679 | 30; 5.988/6.901/6.946 |
| Models ready→all3qualified | N/A: no dispatcher | 30; 35.303/35.670/35.914 | 30; 34.326/34.764/34.768 |
| Token Mix entry | 30; 2.601/3.111/3.115 | 30; 0.071/0.074/0.074 | 30; 0.072/0.075/0.076 |
| AI Stats entry | 30; 4.356/4.754/5.358 | 30; 0.070/0.086/0.091 | 30; 0.070/0.076/0.076 |
| Comparisons entry | 30; 4.984/5.871/6.937 | 30; 0.160/0.203/0.222 | 30; 0.168/0.211/0.235 |
| Models entry→AI usable | 30; 21.873/23.483/25.521 | 30; 49.040/51.096/52.652 | 30; 40.988/42.373/42.473 |

Candidate qualified-entry p95≤.211s meets≤1s; initial warming still takes~34.3s after Models. AI whole-journey clock includes deliberate passive all-three wait; do not pool with cold navigation. Decision Delegate accepted this exact scope, not instant preparation, promotion or real-source speed.

### Whole-attempt resources

Cells p50/p95/max; units in labels. Include actual failed-attempt work, not success-only efficiency. No metrics are invented for interrupted r29-B1. CPU from owned process records; host CPU is not all-child CPU. Sampled aggregate working sets can miss peaks/final child work. Logical I/O includes cache/network, not physical disk. Source deltas are per-result; historical missing block-lifetime totals remain unavailable.

**cold-recent**

| Metric | B0 | B1 | B2 |
| --- | --- | --- | --- |
| Owned CPU s | 38.516/42.938/55.438 | 32.094/34.594/34.656 | 18.562/19.906/20.594 |
| Peak WS MiB | 139.844/145.754/146.402 | 172.957/175.434/176.246 | 134.328/138.000/138.684 |
| Logical read MB | 192.997/195.455/196.173 | 140.165/142.729/143.112 | 131.514/135.582/138.196 |
| Logical write MB | 31.786/32.735/33.096 | 32.918/33.616/33.835 | 33.958/34.421/34.421 |
| Source MB | 258.055/261.624/262.085 | 269.649/272.168/272.340 | 67.685/68.451/68.451 |
| Catalog requests | 5029.000/5109.000/5112.000 | 5295.000/5346.000/5349.000 | 1269.000/1284.000/1284.000 |
| Max Live gap s | 0.468/0.523/0.525 | 0.418/0.468/0.523 | 0.334/0.415/0.431 |

**cold-cutoff**

| Metric | B0 | B1 | B2 |
| --- | --- | --- | --- |
| Owned CPU s | 35.148/40.812/41.578 | 30.852/33.688/34.422 | 17.188/18.406/19.062 |
| Peak WS MiB | 138.984/144.266/147.617 | 166.920/174.203/176.020 | 130.225/134.012/135.074 |
| Logical read MB | 199.149/204.007/204.597 | 155.383/165.175/175.796 | 138.279/145.032/156.766 |
| Logical write MB | 30.912/32.068/32.839 | 34.462/35.416/36.687 | 34.644/35.231/37.291 |
| Source MB | 198.995/200.625/201.986 | 205.205/207.040/207.099 | 35.140/36.344/36.424 |
| Catalog requests | 3856.500/3888.000/3915.000 | 4003.500/4029.000/4041.000 | 621.000/639.000/642.000 |
| Max Live gap s | 0.454/0.571/0.580 | 0.404/0.469/0.470 | 0.322/0.394/0.398 |

**untouched-recent**

| Metric | B0 | B1 | B2 |
| --- | --- | --- | --- |
| Owned CPU s | 37.172/40.250/44.047 | 31.672/36.188/36.281 | 20.758/24.375/25.719 |
| Peak WS MiB | 139.615/144.344/146.129 | 137.725/142.426/144.633 | 131.650/138.328/138.824 |
| Logical read MB | 195.255/198.044/198.677 | 138.630/141.870/142.157 | 132.655/137.453/142.102 |
| Logical write MB | 31.817/32.912/33.195 | 32.964/33.884/34.043 | 34.451/34.871/34.937 |
| Source MB | 258.402/260.703/261.597 | 269.626/273.257/274.828 | 70.148/70.985/70.989 |
| Catalog requests | 5037.000/5082.000/5100.000 | 5296.500/5367.000/5400.000 | 1318.500/1335.000/1335.000 |
| Max Live gap s | 0.467/0.515/0.563 | 0.411/0.468/0.840 | 0.335/0.433/0.509 |

Candidate adds1,100scoped rootGETs+1,100child-page requests/journey; message/context hydration is not eliminated. Logical-write median growth vsB0: recent+2.172MB/6.83%, cutoff+3.732MB/12.07%, untouched+2.635MB/~8.28%. Decision Delegate explicitly accepted these increases with lower owned CPU/source traffic/WS and better measured Live-gap tails. This is not physical-write/storage-wear or unchanged-idle proof; retained/idle decisions remain separately scoped. Static publication gaps do not prove active-content update latency.

Independent reconciliation: `scratch:/reconcile-final-tail.py`, outputs `scratch:/final-tail-reconciliation/distributions.{json,md}` retain individual result/browser hashes, build/support/method segments, exact per-metric counts and all failures. These are private operational evidence, not required public payloads. Repository repro entrypoint: `development/tests/integration/benchmark_web_runtime.py` with `--roots 550 --timezone Europe/Stockholm`, `--activity-pattern recent-metadata` or `cutoff-effective`, explicit pinned `--product-root`, new `--run-root`, explicit Chromium `--browser`, `--seconds 300`, and `--untouched-warm` only for that category. A new reproduction needs its own matched valid input block; do not replay expired historical timestamps.

## Next investigations

Local Full168files passed; package validation, hosted CI and protected final Git delivery remain pending at this check. No further sampling/tuning requested for these accepted narrow tradeoffs.

## Rejected hypotheses

A generic text-size threshold is not account-field correctness; a later fixed predicate cannot upgrade historical failures. Process absence is restart safety, not retrospective graceful shutdown. No baseline failure is repaired by candidate success, no same-host entries become independent hosts, and no real-source/native-OS/cold-disk claim follows from synthetic results.
