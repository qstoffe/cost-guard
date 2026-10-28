# Completion — Windows Web Beta no-build handoff

Implemented as v80.101 on 2026-10-28. The selected specification is preserved
byte-for-byte. No attachments were added or changed.

## Outcome and choice

Chose the simpler no-build control, not a locally compiled native helper. The
normal Windows batch immediately delegates to hidden, separate PowerShell with
null standard handles; Python discovery, configuration/native preflight, verified
restart, host/tray readiness and authenticated browser handoff no longer retain
the visible batch. No compiler, executable cache, manifest/rebuild, installer,
download, daemon or Windows Script Host dependency is introduced. This is still
Python-based Cost Guard, not a standalone packaged executable. Direct PowerShell
invocation retains the supported visible troubleshooting path. Hidden-mode
failures keep sanitized dialogs/private logs and never wait invisibly for input;
each Python discovery probe is bounded and cleaned up.

Existing private loopback/control authority, per-checkout locks, process identity,
source-change shutdown, native tray and pythonw finite-report workers remain
unchanged. CLI/Watch and macOS runtime behavior are not modified. The current
Windows route removes the need for compiled-cache security/rebuild machinery;
Windows executable cache size is zero. macOS retains its existing fingerprinted,
integrity-checked, in-box osacompile Finder app mechanism and documented fallback.

## Verification and evidence

- Full: 113/113 test files PASS; latest local run 59.6 s.
- Working-tree validator: 0 errors, 11 passes, four nonblocking design-budget
  warnings; no caps or assertions weakened.
- Real Windows native probe: tray Open/Exit, failed browser/preflight retention,
  HTTP-fault cleanup, detached survival, no inherited host console, overlap,
  verified restart, source-change exit, CLI Watch process independence and
  ShellExecute of the real batch from a no-Git space/Unicode snapshot PASS.
- Windows 11 AMD64/Python 3.14.7, final joined probe: batch exit 0.028/0.026 s;
  host/tray ready 2.415/3.573 s; delegate exit observed at 2.759/3.973 s. Earlier
  separate synchronous fallback comparator 1.023/1.649 s. These
  single observations separate delegation/readiness, not browser paint or a
  universal performance target.
- Real blocked-delegate regression proves batch exit before slow work and no
  visible delegate console. Real stalled-Python regression proves bounded
  discovery and owned-probe cleanup. Existing lifecycle/security/ReportJobs and
  macOS cache regressions remain in Full.
- OpenCode Desktop built-in browser: synthetic report loaded without console
  errors; expired authentication retained the table, disabled Refresh, removed
  bootstrap fragment and displayed explicit fresh-launcher recovery. No Chrome
  automation fallback was needed. Fixtures were stopped/joined.

Reproduction, comparison method, no-build trade-offs, failed-probe repair and
remaining limits: [Windows handoff evidence](../../../architecture/governance/verification/windows-handoff.md).
Owner instructions/cache and error policy: [Web Beta guide](../../../../docs/web-beta.md).

One native attempt was interrupted and reconciled before retry. A later probe
incorrectly tied Watch independence to real-history `Total today` completion
within 60 seconds; read-only observation confirmed ongoing loading in a live
Watch. The repaired probe retains startup/liveness/ownership assertions and does
not claim complete real-history rendering. The native rerun and Full passed.
Helper knowledge read rejected the existing oversized Web module page; bounded
INDEX/topic updates were applied with exact HEAD/hash guards instead. No
installed runtime was modified. No cross-repository defect proposal was published.

The paused session's final safety audit found an owned startup-error dialog. On
continuation, its log/source evidence identified test teardown that stopped the
host at readiness before the asynchronous launcher necessarily completed its
handoff. The probe now verifies exact-root delegated process births, retains
their handles and joins zero-exit completion before test Exit/teardown. The full
native rerun passed; subsequent inspection found zero task launcher delegates,
no managed instance and no new startup-error record. Production errors are not
suppressed and readiness is still distinct from launcher completion.

The initial PR Windows-hosted regression exposed a separate five-second
visibility-fixture startup budget, while hosted native and browser phases
passed. The repaired fixture retains the immediate batch-exit and invisible
console assertions, allows a bounded 15 seconds for delegate startup, and
records explicit interpreter failure. Local Full passed again. Candidate
`3ed0be0e514e72ab1fd586e8bf1e113d8efa917b` passed the full hosted matrix on
Windows Server 2025, macOS ARM64 and Intel, including isolated native/compiler
and rendered-browser phases: [verified run](https://github.com/qstoffe/cost-guard/actions/runs/40724292824).
This adds hosted macOS evidence, not physical Finder acceptance. No failed check
was bypassed or classified as delivered.

## Explicit remaining acceptance limits

Physical Explorer mouse double-click, visual duration of the possible initial
batch/minimized-PowerShell flash, physical tray/accessibility checks and native
macOS Finder/Gatekeeper acceptance were not performed. Automated ShellExecute,
process/window checks and browser fixtures do not prove these. Near-OS-limit long
paths and all consumer desktop configurations are not claimed. No native helper
was compiled or benchmarked. The chosen control solves the measured
readiness-length wait; if the residual flash is unacceptable, a genuinely GUI
entrypoint needs separately measured justification. No complete consumer-desktop
or standalone-binary acceptance is claimed.

## Knowledge and architecture assessment

Updated the existing Web owner contract and user instructions in place; no new
runtime layer or acquisition/security boundary. Journal learning was updated via
the guarded knowledge writer and INDEX route: delegation is not readiness, and
Watch independence is not real-history scan completion. No architecture diagram
change is needed. Exact native transaction/identity retention state is included;
no pruning or cross-FR dependency changes were required.
