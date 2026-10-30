# Minimal Web Overview — FR 000535

Source revision: e6b2ad827f3f3681123e6ba1eac292b5dc8f31c3
Checked revision: e6b2ad827f3f3681123e6ba1eac292b5dc8f31c3
Last checked: 2026-10-30
Status: current

## Scope and browser evidence

`development/tests/integration/web_minimal_overview.py` passed **12 cases** using
Playwright 1.64.1 / Chromium 156.0.8078.4, isolated contexts and owned fixture hosts.
It serves the actual shipped HTTP/security/SSE/assets over loopback with synthetic
canonical reports; browser requests outside that origin are blocked. No provider,
personal profile, installed application, shared host or model is used.

- 360/1280/1920px, light and dark. Thirty rows with short/long names, tiers,
  promotions, recent/superseded roles and missing release dates. Exact four columns,
  no document overflow, matched header/body cell edges, zero base-ratio drift.
- The first three desktop columns are intrinsic-sized; only Release date expands.
  Body-only scroll geometry, real wheel input, Home/End and horizontal ArrowRight
  access, last-row reachability, stable selection/DOM across host revalidation.
- Slow authorization and changing real job polls expose no report skeleton/controls.
  Approximate percentages **22 → 42 → 55 → 80 → 80 → 99** remain monotonic even when
  an earlier phase arrives late. Only a received complete acquired result reaches
  100; partial results and failures never do. Loading then disappears entirely.
- Failed/timeout/partial/unauthorized/offline acquisition and mid-acquisition
  offline/reconnect/terminal stop. No hidden replacement job on recovery.
- Seven provider/account states including multiple quota windows, unknown native
  values, long labels, blocked/partial/stale conditions; equal collapsed heights,
  independent Details expansion, compact warnings, prepared unit selection and
  retained Normal result on browser Back. Models retains its independent controls.

[Sanitized measurements](web-minimal-overview-browser.json) retain geometry and
case results. Authorizing/ready light/dark screenshots and narrow right-scroll views
were visually inspected in session-owned scratch, not committed as private evidence.

## Reproduction

With separately authorized, already provisioned test-only Playwright and Chromium:

```text
python development/tests/integration/web_minimal_overview.py --approved-browser --output <owned-json-path> --screenshots <owned-directory>
py -3 development/tools/run_tests.py --suite full --file-timeout 120 --json-report <owned-json-path>
py -3 development/tools/validate_package.py --working-tree --json
```

Do not install or launch a browser merely because this document names a command.
The Decision Delegate authorized this delivery's scratch-only provisioning from
official distributions and synthetic loopback browser tests. It did not authorize
personal-profile discovery, system installs, external browsing or policy changes.

## Regression results and narrow exception

Fresh full run: **118 files, 117 PASS, one FAIL; 1,438 registered tests, two skips**.
The only failing file is `test_launcher_feedback.py`; four Windows PowerShell 5.1
subcases fail because running scripts is disabled (`SecurityError/UnauthorizedAccess`,
exit 1 instead of the expected 9009 or 17):

1. `test_windows_missing_python_is_clear_in_both_shells_without_starting_app` — `powershell.exe`.
2. `test_windows_skips_duplicate_failures_finds_next_python_and_preserves_mode_exit` — `powershell.exe`, report.
3. The same test — `powershell.exe`, watch.
4. The same test — `powershell.exe`, diagnostics.

Their launcher behavior remains **unverified**, not PASS. The corresponding `pwsh`
subcases passed but are not equivalent proof. The **Decision Delegate** approved a
delivery-specific exception only for these four unrelated policy-blocked subcases,
conditional on all other tests, package validation and strengthened browser checks
passing. No execution policy, bypass flag or launcher test was changed.

Two existing skips: macOS linked-cache destination and Web guard symlink checks,
because this Windows host lacks symlink privilege. Package validation passed all
11 checks with four design-budget warnings and no failures. Web/CLI display, quota,
sampling, security/lifecycle and other-route regression files passed.

Earlier failures were repaired, not waived: header gutter mismatch; a legitimate
Available account name mistaken for status; this delivery's history entry exceeding
the unchanged cap. Fixture CSP/closed-SSE-slot failures were corrected in the harness
without weakening production security, stream limits or input behavior.

## Limits

This is actual headless Chromium rendering with automated wheel/keyboard/focus,
not physical mouse/touchpad/touch, assistive-technology certification, installed
private-source acquisition, native tray/Finder/macOS or Firefox/Safari acceptance.
No new permanent product/release gate, dependency or architecture boundary is added.
