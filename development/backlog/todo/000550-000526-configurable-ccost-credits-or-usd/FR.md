# FR 000526 — Add configurable CCost display units: AI credits or reference USD

## User request and goal

Cost Guard's CCost currently uses AI-credit-equivalent reference units. Users would like to see equivalent dollars instead, without interpreting these as real provider charges. Add an opt-in display mode, defaulting to the current AI credits behavior, which works across CLI report modes and shared presentation data later used by Web Beta.

## Required behavior

- Add a documented, validated user configuration option, provisionally **ccostDisplayUnit: credits | usd**, with shipped default credits. Offer an explicit CLI override, provisionally **--ccost-unit credits|usd**, for report, Watch, sessions, dates and historical Token Mix. Invalid options fail clearly; existing configs and commands retain their behavior.
- Reference conversion is **100 CCost credits = $1.00 reference USD** (thus 1 CCost = $0.01). In USD mode every CCost-denominated amount is explicitly prefixed by the dollar sign and displayed as **whole dollars with exactly two decimal digits**, for example 10,742 CCost -> $107.42 and 395 CCost -> $3.95. Do not output ambiguous bare 107.42, partial cent formats or numbers pretending to be thousands of dollars.
- Apply consistently wherever CCost amounts are visible: overall summaries, normal/Watch account CCost scopes, model and Token Mix CCost, session/detail/date totals, per-prompt, context/next-context estimates, threshold value explanations and progress/aborted/partial values. Shared canonical Python display/export tokens remain the source of truth, not a separate JavaScript valuation engine.
- Preserve exact underlying Decimal valuations and sorting/threshold/behavior decisions. Rounding happens **only for display**; no revaluation, altered model pricing, prompt attribution, warning thresholds or quota computations. Make explicit that a small positive CCost can round to $0.00 without being actual zero.
- Keep **native GitHub AI credits used/remaining, quota limits, Unaccounted usage (credit residual), provider-reported Billed amounts, native USD price-rate catalogs and dimensionless Relative CCost multipliers** independent and labeled. Never convert these into fictitious invoices or mix them into the CCost display setting. This is NOT live forex or SEK conversion.
- Expose the configured default through the shared application/report presentation so Web Beta can consume it; the interactive Web toggle itself is scoped to FR000528, not a prerequisite.

## Acceptance

Consistent both-mode examples across each CCost surface, including 0, fractional/very small positive, large, negative if supported, partial and unknown values; always $ plus two decimals in USD mode. Verify unchanged canonical totals/Decimal order and thresholds, no effects on Billed/quotas/native rates/relative ratios, and legacy config compatibility. Exercise CLI args, redirected output, normal/Watch/detail/date/Token Mix and supported platform paths using deterministic fixtures. Retain no network currency dependency.

**Priority:** Normal / after FR000525. Relevant files: config/default-config.jsonc, configuration/arg parsing, src/display.py, src/presentation, src/application/display.py, Web projection and tests.
