# Completion — FR 000541

Date: 2026-11-02. Product: v80.122.
PR: https://github.com/qstoffe/cost-guard/pull/117

## Delivered scope

Windows Web can retire a valid legacy schema-1 record whose managed host is
positively absent under the existing lifetime lock, even when its reused PID
cannot be queried. Transition serialization spans retirement and replacement
admission; full-record comparison and nonce checks protect changed/new records.
Busy/unsafe/unavailable proof remains fail-closed. No boot/clock heuristic,
metadata migration, broader process rights, unrelated control request or process
termination was added. Healthy restart, overlap coalescing and native exact-handle
shutdown remain in place; non-Windows identity/termination policy is unchanged.

Native access-denied/unavailable identity, unsafe/corrupt state, coordination and
control/readiness causes remain distinct in bounded feedback and Diagnostics.
Proven-stale retirement has its own event; historical ready snapshots cannot hide
the latest recorded startup cause. Product version/history/README, troubleshooting
and Web lifecycle architecture were updated. Journal: no-update; durable owner
facts and bounded evidence are retained in the Web module contract and
`development/architecture/governance/verification/windows-stale-recovery.md`.

## Verification

- Focused lifecycle/Windows launcher/Diagnostics: 59 tests passed.
- Final full suite, serial: all 121 files passed; 1,480 tests, 1,479 passed,
  one macOS zsh/PTY test skipped on Windows, zero failures (203.7 seconds).
- Working-tree package validation passed, with four existing design-budget
  warnings. Initial history hard-cap failure was resolved by shortening existing
  history prose, not changing a cap.
- Fresh read-only native observation reproduced access denied for the affected
  legacy PID and corroborated reboot/PID reuse. An isolated fixture using that PID
  reached replacement admission with zero actual spawns, control requests,
  termination or browser calls. The real record stayed byte-for-byte unchanged;
  no installation lock, ACL, launcher or host was modified/stopped.
- Real-source non-UI lifecycle probe passed: acquired/frozen report/detail,
  CLI one-shot, authenticated own-host stop and joined thread; no model requests.

## Uncertainty and unperformed scope

The initial parallel full run passed 120/121 files; an existing PowerShell
Python-discovery PATH-fallback assertion failed but passed focused and complete
serial reruns. Concurrent-load sensitivity is not a proven root cause; no test
assertion or product timeout was relaxed. An earlier live-probe invocation failed
with a generic RuntimeError of unknown cause; an stdin diagnostic wrapper was
unsuitable for Windows multiprocessing. The guarded file-based probe passed.
Earlier failures are retained as failures, not relabeled PASS.

No real native tray/browser/dialog interaction or forced reboot was performed.
macOS/Linux native workstation behavior was not freshly exercised here.

Decision Delegate explicitly authorized delivery without waiting for the additive,
optional GitHub cross-platform workflow, which was queued on the inspected final
implementation/completion head (run 41484239761). Reason: mandatory local full
suite, validator and relevant native/non-UI evidence passed; optional platform
results add confidence but are not a missing required gate. No required test was
waived, no pending/cancelled check is PASS, and server protection must not be
bypassed. Remaining uncertainty includes those platform results and unperformed
physical UI/reboot checks; later delivery reporting retains the actual check state.

This is source delivery,
not an update/restart of the user's separate installation or the shared OpenCode
service; no ZIP, release publication or plugin installation was performed.
