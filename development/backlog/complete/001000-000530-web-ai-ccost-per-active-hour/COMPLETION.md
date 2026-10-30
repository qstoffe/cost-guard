# FR 000530 — Web-only reference cost per active hour

Implemented in v80.115 (2026-10-30). Specification moved intact from legacy
`todo`; the bundle contained no attachments. Web remains optional Beta.

## Delivered scope

- Explicit Web-only Cost per Active Hour: Today, configured-local month to date
  and exactly rolling 30 × 24 hours, with scope/observation/status, CCost, active
  execution duration and Python Decimal rate. Existing Credits/USD semantics and
  text-only toggle apply; no JavaScript valuation/rate arithmetic.
- Canonical prompt/child/tool/background/compaction timing, clipped before union
  within/across roots; distinct concurrent requests still each contribute CCost.
  Canonical request/step/clone deduplication and event-time allocation are reused;
  no proportional token billing across boundaries.
- Unknown/zero duration, partial telemetry/pricing/source history never become an
  exact rate. Real priced zero can be zero with positive known duration. Running
  observations remain provisional; outages retain evidence, not completion.
- Complete-session Snapshot/Live rate uses whole-history totals, not the visible
  50-row page. Freeze/Follow and same-revision unavailable health are explicit.
- Period history is acquired only by explicit finite capture, with progress,
  cancel, existing deadline/result bounds and dependency-aware derived cache.
  No new CLI command/option/section, account/Watch polling, model request, browser
  persistence, OpenCode write or durable history ledger.

## Verification

- Focused **14/14 tests passed**: exact formula, zero/unknown/partial inputs,
  session and multi-root concurrency, root/child/compaction/tool/background/abort,
  request deduplication, month/midnight/DST/rolling edge, stale active metadata,
  cache/no-quota capture, whole-history paging, Live advancement/source loss,
  unchanged CLI rendering and shipped route/DOM/unit tokens.
- Final full suite: **117/118 files passed**, 1,438 tests reported, four Windows
  PowerShell failure subcases, zero errors and two symlink-privilege skips.
  All applicable feature/Web/session/CLI/Watch/account suites passed.
- Final isolated headless Edge: **four PASS cases**, 20 assertions each, at
  1200px and 360px, light/dark. Actual shipped app/assets and synthetic HTTP
  capture/cancel/detail; scripted EventSource. Checks cover explicit-only capture,
  units, route/frozen retention, failed refresh/cancel, view isolation,
  Snapshot/Live/Freeze/Follow, stale health, responsive layout and semantic focus.
- Package validator: **11 passes, zero failures**, four existing design-budget
  warnings. Initial version-history cap failure was repaired by shortening an
  older note, never increasing the cap. Initial full-suite foundation failure
  used the pre-repair copy; the final foundation suite passed.

## Decisions and uncertainty

**Decision Delegate**, not the user, authorized only bounded installed-browser
discovery and isolated-profile synthetic loopback testing because integrated
browser tools were unavailable. Specific repair batches were separately renewed.
Earlier evidence remains unsuccessful: one 40-second TIMEOUT with no assertion
result; four cases failed after 13 assertions due to fixture route-readiness;
four failed after 16 because two precomputed clocks reused one immutable one-shot
service. Corrected fixture construction and deterministic actual SessionHistory
checks preceded the final serial stop-on-failure batch. No product cache semantics
or browser assertions were weakened. Owned profiles/browser/server were cleaned.

Decision Delegate approved a **narrow verification exception** for four unchanged
Windows PowerShell 5.1 subcases in `test_launcher_feedback.py`: host policy rejects
`probe.ps1` with SecurityError/UnauthorizedAccess (exit 1, not 9009/17).
Corresponding pwsh.exe coverage passed. Intended 5.1 behavior remains unverified;
neither the tests nor host policy were changed/bypassed. **The full suite is not
labeled PASS.** This exception covers no feature failure or Git protection.

Physical keyboard/mouse/touch, assistive technology, real-history browser/SSE and
native macOS acceptance remain unverified. Programmatic focus/DOM geometry proves
only the asserted synthetic behavior. Deleted/pruned source history is unavailable.

## Knowledge

Updated analysis-owner contracts and the Web journal with finite-capture,
whole-session, stale-health and reproducible fixture lessons. No module-boundary
or permanent-gate change requires a system-diagram update. Evidence is outside
this task bundle: `development/architecture/governance/verification/web-active-hour.md`
and `web-active-hour-2026-10-30.json`. No automatic install, reload or runtime restart.
