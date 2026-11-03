# Completion — FR 000550

Implemented on 2026-11-03 as v80.132. The original specification was moved intact.

## Result

- Finer completed-work observations for early-stopping sampling, model rows/catalog,
  account cache checks/batch analysis and application packaging.
- Separate estimated progress ownership follows actual Normal consumption order,
  keeping later account history/preparation available after model availability.
- Unknown totals remain estimates; blocked I/O can pause. No extra source/provider
  requests, scan, timer-based advance or serialization of background work.
- Latest-only 100ms child progress coalescing retains the 64-message host drain;
  per-job sequences protect progress labels/values across polling and events.
- Fresh loads reset progress; frozen navigation reuses its result. Only receipt of
  a full acquired result paints 100%; partial/error/cancellation stay truthful.

## Verification

- Full local suite: **127 files, 1,549 passed, zero failures/errors, one skip**.
  The normal macOS shell test skipped because zsh/PTY is unavailable on Windows.
- Working-tree validator: **11 passes, zero failures**, four design-budget warnings
  (README, analysis/context, reports/service and Watch coordinator); hard caps unchanged.
- Focused actual-workflow, metadata/privacy, cache/no-extra-hydration, batch/fallback,
  stale/reset and producer/host burst regressions pass.
- Headless Chromium 156: **nine cases pass** through real Normal process/HTTP/events,
  accessible monotonic progress, stable work-stage layout, success transition and
  frozen navigation; synthetic partial/failure/timeout/cancel/auth/offline/reconnect.
- Same 28-root fixture: before observations mapped to **10,20,30,55,90**, with all
  account history stuck at **90**; after browser observations show sampling **32–40**
  and account history **73–87** before successful **100**. Fast stages need not show
  every value. No result delay or clock-driven animation is added.
- Read-only real V2 probe: Normal **118.479s**, full Models **4.437s**, one Live
  owner/two streams retained, owned shutdown passed, shared OpenCode untouched.
  Normal availability was **unverified**; no full live-source/availability PASS or
  overall performance improvement is claimed.

## Documentation and limits

Updated Web user guidance, report/Web architecture, code/test routes, journal,
version/date/history/README and ordinary progress state in this delivery.
Detailed observations and inherently opaque operations:
`development/journal/web/models-progress.md`.

Individual source batches/root work, provider/availability waits, eager comparison,
account indexing and DTO projection can still pause without internal observations.
Physical input, screen-reader certification, macOS and other browser engines were
not tested. No task requirement/test exception was requested or granted. No ZIP,
tag or GitHub Release was produced; current main remains the supported distribution.
