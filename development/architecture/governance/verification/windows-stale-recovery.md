# Windows legacy stale-instance recovery

Date: 2026-11-02. Product: v80.122. FR 000541.

## Protocol and safety evidence

No schema extension or boot timestamp heuristic is used. Existing schema-1
managed entrypoints already acquire `host.lock` before constructing/publishing
their host and retain it until `run_gui` and final cleanup finish. Windows denies
deletion/replacement while that file is open; the deterministic native regression
tests both operations. A nonblocking acquisition of its existing byte lock is
positive evidence that the recorded managed host no longer owns the instance.
Access denied alone is never absence or permission to contact/terminate a PID.

The launcher holds `transition.lock` throughout inspection, full-record comparison,
nonce-guarded retirement, child spawn and verified replacement readiness. It holds
lifetime during retirement, then releases lifetime so the child can acquire it.
Other launchers remain excluded; a delayed prior child can acquire only the same
exclusive lifetime lock. If it wins, the new child cannot run concurrently and the
launcher fails closed without removing another nonce. A busy lifetime lock plus
an inaccessible PID retains the record and reports the original identity reason,
with the coordination failure separately logged. Corrupt/reparse/changed state
and unavailable proof refuse admission. The healthy native identity, graceful
stop and exact-handle forced-stop paths remain in place. Non-Windows identity and
termination policy is unchanged.

## Fresh read-only workstation observations

The affected schema-1 v80.119 record was still present. Its recorded host birth
was 2026-11-01 22:58:50.5566454 UTC; Windows reported the latest boot at
2026-11-02 16:03:09.500 UTC. Narrow native observation of only its recorded PID
found a different process birth, a Windows service process in session zero.
Production native identity returned `process_identity_access_denied`.
These observations corroborate the incident; clock comparison is not the
production retirement proof. No raw PID, process image path, instance identifier,
control material, account data or user path is retained here.

An owned private fixture used that same numeric PID with synthetic schema-1
identity/credentials. Corrected production lifecycle and native identity code
retired the fixture record and reached replacement admission. It verified that
lifetime was available for the child while transition remained held. Control,
termination, actual process spawn and browser calls were all zero. The real record
was byte-for-byte unchanged before/after. Its constructor/locks/ACLs were never
invoked or altered; no real launcher/server/tray/browser was started. The
installation and shared OpenCode service were not modified or stopped.

## Deterministic coverage and limits

`test_web_lifecycle.py` covers access-denied legacy recovery (including a future
ready timestamp), native OpenProcess/GetProcessTimes/GetExitCodeProcess/image
query failures and handle closure, busy/unsafe/unavailable lifetime proof,
readable reuse, record replacement during inspection, overlapping starts,
unsupported schema, corrupt/reparse state and unchanged non-Windows refusal.
Assertions cover retained/removed records and spawn/control/termination effects.
`test_windows_web.py` covers fixed console/dialog-bound feedback and diagnostic
write failure; `test_web_diagnostics.py` covers allowlisted startup facts without
a new host snapshot, specific recovery and historical-ready/late-failure ordering.

Focused run: **59 tests passed** on Windows/Python 3.14.7. Working-tree package
validation: **0 failures, 4 existing design-budget warnings**. The first validator
run exceeded the history hard byte cap after adding the new entry; shortening the
existing v80.100 prose resolved it without raising any budget.

The first four-worker full run executed 1,478 tests in 121 files (one named skip):
120 files passed, while the existing PowerShell discovery PATH-fallback assertion
failed. It passed in both focused runs. A full serial rerun is being used to
investigate concurrent-load sensitivity; neither assertion nor the five-second
production discovery budget has been relaxed.

Actual native tray/browser/dialog interaction and a forced reboot were not run or
claimed. No desktop authorization was needed for this non-UI acceptance route.
macOS/Linux native behavior was not freshly exercised on those operating systems;
their unchanged policy is covered by deterministic regressions. No requirement or
test exception was requested or delegated. Journal assessment: no-update; the
module contract and this bounded evidence retain the durable facts.
