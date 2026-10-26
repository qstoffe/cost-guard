# Test system health

Source revision: 17e6810c620ac007a11bec823e437ba58c2eb295
Checked revision: 17e6810c620ac007a11bec823e437ba58c2eb295
Last checked: 2026-10-26
Status: current

## Summary

Scheduled Test Health assessment at ordinary milestone 15, replacing the milestone-10 baseline. Retain the existing test system: the inspected additions protect distinct application, HTTP, lifecycle and platform-adapter risks without another orchestration layer or new test-to-test imports. No demonstrated disproportionate mechanism justifies a rewrite. This is an evidence-backed no-change decision for tests, fixtures, runners and runtime, not a claim that all tests are optimal.

This development-only delivery changes journal and native state only. Product tests, validator, Diagnostics, live/UI probes, release gates and version updates were not run. No model inference or private history access occurred. Current duration, flakiness and paid-test cost are unknown; historical outcomes are not fresh PASS receipts.

## Evidence

### Inventory and ownership

Reproduce read-only navigation with installed `maintenance_evidence.py inventory --repo-root .` and `python development/tools/code_inventory.py --json`. Neither imports application/test code. Whole-repository inventory: 386 text/config files (184 source/config, 130 test-related, 72 documentation); 23 binary/over-1-MiB files excluded. Git internals and ignored runtime artifacts are outside scope. Zero exact-byte duplicate groups does not prove semantic uniqueness. AST inventory: 162 runtime modules, 12 development tools and 122 test-tree Python modules, including 17 fixture modules counted once. The fixture subtree is a subset, not an additional 17 modules.

Static AST evaluation of `QUICK_PATTERNS` and `FULL_ONLY_PATTERNS` against top-level `development/tests/test_*.py` finds 98 Quick + 3 Full-only = all 101 files, no missing/stale/duplicate entries. AST finds 1,310 syntactically named test methods across the test tree, not an executed count. Since the previous source baseline `6eaa1b17090b96abcfded483d2f84f00d43da661`, six files and one spawn-safe fixture were added; runner edits only register those six files. Scheduling remains four workers, isolated per-file unittest subprocesses, test mode/UTF-8 output, 25-second Quick and 240-second Full per-file deadlines, slow Full files first. Pattern/profile default is one worker. Profiles (startup 6, sources 8, analysis 4, runtime 25) are focused subsets, not exhaustive coverage promises.

Ten distinct static test-to-test import edges remain, unchanged from milestone 10: model-pricing presentation; runtime-errors (two); token-mix economics; V2 synthetic attribution; v784 regressions; Watch lifecycle; Watch subtotals (two); Watch tool activity. These are source/target pairs, not import-statement counts or repeated test execution. New application tests reuse responsibility-owned account, source, report and snapshot fixtures; Web tests share `fixtures/web_reports.py` rather than importing sibling tests. Its intentionally blocked finite report supplies cancellable work, not an implementation worker or paid model. No new universal fixture/service wrapper was introduced.

### Critical risks and current source sampling

Test filenames below are under `development/tests/`. Source/test inspection is evidence of intended protection, not measured coverage.

| Outcome / negative risk | Source owner | Test evidence inspected |
| --- | --- | --- |
| Readiness retries share a deadline; auth/schema errors never wake/retry the service | `src/sources/read_recovery.py` | `test_connectivity_reliability.py`: virtual clock, attempt/deadline limits, forbidden CLI calls, separate fake HTTP service |
| Credential method/identity replacement cannot resurrect stale quotas or send incompatible credentials | `src/accounts/openai_subscription.py` | `test_openai_account_switch.py`: late-response replacement, forbidden token-sharing calls, distinct quota/model auth; existing responsibility fixtures |
| Unknown valuation differs from zero; clone identity and actual billing remain separate | `src/analysis/valuation.py` | `test_application_reports.py`: independent Decimal/null expectations plus parity across six report modes, V1/V2 sources, clone history, missing telemetry and DST |
| Watch accounting survives enrichment and rolls over at local midnight | `src/watch/today_ccost.py` | `test_watch_today_ccost.py` route retained; source still owns published-versus-pending history, clone/step identity and rollover |
| Disposable cache tolerates concurrent access and rebuild | `src/cache/database.py` | `test_cache.py`: generations, WAL/busy timeout, bounded reader/writer threads and insert-only first sightings |
| Optional adapter does not contaminate CLI; fresh report jobs release only their own account work | `src/application/service.py` | `test_application_reports.py`: rejected reused/Watch services, forbidden cleanup, immutable exports, sanitized failures, subprocess import denial |
| HTTP auth, CSRF, rebinding, malformed framing, traversal and injection are denied | `src/web/security.py`, `src/web/http.py` | `test_web_runtime.py`: actual loopback/raw requests, replay/expiry/foreign instance, Host/Origin checks, request limits and secret canaries; text-only browser sink wiring remains a static guard |
| Slow reports cannot block HTTP or orphan acquisition | `src/web/jobs.py` | `test_web_runtime.py`: spawn-safe finite work, cancellation, deadline, backpressure/retention, oversized result and sanitized errors; `test_web_lifecycle.py`: killed synthetic parent with real child sentinel exit |
| Restart/stop never kills an unowned process or advertises a dead host | `src/web/lifecycle.py`, `src/web/host.py` | `test_web_lifecycle.py`: OS lock/crash release, stale/reused PID/unknown endpoint refusal, birth-identity checks, main-thread readiness and cleanup |
| Native menus/launchers preserve shared lifecycle and failure ownership | Windows/macOS Web adapters and launchers | `test_windows_web.py`, `test_macos_web.py`, `test_macos_app.py`: preflight failure preserving healthy host, asynchronous Open/Exit/fatal handoff, typed ABI/callback retention, app-cache tampering/partial cleanup; fake AppKit/compiler evidence is not native Mac proof |
| Package/privacy failures remain detectable without touching installation | Development validator/Diagnostics, `fixtures/package_copy.py` | `test_foundation.py`: disposable negative copies and owning-check assertions; distinct Full-only Diagnostics and parity/performance files retained |

The reserved `development/tests/integration/live/` contains only `.gitkeep`, not a live-model runner. Integration probes are explicit real-source/native evidence routes, not automatically selected unit tests: `probe_web_lifecycle.py`, `probe_windows_web.py`, `probe_macos_web.py`. UI/native probes need separate bounded authorization; this audit did not invoke them.

### Recent outcomes and causal classification

Bounded committed sample since milestone 10: completion reports for FR 000300, 000310, 000320 and 000330, plus the corresponding current runner/test diff. Historical final Full outcomes: 97 files/40.7 seconds, 98/39.5 seconds, 99 files (elapsed not stated), and 101/41.3 seconds respectively. These are different revisions/conditions, not a controlled performance comparison. Each reports validator and real-source checks; only FR 000320 reports explicitly approved native Windows automation. FR 000330 explicitly leaves AppKit/Finder/Gatekeeper/macOS acceptance unverified. No native macOS success is inferred from synthetic tests.

Classified repairs: FR 000300's Windows socket EOF/reset/abort expectation was a platform-sensitive test assumption, now accepting closure but not timeout. FR 000320's exact Beta-folder expectation was obsolete following the authorized launcher addition; current tests still restrict exact contents rather than broadly admitting files. New Web thread roots required explicit failure-policy registration in `test_runtime_errors.py`; current diff adds the four owners and points to their fatal-handoff tests. These are real coordination points, but the sampled evidence does not show repeated setup faults or unrelated multi-suite rewrites. Repeated README-cap repairs are documentation budget friction, not evidence that the test harness is broken or authority to weaken product limits. No unrepaired failure is established by these old reports.

A fresh fully paginated GitHub Actions runs query returned one page, total_count 0. There are no tracked `.github` workflows. CI timing/flakiness evidence is therefore unavailable. Private transcripts and other owners' scratch were not accessed. Earlier fixture extraction and Full-scheduling performance measurements remain attributed in `PERFORMANCE.md`; they are not remeasured here. Earlier blanket quota-401 assumptions were repaired, not a current model-login diagnosis.

### Simpler alternatives assessed before editing

Monolithic discovery loses file isolation/hard bounds. Automatic glob registration silently changes future Quick admission without a current registration defect. Mock-only HTTP/OS/process tests lose framing, lock/crash and orphan evidence. Shared platform fixtures obscure distinct ABI/resource contracts. Removing Full discards package-negative/Diagnostics/parity risks. None is justified by observed burden.

The exact thread-root and source-text/browser-sink checks are refactor-sensitive. They protect real execution/privacy wiring and cannot simply be deleted; an outcome-equivalent replacement should be characterized first. The ten legacy test-import edges remain localized debt, not a new approved permanent exception or proof of healthy execution. No tested mechanism changed, so no seeded-failure experiment or before/after execution comparison was performed or claimed. Mechanisms, gate fanout and fixture layers are unchanged; counts grew with distinct delivered risks, not another governing framework.

## Next investigations

When shipped changes next authorize execution, inspect per-file durations and real failures before adjusting Quick deadlines (especially actual HTTP deadlines and spawn/PowerShell tests). Separate environment startup overhead from product failure; keep absolute timeouts and cleanup assertions. Move a legacy import edge into its existing responsibility-owned fixture when that area changes, preserving negative cases. Characterize browser rendering behavior before replacing source-text guards. Native macOS acceptance remains outstanding under FR 000330's retained checklist; no audit note closes it or grants UI approval.

Architecture assessment: **no-update** to module contracts, overview or diagrams; this delivery changes no ownership/dependency boundary. Journal assessment: update this baseline and its INDEX route in place, not another session log. Exact native state advances Test Health to milestone 15; identity high watermark stays 400 and retention prunes nothing. Five pending FRs 000340 through 000380 and their dependency specifications remain untouched. Existing Web contracts/completion reports retain necessary prior evidence, including native-platform limitations; no dependency or recovery needs the disposable audit exports. No foreign stash or unfamiliar work was found in the isolated clone. No raw inventory, credential, user content, machine path or diagnostic export is published.

## Rejected hypotheses

- More tests alone proves excess: distinct source, valuation, lifecycle, HTTP, platform and privacy risks remain.
- Zero byte duplicates proves semantic health: flakiness and semantic overlap require stronger evidence.
- Historical green suites prove current runtime/native readiness: revision, platform and explicit NOT RUN limits remain binding.
- Quota 401 means model login failed: current method/resource compatibility is distinct from model authentication.
- A development-only audit requires another Full run, product validator or version bump: the active development-only workflow deliberately excludes them.
- Ten legacy import edges justify a broad rewrite now: no new coupling or corroborated blocking burden was established; prefer targeted follow-up.
