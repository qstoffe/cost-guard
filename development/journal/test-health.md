# Test system health

Source revision: 269b570b79ff8f4639f325f952ffe49a4f266ba0
Checked revision: 269b570b79ff8f4639f325f952ffe49a4f266ba0
Last checked: 2026-10-26
Status: current

## Summary

Scheduled Test Health assessment at ordinary milestone 20, replacing milestone 15. **Retain the existing tests, fixtures and runner.** Current source and the five intervening FR reports do not demonstrate disproportionate orchestration, repeated setup failures or new test-to-test coupling warranting replacement. This is a source-backed no-change decision, not proof of optimality or current green execution.

Development-only delivery: journal/navigation and exact native maintenance state only. Product suites, validator, Diagnostics, live/native/UI probes, release gates and version updates were deliberately NOT RUN. No inference or private session-history access occurred. Current elapsed time, flakiness, executed/skipped counts and paid-test cost remain unknown. Historical outcomes below are not fresh PASS receipts.

## Evidence

### Whole-repository inventory and runner

Read-only installed `maintenance_evidence.py inventory --repo-root .`: 412 tracked/nonignored text/config files (198 source/config, 136 test-related, 78 documentation); 26 binary/over-1-MiB files excluded. Git internals and ignored runtime artifacts are outside scope. Zero exact-byte duplicate groups does not establish semantic uniqueness. `python development/tools/code_inventory.py --json` reports 171 runtime modules, 13 development tools and 128 test-tree Python modules, including the 17 fixture modules counted once (not an additive subtree).

AST-only evaluation of runner declarations against top-level `development/tests/test_*.py`: 101 Quick + 4 Full-only = all 105 files, no missing/stale/duplicate entries. AST finds 1,341 syntactically named test methods, not an executed count. Since milestone 15, four files were registered: Web views, Live and Diagnostics in Quick, session-detail scale coverage in Full-only. Four workers, isolated per-file unittest subprocesses, test-mode/UTF-8 environment, 25-second Quick and 240-second Full deadlines remain. Full-only files start first; profile/pattern default is one worker. Profiles remain startup 6, sources 8, analysis 4, runtime 25, not exhaustive coverage promises.

Ten static test-to-test source/target import edges remain unchanged: model-pricing presentation; runtime-errors (two); token-mix economics; V2 synthetic attribution; v784 regressions; Watch lifecycle; Watch subtotals (two); Watch tool activity. New tests reuse responsibility-owned fixtures, not sibling test modules. These are bounded legacy coupling, not new permanent exceptions. The Node VM scripts use the optional installed runtime with skip conditions, no package installation, browser or product/build dependency. Three small DOM substitutes serve different contracts (finite navigation, live replay, keyed selection); textual similarity alone does not justify a shared framework.

### Critical outcomes and source/test mapping

Test paths below are under `development/tests/`. Inspection establishes intended protection, not measured coverage.

| Unique risk / outcome | Source owner | Evidence inspected or retained route |
| --- | --- | --- |
| Readiness budget never becomes auth retry/repeated CLI wake | `src/sources/read_recovery.py` | `test_connectivity_reliability.py`: virtual deadlines, exact attempts/waits, forbidden cache/CLI calls, fake V2 service |
| Credential replacement cannot resurrect stale quotas or mutate credentials | `src/accounts/openai_subscription.py`, acquisition | `test_openai_account_switch.py`: unchanged synthetic SQLite/auth bytes, stale-alias denial, gated late-response replacement |
| Unknown valuation differs from zero and actual billing | `src/analysis/valuation.py`, report projection | `test_application_reports.py`: independent Decimal/null expectations alongside shared-report parity across modes/generations; parity alone is not an independent formula oracle |
| Concurrent disposable cache remains rebuildable | `src/cache/database.py`, repository | `test_cache.py`: generations, WAL/busy timeout, bounded readers/writers, insert-only first sightings |
| Tabs share canonical Watch acquisition, source loss is not completion | `src/watch/acquisition.py`, `src/application/live.py`, `src/web/events.py` | `test_web_live.py`: CLI parity, detached exports, outage/schema distinction, replay/gap/foreign-instance bounds; optional `integration/web_live.cjs` checks actual assets |
| Complete detail is not a page total; omitted running rows gain no evidence | `src/application/session_detail.py`, `src/reports/session_history.py` | `test_web_session_detail.py`: 100/1,000/10,000-row pages, totals, no unchanged reanalysis, freeze, retained omissions/time, late child, unknown pricing, auth/cursor errors; `integration/web_session.cjs` covers keyed focus/selection |
| Navigation cannot silently refresh/deep-scan or reinterpret costs/text | `src/web/assets/app.js`, `reports.js`, `render.js` | `test_web_views.py` / `integration/web_views.cjs`: real HTTP/facade/assets, 55 roots/151 rows, frozen/refresh/stale/missing/empty, account/tier data, explicit-only history, exact Decimal sorting, hostile Unicode text |
| Progress cannot starve host control/backpressure into deadline | `src/web/jobs.py` | `test_web_runtime.py`: deterministic 130-message fixture checks 64-message drain boundaries/completion; separate finite process tests retain cancellation/deadline/orphan evidence |
| Two-checkout auth stays isolated; diagnostics omit private content | `src/web/security.py`, observations, `development/tools/diagnostic_web.py` | `test_web_runtime.py`: old credentials rejected; `test_web_diagnostics.py`: actual CookieJar/two hosts, allowlisted counters, private canaries, malformed/oversized state, persistence failure |
| HTTP framing, process ownership, platform and package-negative risks remain distinct | Web HTTP/lifecycle/platform owners; validator/Diagnostics | Existing runtime/lifecycle/Windows/macOS tests and Full-only foundation/Diagnostics/parity files retained; fake platform evidence is not native acceptance |

Watch Today rollover remains owned by `src/watch/today_ccost.py` / `test_watch_today_ccost.py`; HTTP CSRF/rebinding/framing/privacy denies remain in `test_web_runtime.py`. Native lock/crash/orphan protection remains in `test_web_lifecycle.py`; platform tests retain ABI/resource ownership rather than generic shared setup. The reserved `integration/live/` remains a placeholder, not a live-model runner. Real-source/native probes are explicit opt-in evidence routes, not automatic unit selection.

### Recent outcomes and causal classification

Bounded committed sample since milestone 15: completion reports for FRs 000340–000380 and current test/runner diff. FR 000340 records 102 files / 39.6 s; 000350 records 103 / 42.3 s; 000360 delegates final outcomes to its PR and supplies no final elapsed total in its report; 000370 records 104 / 41.1 s; 000380 records 105 / 41.4 s. Different revisions/conditions are not a controlled speed comparison. No historical failed run counts as PASS. Each report records real-source checks; only 000380 additionally records native Windows checks. Native macOS, physical suspend/soak and visual/assistive-technology acceptance remain unverified.

Classify failures against current source: 000340's missing-session expectation changed intentionally and an indentation error was repaired. 000350 repaired stale HTTP/thread inventory assertions, fixture scope and a real composition-clock omission. 000360 isolates lifecycle fixtures from unintended real integration access. 000370's real report timeout exposed **product IPC backpressure**, not a bad test: `ReportJobs.tick` now drains at most 64 messages, with a deterministic regression instead of needing a real history scan to catch recurrence. 000380 repaired the HTTP-detail fixture's newly required lifecycle dependencies; overlapping source-change/live probes interfered and sequential rerun passed. That is probe coordination friction, not evidence that dropping isolation/deadlines is safe. README-cap repairs are documentation friction, not authority to weaken test/product limits.

A fresh fully paginated GitHub Actions runs query returned one page, total_count 0; no tracked `.github` files exist. CI timing/flakiness evidence is unavailable. Private transcripts and other owners' scratch were not accessed. Prior fixture/scheduling measurements remain attributed in `PERFORMANCE.md`, not remeasured here. Earlier Windows socket-close and Beta-folder expectation repairs remain historical, not current failures; quota 401 never establishes model-login failure.

### Simpler alternatives considered before editing

Monolithic discovery loses hard per-file isolation; automatic glob registration changes Quick admission without a current registration defect. Mock-only transport tests lose framing/cookie/process evidence. Replacing parity with copied arithmetic creates another metric engine; parity must still coexist with independent semantic expectations. A universal DOM fixture couples different asset interfaces without demonstrated repeated failures/savings. Removing Full discards package-negative/Diagnostics/scale risks. None is justified by the available evidence.

Exact thread-root/source-text guards and ten legacy import edges remain refactor-sensitive debt. Move a legacy edge into its responsibility-owned fixture when that area changes; characterize outcome-equivalent wiring protection before replacing static checks. Do not preserve an internal shape merely because it is tested, or erase its only safety evidence. No tested mechanism changed, so no seeded-failure experiment or before/after execution improvement is claimed. Gate dependencies, fixture layers and orchestration are unchanged; registration grew with distinct delivered risks.

## Next investigations and delivery integrity

When shipped changes authorize execution, inspect per-file durations/skips before adjusting Quick deadlines, particularly optional Node, HTTP and spawn/PowerShell tests. The Web-view child permits 60 seconds while Quick bounds its whole file at 25 seconds: a tighter outer ceiling, not observed flakiness; measure before changing either. Keep hard cleanup bounds. Reproduce probe interference sequentially before attributing failures to the product. Native macOS/browser accessibility remains outstanding; this audit neither closes acceptance limits nor authorizes UI.

Architecture assessment: **no-update** to diagrams/module contracts; no responsibility/dependency boundary changed. Journal assessment: consolidate this baseline and its INDEX route in place. Exact native maintenance state advances Test Health to 20; identity high watermark stays 400, retention prunes nothing, todo is empty at the inspected base. Completed prerequisites/reports and native limitations remain intact. No foreign stash/unfamiliar work was found in the isolated clone; no dependency/recovery evidence relies on disposable exports. No raw inventory, credential, private payload or machine path is published.

## Rejected hypotheses

- Test growth or zero byte duplicates proves excess/health: unique risks and measured burden must support that judgment.
- Historical green suites prove current runtime/native readiness: revision/platform/NOT RUN limits remain binding.
- Quota 401 proves model login failed: resource/method compatibility differs from model authentication.
- Development-only audits require Full, validator or version bumps: the active workflow deliberately excludes them.
- Legacy coupling/similar DOM substitutes justify a broad rewrite without a demonstrated cause: retain focused follow-up instead of another framework.
