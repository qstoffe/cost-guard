# Remaining Web Beta presentation — owner review matrix

Date: 2026-10-28. Candidate: v80.100 / FR 000510, based on default
`8b4b779841e7695849bea68448a3f8d468ac62eb`.
Scope: Beta acceptance evidence, not a permanent release gate, design approval by
the owner, native-platform certification or a replacement for cross-platform CI.

## Reproduction and evidence

- `py -3 development/tools/run_tests.py --suite full`: 113 isolated files, 1,373
  passing tests, zero failures/skips (43.8 seconds; [receipt](remaining-web/full-tests.json)). This includes the newly registered remaining-view file,
  existing 100/1,000/10,000-row detail tests, HTTP/authentication, source ownership,
  stale/terminal states, date/DST and CLI/report regressions.
- `py -3 development/tools/validate_package.py --working-tree`: zero failures;
  four design-budget warnings (README and existing analysis/report/Watch owners).
- `fixtures/remaining_views.py` builds a real canonical 120-prompt report from
  `SyntheticMonthSource`, with one running prompt, the fixed clock
  `1793052000000` and `Europe/Stockholm`. The same report feeds CLI and Web.
  `test_web_remaining.py` compares CLI mix cells for complete, partial, unknown
  and empty telemetry/pricing. DOM checks pin columns, total placement, clocks,
  context guidance, links and bounded rows. Raw Decimal sort keys stay separate.
- With explicit user approval, OpenCode's built-in Chromium browser opened
  `integration/serve_web_remaining.py`. It serves shipped HTML/CSS/JS and synthetic
  HTTP/jobs/detail/stream fixtures; there are no real provider or source calls.
  Navigation and interaction used the shipped app. A 360-CSS-pixel iframe checked
  actual narrow-viewport CSS; this is not touch-device emulation.
- [Overview capture](remaining-web/overview.jpeg) and
  [historical Token Mix capture](remaining-web/token-mix.jpeg) were visually
  inspected. They contain synthetic data only. Other routes were inspected in
  the real browser DOM; intermittent hidden Review-pane capture failures are not
  screenshot evidence. The Token Mix total is above its table; its rightmost
  column is reachable by the table's horizontal scroll region, not page overflow.
  The Overview capture precedes the final nullable-unit/window text correction;
  final shared tokens are covered by the suite and narrow DOM inspection.
- A read-only Diagnostics snapshot check for the ordinary installation returned
  `not_observed`, no snapshot or lifecycle codes. It proves neither a running
  installation nor installed-history parity. No live provider check or model
  inference was performed; the shared OpenCode service was untouched.

## Owner-facing matrix

Screenshot privacy/integrity review: both images were inspected and contain only
synthetic fixtures, local UI timestamps and loopback-app content, not credentials,
personal sessions, account identities or user paths. Reviewed SHA-256:

| Evidence | SHA-256 |
| --- | --- |
| `overview.jpeg` | `8996328370ec2fd257ba116f6d1377f44f64dd1adafcd8ff4e4ab2221d38c86c` |
| `token-mix.jpeg` | `ac172928b49bca0c02529a3798e5f7fe04a8d007705bb1a207ef00d67be9107d` |

| View | Deterministic evidence | Built-in browser inspection on Windows | Intentional browser presentation differences |
| --- | --- | --- | --- |
| Overview | Existing CLI/DOM concept, model order, accounts and notices checks | Cards, model tiers and account warnings inspected; capture above; 360px no page overflow | Concept cards, expandable observations and scrollable tables instead of terminal prose |
| Watch | Existing canonical CLI/live projection, ordering, totals, retention and terminal tests | Single table, context warning, canonical columns and detail navigation; 360px no page overflow | Persistent table and contextual details; retained-row subtotals are not full-session totals |
| Sessions | Existing revision-bound 50-root order/scope/Back/empty tests | Sessions to complete detail; 120 prompts and whole-session duration/cost displayed; 360px no page overflow | ID/name and lifecycle labels share one cell; page-only filters/sorts are explicit |
| Models | Existing exact/default ranking, tiers, promotion and native-price tests | Selectable table/tiers, complete long names and default-order control; 360px no page overflow | Wrapped names and horizontal table scrolling; exact reference prices remain exact |
| Accounts | Existing same-CLI native quota, reset, Pace and private-field tests | Known, blocked, unlimited, unavailable, partial, stale, rate-limited cards; 360px no page overflow | Cards, known-only progress and optional source detail; no quota inferred from unknown values |
| Date/Range | New same-report prompt/total/context checks; existing inclusive/DST/error tests | Real date form submitted 2026-10-26 through 2026-10-27; configured zone/date labels, 50 visible rows, full selected-range footer and full-detail links; 360px no page overflow | Context help above table; browser Back retains the frozen range; raw epoch boundaries removed |
| Token Mix | New same-CLI Input/Cache/Write/Output share-and-cost cells and model aggregate CCost; partial/unknown/empty cases | Navigation admitted zero history jobs. Explicit capture showed `history 12/120`; Cancel marked that fixture job cancelled. A second explicitly admitted job was completed through the fixture endpoint; table/total inspected and captured | Optional sample/price coverage and filters; no automatic historical scan; canonical full-report total above table |
| Session Snapshot | Existing full-history/page/retention parity; new formatted-summary/context/action assertions | First/middle/latest: 1–50, 51–100 and 71–120 of 120, always 50 DOM rows; CCost 3, Calls 120, Duration 37s stayed whole-session. Snapshot running row explicitly provisional | Freeze/Follow controls, Go to row, All sessions link and optional source guide; same eight metric columns and footer |
| Session Live | Existing revision-aware anchor/selection/focus/outage tests; mode-aware labels tested | Follow live showed `Running · provisional`; selected row/cell identity survived reload, controls retained focus. 360px latest-page inspection confirmed local table scrolling and no page overflow | User-controlled follow-latest; source state/provenance folded away while actual warnings remain visible |

## Limits and follow-up

- These checks establish the exercised content and interactions, not that every
  visual arrangement is attractive. No physical input, screen-reader, dark-theme
  visual or native macOS review was performed in this task. Historical platform
  evidence is not relabeled as current acceptance.
- Browser fixture streaming/authentication is synthetic. Production authentication,
  no-navigation-acquisition, real SSE ordering, independent source ownership and
  terminal/offline retention are covered by the existing deterministic/HTTP tests,
  not by a claim of installed-provider browser integration here.
- Partial/empty/missing/retained lifecycle combinations have deterministic coverage;
  they were not all individually captured as real-browser screenshots. Exact
  terminal percentile coloring is not asserted as a pixel match: browser semantic
  status/warning text remains primary, with supplemental shared role colors.
- No change to historical analysis, history retention, account acquisition,
  lifecycle/security ownership or browser persistence. `localStorage` and
  `sessionStorage` both remained empty during the browser run.
- Journal assessment: **no-update**. The current Web owner/CODE_MAP and this focused
  evidence contain the reusable facts; no new architecture boundary was introduced.
