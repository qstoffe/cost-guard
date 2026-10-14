# Cost Guard version history

## v80.49 — 2026-10-14

- Watch appends `Today` CCost to its existing run-total line. It combines available local-day history with deduplicated process observations retained through session deletion until local midnight; unavailable history deleted before observation remains excluded, and no ledger is persisted.

## v80.48 — 2026-10-14

- Global Watch keeps one prompt budget across all sessions: `watchDashboardMaxRows` (default now 12) selects the newest prompt/`/compact` rows, while running rows and rows still showing their green/red marker stay protected above it; when markers expire the ordinary limit returns live. The 10-minute idle expiry and two-session protection are gone: a session block disappears only when its last selected prompt is evicted. Row selection never changes Token Mix, `Watch total CCost` or OpenCode history.
- New `watchStartupEarlierSessions` (default 2, 0 disables): startup shows that many sessions completed before the run, chosen by actual latest prompt start (not metadata), each with only its latest prompt and a gold-orange `[Earlier]` header plus one explanation line while any is visible. A new prompt or `/compact` replaces the historical row; evicted representatives never return.
- Session blocks order by the exact start of their latest prompt (session-ID ties) and headers show it as `HH:mm` (`[Earlier] YYYY-MM-DD HH:mm`) in the configured timezone. Header rows span the Session/prompt and Model/effort columns; only the title truncates and prompt/tool row geometry is unchanged.
- Fixed account/quota results appearing late in idle Watch: an accepted provider result now redraws the dashboard on the next one-second wake, and source polls compare against the frame actually drawn, so no prompt activity is needed. Provider cadence, timeouts and requests are unchanged.

## v80.47 — 2026-10-13

- Behavior-neutral cleanup. Watch's local month/today CCost refresh, which runs on each changed poll, produces identical output with about a third less CPU (captured live month of 6,279 requests: 67–70 → 43–47 ms) by packing each request fingerprint in one step and formatting each UTC day once per valuation.
- Removed unused legacy v77 billing aggregation and its usage-note formatter (no runtime caller); fork-clone de-duplication is tested on its live owner. Snapshot, threshold-catalog and warning-projection test setup moved into owned fixtures, retiring 8 of 18 test-import edges.

## v80.46 — 2026-10-13

- Global Watch removes a whole session block (rows, activity, `Σ`, context warning) once its last prompt finished 10 minutes ago. Running sessions and the two most recently prompt-active sessions always remain, each with at least its latest row under the row cap; startup shows them from recent metadata. Idle time uses source prompt end times (observed completion only as fallback), so polling, title changes, resyncs and restarts never extend it, and a session displaced from the recent pair disappears immediately. Presentation only; no timer state, extra hydration or OpenCode/history change.
- Sessions with an identical displayed context warning (severity, threshold, explanation and multiplier or Next Ictx CCost range) share one explanation such as `*1,2,3,4 Context: …`, wrapped to terminal width; each header keeps its own marker and Next Ictx highlighting is unchanged.

## v80.45 — 2026-10-13

- Eligible New Models names receive a bold lime ✦ highlight for 12 hours from one atomic UTC first-sighting timestamp per provider-qualified model ID, shared by Watch and Report. Watch removes the emphasis on a live status wake; the existing seven-day visibility rules are unchanged.

## Earlier v80 history

- v80.43 sampled the latest 100 priceable prompts for Token Mix %/Relative CCost; Watch Token Mix % uses this run's priceable requests. v80.38 added bounded Watch startup recovery, typed source errors and sanitized connectivity history. v80.37 refactored Watch/source boundaries and hot paths; Git delivery moved to isolated clones and every main PR versions docs. v80.39 added retained tool/skill stats, verified failures and width-adaptive rows; v80.40 made rows live-only before v80.44 tied final statistics to existing markers while clearing transient indicators. v80.41 moved shared test setup into owned fixtures (15 of 33 test-import edges retired) with no runtime change. v80.42 stopped counting zero-usage V2 tool-continuation records proven to continue the same response as separate `Calls`.
- v80.35–v80.36 added explicit native abort-cause labels, neutral tool-call endings and stable credit-first account ordering; Watch shows `[ABORTED by user]` only when a live V2 user interrupt matches authoritative interrupted history, keeping that actor evidence bounded and in memory.
- v80.34 pooled V2 reads, memoized model identity, overlapped report acquisition and bounded Watch discovery/startup/resync with identical output (report ~2.1→0.65 s, Watch startup ~6.2→0.65 s, resync 13→1.4 s); Diagnostics gained all-account evidence and Watch geometry.
- v80.32–v80.33 separated Watch account refresh, prompt projection/report orchestration and source normalization; shared catalog ancestry and bounded sampling; moved fixtures (67→43 test-import edges, 46 fewer test-import dependencies), enforced bounded routine/coupling debt without raising caps, standardized `Context:` warning explanations, and added code maps/inventory/layer guards. Source/cache/billing semantics stayed unchanged.
- v80.29–v80.31 fixed synthetic/background continuation and running-model attribution, restored move/unanchored Watch Δctx and N/A for unexplained shrinks, sanitized terminal text and deduplicated source scans. Priced Next-Ictx tiers show one-decimal sample/mix cost multipliers refreshed every 15 minutes; unpriced thresholds keep CCost ranges.
- v80.25–v80.28 kept BLOCKED on accounts, split wide Watch quotas, added privacy-safe observations, compared consecutive Next-Ictx anchors for Δctx and removed mutable session-model attribution; v80.30 corrected move/unanchored regressions.
- v80.21–v80.24 added conservative table-local model fading (plain GPT tiers, Claude families, numeric Grok; preview/variant exclusions), parallel bounded quota acquisition, shared credential discovery and nonblocking Watch account refresh. Current main became recommended; packaged GitHub Releases remain paused.
- v80.15–v80.20 introduced four-column Relative CCost comparison, `--all-models` exact USD/M tiers, shared tier-aware sorting and non-destructive metadata state under cache/state/. Release metadata acquired independent classified health/backoff/cache and Diagnostics evidence; hourly Copilot/15-minute V2 checks retained pinned CCost. Verified New Models/promotions, sleep/wake quota recovery, safe error/recovery logs and Diagnostics archival/cleanup gained regression coverage.
- v80.8–v80.14 unified persistent Windows launchers with usable Ctrl+C/completion/error prompts, added session row subtotals without changing run CCost, simulated macOS diagnostics, hardened Windows release paths and sanitized read-only V1 SQLite errors/cleanup.
- v80.0 established the 0BSD public Python baseline, cross-platform launchers and bounded test membership. v80.1–v80.7 added illustrated docs, token-expiry/sign-in guidance without credential writes, verified V2 background liveness, developer Diagnostics launchers, read-only scoped V1→V2 migration-gap notices, recoverable source outages without fallback, and Simple HTTP/OpenRouter/DeepSeek/MiniMax accounts without fabricated CCost.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
