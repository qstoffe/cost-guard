# Completion — FR 000580

2026-11-04 · v80.161 · implementation base `e0ecfb07d0cd5439026fbc1ee129eab8c4555fed`.

## Implemented

- Every full-Watch Running/Earlier card uses `Session Context / CCost: <context> / <cost>`.
  Canonical session-continuation and entire root-tree cost ownership are unchanged.
- One canonical warning follows both figures, with one outer parenthetical, no repeated
  severity prefix and no nested multiplier/range parentheses. Unit-bound display tokens
  preserve Credits/USD, supported alternate ranges and missing impact details.
- Approaching highlights only an amber SVG triangle and context figure. Exceeded changes
  the same SVG to a red octagonal stop/exclamation and highlights only context and a
  supported relative multiplier. Labels, slash, session cost, boundary and range stay neutral.
- Stable spans/SVG retain focus and update/clear severity in place. Accessible severity
  names do not repeat the warning explanation; context help distinguishes model-tier
  pricing from accumulated session spending. Loading/retained/partial/unpriced states remain.
- Updated current Web guide, architecture/code map, release metadata/history and existing
  Watch knowledge. Historical completed FR 000572 is unchanged. Maintenance progress is
  the selected next state: ordinary count 31, last ordinary `fr/000580`.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: **140 files passed**, zero failures,
  four isolated workers, 86.9s. Focused context, daily/DOM, prompt-cost, Live and Mini tests
  also passed. Existing canonical cases cover exact crossing/disabled approach, hidden
  compaction, model/context epochs, source corrections, concurrent cards and Earlier reuse.
- `py -3 development/tools/validate_package.py --working-tree`: **11 checks passed**,
  zero failures; six existing advisory prose/module design warnings. No caps were raised.
- `probe_watch_cards.cjs`: **12 rendered cases passed**, Chrome/156.0.8078.80 headless;
  Classic/Web light/Web dark at 2560/1920/1366/360px. Checks include severity shapes/colors,
  neutral non-target text, >=4.5:1 context contrast, focus-safe transitions, unknown context,
  range/no-impact fallback, Credits/USD, single explanation and narrow wrapping/no overflow.
  Existing table, history, activity, quota and layout assertions also passed. Representative
  pixels inspected; [measurements/screenshots](../../../tests/evidence/watch-context-summary/).
- `probe_web_live.py --watch-cards --session-cost`: real read-only V2 **passed** with one
  acquisition owner/two streams, preserved run origin/advancing IDs, one active and one
  historical card observed. A stable four-request priced session matched independent full
  history; fresh persisted-cache reuse revalued zero requests and wrote no session-cache
  state. No model calls; zero remaining owned threads/processes; shared OpenCode untouched.
  Phase instrumentation recorded a history-read/cancellation error during shutdown; no
  daily-publication completeness or original error cause is claimed.

## Repairs and limits

The first Full run caught a missing `createElementNS` API in Mini's synthetic DOM stub;
the final rerun above passed after adding the actual SVG seam. The browser probe's older
manual quota mutations initially left the newer prepared display variant stale; the probe
now updates that variant consistently. Its contrast calculation was also corrected to use
the painted body background, not transparent `main`. No production quota behavior or
assertion was weakened to obtain a pass.

No user/Decision Delegate requirement or test exception was requested or granted.
Headless DOM/style/focus/ARIA checks are not physical-desktop, native-shell, actual
screen-reader or macOS acceptance. Mini presentation, CLI, Sessions pages, canonical
pricing/acquisition/cache behavior and other pending FRs were not redesigned. No release
ZIP, tag or GitHub Release was created. Publication/merge truth belongs to the linked PR.
