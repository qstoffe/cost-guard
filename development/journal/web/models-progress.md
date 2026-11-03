# Models loading progress — 2026-11-03

FR 000550 / v80.132. Progress ownership, not source acquisition or report values,
changed. The application allowlists optional work stages in addition to the original
phase/count contract. Separate sample, model, account-cache/load/analysis/projection
and packaging bands prevent early availability from exhausting later history work.
Sampling reports completed roots with a bounded estimate, never an invented total.
Known units report completion after work. Provider prefetch remains concurrent.

## Observations and regression evidence

- Before: executed Normal on base `38c748753e0f1f0f1232766b9b0051fdeb317108`
  over 28 synthetic roots with ten prompts each and batched history. Its 36 actual
  application observations mapped through the former browser formula to distinct
  values **10, 20, 30, 55, 90**. Every later account-history observation remained
  **90**. This is a backend-observation/formula comparison, not an old screenshot.
- After: the same workload with bounded 220ms analysis-unit delays ran through
  `ReportApplication`, production spawned `ReportJobs`, HTTP/events and headless
  Chromium 156. Sampling visibly advanced through **32, 33, 34, 36–40**; separate
  account analysis visibly advanced through **73–87**. A full acquired result alone
  painted **100**, followed by the existing table transition. Fast intervening work
  legitimately skipped percentages; no animation delay was added.
- The loading element remained the same DOM node. Its post-authorization height
  stayed 405px at 1280×900; the initial unstyled HTML briefly measured 52px before
  CSS, excluded from the work-stage geometry comparison. Accessible values retained
  “Approximately”; the ready frame reported “100 percent — report ready”. Returning
  from Accounts reused the single report rather than starting another job.
- Deterministic checks cover actual stage order, 10 sampled/28 total hydrated roots,
  batched and non-batched account history, unchanged cached results without further
  hydration/analysis, approved metadata/privacy, stale polling/events, fresh-load
  reset, 10,000-callback producer coalescing and the 64-message host-turn bound.
- Browser lifecycle cases retain success, partial, failure, timeout, cancellation,
  authorization failure, offline and interrupted/reconnected acquisition coverage.
  Model table geometry/filter/sorting acceptance remains owned by the newer Models
  fixture, not obsolete Overview account/table expectations.

## Real installation and limits

Final local Full: 127 files, 1,549 passes, zero failures/errors; one normal Windows
skip for the macOS zsh/PTY test. Validator: 11 passes, zero failures, four existing
owner/design-budget warnings (README, analysis/context, reports/service, Watch
coordinator), with hard caps unchanged. All nine browser cases passed. Initial
verification caught the account-history preparation seam being bypassed, an
unverified-availability fixture incorrectly expecting 100%, unstyled-HTML geometry
being compared to loaded CSS, and missing synthetic Live state on reconnect. These
were repaired rather than waived. Documentation was consolidated within its caps.

Read-only `probe_web_live.py --models` observed V2, one Live owner/two streams and
three accounts. Normal completed in **118.479s**, 29 catalog rows, availability
**unverified**; full Models completed in **4.437s**. Both preserved the Live owner
and run origin. Owned workers closed and shared OpenCode was untouched. This does
not establish provider availability, a general speedup or a complete live-source
acquisition; those fail-soft warnings remain truthful.

Opaque source snapshot batches, individual root hydration/analysis, pricing or
availability/provider waits, eager comparison calculation, account indexing and
DTO projection can still pause between observable boundaries. No extra source or
provider request, denominator-discovery scan, telemetry ledger or clock-driven
progress was introduced. Physical input/screen-reader and macOS/other-engine
certification were not performed and are not claimed. No requirement/test exception
was requested or granted.

Reproduce browser evidence with provisioned isolated Playwright/Chromium:
`python development/tests/integration/web_minimal_overview.py --approved-browser --output <owned-json> --screenshots <owned-directory>`.
