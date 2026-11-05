# FR 000588 completion — Web-host V2 service wake

Implemented for v80.169, 2026-11-05. Native/cold-start acceptance has the explicit
Decision Delegate exceptions below; this is not full platform verification.

## Delivered scope

- One coalesced, host-start-only installed-CLI wake on the existing Live worker;
  healthy source selection is reused without a launch or retry delay.
- Config/source-mode and narrow failure eligibility precede the fixed process
  command. Explicit/healthy auto V1, invalid/unreadable registration, permission,
  authentication, unsupported scheme/API/schema and unrelated HTTP faults do not
  trigger a wake. No browser process-launch endpoint or security-boundary change.
- Five-second hidden Web command, followed by the existing bounded fresh
  registration/authenticated loopback readiness checks. CLI exit alone proves
  nothing. CLI report recovery shares the primitive and retains its 20-second bound.
- Responsive shell/navigation, visible accessible starting feedback, queued finite
  reports and automatic Live/report continuation after readiness. Failure clears
  the indicator and keeps truthful manual-start/wait/Refresh recovery.
- Tabs/reload/Refresh/reconnect never repeat the attempt. Shutdown continues to
  stop only Cost Guard work, never shared OpenCode.
- Windows fixed batch-tail quoting handles spaces/Unicode; expansion/operators
  are refused. No dependency, listener, installation, config/registration write,
  Desktop launch, model inference or OpenCode-history mutation was added.

## Verification

- Final `py -3 development/tools/run_tests.py --suite full`: **PASS**, 143 runner
  units, 86.5s. New startup tests are included in Full/Quick and startup profile.
- `py -3 development/tools/validate_package.py --working-tree`: **PASS**, zero
  failures, six advisory prose/design warnings. No product release ZIP was built.
- Focused startup, lifecycle, historical-report and source-history tests: **PASS**.
  Earlier Full attempts failed obsolete lifecycle mocking and a clock-dependent
  scale-fixture catalog count. Mocks now isolate the new startup seam; the narrow
  Delegate-authorized source-local clock repair retains real metrics and every
  872-root correctness assertion, with exactly three fixture-specific catalog reads.
  No production deadline/TTL was raised and no failing assertion was weakened.
- Actual hidden Windows batch shim with spaces/Unicode: **PASS**. It reproduced
  legacy quoting failure before the shared-command repair.
- Owned headless Chrome 156.0.8078.80 / actual HTTP/assets: **PASS** success and
  false-CLI-success failure. Checked starting visibility/accessibility, responsive
  Settings navigation, queued Normal completion without manual Refresh, two tabs,
  reload, wake count one and truthful cleared failure/manual-start guidance.
  Sources/reports/Live in this browser campaign are synthetic, not real cold-start proof.
- Real healthy installation startup: V2 ready in 0.134s, guarded **zero wake calls**.
  Installed fixed read-only CLI info command: **PASS**, 0.211s.
- Real Live-only probe: **PASS**, one V2 owner/two streams, first view 2.729s,
  preserved run/sequence, shutdown 0.0742s, zero remaining owned workers. Shared
  OpenCode remained untouched.
- Supplemental real `probe_web_live.py --reports`: **FAILED**, Normal hit the
  unchanged 120-second deadline during history sampling (93 completed units).
  HTTP max 0.2904s, cleanup 0.2568s, zero remaining owned workers. The probe bypasses
  this startup owner; the slowdown's cause/pre-existing nature is not established.
  Synthetic Normal completion does not prove real-history performance.

## Approved exceptions and uncertainty

**Decision Delegate, 2026-11-05, this FR only:** waived real stopped-service
end-to-end, physical Windows launcher/tray/browser handoff, and native macOS
launcher/wake checks. Adequate hidden/deterministic/healthy-live evidence covers
the changed seam; stopping the session's shared OpenCode is forbidden. Accepted
the supplemental Normal timeout as unresolved and nonblocking, never PASS.
No visible-desktop action, alternate identity/configuration, shared-service stop/
restart, or future blanket exception was authorized. Full/final validator remain
required. Cold-start/native/platform behavior and real Normal completion within
its deadline remain unverified. No requirement rewrite or On Hold was decided.

The delegate separately authorized the narrow test-clock repair. Its initial
exact-two catalog assumption was investigated and explicitly superseded by exact
three after identifying deferred endpoint initialization/cache retirement in this
mocked fixture. See the existing historical-report journal for causal details.

## Documentation and accounting

Updated README/current version, release date/history, Web/connectivity guides,
Web/source ownership and code map. Existing startup and historical-report journals
retain evidence, failed attempts, decisions and proof limits. Maintenance state
contains selected progress: ordinaryCount 39, lastOrdinaryId fr/000588, unchanged
maintenance completions; only its merged default publication advances accounting.
The entire original specification bundle is preserved here unchanged.
