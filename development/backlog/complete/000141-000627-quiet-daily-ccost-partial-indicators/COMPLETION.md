# FR 000627 completion

Implemented for v80.210 (2026-11-08). GitHub PR/merge state remains delivery authority.

## Result and scope

- Full and Mini Watch use the server-prepared, unit-switchable `daily_usage.display.daily_ccost` token. Positive known-priced subtotals have no partial prefix; passive daily pricing/token/prompt-completeness notices are removed without replacement cues.
- Acquired empty usage remains zero, observed wholly unpriced usage N/A, and missing/failed acquisition retains Loading/unavailable behavior. Existing retained-observation, midnight, source/authentication and prolonged-update health owners are unchanged.
- Raw daily comparison, token mix, prompt count/completeness and source facts are unchanged. Original comparison tokens, prompt/session/Token Mix/CLI/account conventions, pricing and accounting remain independent. A plain daily amount is not proof of a fully priced day.
- Updated Mini, Watch, cost-reference and current-version documentation; architecture describes the narrow presentation contract. No journal update: no new acquisition/performance mechanism or unresolved product hypothesis was introduced; the relevant evidence and probe repair are captured here.
- Moved the entire original specification bundle intact to Complete ordinal 000141. Included selected ordinary progress (80, last ordinary identity `fr/000627`); no maintenance completion or deferral was invented.

## Verification

- Focused `test_watch_daily.py` and `test_mini_watch.py`: passed, including Python projection and Node DOM fixtures. Complete, positive partially priced, incomplete mix and prompt attribution, Credits/USD switching, retained publications, zero/N/A/loading/unavailable, and unrelated partial tokens remain covered.
- `py -3 development/tools/run_tests.py --suite full`: **174 files passed**, 0 failures, 123.4 seconds. Subsequent edits were confined to probe assertions/evidence and delivery documentation/state; the Delegate did not require repeating Full solely for the assertion repair.
- `py -3 development/tools/validate_package.py --working-tree`: passed; seven advisory existing size-budget warnings, no failed hard budget/layer/version checks. No ZIP built.
- `py -3 development/tests/integration/probe_web_live.py --daily`: real installed V2 passed. The final token-aware observation contained 3,547 requests and 117 prompts with **both pricing and prompt-count completeness false**; both plain daily units matched the known subtotal. Category costs reconciled; one owner/two streams advanced; owned workers closed and shared OpenCode stayed running. No model calls or source writes.
- `node development/tests/integration/probe_mini_fit.cjs <verified Chrome executable> <owned output> 1 1`: final result **PASS**, 204 layout records. Includes 56 daily-header snapshots with partial flags, Credits/USD, themes/fonts/loading/unavailable, actual one-row fit, reference reserve/gutter, opening/two-row capacity, headless pointer/keyboard disclosure, history and paired prompt/session values, Live/settings and one SSE connection.

## Failed probes and scoped decision

The integrated browser was disconnected; verification used an owned strictly headless Chrome process, never external desktop input.

The first Mini run failed because the older width oracle counted duplicate/adjacent text rectangles from existing split amount spans as separate lines and overrode the old total token. The repair groups only matching vertical bands, retains wrapping/overflow/bounds assertions, targets `daily_ccost`, and restores original nodes after temporary measurements. It also explicitly checks plain partial daily text and an empty daily note.

The second run completed 148 layout records but failed later in unrelated paired-cost coverage: a prompt-only span was incorrectly expected to contain `N/A (562)`. Decision Delegate authorized a bounded test-oracle repair, **not an exclusion or waiver**: assert the prompt-only value, independently assert the historical whole pair, retain the active pair and node-identity checks, and rerun the existing headless probe once. That run passed. No product behavior was changed to satisfy the probe.

Owned evidence references: `scratch:/full-tests.log`, `scratch:/live-daily.log`, `scratch:/live-daily-tokens.log`, initial failed `scratch:/mini-fit.json`, second failed `scratch:/mini-fit-current.json`, and final `scratch:/mini-fit-repaired.json`. These transient files are not part of the product distribution.

## Limits and remaining work

No acceptance/test requirement was waived. Native physical Windows frames, other browser/scale combinations, macOS and screen-reader behavior were not newly verified; headless checks do not claim those proofs. No remaining implementation work for this FR. Existing advisories and unrelated historical limitations remain unchanged.
