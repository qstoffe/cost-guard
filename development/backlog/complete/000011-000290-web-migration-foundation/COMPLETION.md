# FR 000290 completion

Delivered in Cost Guard v80.80, 2026-10-26.

## Outcome

Added the optional `src/application/` report facade, immutable JSON-ready result/error/progress contracts and explicit export allowlists. It calls existing ReportService use cases directly, including the separate deep historical Token Mix method. Decimal strings preserve exact values; null, zero, unknown/incomplete pricing and telemetry, CCost versus billing and existing report-duration/context semantics remain independent. Detail retains complete root/child history and stable event/request references. FR000200's running snapshot metrics are inherited, not copied into another analyzer.

Each admitted job owns a fresh one-shot service in a serialized application owner. Concurrent/reentrant callers receive busy; previously used/live services are rejected without closing foreign schedulers. Job cleanup closes accounts on success or error. Unexpected faults discard the entire result and use the existing reporter; cleanup faults propagate. The composition root must supply canonical dependencies and own any external context lifetime; no HTTP host or second account scheduler is introduced.

Schema/application identity, per-view sequence and per-root hashed revisions are separate. Per-root snapshot evidence does not claim a cross-root/provider transaction. Account observations carry their own freshness, status and safe classified error facts. Arbitrary provider observations, account/source filesystem locators, raw exception text and pricing diagnostics do not cross the boundary. Intentional user content such as session titles/previews still requires the future adapter's privacy/security boundary.

CLI, Diagnostics, Watch, launchers and standalone operation are unchanged; no new runtime dependencies, source mutations, browser, web server, permanent release gate, ZIP or GitHub Release was added.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, all 96 files, zero failures (final run 57.8 seconds).
- Focused facade tests compare exact numerical and semantic fields to existing reports using shared synthetic canonical V1/V2, native V1 SQLite and current V2 service fixtures. Coverage includes running/completed/aborted prompts, compaction/child work, subscription evidence, missing telemetry/prices, independent account errors/freshness, DST date bounds, exact Decimal/null/zero, stable identities, immutable detached export, typed failures, repeated cleanup and ownership/reentrancy. Complete 151-prompt detail remains uncapped; copied histories retain 151 distinct requests rather than 302 records.
- CLI help/version and Diagnostics import succeed with application/web imports blocked.
- Read-only real-installation V2 probe: latest-session list (limit 1) matched the existing service exactly for identity, CCost, report execution duration and completeness; one row, all account work closed. Cache/metadata were isolated in owned scratch. No model inference, account quota request, source write or shared-service restart. This is bounded report proof, not full live Web/account/platform parity.
- `py -3 development/tools/validate_package.py --working-tree`: PASS; only existing design-size warnings, no hard-budget failures.
- Original FR and PLAN attachment bytes are preserved. Exact native nextState is included; retention prunes nothing and the identity high watermark remains 400.

## Knowledge and follow-on work

Updated the architecture overview, report/application contract, CODE_MAP and runtime-failure policy. The reports contract contains the mode-to-view parity inventory for FR000380. Journal assessment: **no-update**; this delivery introduces a boundary, not new independent operational/performance learning requiring another topic.

FR000300 can compose the factory into a separately secured HTTP adapter. Runtime security, admission bounds, live scheduling, browser UI, launchers and full supported-platform/live-account parity remain later approved work. The original delivery map remains in this bundle; no future FR/state was edited.
