# FR 000525 — Make Remaining versus Used quota values unambiguous in CLI and Web

## User-observed ambiguity

A user compared GitHub's 5,608 / 25,000 **credits used** to Cost Guard's Month bar at 78% with 19,392 / 25,000. These figures reconcile: 19,392 credits remain, or 77.568%, while 5,608 were used. The current CLI bar is explicitly a Remaining fraction internally, but its compact text does not always say so next to percentage and ratio. This makes a correct value appear wrong.

Cost Guard has already completed FR000490 for Web Accounts layout and FR000190 for independent Copilot Unaccounted usage. This FR is a targeted semantics/label clarity change, not a second quota adapter or dashboard rewrite.

## Required behavior

- Keep **remaining capacity** as the default meaning of every quota progress bar. Every compact indicator must clearly label the percentage and native numerator as Remaining (or Kvar in an explicitly localized future UI); no presentation that can reasonably be interpreted as percentage used.
- Where authoritative native used and limit values exist, show a concise matching Used value in the nearby account/period presentation, particularly for GitHub Copilot. Prefer compact labels that preserve readability at 80/120/160 terminal widths and the current Watch row caps/alignment; don't force an oversized quota line for every provider.
- The same terms and units should be recognizable in CLI Normal, Watch and Web Accounts/Watch; re-use existing shared report/account display/projection primitives. Keep provider-native unit names, month/window labels, reset times, money equivalents and known account exceptions.
- When used/remaining/limit or denominator is unknown, partially unavailable, stale, blocked or unlimited, show only the defensible known quantity. Do not invent used values from CCost, treat a percentage as an absolute used count, attribute Copilot CCost to native GitHub usage or combine account windows. Color is supplemental to text.
- Preserve independent CCost, actual Billed and Unaccounted usage semantics; the quota view is provider-reported capacity, not a billing ledger.

## Acceptance

Synthetic cases include Copilot 5,608 used / 25,000 total / 19,392 remaining, and mismatches/partial/stale/zero/unlimited/multiple-account states. Readable labels survive compact, wrapped and narrow CLI Watch presentations; Web uses the same meaning without introducing separate calculations. No new provider requests, quota formulas, schedule changes or background refreshes. Existing numeric/account tests and bounded browser/terminal presentation checks remain intact.

**Priority:** Normal, after current pending FR000520 and FR000521. Relevant files: src/presentation/accounts.py, src/web/assets/render.js and account presentation tests.
