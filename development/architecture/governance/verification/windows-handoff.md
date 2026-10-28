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
| New `.cmd` process exit | 0.027 s | 0.027 s |
| Required native host/tray readiness | 1.007 s | 2.053 s |
| Synchronous direct PowerShell fallback exit, separate run | 1.023 s | 1.649 s |

Fallback comparator: call the same `src/web/windows_launch.ps1` directly without
`-Detached`, with null input/output and a 45-second bound; retain the managed host
between cold/warm trials, then stop it via verified `stop_existing`. Both exited
zero. Trials are single observations, not medians, a browser-paint measurement,
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

Full: **113/113 files PASS**, final run 43.8 s. Working-tree validator: **0 errors**,
11 passes, four design-budget warnings (README and pre-existing large context,
report-service and Watch modules); no hard limit changed. Existing lifecycle,
loopback/control security, PID/birth ownership, ReportJobs and macOS cache tests
remain in Full. Native macOS tooling/Finder cannot be exercised on this Windows
workstation; no macOS runtime change is included.

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
