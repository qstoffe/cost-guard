# Completion — FR 000535

Date: 2026-10-30
Version: v80.116
Branch: `fr-000535`, targeting actual default `main`.

## Delivered

- Minimal branded/nav shell; healthy status and global footer prose removed.
  Unhealthy loaded pages retain compact actionable hover/focus/touch disclosures.
- Overview-only quiet acquisition: centered determinate, visibly approximate,
  monotonic canonical-stage progress; real local counts when known, success-only
  100%, concise actionable failures/partial data and no background report skeleton.
- Plain complete four-column CLI-ranked model table first. Intrinsic publisher,
  model and Relative CCost tracks; expanding release column, aligned markers/tiers,
  subtle dividers, fixed visual header and native row-only vertical scrollbar.
- One collapsed More information with concepts, current shared global latest-100
  comparison meaning and the existing memory-only Credits/USD selector. Genuine
  promotion/new-model notices retained; no model evidence block.
- Compact equal-height default account grid, one prominent name, canonical CLI
  values and real warnings; one Details disclosure for provenance/billing components.
  Expanded cards do not force neighbors to stretch. Dedicated routes keep controls.
- Frozen report/selection/scroll semantics preserved. No CLI, valuation, source,
  account acquisition, authorization, process lifecycle or resource-limit changes.
- Updated `docs/web-beta.md`, README/version, Web module owner facts and the existing
  Web journal. No system architecture/validation-flow change was needed.

The original specification was moved intact with its whole task directory; there
were no attachments. New evidence is outside the task payload.

## Actual verification

- Approval-only real browser: **12 cases PASS**, 360/1280/1920px light/dark,
  30 model rows, geometry/scroll/selection, loading and acquisition failures,
  authorization/offline/reconnect/stopped, zero/one/many accounts, browser-emulated
  mobile touch pans/taps, unit switching and frozen navigation.
  Screenshots visually inspected. Playwright 1.64.1 / Chromium 156.0.8078.4.
- Fresh full suite: **118 files: 117 PASS, one FAIL; 1,438 registered tests, two
  symlink-privilege skips**. All changed Web/display, CLI parity and causal tests pass.
- Package validator: **PASS**, 11 checks, four design-budget warnings, zero failures.
- [Hosted revalidation](https://github.com/qstoffe/cost-guard/actions/runs/40988348673):
  **PASS** on Windows 2025 and macOS 15 ARM64/Intel at `adfdf7d`.
  Full suite/package, native API/launcher smoke and rendered Chromium smoke passed
  on all three. Windows: 1,438 tests passed, no skips; each macOS: 1,431 passed,
  seven Windows-only skips. The initial terminal-browser fixture race was repaired
  by waiting for real SSE reconnection before stopping its owned host, without
  changing product behavior or removing assertions. Final evidence-only edits
  change no product/test source. The local 12-case Overview rerun also passed.
- Exact commands, sanitized browser measurements, repaired failed attempts and
  coverage limits: [verification](../../../architecture/governance/verification/web-minimal-overview.md).

## Decision Delegate exception and remaining uncertainty

The full suite is **not an overall PASS**. Four `powershell.exe` (Windows PowerShell
5.1) subcases in `test_launcher_feedback.py` failed due to host policy disabling
scripts (`SecurityError/UnauthorizedAccess`), with exit 1 rather than 9009/17:

- `test_windows_missing_python_is_clear_in_both_shells_without_starting_app`.
- `test_windows_skips_duplicate_failures_finds_next_python_and_preserves_mode_exit`,
  separately for report, watch and diagnostics modes.

The **Decision Delegate**, for this delivery alone, approved proceeding with only
these four unrelated environmental failures once all other checks passed and a
fresh full run confirmed that boundary. Those conditions were verified. Launcher
behavior in these subcases remains unverified; passing `pwsh` coverage is complementary,
not equivalent. No policy/bypass flag/test weakening was applied.

The delegate separately authorized isolated scratch-only browser-tool provisioning
and synthetic loopback tests, not a user-directed system installation or personal
browser access. No test waiver was granted for the UI feature. Physical touchpad/touch,
screen-reader, private installed-provider history, consumer macOS desktop and
non-Chromium browser acceptance remain untested. Hosted native API smoke is not
equivalent to those consumer checks. Product source delivery does not install/reload
or restart the user's existing runtime.
