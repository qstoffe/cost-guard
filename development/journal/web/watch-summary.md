# Watch daily summary and continuation guidance

FR 000543, v80.124, 2026-11-02; implemented after FR 000542. Source and focused tests own current behavior.

## Accounting and publication

Retain the existing `WatchHistoryAcquisition` in Web's single history lane, not one disposable daily tracker per acquisition. `history.record` reconciles canonical physical requests and retains their causal initiating-prompt mapping. `analysis/daily_usage.py` filters request completion/attribution timestamps against configured local midnight/current observation time, deduplicates clones, values each request separately and projects cost/count/mix together. Known compaction usage contributes no user prompt; unassigned usage remains in cost/mix and makes the count partial. Account attribution is independent of this global population.

Native quota observation remains separately refreshed. Matching-day historical cost scopes merge onto fresh native snapshots; old-day worker results cannot repopulate a new-day summary. Revision changes request background refresh, with the existing minute fallback. Unchanged roots reuse revision evidence; UI wakes and browser tabs perform no history scans. Provider-attributed estimates are explicit structured report metadata rather than browser-invented account allocations.

## Context and presentation

`session_watch_context` is current guidance, not a rewrite of historical row context. A hidden compaction may replace/remove/downgrade the latest prompt's footer state. Unknown or retired epochs cannot revive an older warning. `watch_context.card_context` carries structured severity and the multiplier belonging to that Watch model/context; only its latest owning focal (or historical session card) receives it. No severity is parsed from prose and no pricing is calculated in JavaScript.

Watch-only account subgrid tracks align within each responsive row without clipping titles. Primary slot selection is provider/adapter-owned, never sorted by depletion. Ordinary Accounts/CLI rendering remains separate. The compact Total Today group uses prepared Credits/USD tokens and distinguishes initial loading, empty evidence, partial attribution/telemetry/pricing and retained acquisition failure.

## Observed verification and limits

- Full: 124 files / 1,504 tests; 1,503 passed, one existing zsh/PTY skip, no failures. Working-tree validator passed with four design warnings and unchanged hard budgets.
- Integrated Chromium: Classic/Web light/Web dark, 360/768/1366/1920px. Common tracks aligned per visual row; desktop daily groups shared one line, narrow groups wrapped with no document overflow. Live update retained focus, disclosure and scroll; footer removal was immediate. VM tests cover Credits/USD without acquisition.
- Real V2: one owner/two streams/three accounts; full-day 1,582 retained requests and 131 attributed initiating prompts with incomplete attribution explicitly reported. Per-category reference costs exactly reconciled with total; daily acquisition 44.461s, independent cards 7.643s. Owned workers closed and shared OpenCode remained running.
- Intermediate extended probe during source edits failed with HTTP timeout and live shutdown timeout; the later source-frozen repeat passed. Do not promote this sequence into a general shutdown diagnosis or performance guarantee.
- No model inference, external browser process, physical macOS/mobile acceptance or real clock/source mutation. Deterministic tests cover midnight/DST, omissions, hidden compaction and delayed results. No delegated exception was needed.
