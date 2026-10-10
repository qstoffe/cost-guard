# Cost Guard version history

## v80.34 — 2026-10-10

- Faster with identical output (byte-compared against v80.33 on live data): normal report ~2.1 s → 0.65 s, date range 7.5 s → 2.1 s, Watch startup ~6.2 s → 0.65 s, V2 resync 13 s → 1.4 s.
- V2 requests reuse pooled keep-alive loopback connections (one retry when the service closed an idle socket); snapshots reuse a fresh catalog as their before-bracket; wire parts are no longer deep-copied twice.
- Pricing identity resolution is memoized per immutable catalog. Dashboards overlap model-availability and account I/O with analysis; the Claude helper is stopped after its answer instead of delaying quotas.
- Watch startup skips roots whose stable cached analysis has nothing since Watch start (a session Watch always hydrates its root); resync re-reads hydrated and changed roots rather than all history. Watch model discovery reads prices/V2 models on a bounded worker.
- Diagnostics drops the duplicated Copilot-only account section and reports all account integrations, terminal facts, V2 transport counters and a numbers-only headless Watch smoke (timings, hydration, render geometry at 80/120/160 columns with real accounts).
- Full tests run concurrently (151 s → 32 s); fake V2 services, the V1 database and package-copy builders moved to fixtures, retiring 10 test-to-test import edges.
- Policy: hosted/web AI runs only Quick + validation and never builds a ZIP; local workstation sessions run Full + live checks and build a ZIP for every completed version.

## v80.33 — 2026-10-10

- Watch account publication, cadence and bounded recovery now have one explicit state owner over an injected account-work protocol; worker acquisition remains with ReportService.
- Prompt/compaction rows have a dedicated projector; session assembly retains range filtering, context epochs, coherent Watch deltas and totals. Report modes now have focused build methods rather than one growing dispatch body.
- Shared Watch sources, scheduling and service builders move to fixtures, reducing direct test-to-test imports from 67 to 43 without deleting assertions.
- Package validation now gates runtime function statements/branches, explicit bounded legacy exceptions, module responsibility descriptions and exact legacy test-import edges; new coupling, growth and stale exemptions fail validation. No file cap was raised.
- Context-price warning explanations now use `Context:` in Watch and session/date reports; ordinary Next-Ictx estimates, threshold calculations and warning colors remain unchanged.

## v80.32 — 2026-10-10

- Reports and Watch share canonical catalog ancestry/tree-activity functions, retaining archived-history, orphan-detail and bounded-cycle behavior.
- Bounded comparison/token sampling and V2 message/part/request normalization have separate testable owners; source acquisition, cache, attribution, billing and output behavior remain unchanged.
- Shared canonical snapshots, prices and fake runtime boundaries move from test modules into responsibility-specific fixtures, removing 46 direct test-to-test import edges without deleting assertions.
- Added a task-to-code/test map, repeatable read-only AST inventory, structural regressions and guards for relative/nested layer imports, all V2 adapter siblings, runtime/development and fixture/test dependency direction.

## v80.31 — 2026-10-10

- Next-Ictx price-threshold warnings in Watch and session/date reports replace `(Next Ictx CCost x–y)` with `(1.9x more expensive)`: the model table's Relative CCost after the threshold divided by the level before it, with at most one decimal (`2x` for 2x → 4x). Unpriced thresholds keep the CCost range.
- The ratio uses the normal report's Relative CCost sample and token mix (its hidden sorting mix without samples), loaded only when a warning is shown and refreshed every 15 minutes.
- Regression coverage reproduces a reported v80.26 Watch whose prompt showed Next Ictx 24k before a +59k → 220k successor. Context grown after a subagent notice now belongs to that prompt (v80.30), so the successor's +59k is consistent rather than v80.27's inflated +196k.

## v80.30 — 2026-10-10

- Invisible synthetic V2 user messages, such as subagent-completion notices injected while work continues or right after a prompt typed during a running one, now continue the prompt current at that time. Their requests, CCost, duration and model stay on that row instead of showing 0 calls and `Model: N/A` while Watch total still counted them.
- A running V2 prompt whose first request has not completed takes model/effort from its own request-bound in-flight assistant message, never from mutable session selection (v80.28 regression).
- Watch Δctx after a session-location move or an unanchored/failed predecessor again shows the epoch-aware per-prompt estimate instead of N/A (v80.27 regression). Unknown compaction results and unexplained shrinks remain N/A.
- Session titles and prompt previews in reports and Watch drop CSI/OSC/C1 escapes, line breaks and control characters.
- Watch observations are recorded per source scan rather than per-second redraw, de-duplicated in memory, retain source errors separately from scans, ignore malformed files and name V2 catalog/normalize stages accurately. Recovery history uses per-process temporary files.
- Test runner and Diagnostics decode child output as UTF-8 regardless of console code page. A stale Watch title test and over-long history summary that kept Quick/Full red were corrected.

## Earlier v80 history

- v80.29 replaced unexplained Watch context shrinks with N/A and kept multiline checkpoint titles on one row.
- v80.25-v80.28 kept BLOCKED on accounts, split wide Watch quotas, added privacy-safe observations, made Watch Δctx compare consecutive Next-Ictx anchors, and removed mutable session-model attribution; v80.30 corrected move/unanchored-baseline regressions.

- v80.21-v80.24 added conservative table-local model-supersession fading (plain GPT tiers, Claude families, numeric Grok; preview/variant exclusions), parallel bounded quota acquisition with shared credential discovery and nonblocking Watch account refresh, and recommended current main as the supported distribution while packaged GitHub Releases are paused.

- v80.15-v80.20 introduced the four-column Relative CCost comparison with `--all-models` exact GitHub USD/M tiers, shared tier-aware price ordering and non-destructive metadata state under cache/state/. They gave release-date metadata independent health with classified sources, bounded non-blocking retries, failure logs and Diagnostics coverage, plus concise Diagnostics endings and launcher-path error hints. They also added hourly Copilot refresh with pinned CCost, 15-minute V2 checks, sleep/wake recovery and one-hour cache age; verified priced Watch/report ✦ New Models, sanitized metadata evidence, root logs/, safe Diagnostics archival/cleanup/staging, support instructions, runtime isolation, bounded history and metadata/refresh regression coverage.

- v80.11-v80.14 added simulated macOS compatibility in Diagnostics, Windows path/release-check fixes, sanitized V1 SQLite read-error guards with read-only triage and Windows-safe synthetic SQLite cleanup.

- v80.8-v80.9 aligned Watch session subtotals with visible rows (run-scoped CCost preserved) and unified the Windows launchers under a persistent PowerShell session with corrected Ctrl+C and error handling.

- v80.7 added shared Simple HTTP account providers and adapters for OpenRouter, DeepSeek and MiniMax, with sanitized diagnostics and no fabricated CCost.
- v80.6 made Watch survive temporary source outages and retry V2 without a V1 fallback; v80.5 scoped read-only V1→V2 migration-gap notices to report windows, never merging histories or showing them in Watch.

- v80.0 established the clean 0BSD public-repository baseline with a fresh root history, retaining the Python functionality and cross-platform launchers, explicit bounded test-suite membership and public product identifiers.
- v80.1-v80.4 introduced the README with static Watch/report/Token Mix images and linked contracts, the OpenAI token-expiry explanation (Cost Guard never refreshes or writes credentials), provider sign-in remedies, prompts kept active during verified V2 background jobs, and Diagnostics launchers under `development/windows|macos/`.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
