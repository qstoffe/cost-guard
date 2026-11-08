# FR 000624 — foreground loading and verified Earlier recovery

Source revision: bdc0494df6acfda2e09060bd42319195c003d416
Checked revision: bdc0494df6acfda2e09060bd42319195c003d416
Last checked: 2026-11-08
Status: current

## Summary

**Implementation verified locally; delivery pending.** [Performance evidence](foreground-performance.md)
separates measured content from Git revisions. The original ledger is backed up
byte-exactly in owned evidence; these notes retain material findings.

## Evidence

### Availability mechanisms and current owners

- **Actor evidence:** deterministic RED showed stable interrupted-tree revision
  mismatch because only the coordinator had a matching actor event. Transfer≤1,024
  detached same-epoch observations, invalidate revision memo, reject late old events;
  persisted idle identity/time remains necessary. No mutable resources are shared.
  Owners: `src/sources/opencode_v2_interruptions.py`, `src/watch/card_workers.py`,
  `development/tests/test_watch_history_acquisition.py`.
- **Initial transient failure:** `src/watch/source_status.py` opts initial Earlier
  into existing five-second confirmation; repeated faults do not restart it and
  terminal/auth remains immediate. Other defaults stay. A2,700-root churn/delayed-
  winner/timeout fixture recovers exact five. Proven mechanisms are not the private
  incident's established cause: initial real90s reached6/2,797/no winners, exact
  terminal notice not reproduced, INCONCLUSIVE.
- **Lifecycle:** removed computation-only120s, retry/admission exhaustion, age and
  Stats/history-stall terminal fallbacks; backoff saturates. Real I/O/cleanup/cancel
  bounds remain. Spawned HTTP/browser tests preserve true observations/intervals
  after61minutes/two days, not fictitious freshness. Owners: `src/web/dispatch.py`,
  `jobs.py`, `history_jobs.py`, `stats_jobs.py`, `src/application/service.py`,
  `src/web/assets/report-loading.js`, `cached-reports.js`, `app.js`.
- **Bounded terminal hints:** the old Attempt Set grew with retired job IDs during
  unlimited recovery. Actual-app RED/GREEN covers1,000 recoverable jobs through one
  acquire lifetime. One scalar last-woken ID preserves pre-poll hints, replay/foreign
  isolation, cancellation and recovery delays. A hint only expedites the authenticated
  current-job poll; it cannot publish a result or shorten failure backoff.
- **Stats contention:** actual SQLite RED on B0/candidate proved native256-root
  slice/50ms write BUSY→`StatsCheckpointError`→nonretryable job→terminal UI.
  Old384/512 counters do not establish the natural cold failure's cause.
  `src/reports/ai_stats.py` types only integer SQLite BUSY/LOCKED primary codes as
  `ai_stats_checkpoint_busy`; READONLY/OSError/unknown stay unavailable. Application/
  dispatcher/browser back off and recover without more timeout/workers/capacity.
  Actual repaired browser GREEN reached automatic success~4.551s after lock release,
  then all8routes/oracles/quota/closure. Stats-first diagnostic detour is not benchmark
  or failure-rate proof. `test_ai_stats_resume.py` covers real writer recovery/genuine
  faults; `web_report_lifetime.cjs` alternates1,000busy/churn recoveries.

### Source, report and scheduling improvements

1. **Compact guidance:** `src/reports/context_sample.py` preserves independent
   comparison/token populations, ≤100compact candidates each, releasing sampler-owned
   analyses. `context_guidance.py` owns scope/repricing; Watch's `card_guidance.py`
   owns one completed observation/at most one producer on existing permits. Epoch,
   config/prices/sample,900,000msTTL, rollback and late generations qualify reuse.
   Verified rows/context publish before guidance without changing IDs/read counts/
   proof epoch/time. Six-root and shipped Full/Mini tests cover this, not OS geometry.
2. **Bounded Models acquisition:** `src/reports/acquisition.py` stages two canonical
   snapshots by default; `src/analysis/cache.py` qualifies positive/negative bulk
   observations against revision/provenance/dependencies. Negative reuse requires an
   authoritative complete staged snapshot; no-snapshot misses recheck concurrent
   cache insertion. Operational errors are not misses. Unused tails are released.
   NORMAL/ALL_MODELS parity and sparse-stale equal-miss tests preserve eligibility.
3. **Exclusive readers:** `src/watch/card_readers.py` bounds source/transport/before-
   catalog reuse; per-job service/cache/pricing/SQLite stay thread-owned. Epoch,
   actor/expiry/cancel/teardown invalidate reuse. Every group has an after-bracket.
   Four logical roots total/three historical including guidance preserve active
   reservation; batching does not multiply capacity.
4. **V2 paging/scoped trees:** actual API cursor-only pages defaulted to50; repeating
   `limit=500` cut51pages→7 with identical2,937members. Opaque cursor/order/traversal
   guards remain. Web-card-only `src/sources/opencode_v2_tree.py` uses documented
   rootGET/recursive parentID pages, leaves included, before/after hydration. No
   complete-global cache mutation or proof shortcut. Tests cover67-node topology,
   moves/active/capability/epoch/errors/cancel; malformed/auth/I/O is not fallback.
5. **Completion-aware work:** completion refills existing permits. Token Mix uses
   qualified≤8-root cache-observation windows, preserving per-root canonical validation.
   Validated terminal IPC publishes before natural exit; exact retirees still count
   against resident bounds/escalate through grace/terminate/kill, later cleanup fault
   remains fatal. Unadmitted speculative startup can yield to foreground, without
   same-child continuation, more workers or cleared cooldown/backoff.
6. **Presentation:** `src/application/display.py` reuses clocks within one projection,
   preserving CCost units/token precedence/DST/resets, no cross-publication cache.
   Account-history day/month extraction preserves valuation/cleanup; no demonstrated CPU gain.

Full and Mini own expiring authenticated history demand independently; a visible
Mini remains important with its opener hidden. Collapse/close withdraw demand, no
second scanner or Live source is created. Finite priorities remain visible0,
hidden-requested1, speculative2, not-ready3 with original quanta/duty pacing. Actual
unfinished AI Stats promotion preserves the same observation/job/checkpoints and
accelerates qualified completion; history already runs at its safe maximum, so its
separate no-material-acceleration exception is explicit in the performance note.

Sessions membership is not scalar completeness. An actual550-root page2 diagnostic
left47pending, returned after5s during an inherited quiet delay and automatically
painted all50 summaries5.384s after reentry, without Retry. The deterministic900s
quiet case finishes exactly50roots in13normal slices; no third-page hydration.
Inactive incomplete15s/current900s cadence stays; visible work bypasses due delay.

### Independent real correctness and native-loop observation

`history_reference.py` independently traverses complete global membership/revisions
and canonical lifecycle, not product ranking/cache/pricing; private identities stay
in memory. `probe_web_live.py --oracle-serial-first` freezes the first verified
certificate with no competing reference refresh, then validates that exact proof.
Regressions reject unverified/later-proof substitution; source churn stays inconclusive.

Current299dd9 RUN6 (`scratch:/real-history-oracle-6/result.json`): **2,961/2,961**,
missing0,2,965hydrations; preparation224.655s, first certificate**125.831s**, exact
independent validation0.676s/matched126.527s, post-browser128.169s. Epoch, membership,
every revision and Full5/Mini3 identity/prompt/finish/order passed, as did hidden-opener/
visible-headless-PiP demand and closure.350Livepublications during timed acquisition,
maxgap1.254s; elapsed353.012s. Decision Delegate accepted this real-loading gate.
Retained caches/preparation may warm storage: **not cold proof, real p95 or B0/B1 ratio**.

RUN5 at30ea06fa matched2,928roots but concurrent reference contaminated412.349s
certification/preparation449.051s. RUN6 supports contention contribution, not isolated
causation across changed builds/workloads. RUN1 handoff and RUN3/4 churn remain
INCONCLUSIVE; RUN2 passed2,852roots. No selective rerun upgrades those results.

Native `WatchCoordinator.run_forever`/120-column `WatchRenderer` memory-sink evidence:
`scratch:/native-watch-responsiveness/summary.json`. Production cadence/hints/deferred
history retained; native accounts/logging disabled as Diagnostics. First frame2.118s;
30s lead/recovery bracketed189.173s real Web loading;418native render/status completions.
Gap p95/max1.205/4.560s; poll max4.557s/completion-gap max12.101s; recovery gap max1.017s.
No runtime faults/source recoveries; owners closed. Decision Delegate accepted the
qualitative gate/temporary delay: **not no-impact, native B0/B1, terminal/keyboard/OS
proof or isolated causation**. No extra sampling required.

### Harness reliability and reproducible evidence

`benchmark_web_runtime.py` runs historical default hosts/children/shipped assets
against owned raw inputs, isolated caches/registration/profiles, `pythonw` descendants
and foreign-import checks. Independent fixture winners and fixed-quota/day controls
are documented in the linked cold evidence; expiry invalidates inputs, not computation.
`benchmark_retained_web_runtime.py` restores native WAL-consistent same-path seeds
without rewriting registration.

Fixture joins owned handlers/connections; active transfer differs from2s idle
keepalive. Immutable exact-sequence hard-link request/ack prevents live replacement;
2,000handshakes passed. Collisions/errors stay terminal. Qualified warm paint requires
exact scope/settled nonempty output/no new acquisition; untouched forbids prior visits.

Accounts r16-B0 remains FAIL/no end validation: arbitrary text_length>100 rejected
an actual100-character populated card. New capture asserts visible heading/quota
and provider/account identity regardless of Map key shape, without cost waiting.
Regression/diagnostic details and changed-method segments remain in the cold note;
no fresh diagnostic established the historical cause or upgrades that failure.

Verification: `py -3 development/tools/run_tests.py --suite full` and
`py -3 development/tools/validate_package.py --working-tree`.

Current Full:168files/0failures/122.4s, including13reference/oracle tests.
All fixed plans remain267completed/twofailed/oneinterrupted, without replacements;
see [cold/warm evidence](foreground-cold-warm.md). No performance producer overlapped suites.

## Next investigations

Hosted Linux/Windows/macOS CI and protected Git/Complete delivery remain pending.
Physical tray/default-browser/window-placement/Finder/Gatekeeper/accessibility checks
were not performed under Decision Delegate exception (unchanged native owners), not PASS.

## Rejected hypotheses

- Root updated/activity metadata and aggregate session stats are not authoritative
  latest-prompt-finish upper bounds/global certificates; keep exhaustive proof.
- Batching alone (~1.15×real gain)/migration-skip did not solve nested guidance;
  compaction reduced retention, not proved speed. Shared guidance improved twelve-
  root subset117.774→15.741s, never global proof. Giant roots remain a memory risk.
- Adaptive two↔three history permits worsened uninterrupted Models8.052→8.522s and
  history8.023→10.985s; removed. History-pending finite pacing cost~2.7–2.9s Models/
  ~1s Token Mix for only.10–.36s history gain; removed. Do not delay foreground to
  disguise prewarming differences or slow hidden history to manufacture promotion.
- Reject Python3.14cProfile's impossible foreign-thread CPU; use owner-thread
  `profile.Profile`/thread_time. Overlap is not additive CPU. Pre-clock reconstruction
  is unresolved; operation-count RED/GREEN, not evolving-real/n1 timing, proves reuse.
- Earlier retained blocks FAILED after49/33successes, excluded from immutable180.
  Six diagnostics did not reproduce the Accounts assertion, not disprove it. Fixture
  shutdown/sharing defects do not retroactively explain every historical failure.
