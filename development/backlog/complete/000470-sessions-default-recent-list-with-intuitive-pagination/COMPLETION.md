# FR 000470 — Completion

## Outcome

Implemented in v80.96 (2026-10-27): Sessions opens without input on the most recent
50 available roots. Previous/Next are real bounded older-page requests with URL
state, truthful available-root totals and catalog-order revisions. Catalog drift
is explicitly rejected; restarting browsing discards cached list observations.
Optional N/all scope is collapsed, not required. Search/filter/sort explicitly
apply only to the fetched page. Canonical row values, formatting, recent-first
CLI order, archived/running/incomplete flags and same-Web detail links remain.

The actual detached Windows report-worker console mechanism was reproduced.
Managed Web launches now use the paired `pythonw.exe`, preventing report child
consoles without changing isolation, cancellation or parent-loss cleanup. The
managed tray remains intentional UI; browser code does not dispatch a CLI.

Implementation candidate: [8b4b0c1](https://github.com/qstoffe/cost-guard/commit/8b4b0c1377f57d78a1508f92f330550d743687a5).

## Design and exclusions

- Bounded catalog-checked pages were chosen over acquiring all history merely to
  show 50 rows. Only selected roots are hydrated/analyzed; unused prompt-identity
  exports are omitted for paged lists. Existing result/deadline bounds remain.
- Catalog membership/order is stable within a revision; prompt row values are
  observed per page, not falsely described as an atomic all-history snapshot.
- No new history ledger, browser-side valuation, deep Token Mix scan, per-page
  account acquisition, dependency, CLI behavior change or release archive.
- The original FR bundle is preserved byte-for-byte; only this report is added.
  New evidence lives outside the selected bundle.

## Verification

- Full suite: PASS, all 109 test files, 0 failing files, 53.6 seconds.
- Working-tree package validation: PASS, 0 failures; four existing-category soft
  design-budget warnings (README and three large modules), no raised hard caps.
- Deterministic 0/1/100/1,001-root tests cover CLI row/order parity, disjoint pages,
  bounded analysis, archives, partial/source changes, additions/deletions and bounds.
- Actual headless Edge: PASS, light desktop, dark narrow and fresh older deep link;
  same-Web detail, Back/Forward, restart, accessible labels and bounded scrolling.
  Actual synthetic screenshots were visually inspected, then removed as artifacts.
- Installed V2: PASS with 1,994 roots, two distinct 50-row pages, 23,105-byte first
  result; 3.452/2.495 seconds in this run. No page account acquisition or inference.
- Windows: PASS for real detached ReportJobs console reproduction and this clone's
  production managed tray/HTTP Sessions request (50/1,994 rows under pythonw.exe).
  Only newly owned processes were stopped; shared OpenCode was untouched.

Reproducible commands, conditions and earlier artifact-related test failures:
[Sessions verification](../../../architecture/governance/verification/sessions-pagination.md).
An interrupted full-suite run after the server restart was not counted as PASS;
the later complete run above supersedes it.

## Knowledge and limits

No dependency-boundary change. Updated the existing Reports module contract with
source-fingerprinted pagination semantics, lightly consolidated its overview
router to fit the existing knowledge limit, and updated current API/user docs.
Journal: no-update; the focused verification document owns this reusable evidence
without a duplicate session log. Native physical mouse, keyboard-only/screen-reader,
external-browser native handoff and macOS desktop acceptance were not claimed.
Browser transport was synthetic; installed-source and managed HTTP probes were
independent. Cross-page catalog changes intentionally require restarting browsing.
