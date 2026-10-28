# Web CCost display selector verification

Date: 2026-10-29. Base: `614d553a16e997216583c7b10c9b1da0a9e380fc`.
Scope: FR 000528, v80.112. Windows workstation, Python 3.14, Node VM and
OpenCode integrated Chromium. No inference, external browser process or shared-service stop.

## Implementation and reproducible checks

- `src/application/display.py` prepares sparse credit/USD differences from the same
  immutable records using existing Python numeric formatting. Native values and raw
  sorting keys are untouched. Structured range/provider-only note costs avoid parsing
  formatted strings or valuing money in JavaScript.
- `render.js` retains weak text bindings; unit selection updates text nodes, preserving
  DOM identities, selection endpoints, scroll containers, sort/filter/page state and
  report identity. Watch/session presenters bind retained summaries and context too.
- `test_web_display.py` cross-compares both prepared modes against independent
  configured exports for every report scope and Watch; covers partial/unknown/sparse
  and native values. CLI goldens remain in `test_ccost_display_unit.py`.
- `web_views.cjs`, `web_remaining.cjs` and `web_live.cjs` cover reversible switching,
  DOM/order retention, historical category/footer amounts, live publication and no
  extra acquisition. `test_account_period_ccost.py` covers structured provider-only costs.
- Commands: `py -3 development/tools/run_tests.py --suite full` and
  `py -3 development/tools/validate_package.py --working-tree`.
- Final runs: all 116 test files passed (51.6s); validator passed 11 checks with four
  existing advisory design-budget warnings. Earlier failures exposed a missing quota
  token lookup, a raw-Decimal fixture expectation and release prose exceeding hard
  document caps. Repaired the lookup/expectation and condensed prose without raising
  caps or weakening assertions. No unresolved required test failure remains.

## Integrated-browser observations

Served the shipped assets with `development/tests/integration/serve_web_remaining.py`;
synthetic fixed reports/HTTP transport, not real provider accounts or a production host.

- Credits→USD→credits matched fresh rendering exactly for Overview, Models, Accounts,
  all-models, Sessions, Session, Date/Range and Token Mix. Tables/rows retained identity.
- A Sessions cell changed `3`→`$0.02` reversibly without an additional acquisition.
  A text-node selection retained its node/endpoints and selected the updated amount.
- Watch matched a fresh USD render and stayed USD after another publication; switching
  back restored exact text with the same rows. This publication test uses synthetic
  retained data, not real-source browser SSE.
- Session detail retained its table/rows and selected CCost text across switches.
  Snapshot→Live kept `Whole session: 120 rows · CCost $0.02 · Billed $1.20 · Duration 37s`.
- Actual browser Back/Forward between cached Sessions and detail retained USD in the
  selector and amounts (`$0.02` in the Sessions CCost cell and detail total).
- A 360px iframe viewport kept the native labeled selector within its bounds. Keyboard
  End/Enter selected USD; focus remained on the control. Accessible description explains
  reference valuation and reload behavior; physical screen-reader output is untested.
- Simulated offline host state retained the table and allowed switching while Refresh
  was disabled; no acquisition occurred. This is a client-state fault, not network outage proof.
- Browser localStorage/sessionStorage remained empty and the synthetic fixture had no
  settings cookies. Reload restored configured credits. URL retained only its ordinary route.

## Real-installation read-only probe

`py -3 development/tests/integration/probe_web_live.py --detail --reports` passed on V2:
one acquisition owner, two streams, five retained rows, three accounts, advancing sequence
and preserved run origin. Detail froze consistently (three rows). Normal, all-models,
sessions and date completed; deep history cancelled. Owned Live/HTTP workers closed;
shared OpenCode remained running. Normal took 106.071s and date 20.105s in this run;
no performance improvement is claimed. This CLI/HTTP probe is not real-data browser proof.

## Limits and knowledge assessment

No physical screen-reader, macOS, prolonged real-browser SSE/outage soak or new native
launcher acceptance is claimed. Existing transport/history tests remain relevant.
No architecture-boundary change; updated the Web module owner facts. Journal no-update:
the focused durable evidence and owner contract suffice; no separate reusable discovery.
No cross-repository suggestion publication was needed.
