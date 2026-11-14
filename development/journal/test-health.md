# Test system health

Source revision: 3266deeab687ca1c3dac0276b687c543d08cd470
Checked revision: 3266deeab687ca1c3dac0276b687c543d08cd470
Last checked: 2026-11-14
Status: current

## Summary

Milestone 150 found an actual **954s common CI job**, beyond the 15-minute controllable release budget before local verification, PR/default repetition or publication. Its mouse journey consumed **799s**, principally twelve serial 61s stationary holds. This is execution, not runner queue time. Test Health reduces ordinary coverage to two unchanged real-time holds, one PiP and one Full Watch; keeps independent mouse/keyboard and touch portfolios; moves the other ten holds and mixed/control diagnostics to manual Full. Production watchdog/security/accounting are unchanged. Coverage is reduced, not equivalent.

On Windows 10.0.26300/Python 3.14.7/four workers: baseline Quick **57 groups/697 passes/11.9s**; candidate **700 passes/10.7s**. Full baseline **197 groups/2424 passes/four macOS-only skips/169.8s**. Milestone 135 was Quick53/660/9.7–9.6s, Full187/2329/151.4s: changed workloads, not an isolated unchanged-work regression. Source investigation and causal CI simplification replace normalization of the slower route. Final hosted execution/readback belongs to the delivery PR; missing after timings are not fabricated savings.

[Assessment](../architecture/governance/verification/test-health-150-20261114.md) and [completion](../architecture/governance/verification/test-health-150/COMPLETION.md) record checks, protection loss and limits. Every-profile end-to-end compliance and the five-minute small-change goal remain **UNVERIFIED** outside measured routes, not HEALTHY or waived.

## Evidence

### Current scope, cause and correction

Inventory: 1,398 text/config records (408 source/config,614 documentation,376 test),370 binary/over-1-MiB exclusions,zero exact-byte duplicate groups. Metadata does not prove semantic duplication/dead code. Top-level tests196; Full197 groups/195 files; only the documented developer benchmark is unregistered.

Read both workflows, `run_tests.py`, `ci_web_beta.py`, integration `ci_browser_web.py`, `ci_mini_tooltips.py`, `probe_web_help.cjs`, `probe_hover_stationary.cjs`, `probe_mini_help.cjs`, `probe_mini_duration.cjs`; selector/exclusion tests, foundation mutation/bootstrap tests; production help watchdog and browser security. Public small FR000705 and larger FR000704 completions/PRs provide development-to-final friction, not private-session evidence. No other-session scratch, transcripts, paid/model/live or visible-desktop sweep.

Main run [43553043571](https://github.com/qstoffe/cost-guard/actions/runs/43553043571) executes common03:43:01–03:58:55Z (**954s**); created03:42:58Z, so total dispatch tail957s includes3s before execution. Steps: container19s, checkout5s, Python0s, Node4s, Quick+validator21s, binding4s, browser8s, mouse799s, touch3s, mixed49s, control35s. Small rounding/gaps remain in total; don't sum parallel job-minutes. Twelve61s holds alone are732s. Mouse/control extra diagnostics and normal setup make the ordinary job itself over budget. The prior visit's missing timings no longer justify leaving this route unchanged.

Main [43588565040](https://github.com/qstoffe/cost-guard/actions/runs/43588565040), an unrelated Token Mix edit, is67s job/70s workflow tail: Quick+validator19s, browser8s; Mini skips. That conditional route cannot certify the affected-tooltip route. Earlier common jobs56/62/60s and browser8/9/9s remain meaningful non-tooltip baselines.

Keep exactly two61s holds with unchanged positive hover/hit/connection checks, zero pointer input,3s updates and normal exits. The full twelve-target selector remains on `workflow_dispatch`. Mixed/control steps also become manual; existing FR000704-only exclusion stays exact, never transferable. Mouse/touch still test exact cost/Total/running Duration, themes/units, focus/selection, invalidation and literal hostile text. Manual dispatch no longer skips probes merely because HEAD's owners are unchanged. Probe/selector changes themselves trigger affected-source execution. Per-journey NOT RUN files avoid overwriting each other's evidence.

The ten removed ordinary holds no longer individually protect Activity, prompt cost/Total, Ctx/summary and Full Watch prompt/session/heading stationary lifetimes. Mixed-input/context-help/watchdog/control combinations may regress unnoticed in ordinary CI; manual coverage is NOT RUN unless executed, not equivalent protection. No production safeguard, native trigger, deadline, model/access control or package/version gate is weakened.

### Local comparison and historical baselines

Quick baseline697 passes/11.9s → candidate700/10.7s (three new selection/routing cases; not an isolated speed gain). Full baseline2428 tests =2424 passes+four named macOS skips,zero failures,169.8s. Slowest: foundation77.53s, historical scale35.44s, Web dispatch35.21s, detail liveness29.81s, catalog24.74s. Foundation repeats actual copied-package validators; larger tree/new tests and concurrent imports/load affect comparison to old68.4s. No measured OS attribution or timing exception. Quick remains a real subset, below90s on this reference environment.

- [135](../architecture/governance/verification/test-health-135-20261113.md): restored six recorded-model provenance tests to Full;187 groups/2329 passes/four skips/151.4s. Moving the long alias matrix first made Quick10.1s versus9.7/9.6s; reverted **NO_GAIN**, not a slower replacement baseline.
- [120](../architecture/governance/verification/test-health-120-20261110.md): Quick52/646/8.6s; moved deep24-layout/321-group navigation/zoom/fault/45s-stall work to manual Full. Browser133–145s/common173–196s before subsequent pinned-container setup improvement. Omitted ordinary deep coverage remains intentional.
- [105](../architecture/governance/verification/test-health-105-20261109.md): nominal Quick175/181 groups/96.2s →52/639/8.2s; Full181/2224/two skips/128.2s. Seeded regressions yielded20 expected failures,zero harness errors. Ordinary Full→Quick and risk-based native triggers intentionally retire universal deep/platform proof.
- Earlier fixture consolidation: pricing edges3→2, rendering7→6; assertions retained, no speedup claim. Milestone45 removed a Daily two-Event timing handshake after reproducing1.1s false latency without weakening64-root/120s/34-fetch controls. FR000553 exempted only named product prose, not source/config/instructions.

### Delivery friction and retained uncertainty

FR000704 records196 files/2419 passes/four skips, real RED old30s cutoff and twelve61s GREEN holds. Independent core passes do not repair its mixed Total-heading FAIL/later NOT RUN cases or Earlier convergence exception. PR310 creation01:28:47→merge03:42:56 spans8049s, including implementation/repairs/decisions; not final-verification latency. Its default alone then took957s elapsed. FR000705 records197 groups/2428 total tests/four skips and five real report scopes; its initial strict timeout remains failed, not erased by later success.

Earlier PR293 observed PR→merge397s + default tail145s =542s, preceding local readiness unknown. PR286's first final-head check→last default native completion1057s includes ARM runner wait: actual native jobs63/76/54s, ARM starts603s after default workflow creation. These are elapsed/wait observations, not1057s controllable work. Native max-parallel2 creates a real wave; PR/default repeat work. No skip/evidence registry or automatic extra dispatch is introduced.

Risk owners remain connectivity retry/credential/CLI wake; account generation/isolation; unknown-versus-zero/history recovery; pinned detail/cache generations; browser replay/gaps/literal text; loopback/framing/CSRF; cancellation/parent-loss/exact native process identity/cleanup. Their deterministic owners remain in Full, not all Quick. Physical clicks/Finder/Gatekeeper/accessibility and old Intel preflight/Linux exiting-child uncertainty remain unproved. No paid-call/agent-effort/billing claim.

### Knowledge mechanics exception

This visit's helper read rejected inherited oversized OVERVIEW with **KNOWLEDGE_LIMIT** before writes; journal ancestor routing already exceeds eight routes, and overview shape differs from current validator. **Decision Delegate** authorizes only direct consolidation of this leaf and `development/architecture/OVERVIEW.md`, retaining diagrams/navigation and reducing both below12KiB. Original HEAD/SHA-256 guards matched immediately before patching; owned backups retained and diff inspected. Ordinary patching lacks cooperative locking/atomic compare-and-swap. No index/helper/cap/control changes, helper PASS or release-budget/test-acceptance waiver.

## Next investigations

Compare actual after CI with the affected799s mouse baseline, not unrelated skipped runs; distinguish measured reductions from the610s removed serial waits. Preserve readiness/local/publication/external-wait gaps and investigate >10% comparable regressions. Optional manual exhaustive/deep runs are deliberately expensive development checks, not an ordinary release prerequisite. No product version/archive or broad live/desktop sweep. Keep inherited knowledge routing debt explicit.

## Rejected hypotheses

- Green unrelated67s CI proves affected tooltip health: false; the affected route executes954s.
- All twelve stationary targets must block every tooltip release: Test Health explicitly subordinates that coverage to release speed; preserve representative real-time evidence and disclose loss.
- Moving a suite to manual means it passed or preserves ordinary protection: false.
- Later native/independent-input success cures historical timeout/mixed-input failures: false.
- Three new fast selector tests or an unrelated micro-cleanup alone fix the over-budget route: only removing its serial mandatory work addresses the cause.
- Development-only maintenance needs product version/ZIP/live checks or unrelated index migration: neither is introduced.
