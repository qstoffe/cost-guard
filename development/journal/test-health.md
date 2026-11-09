# Test system health

Source revision: 139c25f3292f33f71b8ac57bff856af07860c48b
Checked revision: 139c25f3292f33f71b8ac57bff856af07860c48b
Last checked: 2026-11-09
Status: current

## Summary

Milestone 90 moves unchanged synthetic provider pricing Markdown to its existing fixture owner, removing an unrelated account-provider test import. All 37 affected test methods, 181 assertion ASTs and both payload variants remain equal. [Assessment](../architecture/governance/verification/test-health-90-20261109.md) records the source-backed sample, 102 focused passes, deliberate negatives and current hosted cancellation. No runtime, gate, budget, timeout, release or desktop-proof claim changes.

## Evidence

### Pricing fixture ownership and current fanout — milestone 90

`fixtures/pricing_catalog.py` owns `pricing_markdown` directly for provider and presentation tests. Previously presentation imported `test_step6_pricing_accounts.py` solely for this text, coupling it to unrelated account tests. Existing fixture ownership is simpler than copying data, a new wrapper or a fixture framework. Function AST/promo and non-promo bytes are identical; all 37 method and 181 assertion ASTs match. Isolated presentation imports no longer load the provider test module or `src.accounts.github_copilot`; other account contracts remain legitimate transitive dependencies. Sibling-test edges are three → two, without a new module, test deletion or speedup claim. Removing promotion evidence and contaminating a second model's promotion each cause one existing assertion failure before/after; four expected failures, zero harness errors. Initial missing-promotion characterization in the presentation case produced a KeyError; the final independent contamination negative gives a direct assertion failure instead.

Current runner: Quick/Full 172/178 groups, 176 distinct top-level files, no missing entries; only the documented developer benchmark is unregistered. Eight bounded Windows patterns pass 102 tests with zero skips/failures/errors. FR000640 follows independent native amounts/observed cost through Watch/Accounts tokens; FR000629 preserves unverified aliases and selective persisted-cache rebuild across real child restarts; FR000637/639 follows Mini activation/clamp/race policy through the existing Node VM. Those layers do not replace hidden real-browser or installed-source evidence reported by their completions. CI triggers and mandatory/optional boundaries remain unchanged.

Fresh latest-eight main runs: seven success, one failure. [42614424444](https://github.com/qstoffe/cost-guard/actions/runs/42614424444) has Linux Full/validator/browser and Windows/macOS Intel success; macOS ARM was cancelled with no steps, not an assertion failure or PASS. Exact cancellation cause is unavailable. Linux records 178 groups, 2,143 passed/21 platform skips, regression+validation 199.72s, Chromium smoke 13.75s, on `54f613d`; historical, not candidate verification or a controlled speed comparison. No private session history, paid calls, real-provider sweep or visible desktop work was used. Long-run flakiness, agent effort and billing remain unknown.

### Fixture ownership and missing admission — milestone 75

Historical [milestone 75](../architecture/governance/verification/test-health-75-20261108.md): unchanged `one_request` moved to `session_snapshots`, subtotal inputs route directly to `watch_rows`, economics removes a sibling helper's unused unpriced projection. Sibling edges six → three; fixture/function/assertion AST parity and cumulative-usage/subtotal negatives preserved. Seven accidentally omitted AI Stats recovery tests rejoin Quick; only the developer benchmark remains unregistered. Final nine-file sample: 146 pass, no skips/failures/errors. No runtime, assertion, timeout, platform or release change. Detailed before/after counts and the scoped one-time journal-helper exception remain in that assessment, not standing permission for future edits.

Historical milestone-75 CI: [42325700358](https://github.com/qstoffe/cost-guard/actions/runs/42325700358) timed out Sessions scalar indexing at 8/55; current fixture already had a 50ms HTTP-server pump timeout. [42333270967](https://github.com/qstoffe/cost-guard/actions/runs/42333270967) raised ProcessLookupError/identity-unavailable while observing an exiting owned child. The Linux ownership race remains unclosed; Windows success is no substitute. Do not suppress unknown ownership or relax force-stop safety. [42506711399](https://github.com/qstoffe/cost-guard/actions/runs/42506711399) passed all four jobs on another revision, not current/candidate PASS.

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

Investigate Linux's exiting-child identity race using exact owned handles/evidence before changing the reader or its test; do not equate one Windows pass with closure. Inspect per-file durations before tuning Quick deadlines; the VM child's 60s cap does not authorize loosening the 25s outer bound. Two remaining test-import edges are localized debt, not a count target. Long-run flake rates, agent effort and paid cost remain unknown. Architecture: no-update; runtime responsibilities and verification triggers remain unchanged.

## Rejected hypotheses

- Green historical/local/platform mocks prove consumer desktop readiness. Revision/platform limits remain binding.
- Slow AppKit initialization caused Mac readiness timeout. Measured phases were subsecond; numeric-loopback DNS was causal.
- Offline browser mode necessarily closes SSE TCP connections. Prove actual disconnect/reconnect.
- Timing fixes require longer deadlines, weaker ownership or omitted platforms. Retain causal fixtures and exact ownership.
- A monolithic suite/auto-discovery/generic DOM framework is simpler without measured benefit. Retain explicit bounded selection and distinct risks; repair the concrete missing entry.
- Development-only audits require unrelated product gates, or quota401 proves model-login failure. Neither follows.
