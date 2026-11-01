# Completion — FR 000539

Implemented in v80.120 (2026-11-02).

## Delivered

- One Web settings section: Theme and CCost display only. Previous report/shell
  CCost controls removed; changes save immediately without acquisition/reload.
- Independent `webSettings.theme` / `webSettings.ccostDisplayUnit` in the existing
  user JSONC. Legacy user theme fallback survives new shipped defaults; explicit
  nested theme wins. Web defaults to Credits regardless of the unchanged CLI key.
- The existing narrow authenticated settings writer now preserves either nested
  leaf independently, the other preference, legacy/CLI values, comments and unrelated
  settings. Security, lifecycle, atomic replacement and conflict guards remain.
- Confirmed saves update existing Python display tokens across visible and retained
  views, with error rollback/retry. Startup reads settings independently of analytics;
  reload/new tabs/read-on-entry see file values without browser storage or polling.
- User and architecture/navigation docs describe the per-setting promotion rule:
  unpromoted fields remain shared; separately approved editable Web preferences
  receive independent values in this namespace. No generic editor or broad migration.

## Verification

- Full passed all 120 test files. Final strengthened focused targets: 38 tests passed.
- Package validator: zero failures, 11 passes, four existing design-budget warnings;
  no raised caps. Initial obsolete-default and documentation-cap failures were repaired.
- Actual integrated browser: 108 theme/layout combinations, no document overflow,
  exactly two Settings controls; both units across nine routes including captured
  history/hourly, Watch and session Snapshot/Follow live. Legacy fallback, CLI/Web
  default isolation, confirmed persistence, readonly error/retry, reload/new tab and
  native keyboard-focus recovery were observed on disposable canonical settings.
- Real installed V2 read-only probe passed Live/two streams, first/latest detail,
  freeze, normal/all-models/sessions/date and deep-history cancellation, preserving
  one owner. Owned workers closed; shared OpenCode remained running.
- Detailed results, reproduction scripts, prior failed-run facts and limitations:
  [Web settings verification](../../../architecture/governance/verification/web-settings.md).

No requirement/test exceptions. Physical devices, screen readers, native menus,
macOS and real-source visual parity are not claimed by synthetic browser checks.
No paid inference, real user preference/credential changes, runtime installation,
ZIP or packaged Release. Current main remains the supported distribution.

Architecture owner docs updated. Journal no-update: current owner/evidence docs
capture the reusable facts; no separate historical journal entry is needed.
