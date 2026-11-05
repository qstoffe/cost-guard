# Test system health

Source revision: 15bc39ea61eef6af1605216b113f6519758b4576
Checked revision: 15bc39ea61eef6af1605216b113f6519758b4576
Last checked: 2026-11-05
Status: current

## Summary

Milestone 45 replaces Daily's timing-dependent batch check with a controlled-age, real-HTTP catalog-count check. The 120s modeled budget, freshness/retry protection, product deadlines and gate fanout stay unchanged. [Assessment](../architecture/governance/verification/test-health-45-20261105.md). Metadata identifies the observed base; candidate CI belongs in its PR. Older reports are historical, not progress counters or desktop acceptance.

## Evidence

### Daily batch-sharing harness — milestone 45 (2026-11-05)

Fresh [42117653741 attempt 1](https://github.com/qstoffe/cost-guard/actions/runs/42117653741/attempts/1) and main [42121612211](https://github.com/qstoffe/cost-guard/actions/runs/42121612211) fail only Daily's one-second wait; validator/browser/native pass. The former reran successfully on unchanged HEAD, not a fix. A controlled 1.1s legitimate catalog response fails that wait despite one fetch/four intact requests/prompts; a three-second-old cache legitimately needs two brackets and triggers the fixture's artificial hold. Exact remote causes remain unknown.

The four-root test now fixes only V2 catalog-age time and counts actual HTTP fetches synchronously. It removes a test-owned thread, two Events and unrelated wait/hold/join thresholds, not product timeouts. Two Daily and eight source-history tests pass; the unchanged 64-root model retains <=120s/34 fetches/all requests. Per-root hydration and lost-root mutations each fail both Daily tests with assertions/no harness errors; a 1.1s valid response passes the replacement. Source-history still tests expiry and revision retries. No requirement/test exception or new gate.

Inventory: 864 text/config records, 247 exclusions; 144 top-level files/1,710 methods, Quick/Full 139/145 groups. The standalone developer benchmark regression is outside product Full; it passes directly. Seven fixture-import edges remain. Local Full/validator/live/desktop work is not selected for this development-only change; PR test-path CI remains normal. No controlled project-wide speed or effort claim.

### Watch lifecycle fixture ownership — milestone 30 (2026-11-04)

`fixtures/watch_runtime.py` owns unchanged global/scoped `watch_for` and render/status/finish `Recorder`. Runtime faults/lifecycle no longer import other tests for setup. Sibling import statements: 11 → 7; distinct edges: 10 → 7. All 47 method ASTs match excluding imports; moved definitions match excluding new docstrings. Scoped/global/recorder characterization and import-only smoke for 56 direct consumers pass. No wrapper/framework/runtime change.

Before/final: 30 runtime + 8 lifecycle + 9 recovery pass, no skips; privacy/fatal/clean-stop/pump/source protections stay intact. Dropping pump stop or returning zero on fatal errors yields four assertion failures, no harness errors. Two Daily tests pass locally. Focused results are not Full/validator/live proof or timing savings.

Historical [milestone-30 assessment](../architecture/governance/verification/test-health-30-20261104.md) retains inventory, local/CI counts and limits. Development-only work selects no local product gates/version update; candidate CI belongs in its PR.

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

Inspect per-file durations/skips before changing Quick deadlines, especially Node/HTTP/spawn/PowerShell. Daily's demonstrated timing/expiry conflation is repaired; exact historical CI causes and long-run failure rate remain unknown, not proven by a green rerun. The VM child permits 60 seconds while Quick bounds its whole file at 25 seconds: a known tighter outer limit, not authority to loosen it. Seven test-import edges remain localized debt. Hosted API success does not close desktop/Finder/Gatekeeper/accessibility/suspend/soak acceptance.

Architecture: no-update; runtime/validation ownership and triggers are unchanged.

## Rejected hypotheses

- Historical/local green or platform mocks prove consumer desktop readiness. Revision/platform limits remain binding.
- Slow AppKit initialization explained the Mac readiness timeout: measured native phases were subsecond; numeric-loopback DNS was the identified blocker.
- Browser offline mode necessarily closes SSE TCP connections. Verify real disconnection/reconnect.
- Fixing timing means raising product/suite deadlines or weakening ownership. Keep causal fixtures and PID/birth/current-image guards.
- Monolithic discovery/glob admission/generic DOM fixtures are simpler without measured benefit. Retain per-file bounds and distinct risks.
- Quota 401 proves model login failed, or development-only audits require product gates. Neither follows from the evidence.
