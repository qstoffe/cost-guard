# Watch daily summary and continuation guidance

FR 000543, v80.124, with FR 000547/v80.128 amendments below, 2026-11-02. Source and focused tests own current behavior.

## Accounting and publication

Retain the existing `WatchHistoryAcquisition` in Web's single history lane, not one disposable daily tracker per acquisition. `history.record` reconciles canonical physical requests and retains their causal initiating-prompt mapping. `analysis/daily_usage.py` filters request completion/attribution timestamps against configured local midnight/current observation time, deduplicates clones, values each request separately and projects cost/count/mix together. Known compaction usage contributes no user prompt; unassigned usage remains in cost/mix and makes the count partial. Account attribution is independent of this global population.

Native quota observation remains separately refreshed. Matching-day historical cost scopes merge onto fresh native snapshots; old-day worker results cannot repopulate a new-day summary. Revision changes request background refresh, with the existing minute fallback. Unchanged roots reuse revision evidence; UI wakes and browser tabs perform no history scans. Provider-attributed estimates are explicit structured report metadata rather than browser-invented account allocations.

## Context and presentation

`session_watch_context` is current guidance, not a rewrite of historical row context. A hidden compaction may replace/remove/downgrade the latest prompt's footer state. Unknown or retired epochs cannot revive an older warning. `watch_context.card_context` carries structured severity and the multiplier belonging to that Watch model/context; only its latest owning focal (or historical session card) receives it. No severity is parsed from prose and no pricing is calculated in JavaScript.

Watch-only account subgrid tracks align within each responsive row without clipping titles. Primary slot selection follows native declarations/account-window order, never provider identity or depletion. Ordinary Accounts/CLI rendering remains separate. Total Today uses prepared Credits/USD tokens and distinguishes initial loading, empty evidence, partial telemetry/pricing and retained acquisition failure; attribution completeness remains internal.

## Observed verification and limits

- Full: 124 files / 1,504 tests; 1,503 passed, one existing zsh/PTY skip, no failures. Working-tree validator passed with four design warnings and unchanged hard budgets.
- Integrated Chromium: Classic/Web light/Web dark, 360/768/1366/1920px. Common tracks aligned per visual row; desktop daily groups shared one line, narrow groups wrapped with no document overflow. Live update retained focus, disclosure and scroll; footer removal was immediate. VM tests cover Credits/USD without acquisition.
- Real V2: one owner/two streams/three accounts; full-day 1,582 retained requests and 131 attributed initiating prompts with incomplete attribution explicitly reported. Per-category reference costs exactly reconciled with total; daily acquisition 44.461s, independent cards 7.643s. Owned workers closed and shared OpenCode remained running.
- Intermediate extended probe during source edits failed with HTTP timeout and live shutdown timeout; the later source-frozen repeat passed. Do not promote this sequence into a general shutdown diagnosis or performance guarantee.
- No model inference, external browser process, physical macOS/mobile acceptance or real clock/source mutation. Deterministic tests cover midnight/DST, omissions, hidden compaction and delayed results. No delegated exception was needed.

## FR 000547 — tables, native primary and quiet daily updates

v80.128 moves conditional guidance immediately below its table and before activity,
without a warning separator. Tables use shared panel/surface/line roles; sibling-only
rules separate cards. Outlined history expands in document flow, with no vertical cap
or internal scroll restoration. Daily-to-account spacing is Watch-scoped, 4px.

`QuotaWindow.primary` carries explicit native primary declarations. `normalize_quota`
preserves those flags and canonical account-window order in `primary_quota_label`.
Watch excludes model-only limits and no longer invents a five-hour quota from OpenAI/
Claude identity. Partial/error reconciliation retains an established slot, not its old
usage; explicit replacement native contracts win. Unavailable method switches keep
their prior invalidation behavior. Real secondary limits/reset details appear once.
The resolver is shared application input for future Mini Watch, not a Mini-only default.

The displayed prompt count is the known integer regardless of completeness, without
changing canonical attribution/cost/mix. Routine refresh is silent and does not replace
unchanged daily DOM. Loading is still used when the current scope lacks a valid value;
genuine acquisition failures retain their truthful warning.

### Verification and explicitly limited live proof

- Final Full: 126 files, 1,535 tests, no failures; one existing zsh/PTY-unavailable skip
  (1,534 passed). Validator passed, with four existing soft design-budget warnings;
  hard limits unchanged. Initial Full failures exposed documentation caps and an
  over-broad metadata retention on unavailable method switches; both were repaired,
  not waived. No ZIP, model inference, credentials/clock mutation or shared-service stop.
- Hidden Edge 156: nine Classic/light/dark × 1920/1366/360px cases passed. Natural
  five-card history, distinct surfaces, warning adjacency, 4px account gap, ellipsis,
  complete metrics/horizontal panning, focus/disclosures and sibling lines through
  reorder/removal/history transitions were measured. Three synthetic screenshots were
  inspected; no physical-input, screen-reader or macOS acceptance is claimed.
- The broad real `probe_web_live.py --watch-cards --daily` **failed** with
  `probe_daily_timeout`, then `web_shutdown_timeout` during owned-host cleanup.
  Phase timings were not retained. No root cause or performance guarantee is inferred.
- Decision Delegate directed a final-source focused check instead of a blind longer
  retry: 120s work budget plus at most 30s forced cleanup, only attempt-owned processes.
  It passed in 3.225s: three usable current native accounts; one real root/20 sampled
  current-day requests/one initiating prompt; category costs reconciled; CLI/native/Web
  primary population, model-scope exclusion, no invented five-hour/duplicate primary,
  hidden-browser primary placement/plain count/quiet refresh all passed. Assertions
  finished at 3.057s, normal resource cleanup at 3.134s; watchdog never forced termination.
  Private detached projections stayed in memory; only sanitized aggregate results retained.
- **Decision Delegate verification exception:** conditional on that focused pass,
  delivery may omit another broad full-day probe. Full real-data daily completion/
  accounting parity, loaded-host shutdown and the unreached two-stream checks remain
  unverified. This is not owner approval, a reduced implementation, a broad live PASS,
  or real-provider refresh/day-rollover proof. Deterministic cases cover those semantics;
  the focused sum is only the acquired subset, never complete daily/account history.

## FR 000554 — warning emphasis, source confirmation and history order

v80.134, 2026-11-03. `CardWorkers` previously discarded failure classifications and
`WatchCards.accept` immediately marked every failed capture unavailable. The daily
lane likewise immediately marked failure and could wait for the minute fallback.
Separately, Watch mapped any non-connected browser state to a combined source/connection
unavailable message. These are demonstrated presentation/recovery paths, not proof of
the owner's exact intermittent incident. FR 000532's fixed sixty-second SSE rotation
remains absent; no browser/host restart or new acquisition loop is introduced.

`watch/source_status.py` retains the first monotonic failure time independently per
source/card/daily lane. With valid retained data, retryable failures show neutral
retrying/not-current text for five seconds, then unavailable on the next existing
publication. Repeated failures cannot move the origin; terminal/non-retryable errors
and initial missing data bypass grace. Global source recovery keeps its existing
five-second retry. A daily error brings forward the existing single history-lane retry
to five seconds. Authoritative relevant success clears failure, not partial retained
capture, a different card, HTTP or heartbeat. Running duration freezes through retry;
retained context guidance survives transient recovery. Bounded acquisition in flight
can delay publication; the confirmation window is not an absolute network SLA.

History still chooses five most recent eligible distinct sessions before ascending
displayed-prompt start/session/prompt-ID order. Watch warnings split icon/text DOM:
approaching uses theme body foreground for text/values and the old warning-colored
triangle; exceeded keeps both warning-colored. No threshold or CLI change.

Executed Full: 127 files, zero failures. Validator: 11 passes, zero failures, six
advisory prose/design warnings; no budgets changed. Hidden Chrome passed nine
Classic/light/dark × 1920/1366/360 cases and 108 severity/theme transitions, including
clear/reappear. DOM fixtures cover collapsed updates and keyed order; Python fixtures
exercise actual source/card/daily failure/recovery owners, retained freshness and ties.
Real V2 probe: one owner/two streams/three accounts, first row 4.417s, bounded four
captures, coherent daily 1,263 requests/55 known prompts in 11.242s (attribution incomplete,
pricing complete). Owned HTTP/Live workers closed; shared OpenCode untouched; no inference.

First real-source attempt timed out during daily wait and owned shutdown while source
edits were ongoing. The stable-source repeat above passed; the first timeout's cause
was not established. Integrated browser was disconnected; hidden fresh-profile Chrome
provided rendered checks instead. No physical desktop, screen-reader, suspension,
native macOS or reproduction of the exact owner incident is claimed. No test exception
or Decision Delegate waiver was needed. Scratch evidence: `scratch:/watch-summary.json`
and nine synthetic screenshots; no runtime data or browser profile is committed.
