# Windows Web Beta no-build handoff

Observed 2026-10-28 on Windows 11 build 26300, AMD64, installed Python 3.14.7.
Scope: v80.101 candidate, based on e4a36c94ea0a278d12a19d369377a919f573a4fb.
These are local automated measurements, not physical mouse/visual acceptance.

## Cause and implementation choice

The previous `.cmd` synchronously called PowerShell, whose pipeline waited for
Python configuration/native preflight, lifecycle arbitration, old-host shutdown,
host/tray readiness and registered-browser handoff. Browser/report loading was
already asynchronous. A console that remained during those stages was therefore
owned by the launching batch/PowerShell chain, not evidence that report workers
had regressed. The paired `pythonw.exe` managed host/workers remain unchanged.
The visible failure fallback could intentionally wait for Enter if its dialog
failed; the new hidden mode never does so.

Choose the simpler no-build control: `start` a separate, initially minimized
PowerShell with `-WindowStyle Hidden`, `-Detached` and null standard handles,
then exit the batch. No discovery/compiler/lifecycle work precedes delegation.
The same PowerShell/Python implementation still owns preflight, failure dialogs,
private logs and authenticated lifecycle handoff. Explicit direct PowerShell
invocation remains synchronous with timed stage feedback. Batch exit is not PASS
for host readiness. There is no early unauthenticated page or background service.

A tiny C#/GUI-subsystem helper would eliminate the initial batch-shell mechanics
only if the stable entry changed too; it would otherwise still follow the batch
flash. It also adds first-build/compiler discovery, executable integrity/ACL,
manifest, atomic publication and cache-repair responsibilities. The measured
no-build control already removes the readiness-length visible wait without any
new prerequisite. No native helper was compiled or performance-tested, and no
claim of a measured native-vs-script binary comparison is made. Compilation is
not justified by this evidence. Windows executable cache: **absent; 0 bytes**.
Source/OS/Python changes use current installed inputs on every invocation; no
stale/partial/tampered compiled Windows artifact can be selected. Cache-specific
build, compiler-unavailable, fingerprint, corruption and reparse tests are thus
inapplicable to this chosen Windows design, not simulated PASS results.

## Reproduction and measured results

Run from the checkout with installed Python 3.11+:

```text
python development/tools/run_tests.py --suite full
python development/tools/validate_package.py --working-tree
python development/tests/integration/probe_windows_web.py --allow-native-ui
```

The last command requires current bounded UI approval. It opens native tray and
registered-browser test instances; no model inference or shared OpenCode stop.
It cleans only owned Web/Watch children and its own source-change marker.

| Measurement | Cold/no host | Warm verified restart |
| --- | ---: | ---: |
| New `.cmd` process exit, final joined probe | 0.028 s | 0.026 s |
| Required native host/tray readiness, final joined probe | 2.415 s | 3.573 s |
| Delegate exit observed after retained-handle join | 2.759 s | 3.973 s |
| Synchronous direct PowerShell fallback exit, separate run | 1.023 s | 1.649 s |

Fallback comparator: call the same `src/web/windows_launch.ps1` directly without
`-Detached`, with null input/output and a 45-second bound; retain the managed host
between cold/warm trials, then stop it via verified `stop_existing`. Both exited
zero; that comparator was measured before the paused session's continuation, not
simultaneously with the final joined native run. Initial native readiness samples
were 1.007/2.053 s with 0.027 s batch exit. Trials are single observations, not
medians, a browser-paint measurement,
universal timing target or claim that native preparation itself became faster.
The new batch no longer waits for those variable stages.

`test_windows_web.py` executes the unchanged batch in a source-shaped space/Unicode
fixture. A deliberately blocked PowerShell delegate is still unfinished when
the batch exits; real `GetConsoleWindow`/`IsWindowVisible` inspection from its
Python child reports no visible console. The test releases and joins its bounded
delegate. A second real PowerShell test injects a stalled Python startup through
fixture-only `sitecustomize`, verifies the five-second discovery bound, rejection
and disappearance of that exact probe process. No native icon/browser is opened
by Full. Missing/old/supported/multiple Python candidates and private log ACLs
are exercised by the existing real PowerShell discovery harness.

Actual native probe PASS: menu labels/message delivery, failed Open retaining
the host, Exit, HTTP-fault icon cleanup, offline-native initialization, detached
host survival, no inherited host console, overlapping launch coalescence,
verified deliberate restart, failed preflight preserving the existing instance,
source-change shutdown, independent CLI Watch startup/process survival, and
ShellExecute of the real batch in a no-Git space/Unicode source snapshot. No
physical Explorer mouse input or browser-paint timing is implied.

Full: **113/113 files PASS**, latest local run 59.6 s. Working-tree validator: **0 errors**,
11 passes, four design-budget warnings (README and pre-existing large context,
report-service and Watch modules); no hard limit changed. Existing lifecycle,
loopback/control security, PID/birth ownership, ReportJobs and macOS cache tests
remain in Full. Native macOS tooling/Finder cannot be exercised on this Windows
workstation; no macOS runtime change is included. The later hosted matrix passed
Windows Server 2025, macOS 15 ARM64 and macOS 15 Intel regression, isolated native
and rendered-browser phases on the repaired test candidate (see below). This is
not physical Finder/Gatekeeper acceptance.

## Built-in browser and recovery

Used OpenCode Desktop's built-in browser first, with the existing bounded
`serve_web_connection.py` synthetic WebHost fixture. Overview reached
`Snapshot captured`, with no console errors. After fixture-only authentication
expiration, the same tab displayed `AUTHENTICATION EXPIRED — NOT LIVE` and fresh
launcher directions, retained its report table, disabled Refresh and had removed
the bootstrap fragment. The fixture was explicitly stopped/joined. This is
synthetic HTTP/browser evidence, not an installed-history readiness claim; the
registered OS-browser/native handoff remains separately tested by the native
probe. No Chrome fallback was needed for browser automation.

An interrupted native attempt was reconciled: no remaining probe/managed instance
was found before rerun. One subsequent probe failed waiting for `Total today` in
CLI Watch output: a separate 15-second read-only probe confirmed a live process,
Watch heading and ongoing loading, not a completed history scan. The independence
probe now checks live Watch startup after Web restart/exit, not full real-history
completion within 60 seconds. It explicitly does not claim report completion.
Full retains deterministic report/Watch correctness assertions. The repaired
native probe then passed. No production timeouts/assertions were weakened.

Final safety inspection nevertheless found an owned detached launcher still
displaying a startup-error dialog. Its allowlisted `gui_or_server_start_failed`
record followed the timing probe's last launch. Source inspection established a
test teardown race: the probe used host/tray readiness to end a trial and stopped
the host before its separate launcher necessarily observed readiness and finished
the authenticated browser handoff. The same distinction applies to the source
snapshot's immediate Exit. Stopping the server that early can legitimately make
the still-polling launcher report failed startup. This is not readiness proof for
the supervisor and does not call for suppressing production errors.

After explicit continuation, the probe matches only the exact batch argument
suffix for its own root/snapshot, checks CIM birth against a retained process
handle, and waits for each delegate to exit zero before test Exit/teardown. A
bounded failed join cleans only that proven owned launcher and fails the probe.
The complete native rerun passed; post-run inspection found **zero** matching
task delegates, no managed instance, and no new startup-error record. The final
measurements above include separately observed delegate completion; they still
do not measure browser paint. Production lifecycle/security code is unchanged.

The first PR Windows-hosted run also exposed a probe-only startup budget error:
the visibility fixture read its result after only five seconds, producing
`FileNotFoundError`; hosted native command/ownership and rendered-browser phases
passed independently. The fixture now separates the unchanged five-second batch
exit check from a bounded 15-second delegate startup allowance, records an
explicit visibility-interpreter failure marker, and requires the same invisible
console/blocked-delegate assertions. No product timeout or visibility assertion
was relaxed. Local Full passed again (113 files, 59.6 s). The repaired candidate
`3ed0be0e514e72ab1fd586e8bf1e113d8efa917b` then passed **all three hosted jobs**:
[Windows/ARM64 macOS/Intel macOS evidence](https://github.com/qstoffe/cost-guard/actions/runs/40724292824).
The preceding red run remains historical failure evidence, not a waived check.

## Limits and follow-up

- Actual Explorer mouse double-click and visual flash duration remain unmeasured.
  The normal batch may briefly flash, and minimized PowerShell startup may briefly
  appear; automated hidden-delegate/process exit proof is not visual acceptance.
- Physical tray rendering, accessibility, consumer desktop variations, long paths
  near OS limits and native macOS Finder/Gatekeeper remain owner checks. Space/
  Unicode ShellExecute and existing checkout isolation/port ownership regressions
  do not establish all possible desktop configurations.
- Hidden startup intentionally offers no fabricated preparation/progress bar.
  Normal browser readiness/report progress begins after secure host/tray readiness.
  For an abnormally slow pre-browser start, use the direct visible troubleshooting
  command and private Diagnostics. If physical feedback shows the residual flash
  is unacceptable, evaluate a genuinely GUI entrypoint in a separately evidenced
  iteration rather than add a cache without demonstrated benefit.
- No Windows executable artifacts need removal; never delete instance state,
  config/history or analysis caches to repair this launcher. macOS's existing
  protected, fingerprinted Finder app cache is unchanged and separately documented.
