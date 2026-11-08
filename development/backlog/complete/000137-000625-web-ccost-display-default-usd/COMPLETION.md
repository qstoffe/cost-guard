# Completion — FR 000625

Implemented 2026-11-08 in v80.206, after FR 000624's merged v80.204 delivery.

## Delivered scope

- Only the shipped `webSettings.ccostDisplayUnit` changes from `credits` to `usd`.
- Existing Web/Mini inheritance resolves omission and saved `default` to USD;
  Settings derives **Default (USD)** and matching help from canonical defaults.
- Saved explicit Credits/USD remain pinned. Reads preserve original JSONC bytes;
  the existing private Settings API persists Credits, USD and symbolic Default.
- CLI retains its independent Credits default and `--ccost-unit` behavior.
  No pricing, valuation, quota, billing, conversion factor, scan or background-job
  implementation changes. No user configuration migration or running-instance update.
- Current README, usage/Web guides, architecture contract and Settings journal
  reflect the new default. Historical release entries remain intact.

## Verification

- Red/green: focused Web Settings regression failed with the old shipped Credits
  default, then passed as part of Full with USD.
- `py -3 development/tools/run_tests.py --suite full`: **PASS**, 170 files,
  zero failures, 123.0 seconds. Includes configuration, CLI/CCost formatting,
  Settings HTTP/JSONC persistence, DOM state machine, Web and Mini coverage.
- `py -3 development/tools/validate_package.py --working-tree`: **PASS**, 11
  checks, zero failures; seven existing advisory/design warnings.
- `py -3 development/tests/integration/probe_web_live.py --accounts`: **PASS**
  against the real V2 installation; one Live/account-refresh owner, two streams,
  three account cards, zero finite jobs/model calls, zero owned threads/processes
  after close. Shared OpenCode was not stopped or changed.
- Earlier short `probe_web_live.py`: **FAILED** final owned-worker assertion while
  one bounded Claude quota request was pending, despite successful Live/SSE.
  Existing acquisition shutdown has a 0.2-second join and does not wait on
  in-flight provider I/O. The account-aware probe waited for publication and
  closed cleanly; the earlier failure is not reported as PASS.

No requirement/test exception or new harness. A fresh local visual/layout matrix,
complete-history benchmark and physical-desktop check were not performed or
required for this default-only change. The existing hosted browser Settings smoke
now expects Default (USD) and exercises Credits → Default → explicit USD.
The real probe establishes source/lifecycle behavior, not browser painting,
complete-history correctness or upstream quota freshness. Normal required PR
checks remain the delivery gate.
