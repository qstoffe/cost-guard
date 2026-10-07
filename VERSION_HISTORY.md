# Cost Guard version history

## v80.8 — 2026-10-07

- Make Watch session `Σ` the Decimal subtotal of exactly its displayed prompt/event rows, preserving unresolved `?`/`N/A` and native zero-cost compaction behavior. Attaching mid-prompt now includes that row's full known CCost in its session subtotal; row eviction changes the subtotal, not run accounting.
- Keep `Watch total CCost` and `Token Mix %` run-scoped and deduplicated: completed pre-Watch requests remain excluded, so the run total may intentionally differ from session subtotals. Remove the unused per-session run partition and include row-subtotal amount/completeness in dashboard change detection.

## v80.7 — 2026-10-07

- Add maintained Simple HTTP Account Providers behind the existing account abstraction: bounded read-only Bearer HTTPS GET, declarative JSON mappings, per-credential identities, isolated fail-soft observations and sanitized diagnostics, without custom HTTP configuration or new runtime dependencies.
- Add OpenRouter authenticated-key spend and genuine key-limit capacity, DeepSeek separate native total/granted/topped-up balances without fabricated percentages, and a first-class MiniMax Token Plan adapter for supported native windows/count/percentage/reset variants. Report/Watch keep the shared account renderer and lifecycle; account observations never establish historical attribution or CCost.

## v80.6 — 2026-10-07

- Keep a running Watch alive when its selected OpenCode source is temporarily unavailable: the last dashboard stays visible with `OpenCode V2 source unavailable · retrying every 5s`, the same source is retried without V1 fallback, CLI starts or extra account requests, and V2 resumes only after a fresh snapshot and a restarted event stream. A restarted V2 service on a new port is picked up from its rewritten registration. Unsupported schemas still end Watch; data that stays unreadable for about a minute does too.
- The Windows Watch launcher keeps its window open after a non-zero Cost Guard exit, showing the error and `Cost Guard Watch exited unexpectedly (code N).` until Enter; a clean Ctrl+C stop still closes it.

## v80.5 — 2026-10-07

- Scope V1→V2 migration-gap notices to what is shown: Watch never displays them; normal reports add an informational note only while missing/newer V1 activity reaches the latest-prompt sample, date reports only for overlapping periods, session reports only for the requested root, and all-history views for any gap. Diagnostics still records the full counts; source selection and non-merging are unchanged.

## v80.4 — 2026-10-07

- Keep the user-facing `windows/` and `macos/` folders to Cost Guard and Cost Guard Watch; the unchanged Diagnostics launchers move to `development/windows/` and `development/macos/`, and package validation rejects extra public launchers.

## Earlier v80 history

- v80.0 established the clean 0BSD public-repository baseline with a fresh root history, retaining the Python functionality and cross-platform launchers, explicit bounded test-suite membership and public product identifiers.
- v80.1 introduced Cost Guard as an OpenCode AI usage, cost and quota tool in the README, with static Watch/report/Token Mix images, an early quick start and the detailed contracts linked in `docs/usage-and-cost.md`.
- v80.2 added the OpenAI token-expiry explanation: the next OpenCode prompt renews it; Cost Guard never refreshes or writes credentials.
- v80.3 added provider-supplied sign-in remedies and kept prompts active during verified V2 background jobs, with continuing duration, background status and resumed model work attributed to the same prompt; jobs themselves add no usage.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
