# Runtime software-failure policy

## Invariant and entry points

Expected product conditions use local domain handling. Unexpected software faults default fatal; recovery is permitted only with an honest ERROR result and correctness-preserving isolation. Never add a generic log-and-continue catch to valuation, usage, attribution, cache or lifecycle code.

`cost-guard.py:run` and the Diagnostics script's guarded import callback own initialization and final status. Application `SystemExit` is a defect except within Diagnostics' narrowly scoped argparse parsing; shell exits occur outside the guard. Watch Ctrl+C remains clean and normal interactive interrupts return 130. Forgotten thread failures are reported immediately, retained as a pending fatal incident and wake the main boundary; Watch cannot misclassify that wake as user Ctrl+C. No process resurrection, native/OS exception translation or shared-service stop is involved.

## Production execution-root inventory

| Root | Policy | Truthful failure surface |
| --- | --- | --- |
| Main report/Watch | Final fatal boundary after specific product handling | `COST GUARD FAILED`, status 1, log and crash report |
| Explicit Diagnostics | Same final boundary before integration imports; isolated acquisition sections may return ERROR metadata | Fatal main workflow errors are non-zero; failed sections are visible in the bundle |
| `cost-guard-v2-events` / `LiveEventPump._run` | SourceError uses existing resync; software Exception is logged and hints discarded | Watch status ERROR until authoritative resync; failed rebuild propagates |
| `cost-guard-startup-progress` / `_animation_root` | Disable transient animation; no ownership of calculated report state | ERROR through startup sink or independent plain stderr |
| `claude-metadata` / `_ControlReader._read` | Expected OSError/JSON/queue/end become transport state; software faults discard reader output | Typed reader failure → optional provider ERROR, never default thread traceback |
| `cost-guard-model-metadata` / `WatchModelDiscovery` worker | At most one release-date refresh; prices, retrieval time and in-run CCost never change; a software fault discards that result | Classified `unexpected_internal_error` in metadata state/Diagnostics plus software log; bounded retry continues |
| Future/unclassified threads | No assumed isolation; `threading.excepthook` defaults fatal | Original stack/report plus pending fatal main-thread handoff |
| Unraisable/finalizer code | Defensive hook; no repr(object)/err_msg/local capture; defaults fatal | Log/report and pending failure before successful application return |

## Whole-runtime exception audit

This v80.10 audit covers every production broad catch, including those removed or narrowed. Existing specific decode/number/schema catches remain adapter-owned operational contracts, not software errors merely because they use exceptions.

| Area / site | Contract after audit |
| --- | --- |
| Config `read_jsonc` | Only I/O, encoding and JSONC ValueError become sanitized ConfigError; other defects propagate |
| Cache transaction | BaseException rollback, then rethrow; never swallowed |
| Accounts auth JSON and OpenAI JWT | Narrow file/encoding/JSON/token-shape failures; unexpected implementation faults propagate |
| Copilot/OpenAI request adapters | Expected OSError/network/auth states retain normal handling; unexpected acquisition faults discard this account result, log and produce ERROR |
| HTTP account response parsing | Expected transport and bounded JSON-tree validation are handled at those calls; internal normalization faults log and replace only that account with ERROR |
| Anthropic optional reader | Expected OSError/ValueError produce provider error; unknown faults reach ReportService's isolated provider boundary |
| Claude discovery / usage | Operational transport/metadata errors retain policy; unknown discovery faults reach isolated provider boundary; unknown quota faults log and clear quotas into ERROR |
| ReportService `_quotas` | Failed provider result becomes explicit provider ERROR, not silent omission; materialize generators before accepting observations; unexpected orchestration outside acquisition propagates |
| Pricing promotion-cache decoding | Narrow malformed persisted data; no generic catch |
| Pricing probe / refresh | External fetch OSError becomes typed PricingUnavailableError, including cold/no-cache outage; only that domain condition permits normal unavailability/verified cached fallback; software faults propagate |
| Pricing optional release enrichment | Every outcome is classified (DNS/connection/TLS/HTTP/timeout/parse/schema/match); verified dates are kept. An unexpected enrichment fault is logged, recorded as `unexpected_internal_error` and retried with backoff; pricing itself is unaffected |
| Reports promotion wording | Narrow Decimal/ValueError formatting fallback; programming defects propagate |
| Model availability / history filter | Expected SourceError/OSError fail open with ordinary warning; software faults log, return the unchanged full catalog/history and show ERROR |
| Source availability fallback | Only operational source/I/O failures try another established availability adapter; software faults propagate to the visible report boundary |
| Watch account orchestration, quota projection, token valuation | Remove generic swallowing/stale output reuse; software defects propagate fatal |
| Watch event worker / progress / Claude worker | Explicit contracts in the root inventory above; no raw thread failure path |
| Runtime reporter/hooks | Defensive final/emergency BaseException boundaries; original incident has priority, reporting cannot recurse |
| Diagnostics acquisition sections | Failed isolated sections return sanitized ERROR metadata and log unknown faults; normal operational conditions remain unlogged |

The shared reporter is active only during a user-facing guarded execution; direct library/test calls do not install global hooks or create diagnostics implicitly. Tests install a reporter with an isolated root when exercising software faults.

## Artifacts, privacy and lifetime

`logs/errors/` contains daily software-error logs after an actual defect and metadata failure-period events (first failure, change, bounded summaries). Actual metadata recoveries go to `logs/recovery/`. `cache/state/model-metadata.json` owns persistent health/backoff, not error evidence; legacy state is migrated without deletion and excluded from retention/pruning. `logs/crashes/` has an exclusive-created report per fatal incident; PID plus bounded suffix avoids collisions. Logs/reports reference each other. Runtime artifacts never ship.

Full chained stack structure includes file/function/line and exception type, never source lines/locals or arbitrary exception message text. Paths are package-relative; external frames omit directory paths. No arbitrary exception serialization, object repr, prompt/provider/auth payload capture or automatic full Diagnostics collection occurs. Individual reports can be sent directly to a maintainer after user review.

Episodes use component/type/final stack identity, never message text. First occurrence logs the stack; repeats count in memory, flush after 60 seconds, on changed fingerprint, recovery or process end. The episode map is bounded. Cleanup scans errors/crashes/recovery, at most 2048 entries each, removing only owned event filenames older than 30 days; maintenance is fail-soft/non-recursive and never deletes metadata state.

Crash reporting uses plain stderr independently of normal renderers, optionally red for a working terminal. Fatal reports and stopping product errors (not Ctrl+C, intentional Watch ends or self-healing outages) end with the absolute, OS-specific Diagnostics launcher path; Diagnostics is never started automatically. Primary I/O/formatting/render failure emits an emergency original-type notice and cannot turn status into success. Process entry points retain safety hooks through interpreter teardown; reusable library/test executions restore prior hooks. Retired Watch pumps have their stop flag set and cannot publish further results. Python shutdown/native corruption/force-kill cannot be guaranteed.
