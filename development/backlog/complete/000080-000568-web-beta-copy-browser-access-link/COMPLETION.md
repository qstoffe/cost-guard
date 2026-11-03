# FR 000568 — Completion

Implemented in **v80.148 (2026-11-04)** with explicit verification exceptions.
The original specification is retained intact as `FR.md`.

## Delivered behavior

- Windows tray menu: Open Cost Guard → **Copy Cost Guard link** → Exit Cost Guard.
  Copy uses the trusted existing host and never opens a browser or starts a server.
- A bounded independent pool of 16 in-memory, two-minute, one-use credentials
  preserves other pending Open/Copy/launcher links and active sessions/CSRF.
  Overflow fails without revoking another unexpired link; failed copies discard
  only their own credential.
- Typed Win32 Unicode/movable-memory clipboard transfer runs off the native pump,
  with bounded busy retries, privacy-safe feedback and history/cloud opt-out
  formats. Expected failure is retryable; software faults reach the host boundary.
- Receiving an explicit bootstrap fragment in an already-loaded unauthorized tab
  erases it before existing guarded exchange, then reloads the clean Models URL.
  No browser copy UI, new endpoint/dependency/process, broad CORS, persisted login
  token, macOS action or security relaxation is introduced.

## Actual verification

- Final `py -3 development/tools/run_tests.py --suite full`: **138 files passed,
  zero failures, 83.3s**. Earlier changed inventories were repaired; an intermediate
  historical-scale catalog-count timing failure under overlapping browser load is
  disclosed in the journal, with the unchanged assertion passing in final Full.
- Focused runs: initial 58 tests and subsequent 63-test group passed, including
  security/host/native worker, real hidden native-menu handles, clipboard API
  ownership/failure mocks and real HTTP/JavaScript handoff regressions.
- Working-tree validator: **11 checks passed**, zero failures, six advisory
  preexisting prose/module-budget warnings. No hard-cap increases or ZIP.
- Real installed headless Chrome **156.0.8078.80** / Edge **156.0.4314.58**:
  **12 checks passed** for plain-URL authorization boundaries, same-document paste,
  fragment/history erasure, no Web Storage credentials, same-server Models/Watch,
  older pending Open/private context, replay denial, unchanged Chrome session/CSRF
  and continued app SSE in both browsers. Synthetic canonical data and in-memory
  copier callback; no OS clipboard or visible desktop use.
- Read-only real V2 installation probe: one acquisition owner/two SSE streams,
  advancing sequence/preserved run origin, 1.369s first source view, all owned
  workers closed and shared OpenCode untouched. Two history cancellation phase
  errors during shutdown are not a daily-history completion/data-quality PASS.

## Decision Delegate exception and remaining uncertainty

The **Decision Delegate**, not the user, authorized this **FR 000568-only** delivery
exception on **2026-11-04**, including legitimate continuation. Initially requested
real clipboard proof in a fresh hidden private noninteractive window station and
desktop was unavailable: `CreateWindowStationW` returned **WinError 5 (Access
Denied)** before GUI/clipboard operations. Setup stopped; no user clipboard,
desktop, elevation, identity change or access workaround was used. This was a
**setup failure**, not a clipboard product failure or PASS.

The Delegate explicitly superseded the successful-probe prerequisite and permitted
normal completion/PR/checks/squash merge without real clipboard transfer,
contention/retry, ownership transfer or owner-cleanup verification, and without
physical launcher/tray/Edge paste, 150% mouse/keyboard popup checks,
notification/DND visibility, Explorer restart or interactive cleanup. Actual shell
enforcement of history/cloud flags also remains unknown. The reason was substantial
inspected deterministic/native-resource/browser/Full evidence and denied isolation;
additional disruptive testing or holding delivery was disproportionate. No other
tests, permissions or Git protections were waived. **This is not full physical
acceptance.**

Current owners/security/worker inventory, usage/version/history and
[durable findings](../../../journal/web/browser-links.md) are updated. Ordinary
maintenance progress advances to 19 only when this delivery merges to default.
