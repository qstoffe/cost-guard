# Cost Guard version history

## v80.88 — 2026-10-26

- Completed Web Models/selectable and all-catalog views (including exact native rates/tiers), Accounts, configured-local inclusive date/range reports, Sessions N/all and explicit cancellable historical Token Mix. Views reuse canonical report projections and frozen observations; filters/paging never recalculate totals, and exact Decimal sorting avoids JavaScript floating-point ranking.
- Preserved native quota windows/Pace, account attribution/freshness/errors, unknown pricing/history and independent sample scopes. Deep scans reuse dependency-bound analysis caches, never start another account scheduler or stop Live. Bounded progress-message coalescing prevents finite-job IPC backpressure from consuming the report deadline. CLI/launchers remain independent; visual browser and native macOS acceptance remain unclaimed.

## v80.87 — 2026-10-26

- Session details explicitly switch between frozen Snapshot and persistent Live, sharing the established eight-column report semantics, provisional running metrics, child costs and whole-session totals. Revision-aware 50-row pages expose all observed history without Watch's row cap; idle and abort do not end Live. Source omissions retain last-observed evidence without a durable ledger; missing/archive/outage states retain readable results.
- Canonical DOM row identities, anchored paging, follow-latest and explicit Jump to latest preserve browsing and text selection. Shared session subscriptions reuse the existing acquisition/account owner; timer-only ticks do not reload or revalue history. Snapshot-local causal indexes remove repeated full-history scans. Remaining dedicated Web views and native macOS acceptance remain pending.

## v80.86 — 2026-10-26

- Web Beta Live now shares one host-lifetime Watch acquisition/account owner across tabs, with canonical retained prompts, lifecycle/tool/skill/context evidence, Today and engine-start run totals. CLI remains independent. Finite reports retain isolated bounded workers and cannot monopolize live/control scheduling.
- Same-origin authenticated SSE multiplexes immutable live, progress and runtime publications with instance-bound ordered IDs, bounded replay and authoritative gap resync. Disconnects remain visibly offline; received shutdown/source-change notifications stop retry and request a manual launcher run. No packages, model inference, browser storage or control secrets in stream URLs. Session live detail and remaining dedicated reports remain separate work.

## v80.85 — 2026-10-26

- Web Beta now has local, accessible navigation, overview, all-session listing and static session detail with the established eight prompt columns, full-session totals, linked-child contributions and snapshot-time running evidence. Deep links, reload and Back/Forward use fragment routes; prompt text is never interpreted as HTML. No frontend build or runtime dependency.
- Reports remain frozen across navigation and source changes until explicit Refresh; failed refresh retains a visibly stale snapshot. Paging uses the same immutable full result, not fresh source offsets or Watch caps. Missing sessions, acquired empty sessions, partial source and independent account failures remain distinct. Finite API size/time bounds still apply; live acquisition and remaining dedicated report views are not yet available. CLI/Watch are unchanged.

## v80.84 — 2026-10-26

- Added experimental `macos/Beta/Cost Guard Web.command`, a same-process main-thread AppKit status menu through the Python standard-library ctypes bridge, bounded asynchronous browser Open, and the existing shared detached restart/stop owner. No packages, downloaded tools, service or login item; stable CLI/Watch/Diagnostics launchers are unchanged.
- First launch optionally compiles a Finder app with in-box `/usr/bin/osacompile`, stores it outside Git in private checkout-specific app data, and verifies source/version/OS/Python fingerprints and artifact hashes before reuse. Preparation failures retain the `.command` route. Implemented and tested on Windows at the owner's request: real macOS AppKit event-loop, Finder, Gatekeeper, executable metadata and browser behavior remain unverified, not platform acceptance claims.

## v80.83 — 2026-10-26

- Added opt-in `windows/Beta/Cost Guard Web.cmd`: Python 3.11+ discovery, native tray/configuration preflight before verified restart, detached host and automatic authenticated browser handoff. Native same-process Win32 notification icon has exactly Open Cost Guard and Exit Cost Guard; no packages, compiler, downloads, service or startup registration. Stable CLI/Watch/Diagnostics launchers are unchanged.
- Open is asynchronous and never restarts the instance; browser failures retain a usable tray. Native tray/startup/timeout/conflict failures have actionable feedback and private allowlisted records. HTTP faults, Exit and source-change shutdown remove the icon. Native Windows menu/message, detached-console, restart and shell-association probes are separate opt-in checks; physical double-click and visual light/dark review are not automated acceptance claims. macOS native UI remains pending.

## v80.82 — 2026-10-26

- Added checkout/user-scoped OS locks, private atomic instance records, process-birth validation, authenticated restart/readiness/Open controls and standard-library detached launch plumbing for upcoming native GUI launchers. Overlapping launches coalesce; deliberate later invocations restart even the same version. Unknown processes/ports are not kill authority; Windows force-stop uses a revalidated kernel handle, Linux uses pidfd, and platforms without an atomic process handle refuse unsafe force-stop. Native Windows/macOS launchers and icons remain separate FRs, not claims of native GUI success.
- Explicit `--foreground` developer Web mode and the shared managed host use one idempotent shutdown owner. Finite report children monitor the exact parent sentinel so a crashed/force-stopped host cannot orphan a blocked scan. A cheap five-second allowlisted runtime metadata guard stops Web on proven changes, never reloads/restarts it, excludes user-configuration/state/development writes and retries transient inspection failures. This is best-effort, not atomic updating; indistinguishable metadata can be missed. CLI launchers and shared OpenCode are untouched.

## v80.81 — 2026-10-26

- Added optional foreground Web Beta (`python cost-guard-web.py`) with fixed local assets and authenticated, read-only finite report APIs. Exact-host/origin checks, one-use short-lived bootstrap, HttpOnly SameSite sessions, CSRF, restrictive CSP, request/concurrency/result bounds and cancellable isolated report processes protect the loopback surface. No dependencies, browser auto-launch, native icons or background instance lifecycle; CLI and Diagnostics stay independent.

## v80.80 — 2026-10-26

- Added an optional transport-neutral application facade over existing report modes, including all-history Token Mix. Immutable JSON-ready results preserve exact decimal strings, unknown values, report duration/context/valuation semantics and stable detail identities. Isolated serialized one-shot jobs close their account work without sharing a live scheduler. Per-root revision evidence and independent account observations do not claim cross-provider atomicity; raw source/provider diagnostics and private account locators are excluded. No HTTP server, UI, dependencies or CLI/launcher changes.

## v80.79 — 2026-10-26

- Plain session reports always print one snapshot and exit, even with active work. `[RUNNING]` rows show supported provisional token mix and incoming/extra reference CCost from observed requests; incomplete telemetry, attribution or pricing stays unknown. Totals share that snapshot and running duration stays frozen at observation time. Explicit session/global Watch and date modes retain their behavior.

## v80.78 — 2026-10-26

- Normal Copilot Accounts Overview adds signed `Unaccounted usage`: native used AI credits minus canonical OpenCode reference CCost aligned to the supported native UTC billing month. Missing native usage/boundaries, incomplete history/pricing or ambiguous accounts show `—`; acquired priced zero is `0`. Local-month CCost, Watch, quotas and billing remain unchanged. The residual is an estimate, not metered external consumption or proof of free reviews; no new provider endpoint or credentials.

## v80.77 — 2026-10-25

- Account CCost displays the known priced subtotal without a partial marker, using standard upward rounding in reports and Watch. Unknown/empty distinctions, internal priceability evidence and global partial markers are unchanged; documented that missing prices may understate complete reference valuation.

## v80.76 — 2026-10-25

- Compact normal account sections retain today/month numeric CCost and show independent rolling CCost beside the corresponding quota percentage (or textual window when no percentage exists). Remove per-account provenance prose and the final account legend; documentation retains the distinctions.
- Established, acquired empty periods show `0` independently of account type; unpublished/missing history, ambiguous attribution and unknown window anchors remain unknown. Account-only values use `—` for unavailable and downward-rounded `≥…` for partially priced lower bounds; prompt/session/global question-mark semantics stay unchanged. No broader history scans or new polling.
- Known ChatGPT token-sharing accounts explain separate model/quota access and suggest trying OpenCode's Codex browser (legacy) or Codex device code (legacy) for now, without guaranteeing quotas. API keys do not supply Codex subscription quota; other method/status handling and read-only acquisition are unchanged.

## v80.75 — 2026-10-25

- Classify OpenAI OAuth methods and token-sharing scopes before quota lookup. ChatGPT token sharing and unfamiliar methods never send their tokens to legacy WHAM; Watch, reports and sanitized Diagnostics distinguish an unsupported quota method from model sign-in rejection. Legacy browser/headless Codex quota retrieval and genuine returned plans/windows remain supported; 401 is request rejection, 403 endpoint policy and 429 throttling.
- Read-only inspection of the affected OpenCode 2.1.4 installation confirmed the active API-resource token-sharing connection and no installed usage/limits API route. Headless report/Watch checks agree on method-specific unavailability with zero quota requests. Actual token-sharing quotas remain unavailable; no live legacy 200 or upstream 401 root cause is claimed. No credential writes, token refreshes, paid inference or shared-service restarts occurred.

## v80.74 — 2026-10-25

- Watch keeps the last fully published local-day CCost during later enrichment, accepting completed corrections atomically and resetting truthfully at midnight. Its overall line now uses `Total today` without a deletion disclaimer.
- Account rows show daily CCost beside monthly native quotas and independent CCost parentheses beside rolling-window percentages. Normal reports explain period/account/provider provenance and include configured-local calendar-month CCost for all detected providers. Ambiguous accounts stay unallocated; reference valuation is never billing or quota consumption. Period indexing reuses canonical deduplicated valuation; Watch enriches relevant windows in bounded slices without a monthly comparison row or quota-triggered history rescans.

## v80.73 — 2026-10-25

- Fixed global Watch history cap selection to use supported terminal ends for success, abort and error, independently of prompt/compaction display order. Long-running prompts remain eligible at exact highlight expiry; newer completions still evict normally. Unknown ends retain deterministic start ranking without Watch-local timestamps. Earlier startup selection, scoped Watch, Duration, costs, quotas and source read-only behavior are unchanged.

## v80.72 — 2026-10-25

- Fixed OpenAI account-switch inventory: authoritative removal drops superseded rows, generation-pinned requests cannot restore old accounts, and proven aliases prefer canonical V2 credentials without merging distinct subscriptions. Watch clears failed OpenAI quota instead of restoring stale values or an unknown prior plan. Safe novel returned plan names retain valid windows; 403 means endpoint access denied rather than proven bad sign-in. Historical 401 evidence alone cannot establish upgraded-tier support or valid current auth; no credential writes, refreshes or paid probes were added.

## v80.71 — 2026-10-25

- Adopted Toolkit's development layout and six-digit backlog bundles while preserving test membership, repository facts and pending requests. Product versions and release checks remain Cost Guard-owned; legacy adapter data is opaque to Toolkit. Relocated human Diagnostics launchers and updated software-failure hints; Watch, account and cost semantics are unchanged.

## v80.70 — 2026-10-23

- Added pending FR 0140 for stable Watch Today rendering, a shorter overall CCost label and per-provider/subscription CCost for current day and native quota periods, with explanatory normal-report output. FR 0130 remains distinct. No production Watch, report, cost or quota code changed.

## v80.69 — 2026-10-23

- Added pending FR 0130 for global Watch historical recency of newly finished prompts, including verified terminal evidence and plugin-end behavior. This documentation-only delivery does not change running Watch behavior.

## v80.68 — 2026-10-23

- Added two pending Cost Guard adoption FRs for Toolkit-owned release/version-history and version-free Feature Request authoring, with explicit Toolkit/migration prerequisites. No production Watch, quota or shared-authoring runtime changed.

## v80.67 — 2026-10-23

- Added two pending repository-native backlog FRs: migrate Cost Guard to the Toolkit-owned FR-folder/attachment contract, then fix OpenAI account replacement and rejected quota after a subscription upgrade. Diagnostic observations are sanitized in the bug specification; no production account, Watch or quota behavior changed.

## Earlier v80 history

- v80.66 defined repository-native FR finalization, lowercase backlog layout and collision-safe priorities with tracked empty todo/complete directories. v80.65 fixed repeated Watch fragments/overflow scrollback; v80.64 applied finite terminal-failure highlights without losing permanent labels; v80.63 improved redraws, staged progress and launcher/Python preflight.
- v80.62 preserved completed context estimates and separated current anchors across model/effort boundaries with explicit compaction semantics; v80.61 made Windows launchers prefer PowerShell 7 (5.1 fallback) and probe each discovered Python executable separately. v80.60 moved optional Watch release-date refresh off startup, retaining verified dates, report enrichment, prices and promotion expiry. v80.59 staged Watch local-day accounting (`Today: Pending`), shared V2 catalog/revision batches and added payload-free V1 liveness plus semantic cache keys. v80.58 bounded quota histories without upstream freshness guarantees. v80.57 added execution Duration/overlap-safe totals; v80.56 isolated quota lanes/retries (60s stale/5min expiry); v80.55 grouped Watch; v80.54 indexed effort/context. v80.48–v80.53 added overnight Today dates, active-context separation, timestamp-first/running headers, shared warnings/Earlier rows, deleted usage and a global row cap; routine ZIPs stopped. v80.43–v80.47 added priced Token Mix, New Models and faster CCost. Claude limitations remain documented.
- v80.35–v80.42 added native abort-cause labels (`[ABORTED by user]` only for matched live V2 interrupts), neutral tool-call endings, stable account ordering, refactored hot paths, bounded startup recovery/typed source errors, retained tool/skill evidence and stopped counting proven V2 tool continuations as `Calls`.
- v80.34 pooled V2 reads, memoized model identity, overlapped report acquisition and bounded Watch discovery/startup/resync with identical output (report ~2.1→0.65 s, Watch startup ~6.2→0.65 s, resync 13→1.4 s); Diagnostics gained all-account evidence and Watch geometry.
- v80.32–v80.33 separated refresh, prompt projection/report orchestration and normalization, shared ancestry/bounded sampling, moved fixtures (67→43 test-import edges) and added routine/coupling, inventory and layer guards without raising caps or changing billing.
- v80.25–v80.31 kept BLOCKED on accounts, split wide quotas, added private-safe observations, fixed synthetic/background continuation and running-model attribution, restored move/unanchored Δctx and N/A for unexplained shrinks, sanitized terminal text and deduplicated source scans. Consecutive Next-Ictx anchors own Δctx without mutable session-model attribution. Priced tiers show one-decimal cost multipliers refreshed every 15 minutes; unpriced thresholds keep CCost ranges.
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
