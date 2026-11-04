# FR 000577 — Web setting: show account quotas as Used or Remaining

## Owner request and backlog decision

**Owner-approved executable feature request, 2026-11-04.** Permanent identity **000577**; Ready priority **000170**, following existing FR000576 (000160).

Add a **Web-only quota display orientation** preference under **Cost Guard Web Beta → Settings → Web settings**. Today, subscription/account quota percentages, native quota amounts and progress bars are primarily **Used-oriented**. The owner wants the option to instead show **Remaining** consistently throughout **Mini Watch, full Watch and Accounts**. The existing presentation must remain the application default and must not change for anyone who leaves the new preference at Default/Used.

This is **a presentation setting**, not a modification of provider quota data, provider polling, canonical usage, account billing or CCost attribution. It is approved for the Ready backlog, **not for implementation during FR authoring**.

## 1. Setting and inherited default

Add a fourth dropdown under the existing Web settings section, provisionally labelled **Quota display**, with **exactly three visible choices**, consistent with FR000576's explicit inheritance model:

| Selected choice | Effective behavior in this version |
| --- | --- |
| **Default (Used)** | Follow the application's current quota-orientation default: **Used** |
| **Used** | Explicitly pin **Used** |
| **Remaining** | Explicitly pin **Remaining** |

- Default must be the **selected choice on a fresh/unmodified installation** and resolve to **Used**. The shipped behavior, labels, progress fill, cost formatting and appearance on all Web screens must remain unchanged in that state.
- **Default and Used are distinct saved intentions**, even though they currently resolve to the same presentation. Default follows a future shipped change; explicit Used stays Used. Show the resolved label dynamically as **Default (<current application default>)**, not a permanently hardcoded "Default (Used)". Do not collapse explicit Used into Default.
- Use a narrowly validated, persistent **Web-only** preference in the existing `webSettings` namespace; proposed key `quotaDisplayMode` with actual values `used` and `remaining`, plus FR000576's stable symbolic inheritance/default mechanism. Store only selected intention, not the current resolved default. Do not reuse the CLI/terminal preference or browser storage.
- Selection saves **immediately** through the existing authenticated, CSRF-protected narrow settings path, with the same confirmed-save/failure-rollback behavior as Theme, CCost display and Mini Watch placement. A successfully changed selection updates already-open Web presentations, including an open Mini Watch and retained Watch/Accounts views, without requiring a browser/server restart, report recapture, quota refresh or additional live subscription. On failure, restore the last confirmed selected/effective choice and show the existing accessible error behavior.
- Preserve existing user JSONC fields, legacy theme behavior, separate Credits/USD selection, old saved explicit choices, unrelated configuration comments and validation/security. No settings read should create a user config file.
- **Dependency:** implement **after FR000576** establishes the Default-versus-explicit model for the first three dropdowns. This FR deliberately expands its **three-control** Settings UI to **four controls**; do not interpret FR000576's earlier "exactly three dropdowns" acceptance as a permanent prohibition against the fourth. Retain every other FR000576 default-inheritance and Mini-placement requirement.

## 2. What Remaining changes across Web

Apply **the same effective mode** to every account/subscription **quota visualization** in:

1. **Mini Watch:** each account's primary quota percentage/text and thin progress bar.
2. **Full Watch:** each account's primary and secondary quota sections, percentage, native amount/total and progress bar.
3. **Accounts:** all shown account quota windows, native amounts, percentages, progress bars, compact/detailed views and relevant expanded quota disclosures.

Any other Web quota-specific presentation reusing those view/projection primitives must follow the same choice. This does **not** refer to unrelated session token context, Model pricing, total CCost, daily cost, account billing, or the existing `Remaining / day / workday` *pace* calculation.

For each **trustworthy, finite quota/usage cap** with a known or derivable native remaining fraction:

- **Used (default):** keep today's **N% used**, native **used / total** and **used fraction** progress fill exactly as they are.
- **Remaining:** show **N% remaining**, native **remaining / total** (and the appropriate remaining native monetary fraction where genuinely supported), and fill the progress bar to the **remaining fraction**. Native labels/accessible descriptions must say Remaining, not Used.
- Remaining is calculated from the *same native account, quota window and denominator* as Used; if the trusted native remaining value exists, use it. Otherwise a complement of a **reliably finite** used fraction/used amount may be derived safely, without creating unrelated provider or CCost estimates. Keep real native units, precise source values and correct rounding.

Illustrative finite Copilot quota:

| Provider data | Used mode | Remaining mode |
| --- | --- | --- |
| 5,608 used / 25,000 total, 19,392 remaining | About **22% used**; **5,608/25,000** used; bar ~22% filled | About **78% remaining**; **19,392/25,000** remaining; bar ~78% filled |
| 90% used | 90%-filled bar | **10% remaining**, **10%-filled bar** |
| 0% used | Empty bar | **100% remaining**, full bar |
| 100% used | Full bar, exhausted | **0% remaining**, empty bar, **still clearly exhausted** |

- A full bar in Remaining is **healthy available capacity**, not exhaustion. An empty bar at **0% remaining** is exhausted; maintain the existing red exhaustion status and accessible warning (e.g. in the summary/track as appropriate), even if the red fill itself is zero-width. Do not mistake rounded 0% remaining for authoritative exhaustion when the unrounded native quota is still above zero. Keep cyan/teal for genuinely non-exhausted limits and preserve provider restriction/error semantics.
- Bar `value`, percentage text, native numerator and accessible `aria-label`/`aria-valuetext`/tooltips must agree. Clamp visual bars to their legal range without silently erasing genuinely reported overage or provider restrictions in explanatory text/status.
- Preserve each provider's stable primary quota selection, secondary quotas, actual reset time/period and per-account identity. One quota's or account's remaining amount may never be borrowed from another window.

## 3. Unlimited and insufficient capacity evidence

**Remaining mode applies only where a real finite maximum/limit is supported by reliable native quota evidence.** In all other cases, never invent a remaining amount or a 100%-full bar.

- A **provider-confirmed Unlimited** subscription continues to use its **existing Used-oriented presentation**, *even when the user selected Remaining*. Show `Unlimited` and the provider-native Used amount if known, without a finite percentage, a fraction bar or a synthetic remaining limit. This per-account fallback is intentional: a single page may contain Remaining for finite accounts and Used for unlimited accounts. Explain the exception with a short tooltip/help text on the **Quota display** setting, such as: **"Remaining applies to quotas with a known limit. Unlimited plans continue to show Used."**
- If quota capacity or the finite denominator is **unknown, invalid, zero or otherwise unverified**, retain truthful existing Used/unknown/unavailable behavior instead of manufacturing Remaining or a bar. If the finite cap is confirmed but the usage fraction is unavailable, preserve `N/A`/unknown, not an invented 100% remaining.
- Keep genuine **0% and 100%** distinct from missing data, and keep stale, partial, stopped, reset-not-started, expired, blocked, overage and unknown states correctly marked. A quota status must not turn stale observations into current available capacity.
- Native **balance/spend** metrics with no valid finite consumed-versus-limit denominator must not be reinterpreted as a usage bar. Keep existing remaining-pace calculations and reset semantics independent of the selected orientation.

## 4. CCost in parentheses is not the native remaining quota

Current Web Watch/Mini quota lines can show an **observed period CCost in parentheses after the provider-native % used**. That CCost is **Cost Guard's separately attributed reference spending during the quota period**, *not* the provider's native Used amount and **not a quota maximum**. These numbers do not necessarily reconcile, as documented in completed FR000556/FR000562.

- **Do not subtract observed CCost from a native quota limit** or compute `remaining CCost` from native percent, native provider AI credits, reference pricing, billing or a guessed ceiling. No actual CCost budget/denominator is generally available for this calculation.
- Preserve the existing **same-period observed CCost amount, completeness/estimated markers, zero/unknown behavior and Credits/USD formatting** regardless of the Used/Remaining selection. In **Used/default**, retain today's visual parenthetical layout unchanged.
- In **Remaining**, prevent the remaining percentage and adjacent parentheses from falsely claiming that the parenthesized amount is *remaining* CCost: distinguish it compactly as **observed/used CCost** through an explicit short label (e.g. `78% remaining (CCost used: 1 814)`) or an equally clear accessible presentation. Keep Mini compact and usable at its existing opening width. Tooltips/focus explanations must explicitly preserve the different provenance. Hide unknown period CCost as today rather than replacing it with synthetic zero.
- Continue to present native **remaining/total** units distinctly where the provider supplies them. The user-selected **CCost Credits/USD** option affects only CCost formatting, not native quota amounts, native currency equivalents, provider-billed totals or the orientation setting.

The owner is choosing **which side of a finite native quota the Web shows**, not asking to change how reference CCost is priced or attributed.

## 5. Scope, compatibility and acceptance

Acceptance criteria:

1. **Settings:** After FR000576, Web Settings has Theme, CCost display, Mini Watch placement and **Quota display**. The new dropdown shows **Default (Used) / Used / Remaining** in that order. No override selects Default and behaves byte-for-byte/visually as current Used. Explicit Used remains distinguishable in stored/readback selected state and survives future shipped-default changes. Persistence, immediate application, fresh tabs, host restarts, rejected save, JSONC preservation and error/focus behavior match the established Web Settings contract.
2. **Cross-view coherence:** Change to Remaining and check the same finite subscription and period on **Accounts, full Watch and an already open Mini Watch**. All show the correct remaining percentage, native remaining amount where available, bar fill, tooltip and accessibility state. Toggle back to Used and verify exact existing presentation returns; retained/frozen views update presentation without re-fetching data.
3. **Native arithmetic:** Reproduce 5,608/25,000 used ⇒ 19,392/25,000 remaining, complementary unrounded fractions and correct displayed percent across all three Web surfaces. Cover 0%, 10%, 90%, exactly 100%, just-below exhaustion, overage, and a confirmed finite quota with only a safe fraction available. Test multiple simultaneous accounts plus differing primary/secondary windows; never cross wires.
4. **Exhaustion meaning:** Remaining 0% shows an empty bar but still receives the established **exhausted** visual/status treatment. Remaining 100% shows a full healthy bar. Rounding never falsely marks a still-available quota exhausted. Actual provider blocked/restricted states continue to surface independently.
5. **Unlimited/fallback:** In Remaining mode, provider-confirmed Unlimited with known native Used still shows Unlimited + Used and no remaining progress bar; unknown used stays unknown. Missing/untrusted cap, partial/expired/stale/unknown states never display guessed remaining limits or healthy bars. The settings tooltip accurately explains Unlimited fallback.
6. **Independent CCost:** A fixture with e.g. native Used 2,088/25,000 but observed period **CCost 1,814** retains that CCost on switching modes, clearly distinguished from the native remaining amount. Unknown/partial/estimated period CCost, Native money and Credits↔USD preserve their correct independent meaning. `Remaining` pace, Reset, Today, Billed, Unaccounted and other account details remain unchanged.
7. **Regression/performance:** Test the canonical Python projection/shared display tokens and Web **render.js (Accounts)**, **watch.js (primary/secondary)**, **mini.js (primary)**, settings JS/HTTP, and real-browser accessibility/layout/resize/zoom/light/dark behavior at narrow widths. Switching mode is presentation-only: no quota/provider request, history scan, additional SSE stream, new persistent browser storage, source-state mutation or CLI output change. Update `docs/web-beta.md`, `docs/web-mini-watch.md` and relevant account/help descriptions after implementation.

**Not in scope:** changing CLI Normal or CLI Watch's permanently Used-oriented display (FR000525), provider quotas or their API/auth methods, CCost calculation, per-account override, a separate Mini-only setting, a new absolute quota/CCost budget, auto-charging/billing, changing the meaning of Remaining/day/workday pace, adding new polling, window geometry, or implementation/version/release work in this FR-authoring session.

**Authoring boundary:** publish only this approved Ready FR and advance CostGuard's permanent backlog identity high-watermark to **577** on `main`. No product code, active browser/server, price data, user config, tests or release metadata are changed now.
