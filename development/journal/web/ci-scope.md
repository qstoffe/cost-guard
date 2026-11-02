# Shared Web CI and native startup evidence

Source revision: 232fb1ae73b47c1999f13779132c58ec2209bbac
Checked revision: 26b5ca1fdcbef8ad6b938346a042e92cb5fbbc88
Last checked: 2026-11-02
Status: current

## Summary

FR 000548 runs unchanged Full, package validation and rendered Chromium once on Linux. Windows x64 and both Mac architectures retain explicit native Web-launch regressions and real Win32/AppKit/lifecycle smoke, without Node/browser-tool provisioning or general regression duplication. No product boundary/version change. Current scope and historical evidence remain in development/architecture/governance/verification/web-beta-ci.md; older test-health measurements retain their original revision and repeated-suite scope.

## Evidence

Reproduce with .github/workflows/web-beta.yml on standard public GitHub-hosted runners. development/tools/ci_web_beta.py requires --scope common|native and fail-closes missing/malformed/unfinished/failed expected phases, incomplete suite reports, prior step failure and cancellation. Unassigned phases are explicitly elsewhere, never manufactured PASS. development/tools/run_tests.py owns native-web's explicit file/case selection; Full's 125 files, assertions and 240-second deadlines remain unchanged. development/tests/test_ci_web_beta.py has 13 deterministic orchestration/accounting/OS-boundary tests; local Windows native-web passed all 12 groups in 16.1s.

[Run 41526896465](https://github.com/qstoffe/cost-guard/actions/runs/41526896465), source 232fb1ae73b47c1999f13779132c58ec2209bbac, PR 121, tested merge checkout be4ca4ee598b24e6d5ebaa523ad462d6b7cf15b7. All four jobs succeeded. Linux: 125 files, 1,506 passed, 15 named OS-only skips, zero failures/errors; regression/validator 86.65s, Chromium 10.24s. Windows: 27 passed, native selection 23.75s, smoke 17.14s. Mac ARM64 and Intel: 20 passed each, selections 2.79/3.56s, smoke 17.33/23.33s. Native suites had zero skips/failures/errors. Full/native-tests JSON retain exact files/cases/skips and durations; Checks may retain fewer individual skip annotations. Actual images/tool versions/job links are in the current scope document.

Compared with FR's observed baseline 41516683348, repeated Full/validator job steps totalled 13m17s there versus one 86.65s phase here. Native selections plus smoke totalled 87.90s here; whole-job combined execution was 4m47s versus 16m58s. Different revisions/images/OS assignments make this an observed work reduction, not a controlled performance or fixed cost/latency promise.

The Decision Delegate authorized one production registered-browser handoff per confirmed disposable native runner, targeting only its freshly owned synthetic loopback host. All three reported ACCEPTED. The menu/native probe still stubs browser dispatch; the separate production os.startfile or /usr/bin/open result does not prove a browser process, navigation or first paint. No consumer profiles/accounts, registration changes, physical clicks, workstation UI or live acquisition are authorized. An unavailable association must be recorded UNAVAILABLE, not PASS or repaired registration.

The Decision Delegate resolved inherited local/version policy using the user's supplied instruction: 'Development-only edits need no product tests/release/version work.' No unrelated local Full, Diagnostics, live-source, version/release or ZIP work ran. The requested hosted Linux Full/validator/Chromium and all native checks did run successfully; this is not a waiver of their execution.

### Documentation-head duplicate-check exception

Documentation-only head 26b5ca1fdcbef8ad6b938346a042e92cb5fbbc88 triggered [run 41527754941](https://github.com/qstoffe/cost-guard/actions/runs/41527754941), tested merge checkout dbf7d079896b91a5bdd4351b2867fa58da353296. Linux, Windows and Intel Mac passed. ARM64 job 125559763048 remained capacity-queued with no executed steps at the decision: not PASS and not verified at that documentation head.

The Decision Delegate explicitly authorized merge reusing successful ARM64 implementation evidence from run 41526896465 and the three current-head successes because code/workflows/tests are identical. This is evidence equivalence, not an elapsed-queue-time threshold. A reporting-only exception-note commit and its automatically triggered duplicates need not all finish again under the same exception. Uncompleted checks remain unverified, never PASS; any observed failure or changed base must be investigated. No cancellation/retry/protection bypass or further UI permission is authorized. COMPLETION and PR context retain the decision; final delivery reports actual current statuses.

## Next investigations

Inspect retained per-file evidence before altering selection or deadlines. Preserve OS-only Web-launch cases when adding coverage; legacy terminal-only Windows shell cases remain locally registered but no longer execute in hosted Web CI. Consumer-desktop/Finder/Gatekeeper/physical input/default-browser rendering remain separately scoped and unverified. No automatic local UI probe or new release gate.

## Rejected hypotheses

- Removing duplicated Full requires dropping supported native architectures or Web-launch OS cases: explicit native-web and the real hosted matrix retain them.
- A source-level Linux branch is hosted proof: actual Full/validator/Chromium execution supplies this revision's evidence.
- Callback mocks or successful OS handoff prove page rendering: shared Chromium proves its own headless page scope only; physical/default-browser first paint is still unverified.
- Narrow jobs require fake PASS for omitted phases, or summary can hide provisioning/cancellation: explicit plans and fail-closed summary tests reject both.
