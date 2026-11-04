# Test system health

Source revision: 55f74a4fb9b7e8347e3c407881a914dcbfb44745
Checked revision: 55f74a4fb9b7e8347e3c407881a914dcbfb44745
Last checked: 2026-11-04
Status: current

## Summary

Schema-2 milestone 30 removes runtime/lifecycle/recovery test coupling; assertions, admission and deadlines stay unchanged. [Assessment](../architecture/governance/verification/test-health-30-20261104.md). Metadata identifies the observed base; the PR identifies the extraction. Results remain revision/platform-specific, not desktop acceptance. Older reports are historical, not progress counters.

## Evidence

### Watch lifecycle fixture ownership — milestone 30 (2026-11-04)

`fixtures/watch_runtime.py` owns unchanged global/scoped `watch_for` and render/status/finish `Recorder`. Runtime faults/lifecycle no longer import other tests for setup. Sibling import statements: 11 → 7; distinct edges: 10 → 7. All 47 method ASTs match excluding imports; moved definitions match excluding new docstrings. Scoped/global/recorder characterization and import-only smoke for 56 direct consumers pass. No wrapper/framework/runtime change.

Before/final: 30 runtime + 8 lifecycle + 9 recovery pass, no skips; privacy/fatal/clean-stop/pump/source protections stay intact. Dropping pump stop or returning zero on fatal errors yields four assertion failures, no harness errors. Two Daily tests pass locally. Focused results are not Full/validator/live proof or timing savings.

Base: 792 text/config records, 225 exclusions; 138 test files/1,659 methods, no registration gaps; Quick/Full 135/140 selectors. Fresh [41922482417](https://github.com/qstoffe/cost-guard/actions/runs/41922482417): four successful jobs, common 1,639 passed/20 platform skips, Windows native 52 passed/no skips. Candidate CI belongs in the PR, not old-head PASS. Development-only work selects no local product gates/version update.

Earlier [41918986747](https://github.com/qstoffe/cost-guard/actions/runs/41918986747) failed Daily's `finished.wait(1)` on `020e500`; validator/browser/native passed. Same guard remains; comparison removal did not fix it. Current default/local success leaves cause unknown. Scheduling sensitivity is unproven; retain deadlines and the separate modeled 120s budget. No exception/false PASS.

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

`.github/workflows/web-beta.yml` owns the common/native scoped phases. Direct smoke refuses workstation execution. Offline entry shims suppress acquisition/browser dispatch but retain shipped HTTP/native APIs, OS locks and lifecycle. Public standard runners only; no paid/self-hosted fallback.

- macOS numeric-loopback reverse DNS caused startup timeout: use TCPServer binding, not longer deadlines. Native identity compares original PID/birth/current image, allowing same-birth exec but denying foreign birth/forged image. Resolve temp aliases without weakening symlink guards.
- Pin synthetic platform metadata around compiler mocks; platform discovery can otherwise enter mocked subprocess calls. Virtual settling clocks and distinct synthetic credential mtimes prevent wall-clock/file-version races.
- Keep 55 list roots and full 151-row detail, but only one prompt in unrelated roots; do not multiply analysis or increase fixed VM UI deadlines. Keep expensive finite work off HTTP handlers.
- Windows cold Add-Type skewed discovery fixtures: use the console stub, retain native launcher/Watch paths. [40411971939](https://github.com/qstoffe/cost-guard/actions/runs/40411971939) failed despite browser/native success; [40412977788](https://github.com/qstoffe/cost-guard/actions/runs/40412977788) repaired aggregate discovery/DACL fixtures without longer product/file deadlines.
- Browser offline mode does not close SSE sockets: close the fixture's own recorded stream and verify real reconnect. NSApplication is process-global; run a second native fault case in a fresh bounded process. Await owned identity retirement before opening a Windows record being unlinked.
- Darwin ENOTCONN can follow wire rejection at write-half-close; tolerate only that race, assert actual response bytes and retain EPERM propagation. [40413855775](https://github.com/qstoffe/cost-guard/actions/runs/40413855775), with a deterministic canary; never infer rejection by swallowing all errors.
- Historical README CRLF cap failures motivated shortening; FR 000553 makes only three named product-prose caps advisory. All other protected caps stay hard.

Historical raw-log download returned HTTP 401; no identity bypass. Checks provide sanitized totals/failures/skips; split notices below truncation bounds. Failed/cancelled is not PASS; physical desktop/default-browser/accessibility remain separate acceptance.

### Historical causes retained

FR 000525's [40770133676](https://github.com/qstoffe/cost-guard/actions/runs/40770133676) Windows regression failed despite native/browser/validator success: installed `py.exe` need not have registered Python; test supported-interpreter fallback and exact arguments. Serial hosted Windows execution repaired handoff contention without longer waits/skips. [40778103084](https://github.com/qstoffe/cost-guard/actions/runs/40778103084) corroborated recovery at its revision, not desktop proof.

FR 000370: product IPC backpressure, retain 64-message drain canary. FR 000380: overlapping probes interfered; sequential success is not evidence against isolation. FR 000500: finite-only fixture wrongly expected Live connected without a source; require STARTING/source pending then SOURCE UNAVAILABLE/HTTP connected, retaining real SSE/stale/terminal checks. Run 40601136981 corroborated repair; `web_connection.cjs` independently checks source/HTTP readiness with virtual time. Different revisions' times are not controlled comparisons.

## Next investigations

Inspect per-file durations/skips before changing Quick deadlines, especially Node/HTTP/spawn/PowerShell. Daily's unexplained one-second failure needs causal scheduling/catalog evidence before any harness/product diagnosis; a passing rerun is not a fix. The VM child permits 60 seconds while Quick bounds its whole file at 25 seconds: a known tighter outer limit, not authority to loosen it. Reproduce probe interference sequentially. Seven remaining test-import edges stay localized debt; preserve behavioral canaries when extracting their fixtures. Hosted API success does not close desktop/Finder/Gatekeeper/accessibility/suspend/soak acceptance.

Architecture: no-update; runtime/validation ownership and triggers are unchanged.

## Rejected hypotheses

- Historical/local green or platform mocks prove consumer desktop readiness. Revision/platform limits remain binding.
- Slow AppKit initialization explained the Mac readiness timeout: measured native phases were subsecond; numeric-loopback DNS was the identified blocker.
- Browser offline mode necessarily closes SSE TCP connections. Verify real disconnection/reconnect.
- Fixing timing means raising product/suite deadlines or weakening ownership. Keep causal fixtures and PID/birth/current-image guards.
- Monolithic discovery/glob admission/generic DOM fixtures are simpler without measured benefit. Retain per-file bounds and distinct risks.
- Quota 401 proves model login failed, or development-only audits require product gates. Neither follows from the evidence.
