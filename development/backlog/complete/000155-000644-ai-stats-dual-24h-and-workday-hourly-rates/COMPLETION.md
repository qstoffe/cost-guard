# FR 000644 completion

Implemented 2026-11-09 as v80.224. The original specification is preserved intact
beside this report; its FR-only amendment boundary describes the earlier authoring
revision, not this authorized implementation.

## Outcome

- Ten original cards/order retained. The first card alone shows 24h average,
  Workday average and a hypothetical Robot · 8h shift, with the original trait policy.
- Python derives all three from the same period cost, preserving the original
  active-hour raw value and unioned/bounded working time. Robot is never Workday ×8.
- Configured-local nominal date slots, SE/weekend-only workdays, holidays, DST,
  rolling membership, month-to-date and supported All-time beginnings are covered.
  No-workdays and absent active basis are independent safe cases.
- Explicit raw rates and prepared Credits/USD tokens/math help pass through the
  projection allowlist. Switching units updates retained rows/help without fetching.
  Other nine metrics, source/cache acquisition, Watch, CLI and valuation stay unchanged.
- User guide, README/version/history, architecture owners, code map, journal and
  selected maintenance progress are updated. No ZIP, tag or Release is produced.

## Verification

- Full: 179 test files, zero failures (123.6s); final focused Stats/rates/recovery/
  resume checks passed after the exact active-hour help-format refinement.
- Package validator: 11 passes, zero failures, seven existing advisory warnings;
  no budget increases. Git whitespace check passed.
- Hidden Edge: PASS, 16 checks, 72 canonical state/theme/unit cases, 9 layouts,
  80 text layouts and 1,350 contrast samples. Three-way arithmetic and independent
  robot intensity, no-workdays, retained updates, 360/520/1280 widths, Classic/Web
  light/dark, enlarged text/zoom, keyboard/touch/Escape and existing session links
  passed. Owned host/browser/process cleanup passed; no runtime errors.
- Read-only real installation: four complete/error-free attempts, five periods each;
  all new rate identities and both-unit tokens checked. Cold30 116.184s, warm30
  6.114s, reused All 0s (not cold), fresh warmAll 5.512s. Disposable own cache;
  no OpenCode stop, source mutation or inference.

Evidence and reproducible commands: [AI Stats journal](../../../journal/web/ai-stats.md#three-perspectives-on-the-first-card--fr000644).
Own detailed evidence: `scratch:/full-tests.log`, `scratch:/ai-stats-live.jsonl`,
`scratch:/ai-stats-browser-final.json`.

## Limits

The integrated browser was disconnected; permitted hidden Chromium supplied actual
browser evidence. Physical touch, native desktop rendering, non-Chromium engines
and actual screen-reader speech are not claimed. Mutable-source timings are not a
paired performance comparison. No requirement exception or product deferral was used.
