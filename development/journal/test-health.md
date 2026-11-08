# Test system health

Source revision: d9d39caf05f4b68f15a38a2006d398f34e036334
Checked revision: d9d39caf05f4b68f15a38a2006d398f34e036334
Last checked: 2026-11-08
Status: current

## Summary

Milestone 75 removes three sibling-test dependencies and restores seven omitted AI Stats recovery tests to the existing runner. Product behavior, assertions, deadlines, platforms and release policy are unchanged. [Assessment](../architecture/governance/verification/test-health-75-20261108.md). Metadata names the observed base; candidate CI belongs in its PR. Historical success is not current PASS or desktop acceptance.

## Evidence

### Fixture ownership and missing admission — milestone 75

`fixtures/session_snapshots.py` now owns unchanged `one_request`; Token Mix and subtotal tests import it directly. Subtotals also import `inputs`/`prompt` directly from their existing `fixtures/watch_rows.py` owner. Economics calls `tracker.observe(snapshot, analyze_snapshot(...))` directly instead of importing a sibling's helper and computing an unused unpriced projection before the priced one. No new helper/module, compatibility layer or assertion-shape test.

Static sibling-test edges fall six → three. Isolated economics/subtotal imports no longer load Token Mix/grouping tests. Six old/new snapshot values and the moved helper AST match; all assertion ASTs and 60/61 test-method ASTs match. The sole execution change removes the unused projection. Deliberately reinstating cumulative usage after step replacement, or using run cost for visible-row subtotals, causes the same two existing assertion failures before and after; no harness errors.

FR 000619 added `test_ai_stats_recovery.py`, but neither runner list nor another test loaded it. Its seven tests protect safe observed subtotals, unavailable ratios, temporal exclusion, unknown-not-zero and explicit compaction ends. Restore one Quick entry, without a new selector/gate or timeout change: Quick/Full 163/169 → 164/170 groups. The developer-only benchmark remains intentionally unregistered. Direct recovery runs pass in 2.76/2.88s. Final bounded nine-file sample: 146 passed, zero skips/failures/errors. No local product Full/validator/live proof was selected for development-only work; actual candidate CI remains separate.

Recent eight main runs initially show five successes, two failures and one in progress. Failed [42325700358](https://github.com/qstoffe/cost-guard/actions/runs/42325700358) timed out Sessions scalar indexing at 8/55; current `test_web_views.py` already sets a 50ms server timeout so its single-thread fixture can pump independently of HTTP arrival. Current focused test passes; no claim of exact historical causation or measured flake-rate reduction. Failed [42333270967](https://github.com/qstoffe/cost-guard/actions/runs/42333270967) raised ProcessLookupError/identity-unavailable while observing an exiting owned child. Current strict identity reader/test still expose that possible race; one passing Windows dispatch run does not close Linux's cause. Do not suppress unknown ownership or relax force-stop safety. [42506711399](https://github.com/qstoffe/cost-guard/actions/runs/42506711399) passes all four jobs on another revision: Linux 2,053 passed/21 skips, validator/browser pass. It is not this candidate's PASS. No foreign scratch/processes/private transcripts were read.

### Earlier causal simplifications (historical, not current suite proof)

- Milestone 60: unchanged Watch frame/status moved to `fixtures/watch_rendering.py`, seven → six import edges, 36 methods/data equal, isolated import and missing-tail-erase/terminal-live-status negatives retained. [Assessment](../architecture/governance/verification/test-health-60-20261106.md): focused 79 pass. ARM cancellation in run 42251085890 was hosted capacity, not assertions; later success on another revision supplies no waiver.
- Milestone 45: Daily's one-second thread/Event handshake conflated valid HTTP latency with test failure. Fix only catalog-age time and count real HTTP synchronously; remove the thread/two Events/wait/join. Controlled 1.1s latency/three-second age reproduced false positives; per-root/lost-root negatives still fail. Preserve 64-root ≤120s/34-fetch budget, expiry/revision retries and unknown precise remote causes. [Assessment](../architecture/governance/verification/test-health-45-20261105.md).
- Milestone 30: unchanged Watch lifecycle factories/Recorder moved to `fixtures/watch_runtime.py`; 47 methods equal, source-recovery consumers intact; missing pump stop/zero fatal exit negatives retained. [Assessment](../architecture/governance/verification/test-health-30-20261104.md).
- Milestone 15: `session_snapshots.history` and `active_hour` own explicit timing/capture setup, not sibling tests. Lost-completion negatives retained. Initial missing MODEL import was repaired, not skipped. FR 000563/000564's load/cleanup/natural-transition exceptions remain delivery-scoped. [Assessment](../architecture/governance/verification/test-health-15-20261103.md).
- FR 000553: only named README/history/Web-guide prose caps became advisory. Instruction/context, source/config and other artifact limits stay hard. Foundation checks execute bootstrap/minimum-Python/Watch handoff behavior; hidden shell fixtures retain fallback/arguments/exit and 30s startup, 10s join, 60s emergency cleanup. CI topology tolerates formatting but rejects lost phases/platforms/cancellation. No product deadline change.

### Runner and retained critical risks

`development/tools/run_tests.py` launches four isolated local workers with hard Quick/Full file bounds 25/240s. CI cumulative product/test/tool/workflow paths run Full+validator/browser once on Linux, serial native profiles on Windows/macOS ARM/Intel; native omits validator/browser provisioning. Development-only work has no local product gates; test/tool edits still trigger PR CI, journal/state-only edits do not. Reporting commits on a code-changing PR rerun CI; no cache/skip/old-head-as-new-PASS. Missing/failed/cancelled evidence stays non-PASS. Reserved `integration/live` is not an implemented model runner; real-source/desktop probes remain opt-in.

Tests below are under `development/tests/`; these are risk routes, not coverage percentages:

| Risk | Source owner | Protection |
| --- | --- | --- |
| Readiness never becomes repeated auth/CLI wake | sources/read_recovery | test_connectivity_reliability: virtual deadlines, exact waits, forbidden cache/CLI calls |
| Replacement cannot resurrect quotas or mutate credentials | accounts acquisition/subscription | test_openai_account_switch, test_account_acquisition: late response/generation replacement, synthetic bytes |
| Unknown is not zero, billing, or confirmed execution | analysis/valuation, causal, report projection | test_application_reports, test_ai_stats_recovery, test_execution_unverified: independent/null expectations, native status and partial/recovery matrices |
| Rebuildable concurrent cache and truthful history | cache/database, reports history | test_cache; test_web_session_detail: generations/WAL/bounded access, complete totals, freeze/late child/auth/cursors |
| One acquisition, source loss not completion | application/live, web/events | test_web_live, integration/web_live.cjs: parity/outage/replay/gap/foreign bounds |
| Navigation does not refresh/revalue or interpret hostile text | web/assets | test_web_views, integration/web_views.cjs: 55 roots/151 detail rows, exact sorts/stale/frozen/Unicode |
| Progress cannot starve control; children cannot be orphaned | web/jobs | test_web_runtime, test_web_dispatch: 130-message/64-drain fixture, cancellation/deadline/parent-loss and retained-owner paths |
| HTTP and private observations stay isolated | web/security, observations, diagnostic_web | test_web_runtime, test_web_diagnostics: CookieJar/two hosts, CSRF/rebinding/framing, private canaries |
| Native exact-owner cleanup and package negatives | lifecycle/platform owners, validator | test_web_lifecycle/windows_web/macos_web/macos_app and Full-only foundation/Diagnostics |

Watch Today rollover remains `test_watch_today_ccost`. Request-run Token Mix and visible-row CCost subtotals have independent scope, replacement and retention checks; neither is a proxy for the other. Counts/VMs do not replace real browser/network/native evidence.

### Cross-platform causal findings

Keep numeric-loopback binding (not reverse DNS), PID/birth/current-image ownership, platform-pinned compiler mocks, distinct synthetic credential versions and hidden console stubs. Installed `py.exe` need not have a registered interpreter: retain fallback/exact arguments. Serial hosted Windows launcher execution removes contention without extending deadlines/skipping cases. macOS process-global AppKit fault cases need isolated processes; retain Darwin wire bytes/EPERM, not catch-all socket suppression.

Keep 55 roots/151 rows without unrelated analyses, warm separate observed-history acquisition before DOM waits, and close actual SSE sockets for reconnect proof. FR 000370's 64-message IPC drain, FR 000380's overlapping-probe interference and FR 000500's separate HTTP/source readiness remain distinct. Old raw-log HTTP401 grants no identity bypass. Hosted/native API success does not prove physical clicks, Finder/Gatekeeper, default browser, accessibility or suspend/soak.

## Next investigations

Investigate Linux's exiting-child identity race using exact owned handles/evidence before changing the reader or its test; do not equate one Windows pass with closure. Inspect per-file durations before tuning Quick deadlines; the VM child's 60s cap does not authorize loosening the 25s outer bound. Three remaining test-import edges are localized debt, not a count target. Long-run flake rates, agent effort and paid cost remain unknown. Architecture: no-update; runtime responsibilities and verification triggers remain unchanged.

## Rejected hypotheses

- Green historical/local/platform mocks prove consumer desktop readiness. Revision/platform limits remain binding.
- Slow AppKit initialization caused Mac readiness timeout. Measured phases were subsecond; numeric-loopback DNS was causal.
- Offline browser mode necessarily closes SSE TCP connections. Prove actual disconnect/reconnect.
- Timing fixes require longer deadlines, weaker ownership or omitted platforms. Retain causal fixtures and exact ownership.
- A monolithic suite/auto-discovery/generic DOM framework is simpler without measured benefit. Retain explicit bounded selection and distinct risks; repair the concrete missing entry.
- Development-only audits require unrelated product gates, or quota401 proves model-login failure. Neither follows.
