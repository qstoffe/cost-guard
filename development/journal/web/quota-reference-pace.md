# Web quota remaining pace — FR000638

2026-11-09, v80.215. Native `QuotaPace` deliberately divides native remaining units.
Formatting those values as USD would be wrong for arbitrary messages/tokens. The
application now shares `quota_ccost_values` between reference quota displays and
Web-only `quota.ccost_pace`. Quota identity binds both cost and native day/workday
counts; labels never join windows. Verified Capacity without accepted Remaining
still omits pace rather than inventing a conversion.

The projection preserves full Decimal precision. Display-only Credits remaining
rounds down; USD uses normal half-up cents, including `$0.00` for tiny positives.
Unknown/stale/unlimited/inactive/expired bases omit the two rows. Quietly retained
cards keep observed figures but drop stale forward budgets; pace rows independently
detach/reattach without replacing the bar, heading or help/focus owners.

Both real routes share `account-cards.js`; alternate/compact Accounts rendering in
`render.js` consumes the same field. Settings switches only bound server-prepared
tokens. No calendar, pricing, source reads, model calls, CLI or Mini behavior changed.

Evidence: Full suite 175 files/zero failures; validator zero failures/seven advisory
warnings; hidden Edge 157 Watch/Accounts route/theme/zoom/width and open Mini checks;
persisted Credits and Default USD reloads; real read-only V2/account publications.
A scratch observer checked 30 raw math/60 unit assertions across 15 eligible quota
occurrences (18 publications), with 44 inapplicable occurrences omitted. Counts are
observations, not distinct accounts. No private balances or identifiers are retained
in repository evidence. The integrated browser was disconnected; hidden-browser
proof is not native desktop/macOS/assistive-technology proof. No exceptions were used.
