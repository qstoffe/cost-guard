# Cost Guard version history

## v80.29 — 2026-10-09

- An unexplained drop in Watch Next Ictx no longer renders a negative ordinary-prompt Δctx; the cell shows N/A and the following prompt uses the newly observed context as baseline. Explicit /compact shrink remains visible; Next Ictx, CCost, pricing warnings and normal report values are unchanged.
- Embedded line breaks, terminal control sequences and Markdown heading prefixes in session titles can no longer split Watch table rows. Checkpoint failure titles stay separate from their real model requests, whose CCost remains visible.
- Added deterministic regression scenarios for shrink/reanchoring, zero growth, compaction, multiline checkpoint titles and preserved prompt costs.

## v80.28 — 2026-10-09

- OpenCode V2 no longer copies mutable session model selection into historical user prompts. Actual assistant requests supply model and effort, so past Luna prompts remain Luna after a switch to Sol.
- Unanswered prompts have no invented model attribution; Watch/report and request-based CCost/Next Ictx remain unchanged. Synthetic V2 regressions cover model switches and stable historical attribution.

## v80.27 — 2026-10-09

- Watch Δctx now uses the preceding root-event Next Ictx as its baseline within a continuous context epoch. This fixes misleading transitions such as 24k → 220k displaying +59k instead of ~+196k.
- Unknown compaction context and session-location boundaries suppress unprovable deltas (N/A); completed compaction checkpoints establish new comparable baselines. Subtasks do not reset root context. No CCost, token, Next Ictx or price-warning calculations change.
- Synthetic regressions cover the large discontinuity, ordinary following deltas, compaction, missing checkpoint values, location moves and subtask continuity.

## v80.26 — 2026-10-09

- Watch's empty table clarifies it only displays prompts observed since startup, not all historical sessions.
- Bounded privacy-safe Watch observations retain discovery/filter counts and normalized source-error stages for later Diagnostics, with V2 snapshot revision-retry evidence. No session IDs, prompt text or native payloads are persisted.
- Diagnostics includes Watch observation history in its JSON, summary and verified ZIP without modifying OpenCode sessions or the V2 loading algorithm.


## v80.25 — 2026-10-09

- Account-level BLOCKED stays on the account instead of every quota window: OpenAI's weekly quota with capacity left is no longer marked blocked because the 5-hour limit is exhausted. Copilot's window-specific `hasQuota` evidence and `⚠  COPILOT PAUSED` remain.
- When a current account-scoped quota is known to be exactly 0% remaining, its bar and reset explain the block and no BLOCKED text is shown. Positive, rounded-to-0%, unknown, expired or not-started windows keep exactly one account-level BLOCKED in Watch and report.
- Watch keeps compact single-line accounts whenever they fit; wider rows split at `|` into aligned, indented continuation lines with the account name once and no blank lines, wrapping only an oversized component. Genuinely narrow terminals keep the verbose block.

## Earlier v80 history

- v80.24 extended conservative model supersession for plain GPT/Claude names, retaining exclusions for ambiguous, preview and variant models.

- v80.23 improved Grok version-supersession fading, with regression coverage across report variants and themes.

- v80.22 recommended current main as the supported distribution during rapid development, with source-ZIP/Git and Windows/macOS installation guidance. Packaged GitHub Releases remain paused unless policy explicitly changes.

- v80.21 improved model-supersession fading, parallel quota acquisition, shared credential discovery and bounded nonblocking account refresh with diagnostics; these behaviors remain in newer versions.

- v80.15-v80.20 introduced the four-column Relative CCost comparison with `--all-models` exact GitHub USD/M tiers, shared tier-aware price ordering and non-destructive metadata state under cache/state/. They gave release-date metadata independent health with classified sources, bounded non-blocking retries, failure logs and Diagnostics coverage, plus concise Diagnostics endings and launcher-path error hints. They also added hourly Copilot refresh with pinned CCost, 15-minute V2 checks, sleep/wake recovery and one-hour cache age; verified priced Watch/report ✦ New Models, sanitized metadata evidence, root logs/, safe Diagnostics archival/cleanup/staging, support instructions, runtime isolation, bounded history and metadata/refresh regression coverage.

- v80.11-v80.14 added simulated macOS compatibility in Diagnostics, Windows path/release-check fixes, sanitized V1 SQLite read-error guards with read-only triage and Windows-safe synthetic SQLite cleanup.

- v80.8-v80.9 aligned Watch session subtotals with visible rows (run-scoped CCost preserved) and unified the Windows launchers under a persistent PowerShell session with corrected Ctrl+C and error handling.

- v80.7 added shared Simple HTTP account providers and adapters for OpenRouter, DeepSeek and MiniMax, with sanitized diagnostics and no fabricated CCost.
- v80.6 made Watch survive temporary source outages and retry V2 without a V1 fallback; v80.5 scoped read-only V1→V2 migration-gap notices to report windows, never merging histories or showing them in Watch.

- v80.0 established the clean 0BSD public-repository baseline with a fresh root history, retaining the Python functionality and cross-platform launchers, explicit bounded test-suite membership and public product identifiers.
- v80.1 introduced Cost Guard as an OpenCode AI usage, cost and quota tool in the README, with static Watch/report/Token Mix images, an early quick start and the detailed contracts linked in `docs/usage-and-cost.md`.
- v80.2 added the OpenAI token-expiry explanation: the next OpenCode prompt renews it; Cost Guard never refreshes or writes credentials.
- v80.3 added provider-supplied sign-in remedies and kept prompts active during verified V2 background jobs, with continuing duration, background status and resumed model work attributed to the same prompt; jobs themselves add no usage.
- v80.4 moved Diagnostics launchers under `development/windows|macos/`, keeping public launcher folders to normal report and Watch with validator-enforced placement.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
