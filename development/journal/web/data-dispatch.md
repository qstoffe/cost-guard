# FR 000617 — dispatcher measurements and remaining verification

2026-11-07, local Windows workstation, uncommitted implementation. **Not delivered.**
No model inference, external desktop interaction or shared OpenCode stop was used.

## Causal findings

- Strict `/api/data` requires boolean `retry`. Initially an undefined failure flag
  caused JSON to omit it, producing invalid_request. Explicit conversion fixes
  admission; hidden Edge now checks emitted request types.
- Shared AI Stats scopes need minimum numerical priority, not last-entry dict
  overwrite. Scope changes use the managed endpoint and retain earlier goals.
- Continuation needs independently received durable compact progress. Real fresh
  process/SQLite tests cover a child killed after saving roots; the final child
  does not hydrate those roots again.
- Per-root full derived transactions dominated cold shared scans. A 300-root
  profile attributed 5.13 of 10.84 seconds to derived stores. Managed scans now read
  existing bundles but write bounded compact batches only.
- The first bounded real run completed Models/Token Mix but failed AI Stats and
  Comparisons on continuously changing roots. Managed historical batches now
  explicitly omit unverifiable roots, retaining strict ordinary snapshot APIs.
  Later-changed facts are removed before publication; missing coverage is a
  structured count and partial status, never acquired zero or complete history.
  Source membership/provenance changes remain protected. Fresh real proof is pending.
- First healthy Live publication now gates finite admission; an existing driver
  alone is not Watch readiness. Explicit browser Retry is consumed once, so an
  automatic retry loop cannot repeatedly clear host backoff.
- Thirty-second dependency checks read validated cached prices only, without
  upstream pricing/metadata work. A runtime-config change requires relaunch rather
  than mixing differently configured finite and Live owners. Hot preferences do
  not trigger that stop. Temporary price-cache failure is not invalidation proof.

## Synthetic 2,700 roots / 54,000 requests

`integration/benchmark_data_dispatch.py`: complete synthetic snapshots, isolated
disposable caches, canonical report code. Sequential measurements, not a universal
latency target or concurrent Watch fairness proof.

| Measurement | Independent evidence | Shared compact evidence |
| --- | ---: | ---: |
| Hydrated roots, cold + warm cycles | 8,100 | 2,705 |
| Cold Models, seconds | 0.0743 | 0.0375 |
| Cold Token Mix, seconds | 48.5057 | 17.2062 |
| Cold AI Stats, seconds | 10.5894 | 4.5838 |
| Cold Comparisons, seconds | 12.4153 | 0.5300 |
| Process peak working set, bytes | 349,413,376 | 351,334,400 |

Warm shared Models deliberately rereads five sampled roots instead of adding full
raw-bearing analysis persistence. Other warm shared reports hydrated zero roots;
projection CPU remained nonzero (Token Mix 3.3154 s, AI Stats 4.3780 s, Comparisons
0.2259 s). Earlier shared-write prototypes regressed cold wall time; those are not
advertised as improvement. Peaks are not an aggregate over parked children.

## Hidden browser and deterministic checks

`integration/probe_data_dispatch.cjs` uses shipped HTTP/auth/CSRF/assets, synthetic
host, fresh headless Edge, private CDP pipe and hidden helpers. Completed checks:
four reports warm unvisited; warm routes have no blocking loaders/Cancel; identical
lookups retain exact content without new jobs; Sessions main-nav preserves page ten
and its fifty rows; another tab with 61-minute data loads a coherent new result.
This is not actual desktop minimization, sleep, assistive-technology or macOS proof.

Focused dispatcher/catalog/detail/HTTP-view tests passed during iteration. First
refinement Full passed 153/155 files. Its new assertions incorrectly counted
visibility messages as page reads and expected the same durable count after forced
timeout. Corrections verify two actual page reads and saved + final-read roots =
ten; focused reruns passed. Subsequent Full passed 155/155 files (109.1 seconds),
and the browser host-invalidation case passed. Extra final assertions were added
during that Full; the exact dispatcher rerun subsequently passed (7.3 seconds).
The partial-history/dependency Full initially passed 153/155: early dependency checks
were gated on healthy Live publication, and nonmanaged price-constructor arguments
were restored. Both focused reruns passed. The next Full passed 154/155 files in
105.6 seconds: only the legacy generic partial-warning text had changed. Restoring
that text preserved the historical views' new explicit omission warnings; the exact
HTTP/DOM test passed in 11.68 seconds. A final Full is still required.
Hidden Edge passed seven scenarios, now including explicit three-root omission
warnings in AI Stats, Comparisons and Token Mix, one-shot Retry after transient
admission failure and host invalidation. Same-ID foreign-provenance and out-of-range
Sessions epochs now require explicit recovery; deterministic catalog tests passed.
Historical-report scale tests exceed the focused runner's default Quick 25 seconds:
the full-tier focused run passed in 28.2 seconds under its existing 240-second cap;
no timeout/assertion was weakened. Latest validator passed eleven checks, zero
failures, six existing advisories. Product metadata remains 80.196; not delivered.

## Required unfinished evidence

The earlier real-source prototype exhausted 600 seconds: Token Mix timed out,
AI Stats remained unfinished and Comparisons had not started. A later pre-partial
run ended after 485.96 seconds: Models and Token Mix ready; AI Stats/Comparisons
failed concurrent_source_change. It observed 1,029 Live publications, maximum gap
6.274 seconds, host CPU 234.484 seconds, peak working set 329,408,512 bytes. Its
20.17-second idle window consumed 9.969 host CPU seconds with zero new jobs: **not
proof of cheap idle**. Own serving/Live threads closed and no parked child remained.
The probe's original route lease expired after ninety seconds; the harness now
renews it like a browser and can explicitly switch behind an unfinished background
scan. These refinements require new real measurements, not reinterpretation of
the earlier output.
Real foreground/control comparison, Watch publication latency, warmed idle CPU/IO,
source churn and final safety outcomes must be reported before delivery. No FR
requirement or test exception has been approved.

## Fresh control, 2026-11-07

`probe_data_dispatch.py --foreground-only --budget-seconds 600 --idle-seconds 30`
uses the same managed foreground code and real Live, with speculative finite and
Sessions warming disabled. Existing disposable caches were retained; this is not
a cold-cache experiment. Source catalog: 2,880 sessions / 2,784 roots.

- Models ready at 23.375 s; Token Mix at 48.529 s, with one changing root explicitly
  omitted. Token Mix made foreground progress 0.611 s after navigation.
- 175 Live publications; maximum gap 3.105 s. Host CPU 34.641 s over 78.623 s.
- Hidden/Watch idle: 30.095 s, host CPU 14.172 s, zero new finite jobs. Existing Live
  alone is therefore not close to zero CPU on this installation; compare dispatcher
  overhead against this measured control, not an invented zero baseline.
- Host peak working set 267,587,584 B; sampled aggregate host/finite-child working
  set 539,766,784 B, at most one finite child. Sampled IO: 213,258,871 read bytes,
  2,316,962 write bytes, 3,000,268 other bytes. Counters include network/cache and
  may miss final child IO and between-sample peaks; not source-only disk traffic.
- No host failure, Live running; own serving/Live threads closed and zero parked
  children after cleanup. No model inference or OpenCode mutation.

The under-load warm/control comparison is running separately, without concurrent
Full/browser workloads. Source/cache evolution prevents treating sequential real
runs as a tightly controlled universal speedup benchmark.
