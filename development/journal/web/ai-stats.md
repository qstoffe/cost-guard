# AI Stats: evidence recovery and resumable history

Source revision: 8a53900935402c97fe2dcefb0a729ce4f93b00dc
Checked revision: 8a53900935402c97fe2dcefb0a729ce4f93b00dc
Last checked: 2026-11-07
Status: current

## Summary

FR000619/v80.199 implementation delta against the revision above, not a new audit
of untouched history. Owners remain `src/analysis/ai_stats.py` (statistics),
`src/analysis/compaction.py` (canonical compaction timing),
`src/reports/ai_stats.py`/`ai_stats_evidence.py` (acquisition/checkpoints/proofs),
`src/application/ai_stats.py` (prepared display), and `src/web/stats_jobs.py`/`jobs.py`
(logical acquisition and finite processes). No architecture boundary changed;
the CODE_MAP update is navigation-only.

An unknown execution must not erase valid unioned intervals. Working Time now
retains a **Partial lower bound**; Longest Session/Busiest Day retain **Observed**
subtotal leaders, not verified overall winners. Most Expensive Session can retain
a positive observed cost leader. Full averages, hourly rates, Night Owl, Coding
Streak and Peak Parallel Sessions still require their actual dependencies. No
average or concurrency maximum is manufactured from a smaller known subset.

Cost and timing evidence stay independent. A complete, stable, non-running root
with known execution ends, no pending usage and all requests before a boundary
can be excluded. Incomplete snapshots, unknown ends, active roots and membership/
migration gaps cannot be dismissed because catalog metadata looks old. Complete
evidence retains exact original values, traits, root/child dedup, event-time cost,
overlap union and local/DST calendar semantics. All time excludes no old root.

Completed native compaction parts can supply an explicit `time.end` when the
message-level completion is absent. Creation time, normalized updated-time
fallbacks, completed status/summary presence and adjacent unrelated prompts do
not prove an end. Analysis algorithm 17, compact evidence 4 and coverage 2 reject
old interpretations; source revisions and price/config/identity remain required.
No raw snapshots/prompts are newly persisted and no source writes are introduced.

## Evidence

Before formulas changed, opt-in synthetic and authorized read-only V2 probes
produced count-only per-card matrices. The local observation had **2,787 roots**,
**zero incomplete snapshots**, no selected-source warning, **eight missing
compaction durations**, no missing execution starts/negative durations, one running
interval and no missing token categories. Ordinary prompt durations were known.
Wire inspection counted ten native compactions (eight qualified completed records):
all had creation time and none had a supported end/completion field. Missing
prices affected **17 requests in one root**. This establishes a legitimate native
time gap plus avoidable aggregate information loss; it does not identify the
owner's exact earlier failing run or prove a hidden cache/normalizer incident.

The final same-observation baseline/new formula comparison used current compact
facts and exact baseline source, never a second mutable source read:

| Scope | Baseline unavailable | Current unavailable | Current partial | Current exact cost cards |
| --- | ---: | ---: | ---: | ---: |
| Today / 7 days / This month | 7 | 4 | 3 | 3 |
| 30 days / All time | 9 | 5 | 5 | 0 |

The five partial values are total cost, working time and the three observed
session/day leaders. Unknown full time/rate/share/streak/peak and incomplete
average stay unknown. Bounds independently excluded 2,778 / 2,425 / 642 / 2,425
roots from Today / 7 / 30 / month; the eight unknown compactions remained relevant
to every scope. The source's migration comparison was **not inspected**, not a
positive migration-completeness proof. The initial diagnostic's Boolean of the
diagnostic object overstated this as a gap; the maintained probe now reports
`inspected` and `has_gap` separately. No acquisition/price failure was established.

Reproduction (isolated caches; aggregate output only):

```text
py -3 development/tests/integration/probe_ai_stats_evidence.py --synthetic
py -3 development/tests/integration/probe_ai_stats_evidence.py --baseline 8a53900935402c97fe2dcefb0a729ce4f93b00dc
py -3 development/tests/integration/benchmark_ai_stats.py --baseline 8a53900935402c97fe2dcefb0a729ce4f93b00dc
py -3 development/tests/integration/probe_ai_stats.py --cold-and-warm
py -3 development/tools/run_tests.py --suite full
py -3 development/tools/validate_package.py --working-tree
node development/tests/integration/probe_ai_stats.cjs <browser-executable> <output-json>
```

Full: **155 files, zero failures, 97.8s**. Focused recovery cases cover a single
unknown among known intervals, one incomplete snapshot among 2,700 roots,
independent pricing/tokens/pending/time, old complete versus unknown/incomplete
roots, explicit compaction ends versus absent/invalid ends, bound rounding and
old algorithm/proof rejection. Existing source, DST, cache/revision, archived/
deleted-root, process, loading and dispatcher checks remain in Full.

Hidden Edge: **15 checks, 54 canonical state/theme/unit cases, nine layouts,
80 enlarged-text layouts, 1,350 contrast samples, zero runtime errors**. Actual
HTTP/assets/CSP, help keyboard/hover/touch, focus/keyed cards, quiet refresh,
30→7→All and finite-process/two-tab resumption were exercised. Production fixture:
7 days ready at 2/24 roots; 12 children/exactly 24 hydrations; no surviving owned
child/host failure. Integrated browser was disconnected, so no integrated PASS.
Physical devices, real screen-reader speech and non-Chromium paint remain unproved.

Fixed healthy **2,700 roots/54,000 requests**, small histories and cold/warm/1%
changed states retained all ten metrics and optional matched fact: **18 selected-
period baseline comparisons passed**. The benchmark now loads the old formulas
as well as its builder; importing today's formula would make parity vacuous.
Direct-builder large-history seconds (baseline/current):

| Scope | Cold | Warm | 1% changed |
| --- | ---: | ---: | ---: |
| 7 days | 9.644 / 9.389 | 4.031 / 3.906 | 3.466 / 3.494 |
| 30 days | 10.945 / 11.264 | 4.234 / 4.405 | 4.859 / 4.152 |
| All time | 11.635 / 12.162 | 6.346 / 5.186 | 6.114 / 5.516 |

Cold/warm/changed hydrate **2,700/0/27** roots, with unchanged measured acquisition
counts. This immediate baseline supports 7 days directly; only genuinely older
builders fall back to acquiring 30 days. The comparator uses historical report/
formula code with current shared dependencies, not a whole historical checkout.
Direct timings exclude process/IPC and are not a universal speedup claim. Cold
All adds about 0.53s/4.5%; its shared analysis stage adds 0.56s while Stats projection
falls 0.17s. Variation is consistent with noise, not proof that it is noise.
Final real count-only
direct acquisition: **63.379s wall, 40.969s CPU, 291,098,624-byte peak working set**;
initial pre-change direct probe 112.698s/44.094s/295,829,504 bytes was nonpaired and
overlapped synthetic work, not causal latency proof. Actual production cold30
**78.583s**, warm30 **4.261s**, All extension **5.190s**, warmAll **4.848s**, all
complete without terminal errors. No new acquisition scan/lane, catalog policy,
paid inference or Watch scheduling change was introduced.

Own evidence: `scratch:/baseline-heavy-gap.json`, `scratch:/baseline-live-wire.json`,
`scratch:/recovery-live.json`, `scratch:/benchmark-final.jsonl`, `scratch:/browser.json`,
`scratch:/full-tests.txt`, `scratch:/live-cold-warm.jsonl`.

### Retained lifecycle and historical decisions

FR000614 checkpoints share source/config/pricing/algorithm-keyed compact facts,
256-root slices, 64-root batches, maximum-four V2 reads, complete membership/tree
revision verification, volatile refresh, finite child watchdogs and bounded
resource/storage/stall failures. Unknown old roots may delay even Today/7 days;
earlier completion is conditional on independently verified stable coverage.
FR000615 removed arbitrary logical interest expiry and user Cancel; up to five
requested scopes persist without polling interest, narrow goals prioritize work
and earlier goals resume. FR000617's host dispatcher owns retained demand and
shared compact products; it does not turn partial evidence into exact results.
Active-page retention versus one-hour re-entry withholding remains distinct.

**Historical Decision Delegate exceptions, not renewed FR000619 waivers:**
FR000614 accepted conditional shorter-period completion where source capabilities
cannot prove cold exclusion, and a residual warm/changed large-history slowdown
after bounded investigation. Its sliced cold30 improved 50.980→27.023s, while
warm30 regressed 5.010→5.560s; 18 parity comparisons passed. Neither correctness,
freshness nor materially worse future evidence was waived. Mutable real history
prevented paired speed claims. Its helper/schema exception covered contextual
module/navigation edits and a bounded journal only. FR000611's CSS-only live-
timeout exception likewise grants no present verification waiver.

**Current Decision Delegate documentation exception:** the knowledge helper read
failed before writes with `KNOWLEDGE_LIMIT` because this legacy leaf exceeded
12 KiB; inspected ancestors also have legacy routing debt. The delegate authorized
this direct consolidation to ≤12,288 UTF-8 bytes and necessary AI Stats navigation
edits only. No helper PASS, limit increase, blanket exception or architecture
diagram rewrite is claimed. This exception waives no product acceptance/testing.

**Current Decision Delegate performance-proof exception:** accept these mixed
timings and bounded immediate-baseline/current-production measurements instead of
strict frozen-corpus whole-stack latency/CPU/memory comparison against FR000614.
The accepted residual increase includes cold All +0.53s/4.5%. Useful evidence
recovery and unchanged measured acquisition counts justify this tradeoff, not a
nonregression PASS or inherited historical waiver. No correctness, freshness,
resource bound or actual Watch-regression requirement is waived. Comparative Watch
responsiveness and aggregate logical-job memory are not proved by these probes.

## Next investigations

The owner's exact original private observation remains unverified. Native records
without end timestamps cannot be made exact from status/summary alone. A future
source capability could supply stronger per-field/temporal coverage, but old
cached completeness is not such a capability. Full V1-versus-V2 scale benchmark,
physical-device/accessibility speech and non-Chromium paint are not established
by the canonical synthetic benchmark; Full retains adapter/parity regressions.

## Rejected hypotheses

- Finished acquisition/100% is not proof every metric is fully computable. Loading,
  CSS or longer timeouts cannot repair unknown returned canonical values.
- One missing end does not erase the measured union, but the union is not the full
  denominator. Its partial display floors before rounding so `≥` never overclaims.
- Old title/update metadata does not bound usage; missing events may hide overlap.
- Completed compaction status, summary text and creation time do not prove duration.
- Earlier probe `service.close()` cleanup failed after producing its aggregate
  matrix; the maintained probe uses the actual `close_accounts()` owner. That
  harness failure did not invalidate the observed counts and was not product PASS.
- Earlier FR000614 Node/Python console fixtures stalled an unrelated Normal child;
  verified hidden child startup and independent Stats process proof resolved that
  harness assumption. A ready narrow row does not require an extra worker.
- Prior FR000612 changed explanations, not null propagation. It cannot substitute
  for current source diagnosis. Historical speedups and exceptions are not new evidence.
