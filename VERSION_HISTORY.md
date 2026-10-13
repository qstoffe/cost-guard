# Cost Guard version history

## v80.43 — 2026-10-13

- Normal-report Token Mix % and Relative CCost sample the latest 100 prompts with at least one reference-priceable request (real usage, complete I/C/W/O telemetry, resolvable rates for the request's own model and tier), skipping unpriceable prompts and backfilling from older history instead of filtering the latest 100. A prompt counts once; only its priceable requests feed shares, category CCost and the Relative CCost mix, so those CCost amounts no longer show `?`.
- Watch Token Mix % shows only this run's priceable requests; `Watch total CCost`, prompt/session/date/account totals and `--token-mix` keep all usage and their partial-pricing `?`. Eligibility is evaluated against the current catalog, never cached; Relative CCost completed-prompt eligibility, ordering and threshold multipliers are otherwise unchanged.

## v80.42 — 2026-10-13

- `Calls` tracks independently evidenced model requests. A zero-usage, tool-only OpenCode V2 record that directly continues a usage-bearing `tool-calls` response of the same prompt and model no longer counts as its own request when a shared provider response id, or without ids its absent model latency, proves it. The record stays in history, so tools, failures, outcomes and durations are unchanged.
- Ambiguous zero-usage records (model latency, own output, absent counters, errors, model switches, differing or one-sided ids, prompt/compaction boundaries) keep counting; usage, CCost and fallback valuation are unchanged. Live reference prompts move from 21 to 12 and from 8 to 6 Calls; an OpenAI session with response ids is unchanged. Cached analyses are recomputed once.

## v80.41 — 2026-10-12

- Behavior-neutral maintenance: shared report-service, availability/rendering, quota-rendering, account and config-package test setup now lives in responsibility-owned fixtures instead of being borrowed from other test modules, retiring 15 of 33 bounded test-import debt edges. Stale unused imports were removed.
- Recorded audit evidence with no runtime change: 80 live roots analyze in 54 ms (worst root 9.7 ms) and Watch tool observation remains bounded to the latest running prompt. Per-prompt causal scans only become significant on synthetic roots far larger than observed live sessions.

## v80.40 — 2026-10-12

- Watch shows tool-call, Skills and running-status rows only under currently running prompts; the first terminal update removes them while the regular prompt metrics remain unchanged, including after refresh or rehydration.
- Skill calls use physical-call counts and verified V2 registry paths for `builtin skill` versus `custom skill`; unknown origins remain `skill`. The Skills row lists only distinct successfully loaded custom skills, with existing verified failure attribution.
- All normal activity text and prefixes use `watchToolActivity`; verified failures remain red. Width-adaptive totals, failure priority, accurate aggregation and accounting are preserved.

## v80.39 — 2026-10-12

- Watch retains the latest prompt's tool/failure counts and confirmed distinct skill IDs after completion or abortion, replacing activity only when the same session begins a new prompt. Active tool/TODO/background indicators never survive completion; compaction, refresh and reconnect keep prompt ownership.
- A yellow Skills row shows exact persisted IDs, newest load first, with red per-skill tool call failure counts only for explicit metadata or direct skill-script execution. Generic reads, mentions and skill-load recency never imply attribution; unattributed failures remain in the total.
- Known Toolkit script contracts supplement native tool errors with bounded, schema-verified structured failures. Physical-call deduplication and cancellation handling prevent inflated totals; arbitrary output and nonzero exits alone remain neutral.
- Activity rows fit terminal width independently of the fixed metric table: total/failures outrank breakdowns, whole skill IDs/indicators precede an accurate +N more fallback. Stable completed frames reuse observations without new source reads or changes to usage, billing or token accounting.

## Earlier v80 history

- v80.38 gave a missing/unreachable Desktop V2 service actionable startup guidance with bounded readiness retries, recovered Watch initialization through its coordinator, typed source errors (distinct certificate failures) and kept sanitized source incident history for Diagnostics. v80.37 removed dead/redundant code, derived causal trace inputs once per root pass (74 live roots 252→92 ms with identical records) and flattened analysis-cache serialization; Git delivery became tool-independent in isolated clones, and every PR to main now carries a sequential version bump with dated history and current docs.
- v80.35–v80.36 added explicit native abort-cause labels, neutral tool-call endings and stable credit-first account ordering; Watch shows `[ABORTED by user]` only when a live V2 user interrupt matches authoritative interrupted history, keeping that actor evidence bounded and in memory.
- v80.34 pooled V2 reads/fresh snapshot brackets, memoized model identity, overlapped report acquisition and bounded Watch discovery/startup/resync. Recorded live timings with v80.33-identical output: normal report ~2.1→0.65 s, date report 7.5→2.1 s, Watch startup ~6.2→0.65 s, resync 13→1.4 s. Diagnostics gained all-account evidence and privacy-safe Watch geometry; concurrent Full and shared fixtures retired 10 test-import edges. Verification/packaging policy remains in maintainer rules.
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
