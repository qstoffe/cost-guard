# Cost Guard version history

## v80.11 — 2026-10-08

- Run privacy-safe deterministic macOS-behavior simulations inside Diagnostics on Windows, macOS and Linux. Record per-check PASS/FAIL/SKIP and totals in diagnostics.json and summary.txt; no access to live credentials or OpenCode data, no native macOS guarantee.
- Include bounded CLI discovery, XDG directories, V1 override, macOS app installation evidence, absent V2 service registration and Mac launcher contract checks; isolate execution with a 30-second subprocess timeout and sanitized results.

## v80.10 — 2026-10-07

- Own unexpected Python failures before application/Diagnostics imports and at the final process boundary. Fatal faults show `COST GUARD FAILED`, return non-zero, and write a daily software-error log plus a standalone privacy-conscious crash report; intentional Ctrl+C/help/usage and expected operational conditions remain distinct.
- Add explicit isolated worker/provider ERROR states, authoritative Watch observer resync, defensive thread/unraisable hooks, in-process repetition summaries, emergency stderr reporting and best-effort 30-day retention. Healthy runs create no software-error log; no third-party dependency or full Diagnostics invocation is added to the crash path.

## v80.9 — 2026-10-07

- Unify all three Windows launchers behind one persistent PowerShell session in the original console. The outer batch exits before Python runs; explicitly restored Ctrl+C handling stops Watch without a batch confirmation. Completion, failure and Ctrl+C leave an ordinary package-root prompt, without a Watch-only Enter-to-close path. Python 3.11+ detection and actionable errors live in the shared launcher boundary.
- Treat only a typed session-disappearance/archive event as a non-fatal session Watch end. Unexpected ValueError and other terminal runtime/source failures reach bootstrap's non-zero result; Ctrl+C during Watch initialization also remains an intentional stop.

## v80.8 — 2026-10-07

- Make Watch session `Σ` the Decimal subtotal of exactly its displayed prompt/event rows, preserving unresolved `?`/`N/A` and native zero-cost compaction behavior. Attaching mid-prompt now includes that row's full known CCost in its session subtotal; row eviction changes the subtotal, not run accounting.
- Keep `Watch total CCost` and `Token Mix %` run-scoped and deduplicated: completed pre-Watch requests remain excluded, so the run total may intentionally differ from session subtotals. Remove the unused per-session run partition and include row-subtotal amount/completeness in dashboard change detection.

## v80.7 — 2026-10-07

- Add maintained Simple HTTP Account Providers behind the existing account abstraction: bounded read-only Bearer HTTPS GET, declarative JSON mappings, per-credential identities, isolated fail-soft observations and sanitized diagnostics, without custom HTTP configuration or new runtime dependencies.
- Add OpenRouter authenticated-key spend and genuine key-limit capacity, DeepSeek separate native total/granted/topped-up balances without fabricated percentages, and a first-class MiniMax Token Plan adapter for supported native windows/count/percentage/reset variants. Report/Watch keep the shared account renderer and lifecycle; account observations never establish historical attribution or CCost.

## v80.6 — 2026-10-07

- Keep a running Watch alive when its selected OpenCode source is temporarily unavailable: the last dashboard stays visible with `OpenCode V2 source unavailable · retrying every 5s`, the same source is retried without V1 fallback, CLI starts or extra account requests, and V2 resumes only after a fresh snapshot and a restarted event stream. A restarted V2 service on a new port is picked up from its rewritten registration. Unsupported schemas still end Watch; data that stays unreadable for about a minute does too.
- Introduce Windows Watch error visibility on non-zero exits; superseded by the common persistent PowerShell launcher in v80.9.

## Earlier v80 history

- v80.0 established the clean 0BSD public-repository baseline with a fresh root history, retaining the Python functionality and cross-platform launchers, explicit bounded test-suite membership and public product identifiers.
- v80.1 introduced Cost Guard as an OpenCode AI usage, cost and quota tool in the README, with static Watch/report/Token Mix images, an early quick start and the detailed contracts linked in `docs/usage-and-cost.md`.
- v80.2 added the OpenAI token-expiry explanation: the next OpenCode prompt renews it; Cost Guard never refreshes or writes credentials.
- v80.3 added provider-supplied sign-in remedies and kept prompts active during verified V2 background jobs, with continuing duration, background status and resumed model work attributed to the same prompt; jobs themselves add no usage.
- v80.4 moved Diagnostics launchers under `development/windows|macos/`, keeping public launcher folders to normal report and Watch with validator-enforced placement.
- v80.5 scoped V1→V2 migration-gap notices to report windows; Watch omits them and Diagnostics retains full counts, without merging or source changes.

## Earlier versions (v1-v78)

- v78.0 established the Python baseline: Python 3.11+, standard-library runtime, bounded layers, optional JSONC, public 0BSD packaging and cross-platform launchers. The v78 generation added read-only V1 SQLite and V2 registered-service HTTP/events, source selection and migration-gap diagnostics without merging or repairing OpenCode history.
- Retained causal child/subagent attribution, separate compactions, archived-root usage, exact fork-clone de-duplication and disposable revision-sensitive SQLite caching. V2 terminal evidence and session-move context epochs preserve request identity, duration and accounting without treating inactivity as completion.
- Separated observed usage, CCost reference valuation and actual billing. CCost uses Copilot AI-credit-equivalent units; partial pricing and missing telemetry remain explicit. Comparisons reprice recent completed prompts, retain tiers/promotions and use a hidden synthetic mix only for zero-data sorting. Token Mix displays balanced shares, per-category CCost and optional all-history model summaries.
- Added compact available-model reports, full-catalog/session/date modes, request-proven effort labels, independent colors and amber Next-Ictx warnings. Watch retains session grouping, aligned tool/failure/running/TODO status, run/session CCost totals, bounded quota recovery, fixed geometry and terminal cleanup.
- Added read-only provider/account discovery, native quota windows, aligned remaining bars, resets and Copilot Remaining/day/workday without historical account attribution. Claude Code discovery and quotas remain optional/experimental. Diagnostics omits private payloads and combines bounded Full tests with package validation.
- Earlier PowerShell generations established causal attribution, context estimation, pricing-cache safety, configurable colors and low-idle-cost Watch constraints. v77.0 remains the historical behavioral reference for the Python rewrite.
