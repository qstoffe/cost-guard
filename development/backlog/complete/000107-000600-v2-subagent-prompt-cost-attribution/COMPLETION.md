# Completion — FR 000600

Implemented 2026-11-06, Cost Guard v80.176. The original specification is preserved intact in this bundle. Git/PR merge state, not this file's existence, establishes delivery.

## Outcome

- Shared `analysis/child_links.py` recognizes V2 `subagent` and legacy `task`, structured state/top-level `sessionID`/`sessionId`, and exact native output envelopes as a fallback. It validates real acquired parentage and possible invocation times, coalesces physical calls and scopes descendants for both accounting and Watch activity.
- Parent and child usage retain physical invocation identity, initiating prompt and model/effort/tier. Repeated/overlapping links do not double-count; background work, nested background descendants, synthetic notices, late requests and later reuse of a child retain separate windows. Child-only recorded usage is not silently omitted or relabelled as the main model.
- Corrected canonical rows flow unchanged to session reports, CLI, Web Watch and Mini's shared Live export: CCost, I/E, Calls, token mix, model marker and per-agent detail. Whole root-tree CCost remains independently authoritative, not a residual allocator. Actual billing, reference rates, units, compactions, zero/partial/unknown evidence and the established historical Watch Duration metric remain independent.
- Derived algorithm 16 invalidates older attribution. No extra session scan, paid inference, reconciliation registry, product gate or release archive was introduced.

## Verification

- Sanitized incident regression was run before the fix and failed with 2 Calls instead of 3. After canonical V2 loading it now independently proves Main 122 + Subagent 102 = 224 unrounded CCost; I 21 + E 203; 3 Calls; second-model detail and 25/25/25/25 token mix. Full root valuation independently agrees only when coverage/pricing support it.
- `py -3 development/tools/run_tests.py --suite full --verbosity 1 --json-report <owned scratch>/full-tests-final.json`: **147 files, 1726 tests, 1725 passed, 1 platform skip, zero failures/errors**, 92.5 seconds. The skip is the existing zsh/PTY launcher execution test on this Windows host; macOS CI owns its native execution. The initial Full run caught a Watch Duration regression; its cause was repaired and the entire suite rerun successfully.
- Focused `test_subagent_attribution.py` and `test_child_links.py` pass, including exact I/E, independent tier arithmetic, wrong-parent/copied/malformed evidence, repeated/corrected links, nested/background timing, cross-prompt reuse, old/current caches, zero/partial/unknown pricing and legitimate residuals. Existing nested-detail and linked-skill fixtures now supply ancestry/activity times consistent with their assertions.
- `py -3 development/tools/validate_package.py --working-tree`: zero failures, 11 passes, six existing advisory prose/design budget warnings; no limits were raised.
- Read-only real V2 `probe_web_live.py --watch-cards --prompt-cost --prompt-token-mix --session-cost`: raw CLI/Watch cost/category parity, independent 4-request full-session total and no-op persisted reuse, six known token-mix rows over twelve seconds, one advancing Live owner/two streams. Owned workers closed; shared OpenCode was not stopped. Shutdown phase observations include two background history cancellation/error observations, so this is not exhaustive history-coverage proof.

## Limits, decisions and documentation

No user- or Decision-Delegate-approved requirement/test exception was needed. The real observed prompt had zero linked agents: live checks do not independently reproduce the historical incident or verify its precise 109-CCost child contribution. The original child export was unavailable and no private export/transcript was added. Deterministic source/causal/report/Live tests establish the supported incident shape. No new browser-layout or macOS desktop proof is claimed for this backend change.

Architecture owner/test routes, usage/cost documentation, current README, version/date/history and `development/journal/subagent-attribution.md` are updated. The journal retains the original failure, compatibility repair, actual evidence and source limitations. Maintenance state carries the selected ordinary next state (46); it counts only when merged to the actual default. No additional task was selected.
