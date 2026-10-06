# Cost Guard version history

## v80.3 — 2026-10-06

- Explain rejected sign-ins with the fix: reconnect OpenAI or sign in to GitHub again in OpenCode, or run `claude auth login`. Account providers supply the short remedy that Watch shows after `Quota unavailable`; the report prints the full sentence.
- Keep a Watch prompt running while verified OpenCode V2 background work (e.g. a backgrounded shell) is outstanding: Duration continues, Calls/CCost stay usage-based, a `background: shell 2m18s` status row and `background shell` footer replace `Idle`, and the automatic resume stays on the same row. Model work resumed after such jobs, previously outside every prompt row, now counts on its prompt; native job IDs are never shown.

## v80.2 — 2026-10-06

- Explain an expired OpenAI OAuth token: the report says it renews automatically on the next OpenAI prompt in OpenCode, and Watch adds a short renewal hint to `Quota unavailable`. Cost Guard still never refreshes or writes credentials.

## v80.1 — 2026-10-06

- Introduce Cost Guard as an OpenCode AI usage, cost and quota tool, with static Watch/report/Token Mix images and an early Windows/macOS/CLI quick start.
- Preserve detailed mode documentation and link the exact counting, valuation and symbol contracts in `docs/usage-and-cost.md`; runtime behavior and screenshot-independent release semantics are unchanged.

## v80.0 — 2026-10-06

- Establish the clean 0BSD public-repository baseline with a fresh root history, retaining the current Python functionality and cross-platform launchers.
- Keep public documentation within existing budgets and make bounded test-suite membership explicit: Watch tool activity runs in Quick/runtime, and unassigned or stale test declarations fail before execution.
- Align product/version documentation and HTTP product identifiers with the public release; preserve read-only OpenCode integrations, CCost, quotas, Token Mix and Watch accounting.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
