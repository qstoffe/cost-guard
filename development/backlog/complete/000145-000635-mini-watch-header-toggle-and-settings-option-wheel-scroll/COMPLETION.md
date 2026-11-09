# FR000635 completion — v80.214, 2026-11-09

Implemented the coordinated responsive Mini header, stable-label outlined/filled
Earlier Sessions toggle, atomic pressed/disclosure/demand state and corresponding
inert fit measurements. Preserved browser-owned sizing, bounded user-activated
height adjustment, passive-update stability, global Today values and shared history.

Settings retains native customizable select/options/selectedcontent. A scoped passive
wheel handler scrolls the associated visible overflowing help from its option;
native sibling help panes retain preview while allowing direct scrolling without
option activation. No custom combobox, global wheel listener, source/accounting
change, dependency, extra stream, background resize or save-on-preview was introduced.

## Verification

- Full deterministic suite: **175 files, zero failures**, 151.1 seconds.
- Working-tree validator: **11 passes, zero failures**, seven advisory size warnings.
- Chrome156 full Settings: PASS, including real wheel selected/unselected/Default,
  substantial synthetic overflow, reversal/end/boundaries, direct wheel/native drag,
  unchanged preview/value/write count, native keyboard/AX/save/rollback/fallback,
  themes, 360/520/1280 widths, touch and CSS/actual browser200% zoom.
- Chrome156 and Edge157 normal full Mini lifecycle: PASS. Chrome actual width matrices
  at125/150/200% with differing device scale/fonts/themes/units: PASS. Focused compounded
  zoom200%/DPR2: PASS in both sizing modes, trusted disclosure/screenshots, actual clamps,
  height-only requests, no passive resize and scrolling to Earlier/active/accounts.
- Hidden-opener/visible-PiP authenticated history demand: PASS for Enter/Space,
  expand/collapse/close/reopen and one EventSource.
- Real V2 daily and SSE component assertions succeeded: complete prompt count/cost,
  category reconciliation, quiet unit parity, preserved owner/run origin and sequence.
  **The command FAILED at teardown**, not a full probe PASS; see exceptions below.

## Decision-Delegate-approved scoped exceptions and remaining uncertainty

Decision Delegate explicitly approved delivery with these limits after distinct
investigations; these are **not owner approvals** or silently passed requirements:

1. **Edge native scrollbar drag remains FAIL** in the owned hidden environment,
   even after clearing viewport emulation; manual Edge dragging is unverified and
   potentially affected. All other Edge Settings interaction/layout checks passed
   in an explicitly **PARTIAL** continuation. Chrome's successful actual drag is
   complementary, not equivalent Edge proof. No further gesture/UI workaround required.
2. Real `--daily` assertions succeeded, but exit1 reported one quota HTTP daemon
   remaining in SSL read. Main Live/HTTP workers closed, owned processes0, cleanup
   failures[]; clean shutdown/eventual provider completion remains unverified. The
   documented account close contract permits in-flight HTTP after a0.2-second budget.
   Further teardown investigation is deferred for this frontend delivery.
3. Successful full-real Earlier-history proof remains unperformed: a90-second
   `--watch-cards --daily` trial timed out after615/2996 roots/connection_timeout
   before daily assertions. The independent daily-only proof supplied the missing
   real daily/SSE evidence; no repeat cold scan/backend expansion required.
4. A prior version-edit/SourceGuard trial and the old full compounded-scale probe
   were unsuccessful, not PASS. The latter assumed width stability/no scrolling
   despite browser native clamps. Strict normal lifecycle plus both-mode focused
   clamp evidence is accepted; physical desktop/OS/screen-reader proof remains unknown.

The in-app browser was disconnected; all rendered checks used owned strictly
headless profiles, never personal windows or shared OS input. No shared OpenCode
service was stopped and no inference/source mutation occurred.

## Documentation and delivery

Updated `docs/web-mini-watch.md`, Settings in `docs/web-beta.md`, version/date/current
README/history, Web architecture and code-map navigation. Causal evidence and
exceptions are in `development/journal/web/header-picker.md`; exact local artifacts
are retained in the worker session's own scratch. No packaging/tag/GitHub Release.

The original specification/bundle was moved intact to Complete ordinal000145;
permanent identity remains000635. The delivery includes selected maintenance progress
ordinaryCount84/lastOrdinaryId fr/000635, effective only after merge to actual main.
