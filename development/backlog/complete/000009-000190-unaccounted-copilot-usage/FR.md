# FR 000190 — Show Unaccounted usage for GitHub Copilot in Accounts Overview

## Problem and desired outcome

Cost Guard already shows two distinct measurements for GitHub Copilot subscriptions:

- **Native GitHub usage/quota** from the Copilot account adapter: AI Credits consumed in GitHub's billing period, including eligible activity outside OpenCode (for example Copilot PR reviews).
- **OpenCode CCost** from observed and deduplicated OpenCode requests: a token-based reference valuation expressed in Copilot AI-credit-equivalent units, **not verified credits charged**.

The normal report currently shows these independently. The owner wants a compact, informative reconciliation in the GitHub Copilot account block. Call the additional line **`Unaccounted usage`**, without claiming the difference is attributable to Code Review or any other specific GitHub feature.

## Required report behavior

1. **Always render one `Unaccounted usage: <value>` line inside each detected GitHub Copilot subscription/account block of the normal `Accounts Overview` report**, near its quota and `CCost this month` figures. This includes unavailable data: show `Unaccounted usage: —` when a defensible number cannot be computed. Keep the other account/report lines and their existing layout. Do not add this line to Watch, non-Copilot providers, prompt/session reports or Token Mix.
2. For a trustworthy common period, calculate **unaccounted usage = GitHub-reported native AI Credits used − observed OpenCode Copilot CCost in the same period**. Retain full internal Decimal precision until presentation; present a signed difference (`+230`, `-25`, or `0`), without clamping negative values to zero. The number is an **estimate/reconciliation residual in AI-credit-equivalent units**, not independently metered external usage, verified billed cost or an invoice adjustment.
3. Align both terms to the **actual native Copilot monthly quota/billing window**. GitHub's monthly UTC boundary can differ from Cost Guard's configured-local `CCost this month` calendar window. Preserve the existing local-month line unchanged; compute the comparison from a separately aligned request scope using the established canonical deduplicated valuation. Respect the reliable provider reset/billing-period evidence rather than inventing a window when its boundaries cannot be established. At a timezone boundary the visible `CCost this month` may legitimately differ from the internal CCost used in this reconciliation.
4. Obtain native used credits from the existing account/quota provider evidence (`native_used` / `creditsUsed` / `credits_used`) and existing OpenCode history; **no separate PAT, billing API, credential modification, new GitHub endpoint or polling path** for this FR. Do not infer actual used credits from merely a percentage, extra-credit limit, balance, subscription price, or a reference CCost figure.
5. Apply the existing provider/account attribution rules: requests using `github-copilot` and supported Copilot aliases count regardless of model publisher; proven account references stay with their accounts. If just one compatible account exists, provider-attributed history may be used under the existing explicit non-verified-attribution semantics. With multiple compatible accounts and unassigned usage, do not assign or duplicate it across accounts: show `—` wherever reliable comparison is unavailable.
6. Never silently invent missing usage. Display `—` when native used credits are unavailable, the comparison period is unsupported/unknown, history has not been acquired through the required start, attribution is ambiguous, or relevant requests cannot be valued sufficiently for a meaningful residual. A fully acquired and fully priced zero-usage period is `0`, not `—`. Preserve the underlying unknown/partial evidence and the existing account CCost output semantics.
7. Keep the meaning of **`Unaccounted usage` neutral**. Positive values can reflect Copilot Code Review or other out-of-OpenCode consumption, deleted/previously unobserved OpenCode sessions, discounts/price-model mismatch, or upstream reporting lag. Negative values are possible for the same comparability reasons. Neither a positive value nor a zero proves whether a review was free. Document these caveats concisely in `docs/usage-and-cost.md`, not as a long disclaimer repeated on every account row.

Illustrative account excerpt (figures refer to a fully comparable period; these are **not** live observations):

```text
GitHub Copilot Pro+
  Month ... 850/7000 AI credits used
  CCost this month: 620
  Unaccounted usage: +230
```

The month CCost above happens to match the billing window in this example; that need not hold at a local/UTC boundary.

## Scope and implementation constraints

- Reuse `src/accounts/github_copilot.py`'s native usage evidence, shared `src/analysis/period_ccost.py` valuation/index, existing `src/reports/accounts.py` account projection and `src/presentation/accounts.py` / report rendering. If history acquisition needs the native period's earlier start, extend only the relevant existing report scope in a bounded way; do not add a second valuation engine, full-history rescans on every refresh, or a persistent billing ledger.
- Keep GitHub quota/remaining/Pace, existing `CCost today` and `CCost this month`, account ambiguity, Watch performance, provider access and existing global CCost behavior unchanged.
- This FR concerns **only** the normal report. Do not identify or price individual Copilot reviews, alter GitHub billing, add authentication requirements, or infer provider-charged costs from CCost. No product release target is reserved by authoring this request.

## Acceptance examples

- One Copilot account, trustworthy monthly native use of 850 credits, 620 fully valued OpenCode Copilot CCost for the *same* native period → `Unaccounted usage: +230`.
- Native use 500, comparable CCost 525 → `Unaccounted usage: -25` (do not clamp); both exactly zero → `0`.
- Native usage missing, unknown reset/start, incomplete required history, wholly/partly unpriceable relevant requests, or ambiguous multi-account attribution → line still present with `—`, no fabricated number.
- Test a local/UTC month boundary and DST independently of the existing local-calendar-month display; test Copilot provider aliases and non-Copilot models via Copilot, deduplication, account separation, and signed decimal/display rounding.
- Account report gains precisely the intended row. Watch, non-Copilot accounts, other report modes, normal native quota presentation, existing local-month CCost and billing distinctions remain unchanged. Use proportionate focused synthetic/model-free tests during eventual implementation; no new permanent release or validation gate.

## Publication and authorization

Owner-requested **normal-priority FR000190**, following the repository identity high-watermark 180. Publishing this specification is development-only FR authoring on the default branch; it authorizes the described future implementation but makes no runtime changes, no product version/history update, and no implementation claim.
