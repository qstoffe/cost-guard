# FR 000547 — completion

Implemented in v80.128, 2026-11-02. The specification and entire task bundle are
preserved intact; completion ordinal 000060 follows the current highest 000059.

## Result

- Theme-aware one-row table body/header surfaces and edges in Classic/Web light/dark;
  no framed active parent cards, wrapping rows, filters or paging.
- Conditional context guidance immediately follows the table, before active activity,
  without its own separator/panel/empty space. Canonical severity/threshold/model-price
  and compaction semantics remain unchanged. Sibling-only lines separate both lists.
- Outlined five-session history grows naturally in page flow; no height cap, nested
  vertical scrolling or history scroll restoration. Individual tables still pan horizontally.
- Watch-scoped daily-to-subscription gap measures 4 CSS pixels; subscription detail
  dividers/common tracks and card gaps remain.
- Explicit native primary flags and canonical account-window order normalize into the
  shared primary label. Weekly-only OpenAI uses Weekly, without a fabricated five-hour
  slot or duplicate secondary. Model-specific limits cannot become account primary.
  Established primary slots survive partial/error omissions without restoring old usage;
  unavailable sign-in-method changes keep their existing invalidation behavior.
- Total Today shows plain integer prompt counts without changing internal completeness,
  causal accounting or unattributed usage. Routine refresh retains valid values silently
  and skips state-only DOM replacement; initial loading and genuine failures remain distinct.
- One-row/five-session and terminal-lifecycle behavior retained. Mini Watch itself is not
  implemented here; its future shared primary input is corrected, without a second default.
- Updated Web help, README/version history/runtime version, Watch module facts and
  `development/journal/web/watch-summary.md`; no architecture boundary redesign.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: final 126/126 files passed;
  1,535 tests, 1,534 passed and one existing zsh/PTY-unavailable skip. Initial failures
  (documentation hard caps and unavailable-method metadata parity) were causally repaired,
  then the full suite rerun; no deterministic-test waiver.
- `py -3 development/tools/validate_package.py --working-tree`: passed. Four existing
  soft design warnings; no hard-limit raises or ZIP generation.
- `probe_watch_cards.cjs`: hidden Edge 156, nine Classic/light/dark × 1920/1366/360px
  cases passed. Measured surfaces, warning adjacency/wrapping, sibling lines including
  reorder/removal/history transitions, natural five-card height, 4px daily gap, ellipsis,
  complete metric widths, horizontal overflow, focus/disclosure stability and 100-card
  scaling. Three synthetic screenshots inspected. Evidence retained in worker-owned
  `scratch:/watch-visual/`; no physical input, screen-reader or native macOS proof.
- Native weekly `primary_window`/Pro Lite display fixture, five-hour+weekly, reordered
  explicit primaries, model-only limits and explicit missing-primary recovery covered.
  CLI/Web quota population and duplicate secondary behavior checked. DOM regression
  covers complete/incomplete **181 prompts**, repeated silent refresh preserving nodes,
  replacement **182 prompts**, truthful failure and fresh-scope loading without fake zero.
  Existing accounting, compaction, midnight/DST/delayed-result tests remain passing.
- The broad real-installation `probe_web_live.py --watch-cards --daily` **failed**:
  `probe_daily_timeout`, followed by `web_shutdown_timeout` during owned-host cleanup.
  It did not establish broad live success; phase timings were not retained.
- Decision Delegate directed a final-source bounded focused check (120s work plus at
  most 30s cleanup, only attempt-owned processes). It passed in 3.225s: three usable
  native accounts, one real source root/20 sampled current-day requests/one initiating
  prompt; category costs reconciled only for that subset. Common/CLI/Web native-primary
  agreement, model-scope exclusion, no invented five-hour/duplicate primary, hidden
  browser placement/plain count/quiet refresh passed. Assertions completed at 3.057s,
  normal cleanup at 3.134s; no forced watchdog termination. Private projections remained
  in memory. Reproducible attempt scripts: `scratch:/focused_watch_probe.py` and
  `scratch:/focused_watch_browser.cjs` (not a new product gate).

## Explicit verification exception and remaining uncertainty

**Decision-maker: Decision Delegate**, not the owner. Conditional on the focused live
pass above, it authorized completion without repeating the broad full-day probe. Reason:
the changed code adds no history acquisition/scheduling/shutdown work; final deterministic,
rendered layout and targeted real native/source evidence adequately cover this FR.

Full real-data daily completion/accounting parity, loaded-host shutdown and the unreached
two-stream checks remain **unverified**. The two broad-probe failures remain failures;
their cause is not established as either causal or unrelated to this change. No general
performance guarantee, complete real daily/account sum, real-provider refresh/day-rollover
proof, or broad live PASS is claimed. This exception changes verification scope only,
not the requested implementation. No model inference, credentials/clock/source mutation,
visible desktop action or shared OpenCode service stop occurred.
