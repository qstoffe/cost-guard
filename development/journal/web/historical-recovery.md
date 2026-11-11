# Historical report recovery — FR000678

## Reproduced cause (2026-11-11)

Read-only local V2 acquisition enumerated 3,120 roots and completed source reads,
then both Token Mix and AI Stats returned `internal_error` rather than a report.
Sanitized exception frames identified `ValueError` in
`token_mix_cache.py::decode`, reached from freshly generated Token Mix facts and
`StatsAcquisition._batch` → `ai_stats_evidence.decoded`. No private source rows,
prompts, titles, session IDs or credentials are retained here.

Identity admission requires semantic version 3 for both moving family aliases
and opaque Claude Agent catalog candidates. The encoder marked only the former.
An unresolved opaque candidate therefore failed its own encode/decode roundtrip,
even with a brand-new disposable cache. This is a demonstrated software defect,
not evidence of source disconnection or lost history. The owner's approximate
43% UI observation was a useful lead, not proof of a specific cache exception;
the isolated cold reproduction reached history analysis before rejection.

The fix uses the same identity admission predicate for marker emission. It does
not loosen decoding, invent a release/price, change recorded history, bump the
global cache generation or discard unaffected entries. Previous affected facts
rebuild lazily; exact resolved releases and unrelated warm roots remain reusable.

## Independent lifecycle defects and changes

- AI Stats manufactured ten zero cards after failed/interrupted acquisition.
  Only valid source-backed empty/best-effort results now render zero-style cards;
  failure without a matching result stays report status.
- A managed lookup with no result/job during host backoff ended the browser
  attempt. No-result failed pages then had no automatic lookup timer. The two
  historical routes now keep using the existing host lookup/poll lifetime, never
  set explicit `retry:true`, and recheck relevant recovery even from a cold error.
  AI Stats no longer gives up after three transient readiness failures.
- Untyped child interruption/start failures were treated as terminal. They now
  use existing capped host backoff. Typed access/resource/protocol blockers remain
  diagnosable; demonstrated source-readiness recovery rechecks access blockers.
- Cache connection faults have small typed cause codes, and Token Mix checkpoint
  contention distinguishes SQLite BUSY/LOCKED from other unavailable persistence.
  Contention uses short backoff; unavailable persistence uses slower capped checks.
- Missing refresh publications do not erase accepted matching historical data.
  AI Stats incomplete refresh slices cannot overwrite a prior same-period result.
  Both report routes hide Retry/Refresh and redundant toolbar space in all states.
  Models, Comparisons and independent Sessions-detail controls retain their scope.
- The real loaded-UI fault/recovery probe exposed timer starvation: every healthy
  Live status reset the five-second publication lookup. Frequent events prevented
  recovery indefinitely despite healthy completed host jobs. A deterministic
  frequent-status regression failed before repair. The existing single timer now
  keeps its deadline for the same eligible view, and clears ownership on firing,
  navigation, hidden state or unavailable host; no second scheduler was added.
  The first broad deadline-preservation change also prevented nonmanaged probes
  from rescheduling their deliberately aged observations. Both synthetic browser
  probes and the real-HTTP view test exposed it. Preservation is now scoped to
  managed host lookups; nonmanaged absolute-cadence calculation is unchanged.
- A separate synthetic exact-catalog turnover between fresh Stats encoding and
  admission reproduced nonretryable `internal_error`. Only that typed catalog
  change now becomes retryable `ai_stats_revision_churn`; malformed evidence is
  not blindly retried. The focused regression verifies recovery with the new
  catalog and genuinely positive cost.

## Verification

Deterministic coverage includes opaque resolved/unresolved selections, cold and
warm facts, previous semantic markers, one-entry corruption/repair, 3,217 roots /
6,434 requests, real SQLite writer contention/release, continuation/parking,
source readiness/access recovery, typed terminal errors, host backoff without
explicit Retry, cold browser failure and retained provenance.

Initial real AI Stats probe: five scopes returned after 13 slices in 152.269s;
warm refresh completed in one slice in 6.565s (3,098 compact hits, 22 changing roots).
All five rate formulas/display contracts passed. Partial/unpriced/running evidence
remains qualified, not a claim of complete or billed cost.

The first fixed Token Mix cold probe exceeded its old 130s observation budget
while still advancing (2,881 hydrated roots at 120.680s), not a product timeout.
The probe now has an explicit 1–1,800s bound (600s default), matching the existing
AI Stats observation approach. Product work/resource limits are unchanged.

Reconciled Token Mix cold/warm read-only V2 probe: 3,121 roots, 74,099 analyzed
requests, valid nonzero totals, 14 model rows and three publisher rows. Cold
completed in 124.086s; warm in 6.112s, reusing 3,099 compact roots while rechecking
22 changing roots. Counts/timings are observations, not fixed performance gates
or an independent complete-history oracle.

Inherited Full evidence completed all 184 groups with 2,285 passed tests, no
failures/errors and two explicit macOS/zsh-only skips. Final-source focused run
passed 62 tests plus real app/Attempt lifetime and actual AI Stats period-retention
VM checks. The working-tree validator passed 11 checks with no failures and seven
existing advisory size warnings; no caps or debt baselines were raised.

The inherited hidden Chromium probes passed Token Mix and AI Stats over canonical
synthetic history at 360/800/1280/1920px and three themes. Coverage includes both
units, sorting/pan/scroll/focus, real keyboard/emulated touch/help, AX names,
ten-card layout/contrast, legitimate empty evidence versus cold error, and finite
Stats slices/two-tab reuse with clean owned-process shutdown. Those passes predate
the final timer repair; final-source loaded-UI and Full evidence is recorded below.

Final-source real-host hidden Chromium proof passed: all five AI Stats scopes
had positive source-backed total cost, and Token Mix had valid nonzero tokens /
14 model rows / three publisher rows. Both routes passed all four widths, three
themes, both units, warm navigation/provenance, hidden toolbar/actions, retained
last-good DOM through injected transport failure, and automatic recovery with no
click/reload/shared-service restart. Cold injected failure on both routes showed
report status, no cards/tables and no toolbar, then recovered automatically. Browser/server exited zero,
with no runtime/server errors. These controlled faults are synthetic browser
transport faults, not an observed source outage. Artifact:
`scratch:/history-live-browser-delivery.json`; real report phase times were 29.199s
(Stats) and 17.836s (Token Mix), including navigation/fault recovery. The latter
retained honest `partial` qualification while history was changing; it was not
promoted to complete coverage.

Final stable-source Full passed all 184 groups in 142.2s: 2,287 passed tests,
zero failures/errors and two explicit macOS/zsh-only skips (2,289 total).
`scratch:/full-tests-delivery.json` retains the per-group outcomes. The prior
Full run's real-HTTP view failure at its artificially aged observation was repaired
by the scoped timer change above; that group and the final entire Full run passed.

Both post-timer synthetic browser reruns passed (`scratch:/ai-stats-browser-stable.json`
and `scratch:/token-mix-browser-stable.json`), with 12 layout cases each. Stats
reported 17 successful check groups, no runtime errors, both server/browser
exit codes zero, and no active finite child/host/HTTP workers after close. These
reruns precede only the cold Token Mix heading/toolbar removal, independently
covered by the final lifetime regression, final Full and real loaded-UI probe.
The latest working-tree validator again passed 11 checks, zero failures and the
same seven advisory warnings; whitespace validation passed.

No inference, source writes/deletion, shared-service restart, visible desktop
interaction, physical-device acceptance or screen-reader speech is claimed.
