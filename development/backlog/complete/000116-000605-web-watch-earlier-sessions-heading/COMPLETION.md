# FR 000605 completion — 2026-11-06

## Delivered scope

Full Web Watch's native historical disclosure now reads **Earlier Sessions**,
matching Mini Watch. Its observed-empty and unavailable messages read **No earlier
sessions** and **Earlier sessions unavailable**. The production change is limited
to those three strings in `src/web/assets/watch.js`.

Running/individual-prompt wording, loading behavior, session membership, counts,
ordering, rows, calculations and disclosure semantics are unchanged. Mini Watch
code is untouched. Current Web/Mini documentation and the help inventory use the
new section name; historical FRs and journals were not rewritten. The original
specification was moved intact. Version metadata/history/README advance to
v80.185, and the selected ordinary progress advances from 54 to 55.

## Verification

- Regression first: `run_tests.py --pattern test_web_live.py` failed on the old
  `Earlier Prompts` heading before the production edit, as expected.
- `py -3 development/tools/run_tests.py --suite full`: PASS, all 151 test-file
  executions, zero failures, 94.6 seconds. Updated VM assertions cover the exact
  heading, empty/unavailable wording, unchanged running-empty message and retained
  expansion; existing checks retain keyed rows, ordering, focus and loading state.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, zero
  failures. Six existing advisory/design-size warnings remain (README, version
  history, Web guide and three unchanged Python modules); no budgets were raised.
- `node development/tests/integration/probe_watch_presentation.cjs <Chrome>
  <owned-output>`: PASS in Chrome 156.0.8078.80, six cases (Classic light, Web light
  and Web dark at 1366/360 pixels). Actual DOM checks verify all three strings,
  initial collapse, native disclosure activation, stable historical card identity,
  neutral loading and retained expansion across empty/unavailable updates.
  Existing paint/transition, focus, selection, costs and overflow checks also pass.
  Sanitized browser evidence: `scratch:/ui-proof/browser.json`.
- `py -3 development/tests/integration/probe_web_live.py --watch-cards`: status
  OK against the real registered V2 installation; one shared live owner, two
  verified streams, advancing publications, one historical card with a supported
  finish and one-row card bounds. First rows arrived in 5.389 seconds. The probe
  closed its owned workers; shared OpenCode was untouched. Independent daily work
  was not awaited or certified by this task-focused probe.

## Limits and documentation

The integrated OpenCode browser was disconnected; the UI probe used an owned,
hidden Chromium profile instead, without external-desktop interaction. Browser
fixtures prove synthetic DOM/paint behavior; the separate live probe proves real
source acquisition, not physical desktop or screen-reader behavior. No requirement
or test exceptions were requested or granted, and no implementation scope remains.

The current help inventory was updated in place. No additional architecture or
journal update is needed for this display-only rename: no boundary, acquisition,
accounting or lifecycle contract changed. No release ZIP, tag or GitHub Release
was produced; current `main` remains the supported distribution.
