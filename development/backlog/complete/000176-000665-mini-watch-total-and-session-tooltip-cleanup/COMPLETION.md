# FR 000665 completion — Mini Watch Total and Session help

Implemented as v81.15, 2026-11-10, against main `b22cfc98fa123ac50d4a201bb92eafe8c6c236d7`.

- Total is plain selectable text with its existing factual accessible label, no
  tooltip or interactive binding. Dead prompt-specific Total help is removed.
  Its keyboard/hover/touch heading help is exactly the requested sentence.
- Mini Total uses the existing server-formatted, unit-correct `account_ccost`
  known subtotal token. Partial pricing is not displayed with `?` here only;
  wholly unpriced N/A, pending Loading, genuine zero, raw canonical costs and
  completeness retain their meanings. No backend/financial-formatting change.
- Session help keeps the full title/stable-ID fallback and direct prompt identity
  plus the existing 25-grapheme preview, with explicit missing-number/preview cases.
  CCost help/Duration behavior, Activity/Ctx, subscriptions and Full Watch are unchanged.
- Updated focused tests, Mini guide, current version/history, help/code-map facts
  and journal. The original specification and historical FR000654 are preserved.
  Merged progress advances ordinaryCount 114 → 115 for fr/000665; maintenance
  completion/deferred records are unchanged.

## Verification

- Local Full: 181 bounded groups, 2,243 tests passed, two existing macOS-only
  zsh/PTY skips, zero failures (133.1 s). Focused Mini: 12 tests passed.
- Package validation: 11 passes, zero failures; seven existing advisory warnings.
- Owned headless Edge 157: full real Document PiP probe, 127 layouts, including
  themes, light/dark, units, narrow widths, SSE/lifecycle, keyboard/hover/touch,
  selection, exact header/no Total help and unchanged CCost running Duration.
- Owned headless Chrome 156: targeted complete help/source-context/Duration matrix
  passed at 125% zoom/DPR 1.5 with overlay-scrollbar configuration.
- Read-only installed V2: 36 coherent publications, one running row, three
  accounts; acquisition closed cleanly without stopping shared OpenCode.

The integrated browser was disconnected. Headless Document PiP is real browser
evidence, not physical desktop/macOS/screen-reader proof. No real historical cards
were observed; synthetic coverage supplies those transitions. No paid inference,
acceptance exceptions, deferred FR scope, ZIP or release publication.

Fixture failures and their causal repairs, retained screenshot and detailed
evidence/limits: [Mini Watch journal](../../../journal/web/mini-watch.md#quiet-total-and-direct-session-help-fr000665).
