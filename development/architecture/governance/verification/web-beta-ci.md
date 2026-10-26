# Web Beta hosted revalidation

FR 000410 re-tests the implementation delivered through FR 000380; it does not rewrite historical completion reports or promote Beta. Results below must be populated from retrievable Actions evidence before delivery.

## Execution and cost boundary

`.github/workflows/web-beta.yml` supports manual dispatch, relevant pull requests and main pushes. Only standard `windows-2025` (x64), `macos-15` (ARM64) and `macos-15-intel` are used, three jobs maximum, 20 minutes/job, cancel superseded work, seven-day bounded JSON artifacts, read-only token and checkout without persisted credentials. No secrets, `pull_request_target`, paid/larger/self-hosted runners, model calls, protected-environment access or product dependencies. Private repositories skip the jobs: reassess cost/permissions first. This is not branch protection or a blanket release gate.

Verified public repository and [standard runner availability](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) on 2026-10-26. GitHub describes standard public runners as free/unlimited compute; [billing terms](https://docs.github.com/en/billing/concepts/product-billing/github-actions) and storage policy can change. Artifact volume is a few bounded summaries, not screenshots/traces/session dumps. No cache or large browser downloads are retained. Reassess before visibility/runner/retention changes.

Python 3.11 and Node 22 are CI developer tools. Playwright 1.56.0 plus its headless Chromium is installed only on disposable runners. Native probes use in-box Win32/AppKit/Objective-C and macOS osacompile, not downloaded product SDKs. `platform.json` records actual image version, OS build, architecture, Python, Node, Git and macOS shell versions; a label is not proof of a fixed OS.

## Evidence matrix

Pending first CI execution; no platform PASS is claimed yet.

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
