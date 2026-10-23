# Cost Guard version history

## v80.68 — 2026-10-23

- Added two pending Cost Guard adoption FRs for Toolkit-owned release/version-history and version-free Feature Request authoring, with explicit Toolkit/migration prerequisites. No production Watch, quota or shared-authoring runtime changed.

## v80.67 — 2026-10-23

- Added two pending repository-native backlog FRs: migrate Cost Guard to the Toolkit-owned FR-folder/attachment contract, then fix OpenAI account replacement and rejected quota after a subscription upgrade. Diagnostic observations are sanitized in the bug specification; no production account, Watch or quota behavior changed.

## v80.66 — 2026-10-23

- Define repository-native FR finalization, shared lowercase backlog layout, collision-safe priority selection and authorized Git delivery while retaining Cost Guard's ownership/handoff standards and documentation release gates. Track empty pending/completed directories; no backlog execution or runtime behavior changes.

## v80.65 — 2026-10-20

- Fix repeated Watch title/table fragments when scrolling up: wrapped or taller-than-viewport dashboards clear and rebuild the current frame instead of accumulating partial old frames in scrollback. Returning from overflow also clears stale fragments. Fitting dashboards retain buffered row patches, safe resize overwrites and unchanged-frame suppression; status-only updates, redirected output, row selection, acquisition and accounting are unchanged.

## v80.64 — 2026-10-20

- Terminal Watch failures share the finite `watchRecentEventSeconds` highlight: red `!`, critical row styling and final tool/Skills activity expire together, leaving a neutral `[ERROR]` outcome. Startup historical failures receive no fresh emphasis; polling, redraws, quota refreshes and unchanged/revised source snapshots do not restart the window. Zero disables only transient effects. Existing analysis/report outcomes, accounting, row selection and successful/aborted/running semantics are preserved.

## Earlier v80 history

- v80.63 made Watch patch/suppress identical buffered frames without clearing scrollback, added truthful staged startup progress, and improved cross-platform launcher prerequisites/Python probing; active quotas and source accounting stayed intact.
- v80.62 preserved completed context estimates and separated current anchors across model/effort boundaries with explicit compaction semantics; v80.61 made Windows launchers prefer PowerShell 7 (5.1 fallback) and probe each discovered Python executable separately. v80.60 moved optional Watch release-date refresh off startup, retaining verified dates, report enrichment, prices and promotion expiry. v80.59 staged Watch local-day accounting (`Today: Pending`), shared V2 catalog/revision batches and added payload-free V1 liveness plus semantic cache keys. v80.58 bounded quota histories without upstream freshness guarantees. v80.57 added execution Duration/overlap-safe totals; v80.56 isolated quota lanes/retries (60s stale/5min expiry); v80.55 grouped Watch; v80.54 indexed effort/context. v80.48–v80.53 added overnight Today dates, active-context separation, timestamp-first/running headers, shared warnings/Earlier rows, deleted usage and a global row cap; routine ZIPs stopped. v80.43–v80.47 added priced Token Mix, New Models and faster CCost. Claude limitations remain documented.
- v80.35–v80.42 added native abort-cause labels (`[ABORTED by user]` only for matched live V2 interrupts), neutral tool-call endings, stable account ordering, refactored hot paths, bounded startup recovery/typed source errors, retained tool/skill evidence and stopped counting proven V2 tool continuations as `Calls`.
- v80.34 pooled V2 reads, memoized model identity, overlapped report acquisition and bounded Watch discovery/startup/resync with identical output (report ~2.1→0.65 s, Watch startup ~6.2→0.65 s, resync 13→1.4 s); Diagnostics gained all-account evidence and Watch geometry.
- v80.32–v80.33 separated refresh, prompt projection/report orchestration and normalization, shared ancestry/bounded sampling, moved fixtures (67→43 test-import edges) and added routine/coupling, inventory and layer guards without raising caps or changing billing.
- v80.29–v80.31 fixed synthetic/background continuation and running-model attribution, restored move/unanchored Watch Δctx and N/A for unexplained shrinks, sanitized terminal text and deduplicated source scans. Priced Next-Ictx tiers show one-decimal sample/mix cost multipliers refreshed every 15 minutes; unpriced thresholds keep CCost ranges.
- v80.25–v80.28 kept BLOCKED on accounts, split wide Watch quotas, added privacy-safe observations, compared consecutive Next-Ictx anchors for Δctx and removed mutable session-model attribution; v80.30 corrected move/unanchored regressions.
- v80.21–v80.24 added conservative table-local model fading (plain GPT tiers, Claude families, numeric Grok; preview/variant exclusions), parallel bounded quota acquisition, shared credential discovery and nonblocking Watch account refresh. Current main became recommended; packaged GitHub Releases remain paused.
- v80.15–v80.20 added four-column Relative CCost, exact USD/M `--all-models` tiers, shared sorting and non-destructive cache/state/ metadata. Independent metadata health/backoff/cache/Diagnostics, hourly Copilot/15-minute V2 checks with pinned CCost, verified model/promotional notices, sleep/wake quota recovery and safe bounded error/recovery logs gained regressions.
- v80.8–v80.14 unified persistent Windows launchers with usable Ctrl+C/completion/error prompts, added session row subtotals without changing run CCost, simulated macOS diagnostics, hardened Windows release paths and sanitized read-only V1 SQLite errors/cleanup.
- v80.0 established the 0BSD public Python baseline, cross-platform launchers and bounded test membership. v80.1–v80.7 added illustrated docs, token-expiry/sign-in guidance without credential writes, verified V2 background liveness, developer Diagnostics launchers, read-only scoped V1→V2 migration-gap notices, recoverable source outages without fallback, and Simple HTTP/OpenRouter/DeepSeek/MiniMax accounts without fabricated CCost.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
