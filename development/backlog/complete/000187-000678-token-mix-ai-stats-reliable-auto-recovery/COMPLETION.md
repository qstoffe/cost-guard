# Completion — FR 000678

Implemented 2026-11-11 in v81.26.

## Result

- Reproduced both historical report failures on the healthy local V2 source:
  newly encoded unresolved opaque Claude Agent facts rejected their own identity
  semantics. The encoder now uses the decoder's admission predicate; affected
  old derived facts rebuild lazily without weakening validation or changing history.
- AI Stats no longer manufactures ten zero cards on failure. Genuine valid
  empty/best-effort values remain; matching last-good periods survive incomplete
  refreshes and errors. Token Mix retains its valid totals/tables and DOM state.
- Existing host backoff handles worker interruption, cache BUSY/unavailable
  checkpoints and typed model-catalog churn. Healthy Live events no longer starve
  the publication lookup timer. Source-access recovery remains distinct from
  report failure; genuine typed blockers do not hot-loop.
- Neither report has Retry/Refresh controls or a redundant toolbar, including
  cold-error states. Models/Comparisons and independent Sessions controls retain
  their separate behavior. No new scheduler, cache authority or valuation engine.

## Verification

- Final stable-source Full passed all 184 groups in 142.2s: 2,287 passed tests,
  no failures/errors and two explicit native-macOS/zsh-only skips (2,289 total).
- Causal tests failed before the relevant identity, catalog-turnover and timer
  fixes; focused checks passed afterward. Coverage includes 3,217 synthetic roots /
  6,434 requests, selective corruption/repair, real SQLite writer lock/release,
  interrupted workers, source readiness, scope retention and bounded recovery.
- Real read-only Token Mix cold/warm acquisition passed over 3,121 roots with
  positive tokens, 14 model rows and three publisher rows: 124.086s cold / 6.112s
  warm, with 3,099 compact hits and 22 changing-root rechecks on warm acquisition.
- Real AI Stats cold/warm acquisition returned all five scopes and passed rate
  formula/display checks. The real-host hidden-browser probe independently showed
  positive total cost in all five scopes and valid Token Mix tables, retained
  provenance/DOM through injected browser faults, and automatic recovery.
- Hidden Chromium synthetic probes passed four widths (360/800/1280/1920), three
  themes, Credits/USD, exact sorts, pan/scroll/focus, keyboard/emulated touch/help,
  AX names, contrast/layout, genuine empty versus failed acquisition, and finite
  Stats slices/two-tab reuse with clean owned-process shutdown.
- Working-tree validation passed all 11 checks, with zero failures and seven
  pre-existing advisory size warnings. No cap/debt rebaseline or new dependency.

Detailed causes, repaired verification failures, final Full outcomes, timings,
artifact references and limits: [journal](../../../journal/web/historical-recovery.md).
The entire original FR body is preserved. No acceptance exception was requested.

## Limits

Live history is changing; observed counts/timings are not an independent complete
history or billing oracle. Controlled browser transport failures are synthetic,
not an observed source outage. Partial/unpriced/unknown evidence stays qualified.
No source writes/deletion, model inference, shared OpenCode restart, user-setting
change, visible desktop interaction, physical screen-reader/device acceptance,
non-Chromium or new native macOS proof is claimed. No ZIP, tag or Release is made.
