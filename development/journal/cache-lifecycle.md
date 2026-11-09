# Session-cache lifecycle — FR 000626

Date: 2026-11-08. Baseline: `d199963a868f83993e941c533724fa06b5de49aa`
(v80.208); candidate v80.209. This is scoped lifecycle evidence, not a new
benchmark framework, hard database-size target or universal performance guarantee.

## Ownership and conservative policy

`cache/session_scope.py` qualifies actual root/child execution evidence, excluding
session creation/update metadata. `cache/lifecycle.py` owns the opt-in indexed
companion table, atomic payload/metadata publication, coalesced touches and bounded
eviction. Existing entries are not backfilled by hydrating source history.

Recent activity OR meaningful use retains at least 30 rolling days. Hourly use
coalescing adds one hour of expiry grace, never shortens retention. Unknown clocks,
pending use and unmatched current source revisions defer deletion. Passive cache
writes preserve, but never renew, established use. The classified namespaces are
derived analysis, Token Mix, AI Stats evidence/coverage/transient facts, matches,
session summaries and session CCost. Pricing, metadata, first sightings, discovery
and operational JSON are not subject to this retention rule.

The existing Web host loop waits 60 continuous minutes, then attempts at most eight
entries daily with zero SQLite busy wait and a cooperative 20ms deadline. Foreground,
Live/provider/acquisition pressure, active/visible roots, leases, identity changes,
shutdown and new demand defer/cancel work. This deliberately modest initial rate
is not a bulk sweep or a promised reclamation rate. OS/commit/close latency is not
hard-bounded by SQLite's progress handler. There is no VACUUM/checkpoint, source
mutation, daemon or separate JSON retention index.

## Safe installation inventory

A read-only aggregate SQL profile of the ordinary installation (no payload or
prompt reads) measured 6,680,576 file bytes, 1,631 4-KiB pages and 82 free pages.
Derived analysis accounted for 58 rows / 6,218,217 payload bytes; one pricing row
used 13,914 bytes and two model-discovery rows 435 bytes. There was no lifecycle
table then. This is not the owner's historical ~288-MB observation or a measured
growth rate. The ordinary checkout/database was not changed by that profile.

## Deterministic verification

`py -3 development/tools/run_tests.py --suite full --json-report <owned-output>`
passed the final shutdown-fix tree: all 174 files in 120.7s, 2,126 tests passed,
one macOS zsh/PTY-only test skipped on Windows, zero failures/errors. The seven housekeeping tests include
execution of the actual shipped `api()` under Node/VM, not duplicated header
logic. Real SQLite cases cover both clocks, unknown/passive updates, coalescing,
bounded rows, writer contention, cancellation rollback/fair candidates, additive
migration, source/child revision isolation and derived-cache rehydration equality.
Loopback HTTP verifies protected explicit-header job/data delivery and passive
controls; CLI tests verify finite once-only touch handoff.

An earlier Full run timed out in two CLI tests because a new drain loop operated
on a MagicMock. The repair moved finite draining into the real lifecycle owner;
focused affected tests and the complete recovery Full run passed without weaker
assertions or larger test deadlines. Two jobs inherited from a previous session
have unrecoverable outcomes and remain UNKNOWN, not PASS. The foreground Decision
Delegate selected one durable Full/probe recovery run rather than invented results.

`validate_package.py --working-tree` passed 11 checks at v80.209, with seven
existing advisory prose/design-budget warnings; no hard cap or exception changed.

## Evidence method and honest limits

Integrated browsing returned disconnected. A subsequent exact external browser
discovery request was refused before access; it was not retried through another
route. The foreground Decision Delegate selected synthetic raw-V2/full-host API,
retained-SQLite and executable shipped-JavaScript evidence as the adequate backend
method. This was not an acceptance waiver or permission to discover another
browser. Browser navigation/render/paint and native desktop proof remain unrun.

The first real-source probe lost its connection while shipped files were being
edited; SourceGuard contamination is plausible but not established. A later
frozen-source recovery probe succeeded for Sessions (2,976 roots; 50 visible scalar
rows ready, zero unavailable; first page 0.062s, detail 0.543s), but failed at the
default 90s Watch observation cap: 2,573/2,976 checked, 334 Live publications,
normal cleanup, no captured phase error. Session CCost was NOT RUN because Watch
preceded it. No source/host fault conclusion or 90-second completion claim follows.
The delegate approved one supported 300s observation-cap run, not a product-timeout
change, inference, service stop or relaxation of the FR.

That frozen-source 300s-cap run completed successfully in 124.136s. Sessions
observed 2,976 roots, 50 ready visible rows and zero pending/unavailable rows;
first page took 0.050s, complete two-row detail 3.424s. Verified Earlier history
reached 2,976/2,976 roots in 123.649s (first rows 38.893s), with five history cards,
one active card, one row/card and zero pending captures. Publications advanced
242 times; the maximum sampled gap was 1.217s. Session CCost independently matched
116 priced requests, with zero fresh-repository valuations and cache writes off.
Across 393 HTTP requests, maximum latency was 0.937s. One Live owner, original
run/stream identity and normal cleanup were verified; zero owned threads/processes
remained, with no captured phase errors or model calls. Shared OpenCode was not
stopped. This is success within the supported longer observation window, not
completion within 90s or browser/native-paint proof.

## Controlled experiment corrections

The task-specific scratch harness reuses the existing raw historical V2 source,
input-isolation adapters and WAL-consistent `CacheSeed`; it is not a shipped
benchmark command or new verification gate. It uses 120 synthetic two-prompt roots,
half with actual activity shifted 45 days old, one persistent source identity,
fixed synthetic pricing/quota and identical seeds for baseline/candidate fresh hosts.
Only owned synthetic use clocks and host uptime/due are injected; native source,
Live, foreground/lease guards, SQLite deadline and normal host-loop ownership remain.

The first preparation captured before bounded demand touches drained and therefore
could not establish old-use eligibility. The corrected run awaited normal pending
drain and established 555 annotated rows / 247 old eligible entries. Its first
maintenance attempt returned zero before SQL (0.014ms); test `/api/status` traffic
could race the request-epoch guard. Specific cancellation was not yet established.
All rows remained, and Live continued. This is not successful maintenance evidence.

The delegate selected a fresh fixture-host replay whose non-HTTP test-protocol
thread waits for the native prune result before starting responsiveness samples.
No host loop, tracked request or lock is occupied by that waiter, and no consumed
daily retry is reset. Predicate evidence is buffered without changing eligibility.
Post-prune foreground timings describe subsequent responsiveness, not overlapping
request latency; the cancelled experiment separately exercises foreground protection.
Fresh-host All-time reentry must find the actual evicted namespace absent before
demand and rebuild it with equal canonical metrics, rather than reusing a retained
dispatcher result or claiming session-only reads rebuilt unrelated evidence.

That replay committed eight removals (six coverage certificates and two AI Stats
fact rows), retained the deliberately viewed old root and preserved All-time
canonical metric equality on fresh-host reentry. Its diagnostic then failed an
overly strong assertion that every removed SQL row must be rewritten. Actual
reentry missed and rehydrated the two fact roots, recreating their facts/coverage;
four coverage-only certificates remained absent because existing complete facts
already answered All time. Those optional exclusion certificates are not required
history and must not force gratuitous source hydration. The corrected diagnostic
requires actual missing facts to rebuild and equal source-backed results, while
reporting harmless coverage-only absences rather than rewriting production for
the test. No product assertion, deadline or retention guard was weakened.

## Successful retained-cache / idle-prune replay

The corrected five-host replay completed successfully (preparation, baseline,
candidate, maintenance, fresh-host reconstruction). Seed fingerprint:
`baba81e97e20c8bb40f7218d9b18f5ee1be86404dc9fedad591a5f2c0ccfe06c`;
task-specific harness SHA-256:
`2c6e29d2d38f5fc982b5d5f97ae7ce1515d1e5cf23a79550fbb85206b60c30b9`.
The same source process, registration, product-data path and verified seed were
retained; selected-version source-origin checks found no foreign product modules.

Backend/API response time, including admission/child work/polling, in seconds:

| Intentional view | Baseline retained SQLite | Candidate retained SQLite |
| --- | ---: | ---: |
| Models | 1.214 | 0.902 |
| Historical Token Mix | 1.104 | 0.872 |
| AI Stats All time | 1.485 | 1.100 |
| Comparisons | 1.002 | 0.766 |

Both arms reused 62/62 derived candidates in Normal, 120 Token Mix entries,
120 matched-run entries and 120 AI Stats entries per capture, without misses in
those warm captures. Whole-host lookup totals included 129 derived hits and 240
AI Stats hits in each arm. Each arm made 130 raw message/context reads across all
Live/report work; Normal and warm AI Stats themselves hydrated zero roots. This
demonstrates retained SQLite reuse across fresh hosts, not just dispatcher-memory
hits. One controlled pair is not a statistical speedup claim or browser-paint proof.

All 559 eligible-namespace rows were annotated; preparation drained normal bounded
touches before seed capture. Passive/headerless work left 247 entries old; viewing
one old root at the injected yesterday clock protected its five entries, leaving
242 candidates. Before uptime eligibility there were no prune attempts. A fresh
ordinary idle observation then allowed one native eight-row transaction in
**1.438ms**, with no refused predicate and no production clock/deadline override.
It removed six coverage rows and two AI Stats facts across six old roots; the
deliberately viewed root and recent cohort remained.

Payload capacity reclaimed: **3,484 bytes / eight rows**. SQLite stayed at 401
pages and zero whole freelist pages in this replay (space became reusable inside
pages); file bytes stayed **1,642,496**, while WAL grew **28,872 → 127,752 bytes**.
The preceding replay had one new freelist page; neither observation implies an
immediate physical shrink. No VACUUM/checkpoint/rebuild was used.

Live advanced 36 → 56 publications across the maintenance observation. The
publication interval spanning the actual batch was **0.263s**, with whole-window
maximum **0.314s** (before-batch maximum 0.313s). Twenty subsequent status requests
had maximum **1.5ms**; these are post-batch responsiveness, not concurrent-load
latency. Foreground cancellation is separately evidenced by the zero-deletion
attempt and deterministic request-epoch tests. No universal OS/IO bound follows.

Fresh-host reentry verified all eight removed rows absent before demand. All-time
AI Stats completed in **0.777s** with 118 compact hits, two misses, two source-root
hydrations/four analyzed prompts, recreated the two facts and their coverage, and
returned **identical canonical All-time metrics**. Four optional coverage-only
rows remained absent, correctly unnecessary for that demand. Direct inspection of
the protected old root and all six affected roots returned the expected two-prompt
source-backed histories in **0.487–0.592s**. A later controlled synthetic active
update reached a running Live card in **1.185s** in the reentry host, not during the
prune itself. No inference or real source mutation was involved.

## Shutdown touch handoff

Post-experiment inspection reproduced a separate normal-close gap: use queued
between the last flush and host shutdown remained pending. The new focused
regression failed before the repair, then passed with real SQLite after adding the
finite fail-soft drain to normal close after producers stop. The final Full run
above includes that regression: normal immediate close persists queued deliberate
use without waiting for another host tick. This adds no per-read write or new
scheduler. Crash/disk-outage persistence is not promised. The controlled experiment
and long real-source observation predate this close-only change; their runtime
measurements are not misattributed to the final shutdown delta.

The final-tree read-only `probe_web_live.py --session-cost` then passed independent
parity for 90/90 priced requests, zero fresh-repository valuations, cache writes
off and zero model calls. It preserved one Live owner, two streams, run origin and
stream identity, with 314 frame publications and 410 HTTP requests (maximum
0.7804s). Total observation took 113.3554s; normal host close took 0.0873s. No phase
errors, cleanup failures, pending work or owned threads/processes remained. The
shared OpenCode service was untouched. This focused final-tree check verifies real
owner/HTTP cleanup, not another complete Earlier-history or browser proof.

Sanitized/aggregate evidence remains in owned scratch: `scratch:/final-full-results.json`,
`scratch:/final-full-output.txt`, `scratch:/final-live-probe-output.txt`,
`scratch:/live-probe-300-output.txt` and `scratch:/cache-evidence-4/summary.json`.
Synthetic seed/raw fixture payloads are not part of the published source.
