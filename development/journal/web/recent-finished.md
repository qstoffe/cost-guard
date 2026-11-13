# Post-start finished prompts during cold Earlier loading — FR000697

2026-11-13, v81.41. Scope: the independent post-start completion gap, not a rerun
of the FR000624 whole-history performance epic or a reproduction of the owner's
private incident.

## Cause and implementation

The RED canonical-source fixtures confirmed that a 300ms prompt first read already
finished had neither a Running/terminal-grace card nor a usable Earlier card while
the cold global proof remained pending. An old root with a new finish had the same
gap. The initial failures were missing recent membership, not private reproduction.

`watch/recent_finished.py` retains at most five source-qualified cards: exact root
user-event identity, complete nonretained snapshot, matching provenance/revision and
accepted generation, supported terminal outcome and real finish between engine start
and acceptance. A prompt started before the engine may qualify by its actual later
finish. Metadata, hints, late reads, unknown/future ends and Running sightings are
not certificates. Partial/revised reads retain only prior qualified evidence;
authoritative invalidation, archive/removal and source identity changes retire it.
Active/grace and pending-active roots cannot simultaneously be Earlier fillers.

Changed/new roots after the initial catalog baseline reuse foreground card permits.
The existing four-root capacity, historical ceiling and recurring historical turn
remain; retries cannot hot-loop completion wakes. Visible captures/cost enrichment
include the bounded recent set beyond terminal grace. No new scanner or worker lane,
native writes, provider inference, price reload or private export is introduced.

Global `HistoryPublication` still requires complete revision-keyed coverage and
issues its own epoch. `recent_finished_cards` cannot advance that proof. Full and
Mini merge only server-qualified populations, retaining canonical certified order
when there is no overlay. Recent loading context is explicit; final proof hides the
overlay atomically under the same keyed card/row identities. Live events now promote
an authoritative read with a one-second minimum inter-read coalescing interval,
instead of adding five seconds to idle detection. Source-error backoff is unchanged;
V1-style polling retains its supported cadence.

## Verification and measurements

- Full: 191 groups, zero failures, 160.9s. Final focused recent/Live run: 27 tests,
  zero failures, after the final pending-active exclusion.
- Validator: zero failures, seven existing advisory size/design warnings.
- Source-shaped tests cover 5,000 cold roots, V2 loopback saved completion without
  Running, old-root reuse/admission priority, canonical finish ranking/cap,
  pre-start Running→finish/grace expiry, partial/missing/future/unverified evidence,
  metadata-only touch, stale generation/wrong-root rejection, source switch,
  removal/archive and atomic global convergence.
- First Full found two causal issues: unconditional browser sorting changed an
  unchanged certified fixture's order; probe-only host-reason metadata assumed a
  complete host. The owners were corrected; all 34 tests in the failing groups
  passed, followed by the successful Full above.
- Hidden Edge 157 shipped HTTP/CSP/SSE, Full Watch and native Document PiP:
  20 canonical 300ms completions while 5,000 old roots were pending; five-slot cap,
  repeated-session advance, early/late reopen, route away/back, blur, headless
  opener minimize/restore, offline/resync, Web-dark/USD and 125% browser zoom;
  final keyed convergence retained focus and did not passively resize PiP.
  A probe initially used invalid theme `dark` rather than theme `web` plus emulated
  dark media; another compared bounds across deliberate Fit reopen. Both harness
  assumptions were corrected, not product permission/geometry rules.

Controlled stage wall times (ms p50 / p95), 20 samples at 125% zoom:

| Stage | p50 | p95 |
| --- | ---: | ---: |
| Source fixture preparation | 0.11 | 0.15 |
| Catalog detection | 15.34 | 18.14 |
| Worker admission turn | 10.22 | 68.97 |
| Capture/accept turn | 9.82 | 12.88 |
| Live projection | 3.07 | 4.19 |
| Source-fixture command → publication acknowledgement | 70.88 | 133.05 |
| Acknowledgement → both DOMs painted | 15.10 | 40.55 |
| Command → both DOMs painted | 81.44 | 162.00 |

The 100%-zoom predecessor measured 64.84 / 121.11ms command→both-painted.
Synthetic prompt start/finish clocks (300ms duration) are separate from these
wall-clock stages; stdio acknowledgement is not an exact SSE-delivery timestamp.
These results do not claim subsecond real source detection. Event acquisition is
coalesced and normal Live publication is independently paced; polling-only source
visibility can still dominate.

Offline 5,000→5,100-root stress: 100 new completions, one held ancient root,
700 old reads progressed before releasing it, exactly 5,100 source reads overall,
four logical workers, peak five retained captures, 5,843,243 incremental traced bytes.
With tracemalloc enabled: 54.68s elapsed / 54.31s CPU through full convergence;
per-completion detection/admission/capture/projection p50/p95:
27.96/45.06, 33.54/53.61, 35.06/55.00, 5.07/8.98ms. These are offline source calls,
not authenticated HTTP counts or production memory/CPU promises.

## Real installation and limitations

Read-only `probe_web_live.py --recent-finished`: authenticated V2 host, one Live
owner, preserved run origin, advancing publications, two verified SSE stream IDs,
three account cards, bounded four card jobs; 24 observed publications during the
recent-specific window. History was loading (33/3,196 checked). **No qualifying
recent card observed**: this does not prove no eligible source completion
occurred and is not an end-to-end feature PASS. The private quick-prompt incident
was **not reproduced**. Owned threads/processes were zero after cleanup; shared
OpenCode was untouched. No paid prompt was generated.

An earlier broad `--watch-cards --watch-seconds 90` run stayed healthy but reached
only 286/3,195 global proofs: **INCONCLUSIVE**, not a verified global winner oracle.
It made 335 host HTTP requests without HTTP errors, published daily data and kept
four card jobs bounded. Another earlier run was interrupted during concurrent
source editing; its connection reset is not counted as PASS or proof of a runtime
defect. Headless native PiP/minimization is not physical desktop, work-area,
OS suspension or private-source end-to-end latency proof.

Decision Delegate authorized completion without the additional independent
1,800-second real-global oracle, conditional on Full/validator, expanded hidden
Full/PiP, focused read-only observation and required CI/merge checks. Reason:
FR000697 expressly permits private-incident uncertainty and does not repeat
FR000624; waiting for every real root would not necessarily exercise a fast
never-seen-Running finish. This is a minor verification limitation, not a waiver
of recent correctness or global certification. The long oracle is **NOT RUN**;
current-installation full-history convergence remains unverified. No Suggestion
or hold was required. Any actually observed eligible-but-missing finish still
requires exact root/revision investigation, not this exception.
