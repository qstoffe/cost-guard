# Completion — FR 000538

Implemented in v80.119 (2026-11-01).

- Settings is the final/right-aligned navigation route and contains only Theme.
- Classic is the dark default; Web preserves the adaptive light/dark design.
- Authenticated, same-origin, CSRF-protected theme-only API reads the effective
  configuration and minimally updates only `webTheme` in the real user override
  location. Reads do not create it. Comments, unrelated settings/CLI palettes and
  ordering survive; canonical validation, file bounds/path guards, private atomic
  replacement, editor-conflict detection and safe errors protect writes.
- Confirmed saves restyle the loaded shell/all routes without reload or host/report
  restart. Failed saves retain the last confirmed appearance/selection with retry
  feedback. Startup, reload and fresh tabs use the saved effective file value.
- CLI/Watch/account/pricing/valuation contracts remain unchanged. Product version,
  README/history, Web guide, architecture owners and code/test routes were updated.

## Verification

Full suite: 120 files, zero failures, 1,462 passing cases and one ordinary Windows
platform skip (macOS zsh/PTY execution). Working-tree validation passed with four
existing design-budget warnings, no increased caps. Focused theme tests cover
configuration preservation/defaults, HTTP/security/errors, file hazards/conflicts,
source-guard stability, live DOM state/rollback and keyboard focus recovery.

Actual integrated Chromium checks covered 108 combinations over nine views,
360/1366/1920 CSS widths, both themes and both browser preference signals. Settings
submitted no report jobs; switching, file-permission failure/retry, reload/new-tab,
native-select keyboard interaction and focus were observed. No document overflow;
all measured semantic text/surface contrast pairs were at least 5.53:1. These used
synthetic data/transport and real file-backed settings in disposable fixture config,
not the owner's preference file. Cost per Active Hour was checked at its initial
explicit scope, not a captured period report.

Separate real-installation V2 Normal/all-models probing retained one live owner,
two streams and engine origin, completed both reports and joined owned shutdown;
shared OpenCode was not stopped. No model inference or native launcher was started.

## Explicit test exception / remaining uncertainty

The **Decision Delegate**, not a new user instruction, authorized omitting a fresh
full AC6 visual matrix/screenshots after the last small Classic selector refinement.
Prior full browser coverage plus final integrated computed styles were judged
adequate without disrupting the owner or introducing external-browser automation.
The final rule leaves ordinary new-row text grey and marked cells/notices/running
lime only in Classic; its computed-style check passed and Web colors were retained.

Subsequent matrix reruns timed out; Review screenshot access then required a visible
desktop window. Those attempts are **not PASS**. Final post-refinement appearance
was not freshly visually inspected. Native OS/physical-device, assistive-technology
and real-source visual behavior remain unverified; implementation/backend gates
were not waived. Ordinary file-identity/byte checks are not a hostile same-user race
guarantee. Other tabs refresh appearance on their next settings read, not broadcast.

Detailed evidence, reproducible fixture routes, observations, limits and the
delegate's reason are in
`development/architecture/governance/verification/web-theme.md`; the journal index
routes that same knowledge. No duplicate architecture layer, installer, release ZIP
or GitHub Release was added. Current `main` remains the supported distribution.
