# FR 000526 completion

Implemented 2026-10-28 for Cost Guard v80.109, based on `afe6a21568203ced1338106ec2e2537b1b4d9107`.

## Delivered behavior

- Validated `ccostDisplayUnit: credits|usd` defaults to credits; `--ccost-unit credits|usd` overrides report, Watch, sessions, detail/date and historical Token Mix commands.
- Shared Python display primitives convert only reference amounts, at 100 credits = $1.00, with explicit dollars/two decimals and display-only half-up rounding. Zero, tiny positive, negative, partial and unknown values retain their distinctions. A visible disclaimer explains reference USD and positive values rounding to $0.00.
- CLI report/Watch entrypoints and application exports bind an exception-safe, thread-local rendering scope. Watch expands cost-column geometry for large dollar tokens. Application report/Live/frozen detail exports expose their configured unit and exact raw values alongside display tokens.
- Valuation, sorting, warning decisions and pricing are unchanged. Native quota credits, Unaccounted residuals, Billed money, rates and Relative CCost never consult the reference-amount display setting. No currency-network dependency or interactive Web toggle was added; the latter remains FR 000528.

## Verified evidence

- `py -3 development/tools/run_tests.py --suite full`: PASS, 116 files, zero failures, 51.8 seconds on the local Windows workstation. Includes deterministic cross-platform launcher paths and JS fixtures, not native macOS/Desktop proof.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, 11 checks, zero failures; four existing-category design-budget warnings remain (README, analysis context, report service, Watch coordinator). No hard cap was raised.
- New regression owner: `development/tests/test_ccost_display_unit.py`. Covers both units across report scopes, CLI argument/config validation, exact/raw retention and ordering, tiny/large/negative/partial/unknown values, Watch running/aborted/empty states, context ranges, native-field isolation, threshold invariance and nested/concurrent render isolation.
- Real-installation read-only V2 probe: `py -3 cost-guard.py --sessions 1 --ccost-unit usd` exited 0, reported OpenCode V2, contained one dollar-formatted table cost and the reference-USD disclaimer. Stderr contained normal source/cache/pricing/session progress. No prompt/session titles or provider data retained here; no model calls or service restart.
- Initial Full run found the README 13 bytes above its unchanged 32768-byte hard cap; concise wording repaired it. Final README is 32745 bytes. The complete Full suite and validator were rerun successfully.

## Knowledge, integrity and dependencies

Updated the existing presentation module contract and CODE_MAP with display-policy ownership, export propagation and test routing. Journal: **no-update**; no reusable investigation beyond this current architecture contract. Product README, usage reference, version/date and version history are current. Immutable FR specification bytes are preserved; this text-only completion adds no attachments/evidence files to the selected bundle. No dependent FR was modified, no completion was pruned, and native transaction state is staged exactly. No new cross-repository proposal is needed for the repaired README wording issue.
