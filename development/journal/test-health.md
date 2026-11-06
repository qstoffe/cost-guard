# Test system health

Source revision: 43a745a62149b5000701b3b63b261620f366e141
Checked revision: 43a745a62149b5000701b3b63b261620f366e141
Last checked: 2026-11-06
Status: current

## Summary

Milestone 60 moves the shared Watch frame out of the rendering test into its fixture owner: 36 unchanged test methods, equivalent data, one fewer test-import edge. [Assessment](../architecture/governance/verification/test-health-60-20261106.md). Metadata identifies the observed base; candidate CI belongs in its PR. Historical results are not current PASS or desktop acceptance.

## Evidence

### Watch frame fixture ownership — milestone 60 (2026-11-06)

`fixtures/watch_rendering.py` now owns unchanged `tall_projection`/status data. Rendering and tool-activity tests import it directly; the latter no longer loads a sibling test and its unrelated report/warning setup. Seven → six static import edges; no wrapper, new assertion, dispatch/setup change or claimed speedup. All 36 test methods and the moved function have equal ASTs; old/new fixture values match. An isolated tool-activity import leaves the rendering test unloaded. Both fixtures detect missing tail erase and terminal live-status leakage: four intentional assertion failures, no errors.

Before/after rendering 13 and tool-activity 23 pass. Final bounded sample adds 17 exact-input, 8 Mini, 1 loader, 2 Daily and 15 CI-accounting tests: 79 pass, zero skips/errors. Quick/Full remain 147/153 groups. Recent eight main runs contain seven successes and one failure: [42251085890](https://github.com/qstoffe/cost-guard/actions/runs/42251085890) has macOS ARM cancelled because no hosted runner was acquired, not an assertion failure. [42253836493](https://github.com/qstoffe/cost-guard/actions/runs/42253836493) passes all four jobs on `302784d`; Linux has 1,768 passed/21 skips, validator/browser PASS. Different revisions, not a controlled rerun or candidate proof. No capacity/deadline/platform waiver.

### Daily batch-sharing harness — milestone 45 (historical)

[Assessment](../architecture/governance/verification/test-health-45-20261105.md): two observed CI failures hit the old one-second wait; unchanged-head rerun success was not a fix. Controlled 1.1s valid latency and three-second cache age independently reproduced false positives; precise remote causes remain unknown. Fix only catalog-age time, count real HTTP synchronously; remove the test thread/two Events/hold/wait/join, not source timeouts. Two Daily/eight source-history tests pass; per-root/lost-root negatives fail. The 64-root <=120s/34-fetch budget and expiry/revision retry checks remain. Current Daily sample also passes; no long-run flake-rate claim.

### Watch lifecycle fixture ownership — milestone 30 (2026-11-04)

`fixtures/watch_runtime.py` owns unchanged global/scoped `watch_for` and render/status/finish `Recorder`. Runtime faults/lifecycle import fixtures directly. Statements/edges fell 11/10 → 7/7; 47 method ASTs and moved definitions stayed equal excluding imports/new docstrings. Characterization and 56-consumer import smoke pass; no runtime change.

Before/final: 30 runtime + 8 lifecycle + 9 recovery pass, no skips. Missing pump stop or zero fatal exit yields four assertion failures, no errors. Privacy/fatal/clean-stop/source protections remain; focused proof is not Full/live proof or timing savings.

Historical [milestone-30 assessment](../architecture/governance/verification/test-health-30-20261104.md) retains inventory, counts and limits.

Earlier [41918986747](https://github.com/qstoffe/cost-guard/actions/runs/41918986747) failed Daily's `finished.wait(1)` on `020e500`; validator/browser/native passed. Comparison removal did not fix it. Milestone 45 supersedes that harness, retaining the separate modeled 120s budget and uncertainty about individual remote failures.

### Shared hourly fixture ownership — milestone 15 (2026-11-03)

`fixtures/session_snapshots.py` owns explicit start/end `history`; `fixtures/active_hour.py` owns finite hourly capture/setup. Tests/probe import fixtures directly. That extraction removed one sibling-test edge; 27 method ASTs/six snapshots stayed equal, and lost-completion mutations still failed. Initial missing `MODEL` import caused one NameError; restored import yields 14 hourly/13 duration passes. Historical inventory/CI counts and revision limits are in the [milestone-15 assessment](../architecture/governance/verification/test-health-15-20261103.md), not current PASS. FR 000563's load/cleanup exception and FR 000564's natural-transition proof limits remain scoped, not generalized.

### Focused verification cleanup — FR 000553 (2026-11-03)

Only named README/history/Web-guide prose caps became advisory; hard instruction/context, source/config, other Markdown/artifact caps remain. Dormant history rules stay dormant. Foundation checks execute bootstrap/minimum-Python/Watch handoff behavior, not local names. Hidden shell fixtures retain fallback/arguments/exit and 30s startup, 10s join, 60s emergency cleanup without product deadline changes. CI topology tolerates equivalent formatting but rejects misplaced work, lost platforms/cancellation. [CI evidence route](../architecture/governance/verification/web-beta-ci.md): cumulative PR paths mean reporting commits rerun checks; no cache/skip/old-head-as-new-PASS. Shell/validator success is not desktop/provider proof.

### Runner and retained critical risks

`development/tools/run_tests.py`: four isolated local workers, hard Quick/Full bounds 25/240s, named skips/failures/incomplete counts. CI runs Full+validator/browser once on Linux, serial native profiles on Windows/macOS ARM/Intel; native omits validator/browser provisioning. `test_ci_web_beta.py` protects hosted-only admission/truthful sanitized reporting. Counts/DOM substitutes are not execution/browser proof.

Historical milestone-40 counts/timings remain in `development/architecture/governance/verification/test-health-40.md`, not current evidence or controlled savings. Model-mix, quota and display-unit risks remain independent; FR 000553 changes only named prose limits.

Tests below live under `development/tests/`; these are contract routes, not coverage percentages:

| Risk | Source owner | Protection |
| --- | --- | --- |
| Readiness never becomes repeated auth/CLI wake | sources/read_recovery | test_connectivity_reliability: virtual deadlines, exact waits, forbidden cache/CLI calls |
| Replacement cannot resurrect old quotas or mutate credentials | accounts acquisition/subscription | test_openai_account_switch, test_account_acquisition: gated late response, generation replacement, synthetic bytes |
| Unknown value is not zero or actual billing | analysis/valuation, report projection | test_application_reports: independent Decimal/null expectations alongside parity |
| Disposable concurrent cache remains rebuildable | cache/database | test_cache: generations, WAL, bounded readers/writers, first sightings |
| Tabs share one acquisition; source loss is not completion | application/live, web/events | test_web_live: parity, outage/schema distinction, replay/gap/foreign bounds; integration/web_live.cjs |
| Detail totals/history are not page totals or fabricated evidence | application/session_detail, reports/session_history | test_web_session_detail: 100/1,000/10,000 rows, totals, freeze/retained omissions, late child, auth/cursors; integration/web_session.cjs |
| Navigation never silently refreshes or reinterprets costs/text | web/assets | test_web_views and integration/web_views.cjs: 55 roots/151 rows, stale/frozen/missing, exact sorting, hostile Unicode |
| Progress cannot starve control | web/jobs | test_web_runtime: deterministic 130-message fixture, 64-message drain; separate process cancellation/deadline/orphan tests |
| HTTP auth/framing and private observations stay isolated | web/security, observations, diagnostic_web | test_web_runtime, test_web_diagnostics: actual CookieJar/two hosts, CSRF/rebinding, malformed/oversized state, private canaries |
| Owned process identity/native cleanup/package negatives | web lifecycle/platform owners, validator | test_web_lifecycle, test_windows_web, test_macos_web, test_macos_app and Full-only foundation/Diagnostics tests |

Watch Today rollover remains in watch/today_ccost and test_watch_today_ccost. Reserved integration/live is not an implemented live-model runner. Real-source/desktop probes remain opt-in.

### Cross-platform causal findings

The [historical milestone-30 assessment](../architecture/governance/verification/test-health-30-20261104.md) and earlier reports retain detailed run links. Keep numeric-loopback binding without reverse DNS, PID/birth/current-image ownership, platform-pinned compiler mocks, distinct synthetic credential versions and hidden console stubs. Never repair these by extending product deadlines or weakening ownership.

Keep 55 list roots/151 detail rows without multiplying unrelated analysis; warm separate observed-history acquisition before UI waits. Close actual SSE fixture sockets to prove reconnect; macOS process-global AppKit fault cases need isolated processes. Preserve Darwin wire bytes/EPERM checks rather than swallowing all socket errors. Only FR 000553's three named product-prose caps are advisory; instruction/context and other protected caps stay hard.

Hosted smoke refuses workstation execution; public native jobs retain real OS locks/APIs with synthetic acquisition. Historical raw-log HTTP 401 never authorizes identity bypass. Use bounded Checks evidence with actionable failures before skips. Failed/cancelled is not PASS; physical desktop/default-browser/accessibility remain separate acceptance.

### Historical causes retained

FR 000525's [40770133676](https://github.com/qstoffe/cost-guard/actions/runs/40770133676) Windows regression failed despite native/browser/validator success: installed `py.exe` need not have registered Python; test supported-interpreter fallback and exact arguments. Serial hosted Windows execution repaired handoff contention without longer waits/skips. [40778103084](https://github.com/qstoffe/cost-guard/actions/runs/40778103084) corroborated recovery at its revision, not desktop proof.

FR 000370: product IPC backpressure, retain 64-message drain canary. FR 000380: overlapping probes interfered; sequential success is not evidence against isolation. FR 000500: finite-only fixture wrongly expected Live connected without a source; require STARTING/source pending then SOURCE UNAVAILABLE/HTTP connected, retaining real SSE/stale/terminal checks. Run 40601136981 corroborated repair; `web_connection.cjs` independently checks source/HTTP readiness with virtual time. Different revisions' times are not controlled comparisons.

## Next investigations

Inspect per-file durations/skips before changing Quick deadlines, especially Node/HTTP/spawn/PowerShell. Daily's timing/expiry conflation is repaired; exact historical causes and long-run failure rate remain unknown. The VM child's 60s bound exceeds Quick's 25s file bound, not authority to loosen either. Six test-import edges remain localized debt. Hosted capacity failures do not justify deleting macOS coverage. Hosted success does not close desktop/Finder/Gatekeeper/accessibility/suspend/soak acceptance.

Architecture: no-update; runtime/validation ownership and triggers are unchanged.

## Rejected hypotheses

- Historical/local green or platform mocks prove consumer desktop readiness. Revision/platform limits remain binding.
- Slow AppKit initialization explained the Mac readiness timeout: measured native phases were subsecond; numeric-loopback DNS was the identified blocker.
- Browser offline mode necessarily closes SSE TCP connections. Verify real disconnection/reconnect.
- Fixing timing means raising product/suite deadlines or weakening ownership. Keep causal fixtures and PID/birth/current-image guards.
- Monolithic discovery/glob admission/generic DOM fixtures are simpler without measured benefit. Retain per-file bounds and distinct risks.
- Quota 401 proves model login failed, or development-only audits require product gates. Neither follows from the evidence.
