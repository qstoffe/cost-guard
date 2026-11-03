# FR 000556 — Fix misleading Web Watch quota summary: show native Used / Total separately from period CCost

## Owner report and decision

**Owner-approved executable fix FR, 2026-11-03.** Permanent identity: **000556**. Ready priority **000060**, after the existing FR000555 at 000050.

In Cost Guard **v80.134**, the owner compared the same GitHub Copilot Business subscription in Web Watch and CLI Watch:

- **Web Watch:** `Monthly · 8.4% used (1814)`.
- **CLI Watch:** `Month · 8% used · 2088/25000` AI credits.
- The parenthesized web amount is **274 lower** than the CLI Used amount. Numerically, 2,088 / 25,000 is about 8.4%, while 1,814 / 25,000 is about 7.3%.

**Root cause established by source inspection:** these are *different metrics*, misleadingly placed together. The percentage is **provider-native quota Used**, the CLI fraction is **provider-native Used / Total**, and Web Watch's parenthesized **1,814 is OpenCode-observed/reference-valued CCost for the quota's period**. The two numbers do not have to match. The screenshot alone does **not** establish a calculation, period-history or GitHub quota-reading defect. Provider usage can differ from observed local CCost for legitimate scope, attribution, coverage, pricing, or reporting reasons. Do not paper over the difference by changing an amount to make it agree with the percentage.

**Owner-requested correction:** the primary Web Watch quota summary must make native Used as directly comparable to CLI as the percentage, and explicitly label the independent period CCost rather than silently putting it in parentheses after `% used`. Apply the same semantics to secondary quota windows.

This **supersedes only FR000552's ambiguous inline presentation** `<period> · <N>% used (<period CCost>)`; preserve FR000552's actual period-CCost feature, native-month acquisition, reset/pace placement, title band and account-card design. FR000525's provider-native Used/Total contract and FR000549's actual-period CCost accounting remain authoritative.

## Confirmed implementation trail

Inspected `main` at **`8a1940290bcc040b2f88df364b943527100e4ffb`** (v80.134):

- `src/web/assets/watch.js::quotaTrack` renders `value.used_percent + ' used'` and unlabelled parentheses from `value.cost`; its bar uses `value.used_fraction`.
- `src/application/watch_accounts.py::watch_quota` obtains the percentage from `quota_usage` (native quota) but exports `cost=comparison(period.cost)` (observed period CCost); the slim `quota` record **omits native `used`, `limit`, `unit`**, even though the domain already knows them.
- `src/accounts/github_copilot.py` reads the native Copilot `credits_used` / `creditsUsed` and total/entitlement. `src/presentation/accounts.py::quota_parts` renders the same native Used/Total in CLI. `src/application/projection.py::account` already exports native fields for the normal Web Accounts page.
- `src/analysis/period_ccost.py` and `src/reports/accounts.py::_period_scopes` independently compute observed canonical account/window CCost from period-aligned request history. It is *not* native quota consumption. Existing period-state and incompleteness safeguards must remain unchanged.

No private live-account payload or local Web process was inspected. Source evidence explains the semantic discrepancy; the exact reason that these two independent numbers differ by 274 in the owner's environment has **not** been established.

## Required behavior

### 1. Native quota Used must be visible, explicit and comparable

- In each **Web Watch** account card, for both primary and secondary quotas, show a clear **provider-native Used / Total** value (and the real native unit where meaningful) alongside the *same quota/window/scope's* Used percentage and progress bar. A concise format is acceptable, for example:

  `Monthly · 8.4% used · 2088/25000 AI credits`

  followed by the existing progress bar. An equally clear compact layout may put `2088/25000` in parentheses, **provided that the parentheses do not contain an unlabelled CCost amount**.
- For the supplied reproducible fixture, the native percentage/bar must correspond to 2,088/25,000, independently of period CCost being 1,814. Web's 8.4% precision vs CLI's rounded 8% is allowed; do not force identical presentation precision if that reduces clarity.
- Obtain the native quantity and denominator from **the same canonical provider quota observation** used for the percentage. Extend/reuse the typed Python Watch projection as needed; **do not infer native Used by multiplying the displayed percentage by a limit in JavaScript**, derive it from local CCost, or join different accounts/windows by text label. Exact native remaining/total arithmetic is acceptable only when already supported by the trusted shared quota semantics.
- Preserve accurate formatting and any honest native-unit suffix; do not convert provider-native AI-credit usage when the user selects CCost USD display.

### 2. Keep period CCost, but unmistakably label its independent meaning

- Retain the actual **account- and quota-window-specific observed CCost** added in FR000552. Give it a **visibly explicit `CCost` label**, e.g. `CCost Monthly: 1814` on its own concise line or `· CCost: 1814` where it fits. It must be visually distinct from the provider-native Used / Total and never masquerade as the count in `% used (...)`.
- Keep `CCost Today` as a **separate local-day value** above the primary quota, not as the replacement for period CCost. Preserve the existing Credits/USD toggle for *CCost values only*, including appropriate known/partial/estimated/unavailable provenance without inventing completeness.
- If a period's CCost is unknown, show a truthful absent/unavailable value; a known native percentage must not turn unknown CCost into zero. If native quota Used is unknown but period CCost is known, show the latter without inventing native Used or a finite percentage.
- Do not introduce a derived difference, `unaccounted` estimate, error status, reconciliation formula or claim of provider undercount based solely on native Used minus CCost. Such a residual requires the existing independent completeness/attribution checks.

### 3. Preserve UI, lifecycle and correctness boundaries

- Preserve the complete primary section (title, CCost Today, native quota summary, progress bar, reset and Remaining/day/workday), optional secondary section and conditional divider. Maintain aligned card tracks, responsive wrapping and unobstructed narrow layouts in Classic, light and dark themes. Keep the new period-CCost label short and avoid excessive duplicated unit/explanation prose.
- Retain actual provider status, stale/partial/outage handling, first-party quota reset and native period identity, stable primary selection, separate secondary/model-scoped quotas, true Unlimited behavior, correct exhaustion colors, near-100% precision and no fabricated denominator. A provider-confirmed Unlimited may show known native Used without `/Total`, percentage or finite progress bar.
- Do not change native provider parsing, CCost valuation, account attribution, period boundaries/history, quota polling, API auth, the global Today total, Mini Watch, CLI/Normal or the separate Web Accounts screen just to make the two values equal. If a deeper genuine defect is *independently* reproduced, document its evidence and scope rather than silently broadening this presentation FR.
- Prefer the existing common quota formatting/projection contracts and no additional polling/history rescan or synchronous wait for Web Watch rendering.

## Acceptance and verification

1. **Exact owner reproduction fixture:** Copilot Business native `used=2088`, `limit=25000`, period CCost `1814`: Web Watch shows approximately **8.4% used**, the correct progress fill and explicit **2088/25000 AI credits**, plus independently labeled **CCost 1814**. The number **1814 must not appear as the unlabelled native Used numerator**. CLI Watch keeps its legitimate rounded `8% used · 2088/25000`. An unchanged numeric mismatch must not fail tests simply because the figures differ.
2. **Multiple quota windows:** primary monthly, five-hour and weekly-only, plus a genuine secondary weekly/model quota; each native fraction and CCost remains assigned to the correct account/window. Unknown/missing period CCost does not erase known native Used; unknown native Used does not borrow CCost as a substitute. Reset and Remaining stay attached to the correct primary/secondary section.
3. **Special states:** test 0%, exactly 100%, almost 100%, Unlimited with/without known native Used, missing/zero/invalid denominator, partial/stale evidence, confirmed empty/reset vs unknown period, and overlapping windows. No false numerical consistency or invented data.
4. **Currency and presentation:** switching Credits ↔ USD changes labeled CCost amounts but leaves native AI credits and their Used/Total fraction intact. Browser/DOM regression tests in Classic/light/dark themes at narrow/mobile and desktop widths check legibility, alignment, conditional divider and no document overflow.
5. **Correct ownership:** cover the typed Python projection, Web Watch DOM behavior and at least one cross-surface assertion against canonical CLI/account formatting for the same fixture. Preserve FR000549 period boundaries/deduplication/partial pricing and FR000552's independent Today/monthly data acquisition. Run appropriate focused and full tests, package validation and the relevant existing Web render/integration checks. Report exactly what was and was not verified; do not claim an actual provider reconciliation without live evidence.

**Delivery scope:** create this FR in Ready and advance permanent identity only. No product-code change, version bump, release record or test claim is part of FR authoring.
