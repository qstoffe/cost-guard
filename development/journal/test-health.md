# Test system health

Source revision: ebacf2cde20a2ee1db2168569e00fa43c87f27bb
Checked revision: ebacf2cde20a2ee1db2168569e00fa43c87f27bb
Last checked: 2026-10-28
Status: current

## Summary

Milestone-30 audit retains isolated files, responsibility-owned fixtures and hard deadlines: no source-backed harness rewrite justified. Whole-tree inventory, sampled source/tests and fresh three-platform CI outcomes are in development/architecture/governance/verification/test-health-30.md. No product tests, validator, live/model calls or version work ran for this development-only delivery. Historical hosted results are revision-specific, never consumer-desktop acceptance.

## Evidence

### Runner and retained critical risks

`development/tools/run_tests.py` keeps four isolated workers, Quick's 25-second and Full's 240-second per-file bounds. Its JSON report now distinguishes named skips, failures/errors and incomplete known-passed counts for failed files. A test-method inventory is not an executed count. CI supplies Node so optional VM tests actually execute; Chromium smoke remains separate from DOM substitutes. `test_ci_web_beta.py` covers hosted-only admission and sanitized reporting.

At ebacf2cde20a2ee1db2168569e00fa43c87f27bb, AST inventory found 112 registered files (108 Quick, four Full-only), no gaps and 1,370 syntactic test methods. Eleven sibling-import statements remain ten distinct importer/module edges, unchanged since milestone 25. Inventory: 485 text/config files, 61 binary/large exclusions, no exact-byte duplicates (not semantic uniqueness). Latest main run 40601136981 at e25cf3b63a5ffe73e20787a96c9c1ee38f356c1a passed all three hosted jobs: Windows 1,370 passed; both Macs 1,365 passed/five Windows-only skips; no failures/errors. Regression including validator: Windows 107.20 s, ARM64 201.45 s, Intel 214.00 s; browser 9.38/10.33/10.50 s. Structured phase durations are not per-file timings or a controlled speedup. The intervening architecture-only commit changes no tested source. Eight-run sample: five success/three cancelled, not eight PASS.

Tests below are under `development/tests/`; mappings establish intended contracts, not coverage percentages:

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

Reproduce with the committed `.github/workflows/web-beta.yml`: real hosted full suite/validator, then `ci_web_beta.py native`, then CI-only Playwright/Chromium and browser phase. Direct smoke refuses non-GitHub-hosted execution. Temporary offline entries suppress real acquisition and system browser but retain shipped HTTP/native adapters, OS locks and lifecycle. Public standard runners are the cost boundary; no paid/self-hosted fallback.

- Hosted macOS exposed reverse DNS in HTTPServer.server_bind on numeric loopback. A deterministic canary failed before the TCPServer binding repair. Real startup then reached the native polling/record stage instead of exhausting readiness. No product deadline was increased.
- The subsequent Mac startup conflict exposed comparing the published image with an immediately spawned Python launcher. Ready validation now retains original PID/birth, compares published identity to the current live image and checks child liveness. Regression accepts same-birth exec and denies foreign birth/forged image. Hosted identity comparisons report booleans only, never PIDs/paths/state.
- Resolve temporary roots before safe-path expectations: macOS /var aliases and Windows short paths otherwise misclassify fixtures. Do not weaken product symlink checks.
- Mock compiler tests pin synthetic platform metadata: Python 3.11 platform discovery can invoke subprocess.run and accidentally enter a compiler mock.
- A real authenticated model-availability HTTP test uses a virtual settling clock; wall-clock resolution must not decide the number of confirming polls. Synthetic credential replacements use distinct mtimes so same-length rapid writes cannot become the same file-version fixture.
- Finite report work runs on an owned fixture worker and warms canonical scopes before fixed VM UI assertions; HTTP handlers do not perform synchronous expensive report work. Data and UI/suite deadlines stay intact.
- FR 000420's first hosted candidate still exceeded the fixed five-second Sessions UI wait on Intel macOS: the view fixture unnecessarily analyzed 151 prompts in each of 55 roots. Keep 55 list entries and the full 151-row running detail under test, but use one prompt in unrelated roots; large-month analysis belongs to performance tests. Do not increase the UI deadline or remove its content/paging assertions.
- The same candidate's Windows missing-Python fixture timed out in pwsh after 20 seconds. Discovery/argument fixtures now supply a PowerShell console class, isolating their subject from cold Add-Type/native initialization; native launcher/Watch probes retain the real console path. No product change or timeout increase. Initial failing receipt: [run 40411971939](https://github.com/qstoffe/cost-guard/actions/runs/40411971939); rendered-browser/native phases passed separately and did not turn failed Full into PASS.
- A subsequent hosted Windows Beta AST/discovery/private-log fixture exceeded its cumulative 15-second harness budget while repaired CLI fixtures and both macOS jobs passed ([run 40412977788](https://github.com/qstoffe/cost-guard/actions/runs/40412977788)). Keep real Python/py and DACL checks, use a bounded 30-second aggregate child budget and fixed stage-only timeout diagnostics. This aggregate is not the product host-readiness deadline; product timing and the suite file cap stay unchanged.
- Browser offline mode alone leaves existing SSE sockets open. The smoke closes its own recorded TCP stream while offline and verifies actual EventSource reconnect and terminal stop, not a mocked EventSource.
- NSApplication is process-global: test a second HTTP-fault case in a fresh bounded process after native readiness, not another adapter or a pre-install HTTP fault.
- Wait for owned identity retirement before reading a Windows record being removed, avoiding fixture read handles during unlink.
- Darwin may report ENOTCONN at a raw HTTP fixture's write-half-close after the server has already rejected the request. Tolerate only that shutdown race, then read/assert the actual response bytes; do not swallow other errors or replace wire-limit/security assertions with an assumed rejection. Deterministic canary verifies both retained response and EPERM propagation. Observed in [run 40413855775](https://github.com/qstoffe/cost-guard/actions/runs/40413855775).
- Validate README's hard byte budget under CRLF too; shorten prose, never raise the cap to admit a checkout-conversion failure.

Actions raw-log download through the installed transport returned HTTP 401; it was not bypassed with another identity. Supported Checks annotations supply sanitized totals/failure/skip notices, with bounded JSON artifacts. Keep notices below GitHub's observed truncation boundary by splitting totals and failures. Failed/cancelled runs are never PASS. Consumer Windows, physical clicks/status visibility, Finder/Gatekeeper, default-browser integration and accessibility remain separate manual acceptance.

### Historical causes retained

FR 000370's report timeout was product IPC backpressure: retain the 64-message drain canary. FR 000380's overlapping probes interfered; sequential rerun passed, not evidence against isolation. FR 000500's finite-report-only CI fixture incorrectly expected Live connected with no source; current ci_browser_web.py requires STARTING/source pending, then SOURCE UNAVAILABLE/HTTP connected after publication/recovery, retaining actual SSE, stale report and terminal assertions. Successful hosted run 40601136981 corroborates repair; web_connection.cjs independently checks source versus HTTP readiness with a virtual clock. Repaired malformed-request/lifecycle/authorization assumptions are recorded in that delivery, not suppressed. Different revisions' times are not controlled comparisons.

## Next investigations

Inspect per-file durations/skips before changing Quick deadlines, especially Node/HTTP/spawn/PowerShell. The VM child permits 60 seconds while Quick bounds its whole file at 25 seconds: a known tighter outer limit, not authority to loosen it. Reproduce probe interference sequentially. Legacy static shape guards/import edges remain refactor-sensitive debt; move coupling into its responsibility-owned fixture when that area changes, preserving behavioral canaries. Hosted API success does not close desktop/Finder/Gatekeeper/accessibility/suspend/soak acceptance.

Architecture assessment: no-update to diagrams or dependency contracts; existing Web/HTTP/lifecycle owners remain. The workflow is additive evidence, not a permanent all-project gate. Final native delivery preserves immutable selected specifications, new concurrent FRs and the identity high watermark; no evidence depends on disposable private exports.

## Rejected hypotheses

- Historical/local green or mock platform tests prove current native/desktop readiness. Platform, revision and NOT VERIFIED limits remain binding.
- Slow AppKit initialization explained the Mac readiness timeout: measured native phases were subsecond; numeric-loopback DNS was the identified blocker.
- Browser offline mode necessarily closes SSE TCP connections. Verify real disconnection/reconnect.
- Fixing timing means raising product/suite deadlines or weakening ownership. Keep causal fixtures and PID/birth/current-image guards.
- Monolithic discovery, automatic glob admission or a generic DOM framework is simpler without measured benefit. Retain distinct risks and per-file cleanup bounds.
- Quota 401 proves model login failed, or development-only audits require product gates. Neither follows from the evidence.
