# FR 000544 completion

Implemented in **v80.131**, 2026-11-03, with the scoped verification exceptions below.

## Delivered behavior

- Explicit Watch-only Mini Watch On/Off control owns one actual Document
  Picture-in-Picture window. Rejection, cancellation, replacement, delayed callbacks,
  close/reload and in-app navigation preserve honest window state. No automatic
  opening, popup fallback, saved On preference or browser-security workaround.
- A dedicated compact, keyboard-accessible view follows Classic/Web light/dark and
  Credits/USD. Its summary selects Watch and requests focus of the existing owner
  without deliberately closing Mini. Browser chrome, restoration and geometry remain
  browser/OS-owned, with limitations documented in the help.
- One backend aggregate publishes distinct canonical running prompts, their current
  prompt-only CCost and maximum canonical duration from one observation. Compaction,
  history, placeholders, duplicates and terminal grace are excluded. Complete zero,
  partial/unavailable and retained stale observations remain distinct; unavailable
  capture freezes retained duration rather than growing it indefinitely.
- Each primary subscription line retains its stable Used percentage and the same
  native quota period's CCost, including estimate/partial/unavailable meaning. Mini
  reuses FR 000552's indexed native-month/history lane and current-quota association;
  it does not substitute Today, trailing 30 days or percentage-derived cost.
- The app-owned controller consumes existing publications, settings and health with
  independent safe-text DOM. Hidden-main rendering does not depend on main-page
  animation callbacks. No second EventSource, acquisition owner, auth copy or CSP
  relaxation; the freshness timer never extrapolates canonical duration.

## Executed verification

- **PASS:** `py -3 development/tools/run_tests.py --suite full`: 127 files, zero
  failures, 58.1s. One existing macOS shell/PTY case was skipped on Windows; its native
  CI owns that platform proof. Mini lifecycle/DOM and canonical quota-ended child,
  partial acquisition, native-period/reset and retained-duration regressions passed.
- **PASS:** `py -3 development/tools/validate_package.py --working-tree`: 11 checks,
  zero failures, four existing design-budget warnings. Hard caps were not raised;
  older redundant help/history prose was compacted. `git diff --check` also passed.
- **PASS:** Real installed headless Chrome **156.0.8078.76** and Edge
  **156.0.4314.58**, actual Document PiP, shipped HTTP/assets/CSP and real SSE:
  open/close/replacement/reopen/reload, existing-owner Watch return, route persistence,
  one EventSource, keyboard summary activation, resize, all themes, units, six account
  rows and long labels without horizontal overflow. Activation used CDP user gestures,
  **not physical clicks**. Main `hidden=true` / Mini `hidden=false` still received
  prompt completion, zero, source recovery and terminal host-not-live publications.
- **PASS:** Read-only real V2 source probe: three coherent publications, one running
  prompt with complete count/pricing, three accounts and one available primary-period
  cost; other costs honestly unavailable. Acquisition 25.858s; owned direct acquisition
  close 1.363s. This does not prove complete real monthly attribution where absent.
- **FAIL, unresolved:** Earlier broad `probe_web_live.py --watch-cards --daily`
  acquired valid cards/daily reconciliation but raised `web_shutdown_timeout` during
  owned WebHost cleanup. A similar intermittent timeout predates Mini. Root cause is
  not established; direct acquisition close does not prove WebHost shutdown.

## Scoped decision and remaining uncertainty

On 2026-11-03 the **Decision Delegate**, not the user or worker, authorized protected
delivery for **FR 000544 only**, including same-task continuation unless superseded:

1. Omit physical native X/return-control interaction, actual Windows minimization and
   minimized-opener restoration, and OS z-order/geometry proof. Headless native-API,
   hidden-document/SSE and source evidence was adequate without desktop disturbance;
   integrated browser access failed `browser.disconnected`. Screen-reader behavior
   is untested; accessibility requirements are **not** waived. No visible desktop
   action was authorized or performed, and hidden-page evidence is not OS proof.
2. Deliver without repairing unrelated host lifecycle or requiring the failed broad
   probe to pass, explicitly retaining its FAIL and unresolved shutdown risk. No
   runtime requirement, source truth, new-test failure or Git protection was waived.

No blanket future exception, complete physical/native acceptance, model inference,
credential change or shared OpenCode shutdown is claimed. Current Web help, module
architecture/code map, version/history/README and `development/journal/web/mini-watch.md`
are updated. The original specification bundle moved intact. Ordinary progress uses
the selected proposed state and counts only when merged; no release ZIP was generated.
