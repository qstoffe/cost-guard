# Test system health

Source revision: 70462006910b0507c7f21412ef87330c3f675e2f
Checked revision: 70462006910b0507c7f21412ef87330c3f675e2f
Last checked: 2026-11-09
Status: current

## Summary

Milestone 105 replaces nominal Quick (175/181 Full groups) with 52 unit/component groups, including CI-selector regressions. Same Windows/Python 3.14.7 runner, four workers: **96.2s → 8.2s**, 639 passes. All 181 Full groups remain registered; the portfolio run passed 2,224 tests with two macOS skips in 128.2s. Final CI-selector changes subsequently passed their focused 21-test file and final Quick. These are distinct overlapping runs, not additive independent tests or a final unchanged Full rerun.

Ordinary hosted PR/default verification now uses Quick, validator and Chromium smoke. Manual dispatch retains Full. Native Windows/macOS ARM/Intel validation moves intact to a separately path-triggered workflow: entrypoints, launchers, config, host/lifecycle/security/jobs/shared Live and native-test/tool dependencies still trigger it; isolated assets, analysis/application calculations and unrelated tests do not. This deliberately removes universal deep/native regression execution from ordinary CI, not production safeguards. Full and focused development checks remain available. [Assessment](../architecture/governance/verification/test-health-105-20261109.md) and [completion](../architecture/governance/verification/test-health-105/COMPLETION.md) state measured scope and remaining timing uncertainty; actual candidate CI/publication truth is in the PR.

## Evidence

### Release portfolio and trend — milestone 105

Before: Quick 175 groups, 2,151 pass/two skips, 96.2s; just six Full-only groups. After: Quick 52 groups, 639 pass/no skips, 8.2s; Full membership exactly equal to the original 181 groups, with no missing top-level files except the intentional developer benchmark. HTTP, spawned jobs/cache restarts, Node VMs, native launchers, package mutation and scale checks remain in Full, not hidden nested Quick dispatch. No product-behavior tests/assertions or deadlines are deleted/relaxed; CI-selection assertions follow the intentional new route. Six in-memory seeded regressions produce 20 expected assertion failures and zero harness errors: missing host trigger, broad native fanout, lost Full HTTP case, Quick integration expansion, ordinary Full restoration and accepting Quick evidence for manual Full.

Full's 128.2s is consistent with FR000655's recorded 133.9s on the same workstation family, but not a controlled runtime speedup: selection order, revision and concurrent load differ. The Quick improvement is a measured portfolio change, not faster unchanged tests or consumer runtime. Final selector coverage checks ordinary/manual events across all three platforms, exact suite accounting, missing/incomplete reports, prior job failure, hosted-only denial and retained native phases.

Fresh pre-change hosted sample: four successful completed main runs, one failed, one queued. Linux critical-path jobs for equivalent recent routes were 244s and 262s; regression+validator 198s/201s, provisioning 24s/38s, smoke 14s each. Since milestone 90's 199.72s regression and 13.75s smoke, no >10% comparable phase regression is evidenced. No comparable total baseline or flake-rate estimate follows. The old PR/default pair alone repeated roughly eight minutes of unchanged hosted work; local Full, relevant final installation proof and publication add serial latency. Exact whole-release controllable/total elapsed and external waiting were not reconstructed from unrelated sessions. The 15-minute end-to-end objective remains **unverified**, not a healthy classification of unknown time. Candidate timings belong in the delivery PR.

[Run 42693636281](https://github.com/qstoffe/cost-guard/actions/runs/42693636281) failed macOS Intel shell-2 preflight: TimeoutExpired at native install, launcher `tray_unavailable`; 22 native regression tests and other native phases passed. A prior shell preflight succeeded. This is an unresolved native initialization observation, not proven product failure, harmless flake or an authorized deadline increase. New native triggers still cover this mechanism. Historical Linux exiting-child identity race also remains unresolved; neither is closed by local Windows success.

### Earlier causal simplifications and meaningful baselines

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

The targeted knowledge-helper read failed **KNOWLEDGE_LIMIT before writes** because existing documents exceed its 12-KiB read limit; ancestor INDEX also inherits byte/route excess. **Decision Delegate** authorized direct one-delivery edits to this leaf, affected overview verification passages and stale CODE_MAP navigation, with original HEAD/SHA checks, owned backups, drift reconciliation and resulting diff inspection. No existing knowledge lock was found. These guards are not atomic compare-and-swap. No helper, index, cap, production control, release objective or Git protection changes; inherited nonconformance remains failed/unverified, not helper PASS. Exact before/after sizes and scope are in the assessment.

## Next investigations

Keep comparable Quick/CI phase and total release observations at the next scheduled visit; do not normalize unknown publication/wait time to zero. Investigate native preflight and Linux exiting-child identity using exact owned evidence before changing production ownership/deadlines. Two sibling-test edges and inherited knowledge routing/size violations remain bounded known debt, not count targets or fresh workflow gates. No runtime architecture boundary changes; verification flow/table and runner navigation change with executable CI.

## Rejected hypotheses

- Nearly all Full is Quick, or one green suite proves the end-to-end release budget. Neither follows.
- Relocating tests proves faster unchanged execution or replaces real native/browser/source proof. It does not.
- A native preflight timeout justifies a longer deadline, weaker ownership, platform deletion or marking unknown PASS. It does not; risk-triggered native validation remains.
- Development-only maintenance requires production version/ZIP/live/provider sweeps, or bookkeeping requires broad unrelated knowledge migration. Neither is needed.
