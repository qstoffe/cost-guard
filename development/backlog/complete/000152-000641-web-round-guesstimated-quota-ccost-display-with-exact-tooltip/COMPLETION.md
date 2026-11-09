# Completion — FR 000641

2026-11-09 · v80.221

Implemented estimate-only Decimal significant-digit rounding before unit conversion,
preserving raw reference values and exposing them in accessible Watch, Accounts and
Mini help. Monthly equivalents and daily/workday pace use their own unrounded
calculation. Observed Used, verified provider amounts, percentages/bars, billing,
Today/prompt/session costs and CLI formatting remain independent.

Verified: full local suite **179 files / zero failures**; final focused **86 tests**;
hidden shipped-browser Accounts/Watch/Document PiP **PASS**, including actual input,
both units/modes, themes and Live help refresh; read-only real account-owner probe
**PASS**. Real observation had no eligible estimates; estimate-specific evidence is
synthetic, not native-desktop/assistive-technology/macOS proof.
Working-tree validation: **11 passes, zero failures**, seven advisory size warnings;
`git diff --check` passed, with no hard-budget or baseline increase.

**Decision Delegate's narrow exception:** acceptance #3's contradictory example is
resolved as **5517 → 6000**, not 5000, following the prescribed nearest-half-up
one-digit candidate within 10%. The literal 5000 expectation was not passed; no
other acceptance was waived. See [decision, tests and limitations](../../../journal/web/quota-estimates.md).

Docs, code navigation, contextual-help architecture, version/history and ordinary
maintenance progress updated. No inference, new dependency, ZIP or Release.
