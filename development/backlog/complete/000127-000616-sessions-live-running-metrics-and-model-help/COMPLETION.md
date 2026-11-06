# FR 000616 completion — 2026-11-06

Implemented in v80.196. The original specification and bundle are preserved intact.

## Delivered behavior

- Fresh canonical Watch prompt proof establishes running before scalar hydration, independently of pricing/index trouble. Original age, source identity, source failure and newer terminal observations bound that proof; candidates alone never assert execution.
- Existing bounded summary polling updates canonical model, qualified CCost, prompt count and measured execution duration. Actual pre-request model acquisition can be pending independently of known zero/partial/unsupported fields. Retained values remain usable and qualified; no idle-time/cost estimator was added.
- Canonical physical contributors supply a sorted distinct provider/model list, including attributable child requests, capped at 64 identities/256 characters each. Incomplete/running/retained lists say observed so far; missing identities are explicit. Summary algorithm/schema validation invalidates older scalar payloads.
- Shared hover/focus/touch ContextHelp is attached to the `Multiple models` text. Keyed row/cell/link/help nodes update without losing focus, text selection, document scroll or open help; only protected structural changes defer. Six columns, 50-row paging, global sort coverage and older-page epochs remain unchanged.
- Updated README, version history, Web guide, Web module ownership and Sessions journal. Maintenance progress advances to ordinary delivery 66 only when merged.

## Verification

- Final local `py -3 development/tools/run_tests.py --suite full --jobs 1`: **154/154 files passed**, zero failures, 360.0 seconds, unchanged 240-second per-file bounds.
- `py -3 development/tools/validate_package.py --working-tree`: **11 passes, zero failures**, six existing advisory categories; no cap/baseline raised.
- Focused catalog/detail Python and actual-assets VM: 30 tests passed. Regressions cover cold running proof versus mere candidates, revision churn, stale/outage/retained/failure states, terminal/resume, provenance, independent unknowns, contributor deduplication/bounds/allowlisting and old/malformed scalar-cache rejection.
- `probe_web_sessions.cjs ... --live-only`: **PASS** in hidden fresh-profile Chrome 156.0.8078.80 and Edge 156.0.4314.58. Shipped HTTP/auth/assets consume an owned synthetic source. Normal polling covers cold Loading → hydrated values → model/cost/count progression → finish/idle → reconnect/resume. Actual rendered checks cover focused link/node identity, selection/scroll, open-help refresh, Tab, hover/leave, touch pin, Escape, no native/duplicate help, Classic/Web light/dark, 360/1366/1920 widths and 100/150% CSS zoom.
- Read-only real V2 `probe_web_live.py --sessions`: 2,776 roots, index/visible coverage 0→2, 73ms first page, 262ms maximum API reply, two-prompt detail in 5.796s/16,645 bytes. Contributor bounds/distinctness validated over 29 multi-model row samples without printing identities/titles. One Live owner/two verified streams preserved; all owned workers closed. No model calls, source writes or shared OpenCode stop.

## Failures, limits and exceptions

The first rendered attempt found a real DOM `title` property collision (fixed); the next found synthetic cost deltas rounded to identical `<0.1` text (fixture usage increased, assertions retained). An intermediate Full passed 154 files in 132.3s. A later concurrent Full failed the unchanged Windows shutdown fixture's two-second completion assertion: its captured stack was joining the terminated report child, not a blocked source read. The isolated five-test file passed, then the final serial Full passed unchanged. Contention is plausible, not proven; no test/timeouts were weakened and the failed run is not called PASS.

Integrated browser discovery was disconnected; hidden browsers supplied rendered evidence without external desktop interaction. Physical desktop/native browser zoom, macOS and screen-reader operation were not performed. The real observation saw neither a cold-running sample nor a natural new arrival: the exact owner incident and real arrival latency remain unestablished. The deterministic fixture reproduces the causal cold/churn transition, not that private incident.

Global real-source metric sorting remained honestly pending; full-catalog warming was not claimed. Individual index work reached 6.2983s despite the two-second *admission* slice. Independent history-batch/advance counters each recorded two unclassified errors; this task does not certify unrelated historical lanes. Those limits and prior scoped baseline decisions are retained in the Sessions journal. **No new user/delegate requirement or test exception was requested or approved.** PR checks and merge truth belong to the delivery PR, not a fabricated local result.
