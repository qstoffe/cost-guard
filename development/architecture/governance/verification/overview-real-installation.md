# Overview / CLI Normal parity — FR 000531

Date: 2026-10-28. Baseline: `ad28c1e842447e6e66bb695cd6fc5cb2be552b99`
(v80.105); candidate: v80.106. Tested on the owner's Windows workstation with
the already running OpenCode Desktop/V2 service and the built-in Desktop browser.
Default Cost Guard configuration (no clone user override), existing local history
and the same cached pricing metadata were used. No model inference was requested;
OpenCode history/providers/pricing were not edited and the shared service was not stopped.

## Reproduction and boundary inventory

1. Capture `py -3 -X utf8 cost-guard.py` privately. Initial cold capture exceeded
   the harness's 180-second limit; a 600-second bounded retry completed successfully.
2. Start `py -3 -u -X utf8 cost-guard-web.py --foreground`, authorize through its
   normal one-use link and open Overview. Baseline failed with `result_too_large`.
3. Capture one canonical Normal projection using the normal Web composition.
   Render that exact projection through `ReportRenderer` (200-column plain output)
   and the application export. Compare CLI-rendered cells against actual browser
   DOM cells after loading the private capture into the shipped renderer. The
   private File input is test instrumentation, not a product API/authorization change.
4. Re-run the normal foreground host after repair. Its ordinary Overview request
   succeeds with 25 models, four columns and no hidden filter/page.

The baseline result measured **9,445,447 compact ASCII JSON bytes**, of which
**9,129,161** were unused request identities from month-wide account history.
The candidate repeat measured **316,288 bytes**, preserving **283,150 bytes** of
per-root revision evidence. The **8 MiB** transport bound was not changed. Normal
no longer enumerates detail-only causal IDs; no model/account data is truncated.
Other request kinds retain their identity behavior.

V2 source selection, Normal request kind, default config, selectable catalog,
independent samples, pricing, report projection and DTO model membership were
checked. CLI exposed **25, not more than 50**, reference models. There was no
evidence of an upstream missing-model row in this capture. The general table's
50-row slice was a separate proven rendering defect for larger lists. The 8 MiB
rejection occurred before rendering; labeling it a pagination-only regression
would have missed the actual installation failure.

## CLI section/line → Overview matrix

| CLI Normal information | Overview location / observed proof |
| --- | --- |
| Version/source header | Product revision recorded above; snapshot identifies V2/source status. Browser branding is intentionally not an ANSI header copy. |
| CCost equivalence, flat-rate reference valuation, unlabeled-cost meaning | CCost card and its About disclosure; reference value is explicitly not billing. |
| Token Mix definition, latest priced-prompt count and token volume | Token Mix card and About disclosure, sample line and per-category labeled cells. |
| Input/Cache/Write/Output percentages **and category CCost** | Four server-owned tokens; all four matched the frozen CLI projection. Output/reasoning distinction remains in help. |
| Relative CCost own-model/publisher/generic-prior explanation, evidence weights, cheapest base, tiers/boundaries | Relative CCost card/help and model evidence disclosure. Fallback explicitly leaves relative cells blank. |
| Pricing/cache timestamp | Metadata line directly before the table; same source timestamp. |
| Publisher / Model / Relative CCost / Release date | **25/25 ordered rows**, **100/100 CLI-rendered cells** matched after whitespace alignment normalization; zero mismatches. No recent/older suffix is injected into Overview model identity. |
| Promotion markers/terms and New Models notice | Same model-cell marker, promotion-colored text and highlighted notice after table, before accounts. All exported notices matched. |
| Accounts Overview labels, Today/month/native-window CCost | Account cards on Overview itself; all exported scope display tokens matched. No Models/Accounts navigation required. |
| Native remaining %, bars, native values/money, reset wording, Pace | Shared detailed account cards now used on Overview; native-money and configured-timezone relative reset tokens matched. Unknown/zero/unlimited/blocked/stale remain distinct. |
| Bills, Copilot Unaccounted usage, attribution/partial/source warnings | Cards and final notes, not omitted or hidden in another route. Raw provider reasons/transport warning text remain excluded by the existing privacy allowlist; safe classified status is shown instead. |
| Final notes | Visible final paragraphs, exact exported note text. No final notes occurred in the real capture; synthetic notes cover this case. |

Independent CLI/Web acquisitions happened while this coding session added history,
so sample-derived ratios and quota/reset observations can legitimately move. They
are **not** claimed numerically identical across acquisition times. Exact display
equality above uses one frozen canonical report, not a temporal-difference waiver.
No CLI report logic or pricing/selection was changed to make the comparison pass.

## Rendered DOM, interaction and visual checks

- Real built-in Chromium DOM: synthetic **0, 1, 49, 50, 51, 123** model cases
  retained all ordered publisher/model identities with no Previous/Next controls,
  including a stale nonzero page state and duplicate model names across publishers.
  These are supplemental boundary cases, **not** a claim the installation had 123 models.
- Real ordinary Overview: custom sort is labeled, CLI default-order restoration
  restores exact order; explicit publisher filtering is conspicuous and Clear model
  filter restores all 25 rows. Canonical totals never change.
- Desktop screenshot inspected locally: readable four-column hierarchy, aligned
  numeric tiers, promotion marker, muted older variants, recent release and notices.
  No private screenshot/account/history payload is published.
- Real 360px browser iframe/subviewport (actual inner width 356px), using shipped
  CSS and the same frozen real-source report: narrow media query active, 25 DOM
  rows/four columns, no body-wide horizontal overflow. Local table width 270px,
  scroll width 635px; horizontal and vertical scrolling reached the final row.
  This is actual Chromium narrow-viewport layout, **not physical outer-window resizing**.
- Final ordinary Overview: a host-status callback retained the exact table node,
  scroll offset 200, keyboard focus and selection. End/PageDown and mouse-wheel
  navigation were exercised; wheel reached the table's bottom (~325px). Before
  the fix, status-triggered whole-report replacement lost the table/focus/scroll.

## Regression checks and limits

`development/tools/run_tests.py --suite full`: **114 files passed**, zero failures
(52.9s). Initial run failed only file-budget validation because private capture
files were in the source root and release docs exceeded caps. Captures were moved
to ignored diagnostics; old FR-only version-history entries were consolidated
without dropping their facts. Caps/assertions were not raised or weakened.

Deterministic tests cover complete DOM membership/order and reversible presentation,
0/1/49/50/51/123 models, duplicate names, tier transitions, promotions, no priced
sample, null/unknown sorting, availability fallback, notes, account states and
heartbeat-retained DOM. The Normal regression forbids causal identity enumeration
while requiring source revisions and model rows. Session/detail behavior stays tested.

Physical outer-window resizing, assistive technology, native macOS and unrelated
Sessions/history scrolling are not verified by this evidence. No new dependency,
model call, permanent release gate, ZIP or automatic launcher refresh was added.
