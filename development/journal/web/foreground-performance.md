# FR 000624 — measured performance and scoped acceptance

Source revision: bdc0494df6acfda2e09060bd42319195c003d416
Checked revision: bdc0494df6acfda2e09060bd42319195c003d416
Last checked: 2026-11-08
Status: current

## Summary

**Locally measured; final delivery gates pending.** [Recovery/owners](foreground-recovery.md) records correctness and
rejected designs. Git base is not the measured dirty contents. Times mean usable
content/settled paint, not progress. No real-source or physical OS/disk-cold ratio.

| Arm | Pinned Git revision | Measured product-content SHA256 |
| --- | --- | --- |
| B0, pre-dispatcher v80.196 |41c4ead868d62e955ba693ab9c50bbcbe04323af|e4f624a7f9dc49d0f075b00eb0136e3715468fd1bcc1ca8ab95282625ae87566|
| B1, pre-implementation v80.203 |684c5785d045ba9651282bcb586369c0b17cda74|c83d55e8fcac7fee98048974391e677b45a6efa6a9268570825bb6e229f07fa1|
| B2, retained180/original cold36 v80.204 |bdc0494df6acfda2e09060bd42319195c003d416|b2415ba7d630108797aa2ac2d303d4a6b491d6abe0db75d7bfcb7ca965d9e834|
| Repaired B2, Stats BUSY recovery |same base, uncommitted|299dd9c63cb406730a2edc24e323db20ee3e42ae4e378a8a74e1ed737b77c5bc|

Delegate allows limited timing carry-forward across four-file failure-only Stats
repair, retaining actual digests, not repaired-build repeated reliability proof.
Earlier scalar-wake/version-only carry-forward remains focused/browser/final-gate
conditioned. Neither claims unexecuted repaired trials.

## Evidence

### Controls and statistics

- Synthetic550roots/two prompts, independent Full5/Mini3/100Models prompts,
  550Sessions/11pages/positive quota. Exact old executables, normal warming/ceilings,
  Chrome156/pythonw. Recent-metadata stresses cutoff exhaustion; cutoff-effective
  fixes10%recently touched old roots, not a real population model. Fixed asof/raw quota/
  Stockholm pre/post guards; owned fresh caches/hosts/profiles; no competing producers.
- Retained:60journeys/version, all6orders×10,3untimed native preparations excluded,
  same-path per-version WAL-consistent seed restores, one source registration.
  **p50=ordinary median; empirical p95=nearest rank57/60**. All successful observations,
  including slow ones, stay. No population-tail confidence bound is asserted.
- Cold30**attempts**/version/profile, all6orders×5; failed/unreached routes explicit,
  successful-only actualn. No300s imputation or benign-censoring assumption.
  Untouched30/version/recent only: passive all-three B1/B2qualification, B0on-demand;
  each entry≤1s/exact scope/publication/unvisited/no acquisition/settled paint.
  Same-tab, fresh-document/host-warm and untouched categories remain distinct.

### Completed retained-cache/fresh-host block

`scratch:/reconcile-immutable-retained.py` independently reconciled183actual results/
180seed restores/controls/oracles/qualified entries/closure in
`scratch:/approved-tail-blocks-immutable/retained-60/`. Full distributions/hashes
remain in `reconciled-distributions.{json,md}`.180measured journeys PASS, actual
candidate**b2415ba7**, not299dd9c. B0history stays UNPROVEN.

| Metric, seconds p50 / p95 / max | B0 | B1 | B2 | B1/B0 p50 | B2/B0 p50 |
| --- | --- | --- | --- | --- | --- |
| Models |3.787/4.115/4.373|3.532/3.874/4.048|1.940/2.115/2.219|.933|.512|
| Token Mix |1.229/1.563/1.604|2.139/2.771/2.819|.993/1.041/1.097|1.740|.808|
| AI Stats navigation |1.243/1.285/1.576|.569/1.389/1.576|.887/.952/.972|.458|.713|
| Models entry→AI usable |6.269/6.742/7.000|6.171/7.297/7.462|3.827/3.987/4.103|.984|.610|
| Comparisons |2.867/3.230/3.258|3.203/3.279/3.356|2.120/2.251/2.419|1.117|.739|
| Full Earlier route |38.431/38.782/39.093|33.873/34.551/34.678|.040/.049/.455|.881|.00105|
| Accounts |.0139/.0206/.0207|.0205/.0208/.0211|.0200/.0203/.0205|1.475|1.440|
| Sessions page2 membership |.1326/.1401/.1460|.1329/.1463/.1535|.1398/.1534/.1542|1.003|1.055|
| Mini Earlier |.0832/.0853/.0977|.0830/.0973/.1035|.0824/.0935/.1023|.997|.990|
| History after host start |39.048/39.309/39.456 **UNPROVEN**|43.519/44.230/45.030 certified|5.732/6.058/6.937 certified|not equivalent|not equivalent|

Models**1.952×**, preferred≥2×**MISSED** (~47ms); p95~1.95×better. Certified history
**7.59×median/7.30×p95**better thanB1. B0later identity matching is not retrospective
certification. Sessions membership is not scalar/detail completion.

| Qualified warm entry, p50 / p95 / max seconds | B0 | B1 | B2 |
| --- | --- | --- | --- |
| Same-tab Models |.0167/.0202/.0239|.0164/.0207/.0253|.0155/.0206/.0220|
| Same-tab Token Mix |.0155/.0201/.0208|.0145/.0198/.0224|.0158/.0199/.0234|
| Same-tab AI Stats |.0180/.0210/.0220|.0199/.0614/.0767|.0184/.0214/.0226|
| Same-tab Comparisons |.0889/.1158/.1189|.1041/.1323/.1654|.0839/.0974/.1418|
| Fresh-page Models |2.844/2.929/3.174 **on-demand**|.0903/.1077/.1369|.0903/.1030/.1071|
| Fresh-page Token Mix |.0725/.0766/.0779|.0701/.0759/.0767|.0721/.0758/.0770|
| Fresh-page AI Stats |.0728/.0768/.0777|.0719/.0760/.0763|.0728/.0766/.0776|
| Fresh-page Comparisons |.1541/.1837/.1910|.1495/.1739/.1903|.1535/.1795/.1895|

All B2warm p95s≤1s; B1/B2publication reuse/no new job/heavy acquisition proved.
B0lacks dispatcher equivalence.480entries/version(1,440total) still**n60/route/mode**,
not pooled independent hosts.

### Retained resource boundaries

Primary boundary precedes appends; main-hostCPU≠allchildCPU. Sampled WS/logicalI/O
can miss peaks/final-child work; network/cache≠physicaldisk. Source totals combine
phases and cannot be split into retained-only traffic.

| Metric, p50 / p95 / max | B0 | B1 | B2 |
| --- | --- | --- | --- |
| Primary host CPU s |18.805/19.500/20.484|16.492/17.297/18.531|6.438/7.047/7.594|
| Primary elapsed s |48.360/48.739/48.971|43.946/44.626/45.523|6.727/7.098/7.303|
| Primary peak WS MiB |137.816/144.254/145.414|168.637/174.309/175.695|130.215/138.617/140.863|
| Primary logical read MB |106.355/106.531/106.664|115.252/116.086/116.164|103.073/104.298/104.446|
| Primary logical write MB |.462/.470/.470|.761/.773/.773|1.279/1.357/1.358|
| Combined owned-process CPU s |29.828/30.750/31.625|24.086/25.016/26.688|11.867/12.781/13.438|
| Combined source MB |185.984/186.746/187.050|172.268/172.877/173.030|4.118/4.879/5.181|
| Combined catalog requests |3675/3690/3696|3405/3417/3420|51/66/72|
| Combined message requests |644/648/649|572/575/576|564/568/568|
| Combined max Live gap s |.425/.467/2.004|.405/.437/.449|.319/.342/.366|

B2adds1,100rootGETs+1,100child pages/journey; no hydration shortcut. Write median
**+.817MB/2.77×B0**, CPU~66%less/source~98%less. Fewer publications reflect shorter
journeys, not lower cadence; static gaps are not content-update latency.

Delegate2026-11-08 accepted retained-tail evidence and narrow Models/both-clock
AIStats/logical-write tradeoffs; no extra sampling/47ms tuning. Other gates remain.

### Cold and untouched — fixed plans reconciled

[Cold/untouched evidence](foreground-cold-warm.md) gives the actual route/resource
tables, denominators, method changes and limitations.270planned slots yielded267
completed journeys, two failed and one interrupted attempt. All90candidate journeys
completed, but cold-recent includes12oldb2415+18repaired299executions, not30repaired
trials. Candidate Models~2.45×/7.79×B0recent/cutoff; certifiedEarlier~5.57×/5.62×B1.
Default untouched finite entry p95≤.211s after~34.3s initial background preparation.
Cutoff Token Mix median2.770506vsB02.711395s (+59.111ms/2.18%) misses faster-than-B0;
Decision Delegate accepted scoped practical parity, not exact/statistical equivalence.
New logical-write growth is explicitly accepted there, not physical-disk/idle proof.

### Separate completed promotion, idle and scalar evidence

- **Finite promotion:** actual advancing unfinished AI30, cutoff550, hold→normal and
  reverse. Switch→qualified paint6.328→1.393s and7.199→1.890s; original-job completion
  6.272→1.348/7.141→1.827s. Native priority2→0grant70/213ms, same observation/result
  identity/checkpoints/two slices; unchanged cooldown. Startingwork differs slightly
  (first normal one64-root batch ahead; reverse218vs220).4/4semantics/closure,
  maxLivegap≤.315s; no new repeat matrix required. Not a populationp95 result.
- **Earlier promotion:** six actual Full/Mini partial-history observations, three
  per mode, Full switch→certified6.397s/Mini6.713s. **No material acceleration
  observed; scoped exception approved by Astra Decision Delegate**, because history
  already runs at demonstrated safe maximum from startup. Do not call promotion
  speed PASS or restore foreground-slowing pacing. Demand/hiddenopener/reuse/proof/
  Live hard requirements remain. Evidence `scratch:/promotion-final/`.
- **Idle:** nine matched n3/version, cutoff550,240ssettle+120sopen/closedwindows.
  HostCPU open/closed medians B013.57/13.93%,B114.72/14.20%,B211.33/10.99%; maxWS
  90/94/64MiB. Closed requests/h3084/3083/3110(max3205). Open3117/4537/4534 includes
  bounded Comparisons refresh, not continuous Earlier scans. Logicalread closed/open
  B0.18/.44MB,B1.38/1.59,B23.86/5.04MB. Trace attributed~105pricing-cache checks/120s,
  ~1.7KBpayload/~37KBlogicalread/get; physical disk/cache-hit ratio unknown. Astra
  accepted logicalread growth and bounded freshness schedule, not arbitrary future
  idle increases. Old windows still had117–118last-page scalar keys pending, so
  they are not all-scalar-warming-complete; visible Sessions recovery is separate.

Earlier n3cold data is not sufficient tail proof. Actual cutoffTMregression
7.264vsB02.680s(2.71×) prompted bulk-cache/retirement/admission/poll-wake repairs.
Final n3was2.923vs2.875s,+48ms/1.017×: narrowly accepted practical parity,
**not exact≤1.00PASS**. The new fixed-cutoff disposition above supersedes its narrow
numerical scope, not the fact that a median target remains missed.
Aborted49/33retained samples and diagnostic/preparation data remain excluded;
failure mechanisms/unknowns are preserved in the recovery note.

## Next investigations

Fixed plans and honest observed-route statistics are reconciled; missing planned
percentiles remain unavailable. Local current Full passed168files. Validator/diff/hosted CI,
latest base/version, concise completion with all attributed exceptions and protected
Git delivery. Passing an intermediate block is not completion.

## Rejected hypotheses

No pooling aborted/diagnostic/preparation entries into acceptance; no slow-sample
replacement or optional extension to chase targets. No physical-disk, real cold
ratio, all-scalar-ready, population-tail confidence or physical desktop claim can
be inferred from this fixture. A repaired diagnostic is not repeated reliability
sampling; unavailable/unproved evidence remains explicit.
