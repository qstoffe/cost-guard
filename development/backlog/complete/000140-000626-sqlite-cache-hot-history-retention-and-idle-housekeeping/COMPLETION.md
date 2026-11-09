# FR 000626 completion — conservative session-cache lifecycle

Implemented in v80.209, 2026-11-08. The original FR is preserved unchanged.

## Delivered behavior

- Reconstructible session namespaces opt into additive indexed lifecycle metadata:
  explicit source-qualified root, current source revision, actual root/child activity
  and a separate meaningful-use clock. Either recent clock retains at least 30 days;
  missing/legacy or ambiguous evidence conservatively keeps entries.
- Selected-visible Web reports/history, Full/Mini Watch and successfully rendered
  CLI reports count as demand. Passive warming, cache writes and diagnostic API
  reads do not renew use. Touches coalesce in memory and flush in bounded batches,
  including finite normal-close/CLI handoff, not one SQLite write per read.
- The existing host loop waits at least 60 continuous minutes before attempting
  at most eight entries daily. Zero busy wait, cooperative SQLite deadline, current
  inactive revisions, pending use, Live/provider pressure, leases, real requests,
  source identity and shutdown guard deletion. Failed/cancelled attempts do not loop.
- No source sessions/messages, user files, pricing/discovery/first sightings or
  operational JSON are removed or migrated. No daemon, JSON lifecycle index,
  eager source backfill, VACUUM, aggressive checkpoint or database reset was added.

## Actual verification

- Final local Full: **174 files passed, 2,126 tests passed, one macOS zsh/PTY-only
  test skipped on Windows, zero failures/errors**, 120.7s. Includes real-SQLite
  two-clock/isolation/migration/rehydration cases, protected HTTP demand controls,
  execution of actual shipped `api()` under Node/VM and the normal-close regression
  reproduced before its fix. No weakened assertions or test deadline increases.
- Package validation: 11 checks passed, zero failures, seven existing advisory
  prose/design warnings; no hard cap, legacy exception or structure baseline raised.
- Controlled matched retained-SQLite baseline/candidate hosts used 120 synthetic
  roots (60 recent, 60 genuinely 45-days-old), identical verified seeds and one
  persistent raw-source identity. Warm report captures retained all expected hits
  with no misses; Models/Token Mix/All-time/Comparisons measured respectively
  1.214/1.104/1.485/1.002s baseline and 0.902/0.872/1.100/0.766s candidate. This is
  one controlled backend/API pair, not statistical speedup or browser-paint proof.
- Actual idle maintenance removed **eight rows / 3,484 payload bytes in 1.438ms**;
  recent and deliberately viewed old roots stayed. SQLite file stayed 1,642,496
  bytes, 401 pages/zero whole free pages; WAL grew 28,872 to 127,752 bytes. Space
  inside pages became reusable; immediate physical shrink is not claimed.
- Live advanced through that batch with a 0.263s spanning publication interval,
  whole-window maximum 0.314s versus preceding 0.313s. Twenty **post-batch** HTTP
  status samples peaked at 1.5ms, not an overlapping foreground-latency claim.
- Fresh-host demand found all removed rows absent, missed/rebuilt two actual
  AI Stats facts from source and returned identical canonical All-time metrics
  in 0.777s. Four optional coverage-only certificates correctly remained unneeded;
  protected/affected source histories remained complete. No source deletion.
- Real-installation Sessions/CCost/Watch probe completed within its supported 300s
  observation cap: 2,976/2,976 roots, 50 ready visible summaries, complete detail,
  five verified history cards plus one active card, and independent CCost parity
  for 116 priced requests. One Live owner, zero model calls, no cleanup failures or
  remaining owned threads/processes; shared OpenCode remained running.
- Focused **final-tree** real-installation CCost probe also passed: independent
  parity for 90 priced requests, zero model calls/cache writes, 314 publications,
  one Live owner/two streams, 410 HTTP requests and clean shutdown (0.0873s host
  close, no phase errors, cleanup failures or remaining owned workers).

## Scoped decisions and limits

Integrated browser was disconnected; refused external browser discovery was not
retried. The foreground Decision Delegate selected full-host API/retained-SQLite
and executable shipped-JavaScript evidence as adequate backend verification, not
an acceptance waiver or browser navigation/render/native desktop PASS.

Two predecessor background outcomes remain UNKNOWN; delegate-approved durable
recovery runs supply independent results. The recovery 90s real Watch observation
failed at 2,573/2,976 roots before CCost ran; the delegate-approved 300s observation
then completed in 124.136s. Neither rewrites the earlier failure nor changes a
product deadline. The controlled replay corrected test-owned seed capture,
foreground-sampling cancellation and an overly strong optional-certificate
assertion; production eligibility/cancellation guards were not relaxed.

Runtime measurements above predate the final normal-close-only touch-drain repair;
the final Full includes that repair. OS/commit/close latency and crash/disk-outage
touch durability are not guaranteed. No model inference, service stop, tag, packaged
Release or local release ZIP was performed. Main remains the supported distribution.

See [design, evidence and failed attempts](../../../journal/cache-lifecycle.md).
This PR proposes ordinary progress 79; only its actual merge to main advances the
durable count. The earlier session-learning assessment remains INCONCLUSIVE.
