# Web Cost per Active Hour — 2026-10-30

FR 000530 / v80.115. Web remains optional Beta. No CLI report, option or output
section was added; Billed, native quotas, Watch and account acquisition retain
their owners. `docs/web-beta.md` defines cost/time scopes and unavailable states.

## Deterministic evidence

`development/tests/test_active_hour.py` verifies unrounded Decimal formula and
prepared credits/USD tokens; session/period overlap, root/child/compaction and
background timing; abort/running/unknown/zero; request/step/clone deduplication;
cross-midnight/month event-cost allocation and clipped execution; 23/25-hour DST
days and precise rolling edge; stale active-root metadata; finite capture/cache
and no quota refresh; whole-session totals across 50-row pages; actual Live clock
advancement and frozen source-outage evidence. The shipped renderer/route Node VM
test verifies three scopes, explicit-only capture and reversible display tokens.

The focused suite passed. Existing CLI report rendering remains identical when
the new rate metadata changes; CLI parser/presentation files were not modified.
The product-version heading advances normally to v80.115.

## Browser evidence and authorization

The Decision Delegate authorized exact installed Edge/Chrome path checks, then
bounded isolated-profile headless Edge over synthetic loopback fixtures. No
existing browser window/profile, credentials, installed history, provider/model
call, login or shared-service mutation was used. Each owned browser/profile/server
was closed/cleaned. No executable download or system-policy change occurred.

`development/tests/integration/probe_web_active_hour.py --browser <explicit executable> --output <owned JSON>`
uses shipped app/assets with real fixture HTTP capture/cancel/detail requests and
a **scripted EventSource**. It does not prove real SSE/source integration.

Final run: **four PASS cases**, 20 assertions each, light/dark at **1200px/360px**.
The [sanitized receipt](web-active-hour-2026-10-30.json) records each assertion:
no history on opening; capture; three readable scopes/no document overflow;
Python-prepared USD/credits without acquisition or DOM replacement; focusable
semantic navigation/capture controls; frozen route revisit; stale failed refresh;
view-only cancel; no Watch/account report submissions; provisional session;
Freeze/Follow and frozen snapshot; same-revision unavailable/retained label; and
keyboard-scrollable detail region. Existing Live/account scheduling tests provide
independent regression coverage, not physical keyboard or native-device proof.

Earlier attempts remain unsuccessful:

- One initial **40-second TIMEOUT**, no assertion result, with a long-lived fixture
  SSE response. No feature PASS/failure was inferred. An exact prior-profile
  process query found no residual owned process.
- Four **FAIL** cases after 13 passing assertions each: the probe saw old hourly
  text before asynchronous session navigation had created its detail controller.
- Four **FAIL** cases after 16 passing assertions each: fixture construction reused
  an immutable one-shot service for two observation clocks. Independent non-UI
  reproduction showed 3000ms for both reused observations versus 7000ms for a
  fresh late observation. Corrected fixture creates one service per capture.
- Decision Delegate renewed only the specific bounded repair batches. Before the
  final batch, real SessionDetails/SessionHistory deterministic checks confirmed
  3000→7000ms advancement and retention on outage. Final cases ran serially with
  stop-on-failure. No shipped cache behavior or browser assertion was weakened.

## Release validation and limitations

Final `run_tests.py --suite full`: **117/118 files passed**, 1,438 tests reported,
four policy-blocked PowerShell failure subcases, zero errors, two existing
symlink-privilege skips. All 14 new focused tests and applicable Web/CLI/Watch,
session-history, pricing, duration and account suites passed. This is not an
overall full-suite PASS; the exception below is explicit.

Working-tree package validation passed **11 checks**, zero failures, four existing
design-budget warnings. Its initial version-history hard-cap failure was repaired
by condensing an older note, without raising the cap; the initial full-suite
foundation failure used the pre-repair copy and is not reclassified as PASS.

The unchanged Windows PowerShell 5.1 launcher subcases are blocked by host script
execution policy (`SecurityError` / `UnauthorizedAccess`, exit 1 rather than
9009/17). Corresponding pwsh.exe coverage passed. Decision Delegate approved this
narrow unrelated verification exception contingent on applicable checks passing;
no policy bypass or unrelated test change was made. Intended 5.1 behavior remains
unverified and the full suite is not labeled overall PASS.

Physical keyboard/mouse/touch, assistive technology, native macOS and installed-
history browser integration remain unverified. Programmatic focus/DOM layout is
not physical-input or visual-design approval. Deleted/pruned history cannot be
reconstructed; complete is always scoped to observed evidence.
