# FR 000340 completion — navigable static Web Beta

## Outcome

Implemented in v80.85 (2026-10-26). Overview, all-session listing and selected static session detail are working routes over the existing shared application API. The original specification is preserved byte-for-byte. Implementation candidate: [40326d2](https://github.com/qstoffe/cost-guard/commit/40326d2d2d58de76d3a5c54166478d5b73a7efb9).

## Changes and choices

- Local HTML/CSS/JavaScript shell, Beta/source/status labels, wrapping navigation, hash deep links and reload/Back/Forward handling. No frontend build or runtime dependency.
- Eight-column prompt tables preserve canonical order, compaction, model/effort, abort/error/running evidence, provisional metrics and main/linked-child breakdown. Complete canonical session totals are independent of the 50-row visible page. CCost remains reference credit-equivalent valuation, distinct from monetary billing.
- Full immutable finite API results back local paging: no cross-revision offset requests, no Watch row cap, all listed rows reachable. Session listing explicitly requests all roots. Existing 8 MiB/120-second limits remain; failures never masquerade as truncated success.
- Snapshot observation time and independent source/account status remain visible. Only explicit Refresh replaces a retained report; navigation and new source events do not mutate it. Failed refresh preserves the visibly stale last result. Missing catalog sessions have an allowlisted application error distinct from an existing empty session; CLI keeps its existing ReportRequestError handling.
- Text-only DOM insertion; no private payloads in browser storage/history state, tooltips, analytics or browser-to-OpenCode acquisition. Page controls and view state are memory-only. Sticky table headers, keyboard/skip controls, responsive overflow and system light/dark styles are implementation-owned layout choices; owner testing is described in `docs/web-beta.md`.
- Dedicated Live, Models, Accounts, date Reports and Token Mix pages explicitly remain unavailable; overview model/account summaries and existing API/CLI report modes remain reachable equivalents. No live acquisition, editing, account login, remote hosting, launcher rewrite or new permanent release gate.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, all 102 files, 0 failed files; final run 39.6 s. Includes ordinary CLI/Watch tests and shared application parity at the same clock/projection.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, 0 failures, 4 nonblocking design-budget warnings (README and existing context/report/coordinator owners); no hard caps raised or budgets rebaselined.
- New `test_web_views.py` / `integration/web_views.cjs`: PASS through real loopback HTTP, shared ReportApplication/ReportService and actual served assets in an optional already-installed Node VM/DOM harness. Covers 55 roots, 151-row detail, canonical totals unchanged across pages, insert-after-capture reaching 152 rows only on Refresh, frozen running duration, child/compaction/abort/unknown-pricing/partial/hostile Unicode text, independent overview account data, missing/empty distinction, stale refresh, hash navigation and direct-link reload. No runtime/build Node requirement.
- `py -3 development/tests/integration/probe_web_lifecycle.py`: PASS against the real read-only installation: acquired session listing, acquired frozen detail, CLI one-shot, authenticated stop and joined owned host; source guard unchanged; 0 model requests. Shared OpenCode was not stopped.
- Initial regression runs caught a now-intentionally-more-specific missing-session expectation and README hard-cap growth; expectation updated and README consolidated. A subsequent test edit indentation error was repaired. Final required checks pass.
- NOT RUN: visual browser rendering, physical keyboard/mouse interaction, actual narrow/wide and light/dark layout review, native macOS. The no-browser DOM harness does not establish these. No screenshots, paid/live-model calls, self-review agent, ZIP or GitHub Release.

## Knowledge, dependencies and limitations

Architecture assessment: presentation remains inside Web; acquisition/valuation stay in the shared facade/reports. Updated only the affected Web module route and current user docs. Journal assessment: **no-update**; no new durable acquisition/performance finding beyond these source contracts. Existing journal authority and limitations are preserved.

No selected/foreign FR was rewritten and no retention entries were pruned. Later live/detail/complete-report work remains pending in the existing backlog. Large finite reports may still hit the explicit result/deadline limit; this is not a claim of streaming or live-history completion. No unrelated dependency or recovery artifact is required from this task's scratch.
