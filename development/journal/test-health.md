# Test system health

Source revision: d2079700399bebc77cb6d0470ce673f6fd206fad
Checked revision: d2079700399bebc77cb6d0470ce673f6fd206fad
Last checked: 2026-11-13
Status: current

## Summary

Milestone 135: Quick's 53 groups pass **660 tests in 9.7/9.6s** on Windows/Python 3.14.7/four workers; milestone 120 was 52/646/**8.6s**. The >10% increase prompted source investigation and an actual scheduling simplification attempt: moving the long alias matrix first took **10.1s**, no gain. That candidate was reverted, not normalized into a slower baseline. The portfolio has changed; these observations do not isolate every cause.

Inventory found six `test_recorded_model_help.py` regressions absent from Full. Register them in Full only and extend the existing selector assertion. Final Full: **187 groups,2329 passes,four macOS-only skips,151.4s**, zero failures. Seeded omission gives one expected selector failure/zero harness errors. Quick, ordinary CI, deadlines, production controls and native triggers are unchanged. The sole remaining unregistered top-level file protects an intentionally separate developer benchmark. [Assessment](../architecture/governance/verification/test-health-135-20261113.md) and [completion](../architecture/governance/verification/test-health-135/COMPLETION.md) record current checks and limits. No product/version/archive work.

Recent common hosted jobs take **56/62/60s**, browser **8/9/9s**, versus milestone 120's **173/189/196s** and **133/142/145s**. Deep coverage remains manual and NOT RUN in ordinary CI. Native runner waiting can dominate elapsed delivery. Every-profile end-to-end 15-minute compliance and the five-minute small-change goal remain **UNVERIFIED**, not HEALTHY; no evidenced >15-minute controllable route is waived.

## Evidence

### Milestone 135: scope, cause and change

Source inspected: both workflows; `development/tools/run_tests.py` and `ci_web_beta.py`; integration `ci_browser_web.py`; `test_ci_web_beta.py`, `test_active_hour.py`, `test_ccost_midnight.py`, `test_claude_alias_identity.py`, `test_recorded_model_help.py`, `test_benchmark_large_month.py`, bootstrap and representative Web runtime/lifecycle tests; production `src/analysis/active_hour.py` and `src/web/security.py`. This samples normal/failure/recovery and risk ownership, not exhaustive executed coverage. Inventory: 1,315 text/config records (393 source/config, 566 documentation, 356 test); 355 binary/over-1-MiB exclusions, zero exact-byte duplicate groups. Metadata does not establish dead code or semantic duplication.

The 186 top-level test files initially mapped to 184 selected files/186 groups (three historical-report class groups). `test_recorded_model_help.py` was unintentionally omitted: alias/pinned contributor separation, exact per-effort compact-codec identity, sampled TPS provenance, compaction's own model, failed saved selection versus zero usage, and incomplete session-help coverage. Six cases pass focused in 0.7s. Full registration becomes 187 groups/185 files; the developer benchmark remains focused/manual, as already documented in milestone 60. Existing selection tests pass 24 cases in 1.4s. Tests/fixtures/assertions are not deleted or weakened.

Quick before: 9.7/9.6s, 660 passes/zero skips/failures. New midnight registration and broader alias matrices explain changed work; no unchanged-workload 13% regression is asserted. On the same candidate tree, moving alias identity from the tail to the start gave 10.1s with the same 660 passes; its own process rose from 1.57–1.66s to 2.28s under different overlap. Concurrent imports/setup are a plausible contributor, not measured OS attribution. No scheduling change retained and no speedup claimed. Quick remains a real small foundation, not nearly all Full; its 90s objective is satisfied on this defined reference environment only.

### Current hosted phases and completed-change friction

Fresh bounded latest-main sample: 12 runs, 11 initially complete successes and one native still in progress; targeted later job evidence shows that native's three jobs succeeded. No transcript/session crawl. Runs [43330632451](https://github.com/qstoffe/cost-guard/actions/runs/43330632451), [43324731675](https://github.com/qstoffe/cost-guard/actions/runs/43324731675), [43318204420](https://github.com/qstoffe/cost-guard/actions/runs/43318204420): common job **56/62/60s**, Quick+validator step **10/17/16s**, container initialization **28/25/23s**, pinned browser binding **2/3/2s**, browser **8/9/9s**. Current source uses Playwright's pinned container instead of per-run browser/OS dependency installation; the deep matrix stays on manual Full. Workload/setup differ from milestone 120, so this is observed route improvement, not an isolated attribution or gain caused by this visit. Current annotations confirm 660 unit passes, regression 9.11s, rendered smoke 7.98s, Chromium 141.0.7390.37/Python 3.11.18/Node 22.23.4. Container image metadata is null; no guessed image identity.

Sampled small FR000690 and larger native FR000681, plus FR000689's repaired verification history, through public completions/PRs, not private records. FR000690 records local Full 155.6s/2323 passes/four skips, focused source/rendering, hidden PiP and installed-source evidence. Its broad mixed-input Total-heading probe remains FAIL and later Duration cases NOT RUN under its own scoped Delegate decision; this assessment does not reuse or erase that exception. FR000689's first Full was not wholly green: version-edit race, focused repairs and a validator-child timeout; cold historical causal replay remains unverified. Freeze the candidate during measurements; independent warm successes are not retrospective failure repair.

[PR293](https://github.com/qstoffe/cost-guard/pull/293) final-head common/Windows/ARM/Intel checks took **64/50/43/80s**; ARM started 299s after the first jobs. PR creation to confirmed merge was 397s; merge to last default native job completion 145s, hence **542s total observable PR-to-default tail**, including dispatch/wait and publication. Readiness/local final validation before PR creation is not timestamped. [PR286](https://github.com/qstoffe/cost-guard/pull/286) final-head jobs took **70/62/53/77s**. Its default native run [43274367471](https://github.com/qstoffe/cost-guard/actions/runs/43274367471) spanned 658s workflow elapsed, yet Windows/Intel/ARM executed **63/76/54s**; ARM started 603s after creation, 456s after both earlier jobs ended. Do not call that 658s of controllable testing or sum parallel job-minutes. The first final-head check start to last default native completion spans **1057s**; that is total elapsed, not a proven >15-minute controllable route. Waiting after checks and untimestamped local/publication work remain unallocated, not zero.

Native `max-parallel:2` adds a real serial wave; PR/default repeat selected work. No stale-evidence registry or skip introduced. Current default jobs take63/56/78s, ending143s after workflow creation; another native sample spans132s. The only manual-dispatch sample (2026-11-01) predates current deep routing, not current manual compliance. No new dispatch.

### Meaningful earlier baselines

- [Milestone 120](../architecture/governance/verification/test-health-120-20261110.md): 52 groups/646 passes/8.6s. Deep 24-layout/321-group navigation/zoom/fault/45s stall moved intact from every ordinary run to existing manual Full. Original smoke/pager AST characterized; 24 selector cases passed. Unique deep bugs may escape ordinary CI; omission is NOT RUN, not equivalent protection. Browser then 133–145s/common jobs 173–196s.
- [Milestone 105](../architecture/governance/verification/test-health-105-20261109.md): nominal Quick 175/181 groups, 2151 passes/two skips, **96.2s → 52/639/8.2s**. Full retained 181 groups/2224 passes/two skips in128.2s. Six seeded regressions caused20 expected assertion failures/zero harness errors. Ordinary CI Full→Quick; native restricted by platform risk. Universal deep/native regression coverage intentionally retired, not replaced by Quick proof.
- [Milestone 90](../architecture/governance/verification/test-health-90-20261109.md): pricing fixture sibling edges3→2, 37 methods/181 assertion ASTs equal,102 focused passes; no speedup claim. Milestone75 moved fixtures6→3 edges and restored seven omitted AI Stats tests. Milestone60 moved rendering fixtures7→6 edges. Earlier bounded negative checks retained missing-tail, terminal-status, subtotal and cleanup protection.
- Milestone45 removed a Daily thread/two-Event timing handshake and reproduced1.1s false-positive latency without weakening64-root/120s/34-fetch protection. Milestone30 moved lifecycle fixtures unchanged. FR000553 relaxed only named non-executable prose caps; source/config/instruction/context controls stay hard.

### Retained risk owners and limits

Under `development/tests/`: connectivity_reliability protects typed retry/no credential/CLI wake; account_acquisition/openai_account_switch protect generation/account isolation and synthetic credential bytes; application_reports/ai_stats_recovery/execution_unverified protect unknown-versus-zero and recovery; cache/web_session_detail protect disposable generations, pinned history and late/auth/cursor handling; web_live/web_views protect one acquisition, replay/gaps, literal hostile text and no revaluation; web_runtime/web_dispatch protect numeric loopback, framing/CSRF, IPC, parent-loss/cancellation and retained handles; lifecycle/native-web protect process birth/image, locks and cleanup. These are owners, not coverage percentages or claims that Quick executes them all.

No coverage retired this visit. Preserve hidden launch stubs, serial native fixtures, AppKit isolation, exact Darwin bytes/EPERM, distinct credential versions and real socket closure for SSE loss. The historical macOS Intel preflight timeout and Linux exiting-child identity race are not closed by later successes. Current Intel native annotations report successful real preflight children, including6.122s shell2, but do not establish old root cause or a long-run flake rate. No paid/model, real-source, browser or visible-desktop sweep. Physical clicks/Finder/Gatekeeper, accessibility, agent effort and billing remain unmeasured.

### Knowledge mechanics exception

Milestone135's leaf read succeeded; apply failed **INDEX_LIMIT before writes** on inherited ancestor routing. **Decision Delegate** authorized only this direct journal consolidation: unrelated router migration is disproportionate. Original HEAD/SHA-256 guards matched and owned backup retained; diff inspected. Ordinary patching lacks the helper's cooperative locking/atomic CAS. INDEX/CODE_MAP/overview/helper/caps remain unchanged; no helper PASS or release-objective waiver. Completion points here.

## Next investigations

Keep comparable Quick/Full/CI/manual and readiness-to-publication observations, without per-feature gates or mandatory telemetry. Investigate >10% comparable regressions and exact native failures causally. Current unknown local/publication/manual time is not zero or budget PASS. Runtime and verification topology remain unchanged; only existing Full membership and its selector assertion change. No architecture diagram churn is warranted. Keep inherited knowledge routing/overview debt explicit rather than broadening this visit into migration.

## Rejected hypotheses

- Moving the longest Quick group first must save time: tested, slower, reverted.
- A missing Full registration is intentional because focused tests once passed: false for the six product model-provenance cases; unlike the documented developer benchmark, no manual-only disposition exists.
- Green Quick/CI or summed parallel job times certify every15-minute route: neither follows; external waits and untimestamped work remain distinct.
- Later native success proves the old timeout harmless or authorizes weaker ownership/deadlines: it does not.
- Development-only maintenance needs product version/ZIP/live/provider sweeps or unrelated knowledge migration: none is introduced.
