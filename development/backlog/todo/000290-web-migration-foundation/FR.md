# FR 000290 — Shared application boundary for an incremental Web migration

## Outcome and scope

Introduce the smallest additive application boundary needed for Web Beta to consume Cost Guard's existing analysis and report projections. This is not a rewrite of the calculation engine or a mandatory conversion of CLI into an HTTP client. The delivery map and cross-cutting owner decisions are in [PLAN.md](attachments/PLAN.md) in this bundle; later FRs refer to it by FR identity when the bundle moves.

Normal priority. No web prerequisite. Coordinate with the separately approved FR000200: its running-metric improvements must be inherited, not reimplemented or overwritten. Do not alter another selected/in-progress FR, including FR000210, or reserve a product release version.

## Required behavior

1. Provide a transport-neutral application facade over existing report use cases: normal overview, all-models, session listing/detail, date/range and historical Token Mix. Use `ReportService`, canonical sources, account/pricing boundaries and existing acquisition/cache owners; do not parse terminal output or call the CLI as a subprocess to obtain reports.
2. Preserve every calculation and eligibility rule. In particular CCost is reference valuation, not actual billing; incomplete telemetry/pricing stays incomplete; request/subagent/clone deduplication, root scope, compaction, context warnings, account attribution and local/UTC period distinctions retain their existing owners. Match the existing report execution-duration metric rather than silently switching to Watch duration. Do not reuse a capped global Watch projection as complete session history.
3. Define explicit result/error/progress DTOs for a future JSON adapter. Preserve exact Decimal values through decimal strings, stable session/event/request identities, null versus zero, incomplete/unknown evidence, source and acquisition status, observed-at times and report scope. Do not serialize arbitrary dataclasses wholesale: source objects, credentials, raw provider responses, private paths and internal diagnostic state must not cross the boundary. Browser sorting/display must not require independent business calculations.
4. Distinguish a consistent session snapshot from independently acquired account observations; do not label an entire multi-provider response as transactionally atomic. Give account/source observations their own freshness and error facts. Separate application-instance/schema identity from source revision and per-view update sequence.
5. Explicitly define ownership and cleanup. `ReportService` has mutable clocks, acquisition caches and account lifecycle, and one-shot build currently closes account work. A long-lived host must not concurrently share that instance across arbitrary HTTP threads or let a snapshot report close the live scheduler. Choose a narrow serialized owner or isolated job contexts with publication of immutable results. Reuse shared pure analysis; avoid speculative enterprise buses or a second account scheduler.
6. Keep old CLI startup, output, launchers and standalone operation intact. Web-only imports/dependencies must never be imported by ordinary `cost-guard.py`, CLI help/version, Diagnostics, domain or analysis. A shared bug fix can benefit both clients through its existing semantic owner, not by copying the engine into Web.

## Acceptance

Use existing synthetic V1/V2, report, pricing and Watch fixtures to compare old report projections against the new facade for the same data, configuration, clock and catalog. Include running/completed/aborted prompts, compactions, child work, missing telemetry/prices, subscription-versus-billing and DST/period cases. Assert exact numerical/semantic parity, not merely similar rendered strings. Prove web dependencies can be absent while CLI still runs, repeated calls close owned resources, and source/account errors remain honest rather than becoming zero or success.

Record a small mode-to-view parity inventory for later FR000380. Implement only the application seam and focused tests/documentation here; do not add a browser, tray process, new pricing formula, source mutation or launch-mode change. No new permanent release gate is introduced.

Current owner pointers: `src/reports/service.py`, `models.py`, `prompt_rows.py`, `prompts.py`, `acquisition.py`; `src/analysis/`; `src/bootstrap.py`; `development/architecture/modules/reports.md` and `CODE_MAP.md`. Re-read current implementations rather than treating these paths as a mandated module structure.
