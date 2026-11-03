# Web Beta hosted revalidation

## Current scope and reporting — FR 000553 / FR 000548

FR 000553 keeps this common/native plan and its cancellation behavior unchanged.
Concise completion records describe delivered behavior, known limits and the PR;
detailed counts, tested revisions, effective merge base and hosted results belong
in that PR/CI run. Updating a PR description does not create another tested head.
This avoids a commit solely to copy results back into a tracked evidence table.

Limitation: path filters distinguish an entirely documentation-only PR/push, not
a report-only follow-up on an already code-changing PR. Such a commit still runs
the existing checks. No skip/cache/receipt mechanism is added; changed or uncertain
implementation, tests, configuration, workflow or effective base needs fresh
applicable verification. Earlier results retain their own tested revision, never
become PASS for another head, and do not bypass actual required GitHub statuses.

Additional live evidence follows the change's risks and approved acceptance:
fixture/validator edits use hidden real-shell and broken-package checks here,
not unrelated history/provider/browser campaigns. A platform behavior change or
explicit live acceptance still needs its real-platform evidence. Synthetic shell
contracts do not establish native tray/browser/consumer-desktop acceptance.

The workflow now assigns shared behavior to one `ubuntu-24.04` **common** job:
Full's unchanged registry and package validator, followed by one rendered headless
Chromium probe. Python 3.11, Node 22, CI-only Playwright 1.56.0, Chromium and Linux
browser dependencies are provisioned explicitly (`playwright install --with-deps`).
The native jobs do not install/discover Node, Playwright or Chromium.

**Native** retains `windows-2025` x64, `macos-15` ARM64 and `macos-15-intel`.
`run_tests.py --suite full --profile native-web --jobs 1` uses Full's existing
240-second per-process deadline without running Full. The explicit selection is
owned by `NATIVE_WEB_PATTERNS` in `development/tools/run_tests.py`:

- Windows: `test_windows_web.py`, `test_windows_web_activity.py`, and ten named
  `LifecycleTests` cases for paired/missing GUI Python, held lifetime-file
  protection, legacy/access-denied/stale process safety, native query/handle
  cleanup, crash-released OS locks and owned birth/termination identity.
- Both Macs: `test_macos_web.py` (including real zsh/PTY command lifetime/status),
  and the two lifecycle cases for crash-released locks and owned process identity.
- Exact case names, executed counts, named skips and durations are retained in
  `native-tests.json`; Full retains every portable/mock case once in `full.json`.
  Legacy Windows terminal-only shell cases in `test_launcher_feedback.py` and
  `test_windows_launcher.py` remain registered and locally available, but their
  OS-only execution is intentionally no longer part of hosted Web CI.

Native smoke still exercises real Win32/AppKit, owned HTTP readiness, restart,
Exit/fault cleanup, Unicode/space paths, source-change shutdown and Mac app cache.
The offline entry shim and native-menu callback probes still replace browser
opening. Separately, exactly one initial `launch(..., opener=...)` per native job
uses the production `os.startfile` or fixed `/usr/bin/open` against that owned
loopback destination. Evidence records **ACCEPTED** or **UNAVAILABLE**, not a page
load or browser-process assertion. The second launch retains the false-opener
failure/restart check. Deterministic tests assert exact URL argument and native
success/failure propagation without UI. No registration changes, consumer
profiles/accounts, physical clicks or local workstation UI are authorized.

The **Decision Delegate** authorized that bounded hosted handoff and resolved
development-only verification against the user's instruction, “Development-only
edits need no product tests/release/version work.” No product version/release or
unrelated local Full/Diagnostics/live-source test is required for this tooling
change; the requested actual hosted Full/native/browser checks remain required.
An unavailable registered browser is explicitly reported, not PASS, and is not
repaired by changing runner registration. Handoff acceptance never establishes
consumer-desktop behavior, navigation, first paint or Beta promotion.

`ci_web_beta.py ... --scope common|native` requires only its assigned phases;
the other scope is labelled assigned elsewhere. Missing, malformed, blocked,
unfinished or failed required evidence, incomplete suite inventories/counts,
prior step failure and cancellation make summary exit nonzero. JSON notices retain
sanitized failures/counts/skips and measured durations. Provisioning cannot be
turned into PASS by summary. Public standard-runner/read-only-token/no-secrets,
synthetic/offline data, superseded-run cancellation, relevant path triggers and
seven-day artifacts remain. Native `max-parallel: 2` plus one common job bounds
concurrency at three; common has 20 minutes, each native job 10 minutes.

### Current measured evidence

[Run 41526896465](https://github.com/qstoffe/cost-guard/actions/runs/41526896465)
passed all four jobs on 2026-11-02 for [PR 121](https://github.com/qstoffe/cost-guard/pull/121),
source `232fb1ae73b47c1999f13779132c58ec2209bbac`, tested PR merge checkout
`be4ca4ee598b24e6d5ebaa523ad462d6b7cf15b7`. No portability repair or timeout
change was needed. The actual current Full registry contains **125** files
(121 Quick + four Full-only), not the FR's earlier 124-file inspected baseline.

| Job | Whole job | Regression / validation | Native smoke | Browser |
| --- | --- | --- | --- | --- |
| [Linux common](https://github.com/qstoffe/cost-guard/actions/runs/41526896465/job/125556835754) | 2m 06s | 86.65s; 125 Full files; 1,506 passed / 15 named OS-only skips; validator PASS | Assigned native | Chromium PASS 10.24s; tooling/dependencies step 22s |
| [Windows x64](https://github.com/qstoffe/cost-guard/actions/runs/41526896465/job/125556835295) | 1m 04s | 23.75s; 12 groups, 27 passed / zero skips; no validator | PASS 17.14s | One OS handoff ACCEPTED; no rendered suite |
| [Mac ARM64](https://github.com/qstoffe/cost-guard/actions/runs/41526896465/job/125556836025) | 34s | 2.79s; three groups, 20 passed / zero skips; no validator | PASS 17.33s | One OS handoff ACCEPTED; no rendered suite |
| [Mac Intel](https://github.com/qstoffe/cost-guard/actions/runs/41526896465/job/125556835831) | 1m 03s | 3.56s; three groups, 20 passed / zero skips; no validator | PASS 23.33s | One OS handoff ACCEPTED; no rendered suite |

All executed suites reported zero failures/errors and complete passed counts.
Linux's OS-only skips remain named in `full.json`; native jobs execute the
retained Web-specific skipped cases. Historical CLI-only Windows cases are not
native Web acceptance. Checks exposes bounded notices (not necessarily every
individual skip annotation); the artifact is the complete per-file skip record.

Actual images: Linux `ubuntu24` 20261026.354.1 x86_64, kernel 7.0.0-1017-azure,
Python 3.11.17, Node 22.23.4; Windows `win25-vs2026` 20261030.294.1 AMD64,
10.0.26100, Python 3.11.9; ARM64 `macos15` 20261028.0489.1, macOS 15.8.2
(24H232), Python 3.11.9; Intel `macos15` 20260824.0482.1, macOS 15.7.9
(24G830), Python 3.11.9. Both Macs use zsh 5.9 and in-box osacompile. Native
tool facts contain no Node discovery. Shared Chromium: 141.0.7390.37.

The FR baseline run 41516683348 spent 13m 17s combined across three repeated
Full/validator steps. This run did that shared work once in 86.65s, plus the
explicit native selections above; native selection + smoke summed to 87.90s.
Whole-job combined execution was 4m 47s versus the baseline's 16m 58s. These are
observations across different images/revisions/OS assignments, not a controlled
benchmark, guaranteed saving, monetary estimate or queue/wall-clock promise.

Local Windows verification: 13 CI-accounting/boundary tests passed; native-web
passed 12 groups in 16.1s. No product version/release/ZIP or unrelated local
Full/Diagnostics/live-source test was run, per the scoped Decision Delegate
resolution above. All three real OS handoffs were accepted, but browser process,
navigation/first paint and consumer/physical desktop acceptance remain unverified.

Documentation-only head `26b5ca1fdcbef8ad6b938346a042e92cb5fbbc88` triggered
[duplicate run 41527754941](https://github.com/qstoffe/cost-guard/actions/runs/41527754941),
merge checkout `dbf7d079896b91a5bdd4351b2867fa58da353296`. Linux, Windows and
Intel Mac passed; ARM64 remained capacity-queued, not executed/PASS at that head.
The Decision Delegate authorized reuse of the unchanged implementation's earlier
successful ARM64 result, and permitted this reporting-only exception note to
merge without waiting for further duplicate checks. This is source-equivalent
evidence, not an elapsed-time rule or protection bypass. Uncompleted final-head
checks remain unverified and must be reported honestly; observed failures or a
changed base still require investigation. No test/workflow/source was changed
to avoid execution, and no run was manually cancelled or retried. Publishing the
permitted reporting-only exception note automatically superseded run 41527754941
under the preserved `cancel-in-progress` policy: its overall outcome is CANCELLED,
not PASS. Its three completed successes remain attributable to that head; ARM64
did not execute. Newly triggered reporting-head checks remain separate/unverified
until they actually complete.

## Historical evidence — FR 000410

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

A subsequent [documentation-head rerun 40408713197](https://github.com/qstoffe/cost-guard/actions/runs/40408713197) passed both Mac jobs and all native/browser checks, but Windows Full errored in the PowerShell-7 missing-Python fixture. Validator still passed. Its empty diagnostic did not establish the exception type; the reporter now explicitly preserves child TimeoutExpired as a fixed safe code without exposing argv. This failed rerun is not PASS and requires follow-up verification; the successful matrix above remains evidence for its stated source only.

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
