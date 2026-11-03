# Test system health

Source revision: 0efa18782fde1dfd2a34da9d87a95ed2695c18be
Checked revision: 0efa18782fde1dfd2a34da9d87a95ed2695c18be
Last checked: 2026-11-03
Status: current

## Summary

Current schema-2 milestone 15 removes hourly/duration/probe test-module coupling without changing assertions, admission or deadlines. [Assessment and evidence](../architecture/governance/verification/test-health-15-20261103.md). Whole-suite/platform results remain revision-specific, not consumer-desktop acceptance. Older milestone reports are historical evidence, not the current progress counter.

## Evidence

### Shared fixture ownership — milestone 15 (2026-11-03)

`fixtures/session_snapshots.py` now owns explicit start/end `history`; `fixtures/active_hour.py` owns finite hourly capture/setup. The two tests and `integration/probe_web_active_hour.py` import those fixtures directly, without a shim. Top-level sibling-test imports: 12 → 11 statements / 11 → 10 distinct edges. The probe imports neither test module. All 27 test-method ASTs are unchanged; six pre-extraction canonical snapshots compare equal. Existing duration/rate checks both reject deliberately lost completion evidence (two assertion failures, zero harness errors).

Focused before/final: 14 hourly + 13 duration tests pass; timing differences are not controlled savings. Initial extraction removed a still-used `MODEL` import (one NameError); restore it, final 13 pass. Finite probe setup works without browser/UI. Local Full/validator/live/model/version work was not selected for this development-only change; candidate CI belongs in its PR. No gate/budget changed.

Base inventory: 704 text/config entries, 94 exclusions; 134 test files, 1,613 methods, no registration gaps. Quick/Full: 131/136 selectors, 872-root scale cases Full-only. Fresh [41718551110](https://github.com/qstoffe/cost-guard/actions/runs/41718551110): four successful jobs, common 1,595 passed/18 platform skips, Windows native 28 passed/no skips. Full source IDs, durations and limitations are in the assessment, not candidate PASS. No private sessions/foreign scratch/user payloads were read.

Recent source/completion review retains revision-safe date hydration, coverage/rounding, HTTP/auth/isolation and cancellation. FR 000563's delegate load/cleanup exception remains unverified scope; FR 000564 fixes completed-partial CLI/Web mix but retains natural-transition proof limits. No broader harness replacement is justified.

### Focused verification cleanup — FR 000553 (2026-11-03)

Only the three named public README/history/Web-guide prose caps became advisory;
broken-package negatives retain hard instruction/context, source/config, arbitrary
Markdown and universal artifact caps. Dormant history-structure rules stay dormant.
Foundation checks execute bootstrap/minimum-Python/Watch handoff behavior rather
than local-name/source shapes. Hidden shell fixtures retain interpreter fallback,
arguments and exit propagation; readiness/release plus 30s startup, 10s join and
60s emergency lifetime permit owned-child cleanup without product deadline changes.

CI topology accepts equivalent names/indentation/matrix order/arguments but rejects
misplaced shared work, lost platforms or cancellation. The
[evidence route](../architecture/governance/verification/web-beta-ci.md) records
cumulative PR paths: report actual CI in the PR, not a reporting-only commit that
reruns the unchanged product. No evidence cache/phase skip or old-head-as-new-PASS.
Shell/validator checks do not prove unrelated providers or consumer desktop UX.

### Runner and retained critical risks

`development/tools/run_tests.py`: four isolated local suite workers, hard Quick/Full file bounds 25/240s, named skips/failures/incomplete passed counts. Current CI runs Full+validator/browser once on Linux and focused serial native profiles on Windows/macOS ARM/macOS Intel, not Full on every native platform. Native profiles omit validator/browser provisioning. `test_ci_web_beta.py` protects hosted-only admission and sanitized truthful reporting; method counts/DOM substitutes are not execution/browser proof.

Historical milestone-40 inventory/measurements and sampled three-platform run are in `development/architecture/governance/verification/test-health-40.md`; they are not current counts or controlled speed comparisons. Independent model-mix, quota and display-unit risks remain separately owned. Earlier README CRLF failures stay historical; FR 000553 changes only its named prose limits.

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

`.github/workflows/web-beta.yml` owns the common/native scoped phases. Direct smoke refuses workstation execution. Offline entry shims suppress acquisition/browser dispatch but retain shipped HTTP/native APIs, OS locks and lifecycle. Public standard runners only; no paid/self-hosted fallback.

- Numeric-loopback reverse DNS caused macOS startup timeout; use TCPServer binding, not a larger deadline. Native identity must compare original PID/birth and the current live image, accepting same-birth exec but denying foreign birth/forged image. Resolve temporary-root aliases without weakening symlink guards.
- Pin synthetic platform metadata around compiler mocks; platform discovery can otherwise enter mocked subprocess calls. Virtual settling clocks and distinct synthetic credential mtimes prevent wall-clock/file-version races.
- Keep 55 list roots and full 151-row detail, but only one prompt in unrelated roots; do not multiply analysis or increase fixed VM UI deadlines. Keep expensive finite work off HTTP handlers.
- Windows cold Add-Type skewed discovery fixtures: use their console stub while retaining native launcher/Watch paths. [40411971939](https://github.com/qstoffe/cost-guard/actions/runs/40411971939) failed despite separate browser/native success. The later aggregate discovery/DACL fixture budget repair ([40412977788](https://github.com/qstoffe/cost-guard/actions/runs/40412977788)) preserved product readiness and file deadlines.
- Browser offline mode does not close SSE sockets: close the fixture's own recorded stream and verify real reconnect. NSApplication is process-global; run a second native fault case in a fresh bounded process. Await owned identity retirement before opening a Windows record being unlinked.
- Darwin ENOTCONN can follow wire rejection at write-half-close; tolerate only that race, assert actual response bytes and retain EPERM propagation. [40413855775](https://github.com/qstoffe/cost-guard/actions/runs/40413855775), with a deterministic canary; never infer rejection by swallowing all errors.
- Historical README CRLF hard-cap failures motivated prose shortening. FR 000553 supersedes only the three named product-prose caps with advisory warnings; source/config/artifact and agent-context caps remain hard.

Actions raw-log download through the installed transport returned HTTP 401; it was not bypassed with another identity. Supported Checks annotations supply sanitized totals/failure/skip notices, with bounded JSON artifacts. Keep notices below GitHub's observed truncation boundary by splitting totals and failures. Failed/cancelled runs are never PASS. Consumer Windows, physical clicks/status visibility, Finder/Gatekeeper, default-browser integration and accessibility remain separate manual acceptance.

### Historical causes retained

FR 000525's [40770133676](https://github.com/qstoffe/cost-guard/actions/runs/40770133676) Windows regression failed despite native/browser/validator success: installed `py.exe` need not have registered Python; test supported-interpreter fallback and exact arguments. Serial hosted Windows execution repaired handoff contention without longer waits/skips. [40778103084](https://github.com/qstoffe/cost-guard/actions/runs/40778103084) corroborated recovery at its revision, not desktop proof.

FR 000370: product IPC backpressure, retain 64-message drain canary. FR 000380: overlapping probes interfered; sequential success is not evidence against isolation. FR 000500: finite-only fixture wrongly expected Live connected without a source; require STARTING/source pending then SOURCE UNAVAILABLE/HTTP connected, retaining real SSE/stale/terminal checks. Run 40601136981 corroborated repair; `web_connection.cjs` independently checks source/HTTP readiness with virtual time. Different revisions' times are not controlled comparisons.

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
