# FR 000615 — Completion

Implemented 2026-11-06 in v80.195. The original approved specification is preserved
intact in this bundle. Main remains the supported distribution; no ZIP, tag or
GitHub Release is produced.

## Delivered behavior

- Removed the shared finite-report Cancel markup, handler and stale styling/fixture
  assumptions, not just its visibility. Models' genuine Retry and independent price
  refresh remain available; empty healthy toolbars collapse.
- Existing bounded pre-admission intent and admitted acquisitions survive navigation,
  Back/Forward and hiding. Each view retains its own result/error; inactive routes
  never initiate new periodic history checks. Throttled return accepts a settled
  server outcome before checking the client deadline.
- AI Stats retains up to five requested scopes in one host-owned job. A narrow
  priority milestone cannot erase the original broad goal; missing scopes resume
  with pinned observation/scan identity. This narrowly supersedes FR000614's user
  cancellation/inactivity behavior, not internal lifecycle safety.
- Preserved authenticated internal cancellation, host/source-change/parent-loss
  shutdown, watchdogs, resource/result/queue limits and source read-only ownership.
  Tab-close/reload pending-memory persistence and work beyond host stop are unsupported.
- Repaired a recurring live-child `process.close()` failure found during Full.
  Valid terminal IPC alone permits up to one second of natural teardown; all forced
  paths retain prompt terminate/kill with one-second joins. Unconfirmed exit latches
  a sanitized host failure, retains exact handles/ownership, blocks reuse/replacement
  and permits bounded main-owner cleanup retries. HTTP cancellation propagates the
  fault; independent host resources still close. Rare Windows delay cause is unknown.

## Verification

- Local Full: **154 file targets, 1,824 tests; 1,823 passed, one macOS zsh/PTY skip,
  zero failures/errors**, 147.0 seconds. Includes deterministic stop/IPC tests, real
  host/HTTP failure propagation, actual spawned slices, watchdog/internal cancellation
  and force-stopped-parent coverage. Evidence: `scratch:/evidence/full-safe-stop.json`
  and `full-safe-stop.log`. Affected focused scope also passed 94 tests.
- Working-tree validator: **11 passes, zero failures**, six advisory size warnings
  (Web guide, README, version history, context, report service, Watch coordinator).
  No cap increases, structure baseline changes or weakened assertions.
- Hidden Chrome UI: **13 checks / 24 layouts**, all four routes, Classic/Web light/
  Web dark and 360/1366px, no DOM/AX Cancel in loading/wait/quiet/retained/error/
  complete states; visibility/navigation/Back and competing Comparisons association.
  Screenshots inspected. Independent AI Stats **14 / 9**, Comparisons **9 / 12**,
  Token Mix **4 / 9**, Models refresh **4 / 6** retain their scoped evidence.
  These UI/layout runs precede the safety-only repair; UI source did not change later.
- Final frozen-source production browser slices: **PASS**, two-tab identity,
  coherent 7-day milestone at 2/24 roots before 30-day readiness, original broad goal
  finishes after navigation, twelve finite children, exactly 24 hydrations/reuse.
  Verified no active child, host fault, serving/HTTP threads or runtime errors after
  teardown; fixture processes/browser exited code 0 with empty server errors.
  Evidence: `scratch:/evidence/ai-stats-safe-stop-final.json`.
- Real installation: independent Comparisons completed twice in **89.141s / 9.013s**,
  2,774 roots and 294 groups, no result error. Both DTOs retain **`complete:false`**:
  usable partial coverage, not full historical coverage.

## Failed evidence, decisions and limits

Real Normal acquisition **FAILED** typed `connection_timeout` after verified real
V2 shell/source/two SSE streams; subsequent real report/cancel stages were unperformed.
Cleanup retained zero owned processes/threads. Exact cause/baseline relationship is
unknown. Integrated browsing was disconnected; hidden fresh profiles used no personal
browser, visible desktop, shared input or clipboard. Physical speech/desktop and
non-Chromium proof remain unperformed. No inference, source writes or shared OpenCode
stop occurred.

**Decision Delegate** authorized accepting independent real heavy Comparisons plus
hidden/VM/spawn/direct internal cancellation evidence for this FR without requiring
successful Normal or the unreached real stages/physical proof. This is not a source
performance fix or blanket failure waiver. The same delegate authorized the bounded
confirmed-exit/host propagation repair; all required final gates passed afterward.

Earlier Full failures remain recorded: invalid synthetic Models DTO, missing test-only
launcher activity dependency, and recurring live-child close failure. A first final
browser attempt **FAILED** its generic 15-second broad-goal wait while progress reached
20/24 roots. **Decision Delegate** approved 45 seconds only for that deliberately slowed
twelve-child test wait, preserving all semantic assertions, other 15-second waits,
180-second outer bound and product watchdogs, plus stronger post-cleanup/runtime checks.
The single corrected run passed. Load/Windows timing contributions are not established.
Details and evidence routing: `development/journal/web/report-loading.md`.
