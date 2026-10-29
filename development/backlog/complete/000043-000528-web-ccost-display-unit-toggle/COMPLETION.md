# Completion — FR 000528

Implemented in v80.112 (2026-10-29), from base
`614d553a16e997216583c7b10c9b1da0a9e380fc`.

- Shared accessible CCost Credits/USD selector; configuration is the fresh-page default.
  Page-memory only across routes, retained reports, Watch and Snapshot/Live; reload resets.
- Python prepares both displays from the same facts. JavaScript selects tokens and
  updates bound text, without repricing, report jobs, source/provider requests or storage.
- Includes context/breakdown/footer, historical mix, date-range and provider-only account
  CCost amounts. Native quotas, Billed, Unaccounted usage, rates and Relative CCost unchanged.
- Regression tests compare CLI-derived tokens, raw ordering, unknown/partial markers,
  immutable DOM/report identity and acquisition counts. Full suite: 116 files passed.
  Working-tree product validation passed with existing advisory design-budget warnings.
- Real-installation V2 Live/detail/reports/cancellation probe passed and closed only its
  own workers. Integrated-browser synthetic checks covered all report renderers, Watch,
  detail, narrow layout, keyboard, selection and offline retained state.

[Evidence and explicit proof limits](../../../architecture/governance/verification/web-ccost-toggle.md).
No physical screen-reader/macOS or prolonged real-browser source/SSE soak is claimed.
Architecture boundaries unchanged; Web owner facts updated. Journal assessment: no-update.
No new reusable cross-repository suggestion. Original FR bytes retained; no attachments.
