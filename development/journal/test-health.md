# Test system health

Source revision: dacef69cd72f6a37343798902df474fc8afe4714
Checked revision: dacef69cd72f6a37343798902df474fc8afe4714
Last checked: 2026-11-10
Status: current

## Summary

Milestone 120 keeps Quick at 52 groups: **8.6s, 646 passes** on Windows/Python 3.14.7/four workers, versus milestone 105's 8.2s/639 passes (+4.9%, changed portfolio). Hosted browser phases now take **133–145s**, versus the earlier 14s smoke: subsequent feature work added a 24-layout pager matrix, 321-group source/job/navigation/zoom sequence and deliberate ≥45s stall to every ordinary PR/default run.

The existing manual Full selector now owns both deep browser sequences, intact and in order. Ordinary CI retains Quick, validator and the original rendered auth/SSE/navigation/hostile-text/360px/Settings/reconnect/shutdown smoke. Omitted deep coverage is **NOT RUN**, not PASS; manual failures propagate. Three focused selector regressions join the existing 21 cases (24 passes in 1.1s). AST comparison confirms the original smoke and pager bodies are unchanged except for dispatch. No production, timeout, dependency, native trigger or product version changes. [Assessment](../architecture/governance/verification/test-health-120-20261110.md) and [completion](../architecture/governance/verification/test-health-120/COMPLETION.md) distinguish observed baselines from candidate timings retained in the delivery PR. Whole-release budget compliance remains **UNVERIFIED**, not HEALTHY.

## Evidence

### Release portfolio and trend — milestone 120

Fresh bounded sample: 12 latest main runs, 11 successes/one macOS Intel native failure. Source and completions sampled small FR000665/FR000668 and larger FR000658. The latter correctly added deep source/job/route regression coverage, but its CI dispatch also made that whole portfolio ordinary-release work. `ci_paging_navigation.py::paging` alone requires a real 45–60s stall observation, plus busy/source/preview retry budgets; `ci_browser_zoom.py` starts an additional browser profile. This is a release-portfolio burden, not a measured production slowdown or reason to shorten production recovery.

Common Linux jobs on runs [42888081861](https://github.com/qstoffe/cost-guard/actions/runs/42888081861), [42883322314](https://github.com/qstoffe/cost-guard/actions/runs/42883322314) and [42877704376](https://github.com/qstoffe/cost-guard/actions/runs/42877704376): **173/189/196s**, Quick+validator **10/13/15s**, browser provisioning **21/23/25s**, browser **133/142/145s**. First two share Ubuntu image 20261101.360.1, Python 3.11.18, Node 22.23.4 and Chromium 141.0.7390.37. Broader browser coverage differs from the earlier 14s baseline; not every second is causally isolated. No savings claimed until candidate hosted observations; those are retained in the delivery PR without an evidence-only commit rerunning unchanged checks.

Native run [42877704154](https://github.com/qstoffe/cost-guard/actions/runs/42877704154) spans 341s, but its ARM job starts 304s after workflow creation and executes for 37s; Windows/Intel jobs take 60/75s. External capacity/start delay is not zero or controllable test work, and parallel job-minutes are not serial latency. Both PR and default still repeat selected hosted work. Local Full remains roughly 130s in sampled completions, with relevant development/browser/installed-source probes distinct from release readiness. Complete controllable critical path, publication, external waiting and total release elapsed are not reconstructible from those reports: all-profile 15-minute compliance and the ≤5-minute small-change goal remain **UNVERIFIED**. No evidenced >15-minute controllable route is being waived or called healthy.

[42865548378](https://github.com/qstoffe/cost-guard/actions/runs/42865548378) repeats macOS Intel shell-2 preflight failure: 10.074s child timeout at `native_install`, `tray_unavailable`, while shell-1/22 regressions/adapter/fault/cache checks pass. Child reaches native install at 6.822s after slow imports; source does not establish harmless flakiness or root cause. Prior [42693636281](https://github.com/qstoffe/cost-guard/actions/runs/42693636281) has the same broad stage observation. Native triggers/deadlines stay intact; later successes do not close this or the historical Linux exiting-child identity race.

Unique deep layout/zoom/paging/recovery bugs may now escape ordinary CI; manual Full/focused development probes retain coverage when run. Deep checks were **not executed locally**. Full remains 182 groups, unchanged here; no test/assertion deletion. Routing tests cover ordinary exclusion, manual order and both failure paths. No paid/provider/real-source/desktop sweep, new gate, watchdog or environment spoofing.

### Earlier causal simplifications and meaningful baselines

- [Milestone 105](../architecture/governance/verification/test-health-105-20261109.md): nominal Quick 175/181 groups, 2,151 passes/two skips, **96.2s → 52 groups/639 passes/8.2s**; retained 181-group Full, 2,224 passes/two macOS skips in 128.2s. Final selector file subsequently passed 21 tests; distinct runs, not additive totals. Six seeded regressions produced 20 expected assertion failures/zero harness errors. Ordinary CI changed Full→Quick; path-triggered native retains Windows/macOS ARM/Intel. Universal deep/native coverage was intentionally retired, not replaced by equivalent Quick proof. Pre-change Linux jobs 244/262s, Full+validator198/201s, setup24/38s, browser14s; not an end-to-end release comparator.
- [Milestone 90](../architecture/governance/verification/test-health-90-20261109.md): unchanged pricing Markdown joined `fixtures/pricing_catalog.py`; sibling imports three → two. All 37 methods/181 assertion ASTs and both payload variants equal; 102 focused passes. Missing/contaminated promotion negatives retained. Linux Full+validator 199.72s, smoke 13.75s on another revision; ARM cancelled without steps, not PASS. No speedup claimed.
- [Milestone 75](../architecture/governance/verification/test-health-75-20261108.md): snapshot/row factories moved to existing owners, six → three sibling edges; 146 focused passes and cumulative-usage/subtotal negatives retained. Seven omitted AI Stats recovery tests rejoined registration. The Linux exiting-child race and prior Sessions timeout were not closed by another revision's success.
- Milestone 60: unchanged Watch rendering fixture ownership, seven → six edges, 36 methods/data equal; 79 focused passes and missing-tail-erase/terminal-status negatives. Milestone 45 removed a Daily thread/two-Event timing handshake; synchronous real HTTP plus fixed catalog age removed the reproduced 1.1s-latency false positive without weakening 64-root ≤120s/34-fetch protection. Milestone 30 moved lifecycle factories/Recorder unchanged, 47 methods equal; missing-pump-stop/zero-fatal-exit negatives retained. Milestone 15 fixed snapshot timing/capture ownership; initial missing MODEL import was repaired, not skipped.
- FR000553 made only named README/history/Web-guide prose caps advisory. Source/config/instruction/context controls remain hard. Foundation checks actual bootstrap/Python/Watch handoff; hidden launcher fixtures retain fallback, arguments, exits and 30s startup/10s join/60s emergency cleanup. Formatting-tolerant CI topology rejects lost phases/platforms/cancellation.

### Retained risk owners

Paths below are under `development/tests/`; selections are risk routes, not coverage percentages:

| Risk | Source owner | Protection retained in the portfolio |
| --- | --- | --- |
| Readiness cannot repeat auth/CLI wake | sources/read_recovery | connectivity_reliability: virtual deadlines, exact waits, forbidden cache/CLI calls |
| Replacement cannot resurrect quotas or write credentials | accounts acquisition/subscription | openai_account_switch/account_acquisition: late generations, synthetic credential bytes |
| Unknown is not zero, billing or confirmed execution | analysis/valuation/causal, reports | application_reports, ai_stats_recovery, execution_unverified: independent/null expectations and failure/recovery matrices |
| Rebuildable cache and truthful complete history | cache/database, report history | cache, web_session_detail: WAL/generations, bounded access, freeze/late child/auth/cursors |
| One acquisition; source loss is not completion | application/live, web/events | web_live and nested VM: outage/replay/gap/foreign bounds |
| Navigation cannot revalue or interpret hostile text | Web assets | web_views: 55 roots/151 rows, exact sort/stale/frozen/Unicode |
| Progress cannot starve control or orphan children | Web jobs | web_runtime/web_dispatch: IPC drain, cancellation/parent loss/retained handles |
| HTTP/private observations stay isolated | web/security/observations | web_runtime/web_diagnostics: two hosts, CSRF/rebinding/framing, private canaries |
| Exact native ownership/cleanup | lifecycle/platform owners | native-web profile/smoke; Full foundation/package negatives |

Quick retains independent unit outcomes across domain, attribution, context, projection, Watch grouping/activity, quota periods and reference amounts. Unique transport/process/native/browser protections outside Quick are deliberately no longer universal ordinary-CI coverage; they are **not** reported as Quick passes. No paid/model runner exists under reserved `integration/live`. Real-source/desktop probes remain relevant opt-in evidence, never implied by mocks/VMs/CI.

Keep numeric-loopback binding, PID/birth/current-image ownership, platform-pinned compiler mocks, distinct credential versions and hidden console stubs. `py.exe` existence does not prove an installed interpreter. Native fixture execution stays serial, macOS process-global AppKit faults isolated. Preserve Darwin wire bytes/EPERM rather than catch-all socket suppression. Actual SSE reconnect requires closing sockets; offline browser mode is not that proof. Old HTTP401 grants no identity bypass. Physical clicks, Finder/Gatekeeper, default-browser paint, accessibility, soak, agent effort and billing remain unmeasured here.

### Knowledge mechanics exception

Milestone 120's targeted helper read failed **KNOWLEDGE_LIMIT before writes**: overview exceeds 12 KiB and ancestor journal INDEX independently exceeds routing limits. **Decision Delegate** authorized this delivery's direct edits to this leaf and only the affected overview verification passage/chart/table, preserving runtime provenance. Owned backups and immediate original HEAD/SHA-256 checks matched; resulting diff inspected. These guards are not atomic compare-and-swap. INDEX/CODE_MAP, helper/caps, production controls and release objectives remain unchanged; inherited nonconformance is not helper PASS. The earlier milestone-105 decision was not reused as authority. [Completion](../architecture/governance/verification/test-health-120/COMPLETION.md) points to the normal assessment evidence.

## Next investigations

Keep comparable Quick/CI/manual Full and whole-release observations; unknown publication/wait time is not zero. Investigate native preflight/Linux identity from exact owned evidence before changing production ownership/deadlines. Two sibling-test edges and inherited knowledge violations remain known debt, not count targets or gates. Runtime boundaries are unchanged; verification flow/table describes the dispatch change.

## Rejected hypotheses

- Nearly all Full is Quick, or one green suite proves the end-to-end release budget. Neither follows.
- Relocating tests proves faster unchanged execution or replaces real native/browser/source proof. It does not.
- A native preflight timeout justifies a longer deadline, weaker ownership, platform deletion or marking unknown PASS. It does not; risk-triggered native validation remains.
- Development-only maintenance requires production version/ZIP/live/provider sweeps, or bookkeeping requires broad unrelated knowledge migration. Neither is needed.
