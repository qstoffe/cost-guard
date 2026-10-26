# Web Beta hosted revalidation

FR 000410 re-tests the implementation delivered through FR 000380; it does not rewrite historical completion reports or promote Beta. Verified 2026-10-26 from the successful hosted run below.

## Execution and cost boundary

`.github/workflows/web-beta.yml` supports manual dispatch, relevant pull requests and main pushes. Only standard `windows-2025` (x64), `macos-15` (ARM64) and `macos-15-intel` are used, three jobs maximum, 20 minutes/job, cancel superseded work, seven-day bounded JSON artifacts, read-only token and checkout without persisted credentials. No secrets, `pull_request_target`, paid/larger/self-hosted runners, model calls, protected-environment access or product dependencies. Private repositories skip the jobs: reassess cost/permissions first. This is not branch protection or a blanket release gate.

Verified public repository and [standard runner availability](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) on 2026-10-26. GitHub describes standard public runners as free/unlimited compute; [billing terms](https://docs.github.com/en/billing/concepts/product-billing/github-actions) and storage policy can change. Artifact volume is a few bounded summaries, not screenshots/traces/session dumps. No cache or large browser downloads are retained. Reassess before visibility/runner/retention changes.

Python 3.11 and Node 22 are CI developer tools. Playwright 1.56.0 plus its headless Chromium is installed only on disposable runners. Native probes use in-box Win32/AppKit/Objective-C and macOS osacompile, not downloaded product SDKs. `platform.json` records actual image version, OS build, architecture, Python, Node, Git and macOS shell versions; a label is not proof of a fixed OS.

## Evidence matrix

[Successful run 40407897072](https://github.com/qstoffe/cost-guard/actions/runs/40407897072), PR head `034b54e3921a0be9fcd5e53080fc30913d7265a5`, executed the PR merge checkout `15afa826d2e7d9c66c2cccf180ce2a4f78a5811b`. All three jobs completed successfully. Each ran 106 registered Full files and Python 3.11.9; no failed/error cases. Later completion/journal/identity bookkeeping does not change this tested runtime.

| Actual platform / image | Full passed / skipped | Validator | Native APIs / offline lifecycle | Chromium |
| --- | --- | --- | --- | --- |
| [Windows x64](https://github.com/qstoffe/cost-guard/actions/runs/40407897072/job/121870285351), build 10.0.26100; win25-vs2026 20261021.278.1 | 1,346 / 0 | PASS | PASS; real Win32 menu/message dispatch, detached restart/Exit/source-change, real .cmd/PowerShell | PASS |
| [macOS ARM64](https://github.com/qstoffe/cost-guard/actions/runs/40407897072/job/121870285753), 15.7.9 / 24G830; macos15 20260907.0337.1 | 1,343 / 3 | PASS | PASS; actual AppKit ABI/callbacks/pump, HTTP-fault cleanup, detached restart/source-change, .command and osacompile cache/rebuild | PASS |
| [macOS Intel](https://github.com/qstoffe/cost-guard/actions/runs/40407897072/job/121870285059), 15.7.9 / 24G830; macos15 20260824.0482.1 | 1,343 / 3 | PASS | PASS; same real native/offline scope as ARM64 | PASS |

The three Mac skips are explicitly Windows-only: two shell-boundary cases in `test_launcher_feedback.py` (missing Python; skip duplicate failed candidates/preserve mode exit) and real PowerShell discovery in `test_windows_web.py`. Node VM cases executed. Node was 22.23.4 on Windows, 22.23.2 on Mac; Chromium was 141.0.7390.37 everywhere. macOS used in-box zsh 5.9 and osacompile SHA-256 `3b685aa1f98552482f51ee3d95879ebccb99d818ed96d976543efbcf9f57f697`.

Checks annotations retain sanitized platform/suite/regression/native/browser notices and named skips; bounded artifacts last seven days. Raw Actions log download through the installed API transport returned HTTP 401 and was not bypassed. Conclusions here use the independently retrievable Checks evidence, not inaccessible raw logs. `upload-artifact@v5` emits a Node-20-deprecation warning but succeeded under runner Node 24; it is not a failed test.

Earlier runs failed and are not PASS evidence: [40404404891](https://github.com/qstoffe/cost-guard/actions/runs/40404404891) exposed Mac readiness delay, then [40405973252](https://github.com/qstoffe/cost-guard/actions/runs/40405973252) reached a startup identity conflict and a Windows synthetic credential-generation flake. Narrow repairs removed numeric-loopback reverse DNS, retained original PID/birth while checking the ready child's current image, and gave synthetic credential replacements distinct mtimes. The successful native probes recorded same birth with changed image on both Mac architectures, supporting the interpreter-exec cause; foreign-birth/forged-image regression denials remain. No readiness/suite deadline was raised. Local Windows Full passed all 106 files in 49.7 seconds; validator passed with four existing design-budget warnings.

`full.json` retains per-file executed/failure/error/skipped counts and named skip reasons. The registered full runner still isolates each file, four workers, 240-second deadline. No timeout weakening. `regression.json` separately records validator exit. Actions logs hold normal synthetic test failure output; uploaded JSON excludes raw output, paths, URLs/credentials, prompts and instance state. Missing phases report NOT RUN, provisioning failure BLOCKED, test/assertion errors FAIL. Skips are never native proof.

## Native and browser scope

`ci_native_web.py` refuses non-GitHub-hosted execution. It copies source to disposable spaces/Unicode paths and supplies an explicit offline entry shim: shipped GUI/HTTP/locks/process identity/restart/source-guard code executes, but real acquisition and default-browser opening do not. Windows reuses the real tray/menu/WM_COMMAND probe and HTTP-failure cleanup; macOS reuses typed AppKit Open/Exit callbacks/main-thread pump and checks real osacompile cache reuse/fingerprint rebuild plus executable `.command` argument plumbing. The shim is not end-to-end consumer launcher proof. Historical opt-in workstation probes remain opt-in and are never run by CI.

`ci_browser_web.py` launches actual headless Chromium against shipped assets/HTTP with the responsibility-owned synthetic report worker. It checks bootstrap/HttpOnly auth, tables/session detail, Back/Forward, hostile literal text, narrow viewport/keyboard focus, SSE offline/reconnect and terminal shutdown. Network routing permits only this loopback origin. No screenshot, trace, browser profile or cookies are uploaded.

## Still NOT VERIFIED — manual acceptance

- Consumer Windows 11 desktop; physical tray/status-menu clicks and visual light/dark/high-DPI behavior.
- Finder double-click, Gatekeeper/quarantine, downloaded ZIP permissions, Terminal lifetime and registered system-browser selection.
- macOS status-item visibility on an ordinary unlocked desktop, accessibility/screen-reader behavior, physical suspend/resume/long soak.
- Real OpenCode/provider/Watch source behavior on hosted runners (intentionally excluded); no accounts/models are exercised.

These require separately approved last-mile UI work. No security bypass, quarantine removal, persistent app/login item, shared-service stop or automatic Beta promotion is authorized.
