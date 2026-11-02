# FR 000548 — Run shared Web regression once and narrow Windows/macOS CI to native startup

## Owner goal, priority and scope

Reduce repeated GitHub Actions work now that CostGuard's presentation is a web application. The owner asked on **2026-11-02** to inspect whether Windows/macOS jobs run more than the platform-specific web launch path and, if they do, narrow them to launching the web server, creating the tray/menu-bar integration and opening the web page through the platform launcher.

The inspection confirms substantial duplication. Split common regression/browser verification from native integration instead of repeating the full suite on each native OS. Preserve shared test coverage once and retain a small, explicit native Web-startup selection on Windows and both supported Mac architectures.

Permanent identity: **000548**. Ready priority: **000105**, after **FR000546** (000100, already selected for terminal-lifecycle work at inspection) and before the remaining Watch UI/Mini tasks. This is independent CI maintenance; it does not change the selected worker's task or require changing product behavior. Implement against the latest main without modifying unrelated active PRs.

Scope is the hosted Web Beta workflow, its evidence runner and the focused test selection/documentation needed for that split. It does not remove test files, redefine the Full suite, retire CLI support, promote Web out of Beta, introduce a new permanent release gate, or require a product version bump merely for development tooling changes.

## Inspected baseline and measured duplication

Inspected main: **`05c4dc91a45c733b7bf7a7a1337be8f5e741fed2`**. The only workflow is `.github/workflows/web-beta.yml`. Its `verify` matrix contains **windows-2025**, **macos-15** (ARM64) and **macos-15-intel**, and every matrix entry runs:

1. The full registered regression suite and package validation.
2. The isolated native API/launcher smoke.
3. Installation of Playwright and Chromium.
4. The same rendered Chromium browser smoke.

There is no separate Linux/common job. `development/tools/run_tests.py` currently registers **124 Full files**: 120 quick files plus 4 full-only files. The older CI evidence document's 106-file count describes its historical revision and must not be presented as the current total.

The successful [main run 41516683348](https://github.com/qstoffe/cost-guard/actions/runs/41516683348), on 2026-11-02 at product revision `389f9881bc4e00e4c0cbd0f6245fe2af86e037c2`, confirms actual repetition:

| Job | Whole job | Full suite + validator | Native smoke | Browser installation + rendered smoke |
| --- | --- | --- | --- | --- |
| [Windows](https://github.com/qstoffe/cost-guard/actions/runs/41516683348/job/125521923220) | 7m 04s | 5m 31s | 21s | 30s + 16s |
| [macOS ARM64](https://github.com/qstoffe/cost-guard/actions/runs/41516683348/job/125521922934) | 4m 19s | 3m 30s | 10s | 12s + 14s |
| [macOS Intel](https://github.com/qstoffe/cost-guard/actions/runs/41516683348/job/125521923457) | 5m 35s | 4m 16s | 15s | 26s + 24s |

Full/validation consumed **13m 17s of combined job execution**, compared with **46s** for the three native phases. These are observed durations, not a forecast of the new workflow's runtime, monetary savings or wall-clock latency. The retained focused native tests will also take some time. Record the new measured result rather than claiming the old native-phase duration is the complete future job duration.

## 1. One common job for shared behavior

Add one standard hosted **Linux** job that runs the shared work once per workflow execution:

- The complete existing **Full** registered suite, including canonical analysis/accounting/report/Web tests and existing portable CLI tests.
- The package validator once.
- The existing rendered headless Chromium browser smoke once, including shared HTTP/auth, navigation, settings, DOM behavior and SSE/reconnect/shutdown coverage.

Provision Python, Node and the CI-only Playwright/Chromium tooling and required Linux browser dependencies explicitly in that common job. Keep browser tooling outside product dependencies. Use an appropriate supported standard Linux image; do not add a Linux version matrix, extra browser matrix or another copy of the shared tests on Windows/macOS.

The current regression wrapper already has a Linux/non-Windows path using four file workers, and `test_ci_web_beta.py` covers that command construction. The browser probe uses a plain loopback `WebHost` and synthetic report worker rather than a native tray. These make the split feasible, but they are not evidence that the new hosted Linux job has already passed. Run the actual job during implementation and resolve concrete portability/provisioning problems.

Keep the Full registry's meaning and existing assertions/deadlines. Do not achieve a green Linux result by deleting broad test groups, treating failures as success, excluding ordinary Web/accounting checks, or globally loosening timeouts. Legitimate OS-only skips remain named and honest; relevant native Web-launch cases are retained in the jobs below.

## 2. Small native Web-startup jobs

Retain **Windows x64, macOS ARM64 and macOS Intel** for a bounded native test group. The objective is to remove duplicated common work, not silently drop a supported native architecture. The Win32/AppKit/ctypes integration and platform shell boundaries remain OS-specific even when page rendering is shared.

Each native job should contain only the selected Web-launch regressions and the native startup/integration smoke needed to establish:

1. The supported `.cmd`/PowerShell or `.command` launch path starts the owned web host, reports startup success/failure correctly and has the intended command-window/exit behavior.
2. HTTP readiness is associated with a usable native tray/menu-bar event loop, with the real Windows tray or macOS status-item APIs exercised.
3. The Open action and launcher browser handoff target the correct owned loopback page; handoff success/failure is handled correctly and the actual extent of browser-opening evidence is stated.
4. Exit and failed startup clean up the owned server/native resources without leaving an orphan or touching another instance.
5. Necessary native interpreter/process/lock behavior for that startup and ownership boundary remains covered.

Remove the Full-suite invocation, general package validation, Playwright/Chromium installation and generic page-rendering/navigation tests from these native jobs. Do not retain the broad report/accounting/CLI/performance suite under a newly named native profile.

The existing bounded native probe's restart, startup-fault cleanup, source-change shutdown and macOS app-wrapper cache/rebuild checks belong to the same launcher/owned-host area and can be retained. Do not expand this FR into new unrelated native acceptance work.

### Retain relevant OS-only cases that Linux will skip

Running only the current `native` phase would lose some useful launcher regressions previously executed incidentally inside Full. Define an explicit, maintainable **native Web-launch selection** using existing tests and, where proportionate, a named runner profile or selected cases. Include the necessary real platform cases from:

- `development/tests/test_windows_web.py`: `.cmd` waiting/status propagation, bounded Python discovery and real PowerShell argument/discovery behavior.
- `development/tests/test_windows_web_activity.py`: Windows startup-stage output and failure status handling.
- `development/tests/test_web_lifecycle.py`: Windows-only console-free interpreter selection, missing GUI interpreter behavior, owned lifetime-lock protection, stale/access-denied process identity and native handle cleanup needed for safe Web startup.
- `development/tests/test_macos_web.py`: the real zsh/PTY `.command` lifetime/status case where supported, alongside the actual AppKit smoke.

Keep the selection focused and reviewable. Portable mocked tests remain in Full; modest overlap within a genuinely focused launcher file is acceptable, but it must not grow back into a general regression suite. Legacy terminal-only launcher cases need not be part of native **Web** CI merely because they mention Windows/macOS. Preserve their files/registry and document any intentionally no-longer-hosted OS-only CLI coverage accurately.

## 3. Be precise about browser opening

The inspected `development/tests/integration/ci_native_web.py` uses a disposable entry shim and intentionally replaces `WebHost.open_browser`/lifecycle openers. It exercises real tray/menu Open dispatch and failure handling, but does **not** prove that the OS-registered browser opens. The separate current Playwright phase launches its own headless Chromium, which also does not prove that native handoff.

Retain or refine a bounded handoff check at the actual platform boundary. Verify the supported launcher/Open action supplies the correct owned loopback destination and preserves truthful success/failure behavior. Where a real registered-browser handoff can be safely exercised on the disposable hosted runner, use the production handoff and record that distinct result. Do not claim real browser opening when the boundary is replaced, or infer a loaded/painted page merely from an OS handoff return value.

If the hosted environment cannot establish actual default-browser launch or consumer desktop behavior, state that precise limitation in the evidence rather than reinstalling the full page-test stack on every OS or declaring a mocked action equivalent. Full page loading/rendering remains covered once in the common job.

Do not invoke the broad opt-in workstation probes automatically, alter default-browser registration, use consumer profiles/accounts, run live model/source work or introduce persistent desktop configuration. The existing disposable fixture/owned-process boundary remains appropriate. Physical tray visibility/clicks, Finder/Explorer double-click, Gatekeeper and browser first paint are separate from programmatic native API/handoff evidence; no new blanket manual approval/release gate is introduced.

## 4. Evidence and dependencies must match each job's scope

`development/tools/ci_web_beta.py summary` currently expects regression, native and browser phase files in every job. After the split, give each job an explicit expected-phase plan or equivalent scope:

- **Common:** full regression/package validation and rendered browser checks.
- **Native:** the selected native Web-launch regressions and native smoke/handoff checks for that platform.

Report an intentionally out-of-scope phase as assigned elsewhere/not applicable, or omit it with a clear job scope. Do not manufacture PASS output for phases that never ran, and do not present intentionally omitted phases as unexplained missing work. Conversely, an expected phase that was blocked, failed or did not finish must remain visible and must not result in a falsely successful verification. Preserve failure propagation across provisioning, malformed/missing evidence and cancellation; summary generation must not mask a failed step.

Retain useful bounded evidence: actual platform/architecture/image and relevant tool versions; per-file Full counts and named skips; selected native checks; sanitized failure diagnostics; measured phase durations; short-retention JSON artifacts. Keep the historical successful/failed run records truthful and add/update current scope documentation rather than rewriting past evidence as if it used the new split.

Avoid unnecessary native tool provisioning. `facts()` currently calls `node --version` unconditionally, so removing `setup-node` alone can leave an accidental dependency on a preinstalled executable. Make irrelevant tool discovery scope-aware/optional, or keep an explicit dependency only when a retained native check truly needs it. Native-only jobs do not need Playwright/Chromium just to record a browser version.

Preserve the existing public-repository boundary, standard hosted runners, read-only token, checkout without persisted credentials, synthetic/offline data, bounded timeouts, superseded-run cancellation and short artifact retention. Keep runner concurrency bounded when adding the common job. Preserve current manual/PR/main trigger intent and avoid launching CI for unrelated backlog-only changes. Do not add secrets, paid/larger/self-hosted runners, caches of private/browser state, branch protection or new release requirements.

## Acceptance evidence and implementation pointers

1. **No repeated common suite:** workflow inspection and a hosted run show Full regression, package validation and general rendered Chromium verification exactly once, in the common Linux job. Windows/macOS contain only the declared native Web-startup scope.
2. **Actual Linux verification:** the common job executes successfully with explicitly provisioned dependencies, the current full registry and meaningful browser checks. Report actual failures/limitations; a source-level Linux branch or a mocked orchestration test is not hosted PASS evidence.
3. **Native boundary retained:** all three native architecture jobs exercise their real launcher/native API/server readiness/cleanup boundary plus the relevant selected OS-only startup cases. Full-suite removal does not silently skip Windows PowerShell/interpreter/ownership regressions that belong to that boundary.
4. **Browser evidence is honest:** distinguish Open callback routing, actual OS handoff, loaded browser page and physical desktop acceptance. No stubbed call is reported as a real default-browser launch; no broad repeated browser suite is added back to hide that gap.
5. **Scoped reporting:** test correct common/native plans, a failed/blocked required phase, missing/malformed phase output, cancellation and intentionally absent phases. Expected work cannot silently disappear or be counted as PASS, and deliberately narrower jobs are not misleadingly reported incomplete.
6. **Tool/resource discipline:** native jobs install no unused browser tooling and do not depend accidentally on Node. Full definitions, assertion/deadline semantics, isolation, triggers, permission boundaries and bounded artifacts are preserved. Existing selected task/PR execution is not cancelled merely to publish this FR.
7. **Measured result and documentation:** record the new run/job links, actual selected files/cases, phase durations and native/default-browser limitations. Compare observed work with the baseline without promising a fixed percentage saving. Update current CI owner documentation; preserve historical evidence and local/full test availability.

Likely owners: `.github/workflows/web-beta.yml`; `development/tools/ci_web_beta.py`; `development/tools/run_tests.py` if adding a narrow selection; `development/tests/test_ci_web_beta.py`; `development/tests/integration/ci_native_web.py`; and current CI scope/evidence documentation. Change `ci_browser_web.py` only if the actual Linux run exposes a concrete portability problem. Reuse existing relevant fixtures rather than create a second CI framework.

Publishing this FR is backlog-only. The workflow reduction itself is implementation work; no tests were disabled and no active run was cancelled when the request was created.
