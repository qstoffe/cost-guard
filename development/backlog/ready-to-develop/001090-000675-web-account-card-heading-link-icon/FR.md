# FR 000675 — Web account cards: show a link icon before linked account names

**Owner-approved Ready Feature Request, 2026-11-10.** Permanent identity **000675**; Ready queue priority **001090**, after the existing Ready FR000673 (001080), while leaving the higher-priority FR000674 (001065) untouched. **Backlog publication only:** do not implement, run product tests, alter product documentation, change release/version metadata, or disturb any running application in this transaction.

## Owner observation and desired outcome

In **Cost Guard Web**, the account/subscription card heading on **Full Watch** and **Accounts** is already a clickable provider usage/settings link (delivered by FR000636). However, because the account name looks like an ordinary card title until hover/focus, a user can easily miss that it is a hyperlink.

Show a **small, recognizable link/chain icon immediately before the account name** in each *linked* account-card heading. The icon must be visible even before hover, making the existing navigation affordance discoverable while keeping the header clean and attractive.

## Required presentation and behavior

1. Put the icon **to the left of the account name, inside the same existing `<a>`**. Icon and name together form **one link**, not two controls. The account name remains unchanged and fully readable. Do not turn the whole header background or card into a click target.
2. Use a restrained, familiar **outline chain/link symbol** (prefer a simple existing UI asset or lightweight inline SVG; avoid a large colorful emoji or new icon dependency). Size it proportionately to the heading text, align it neatly with the text, use a modest gap, and inherit appropriate heading color. Keep the combined icon + name centered in the existing colored heading region.
3. Display the icon **only when the account heading has a trusted destination URL**. Unknown/unmapped providers that retain a plain-text heading do **not** get a misleading icon, hover/pointer decoration, or fake action.
4. Preserve the existing link destinations, provider/plan selection, **new-tab** behavior, `target="_blank"`, `rel="noopener noreferrer"`, pointer cursor, hover underline, and keyboard `:focus-visible` treatment. The icon is a permanent visual cue; the original hover/focus feedback must still work.
5. The icon is **decorative** (`aria-hidden="true"`, not separately tabbable); the link's accessible name still identifies the account and provider usage/settings destination, including opening a new tab. Do not announce a duplicated “link” label or accidentally replace the accessible account name.
6. Preserve existing themes (Classic/Web light/Web dark), exhausted-state header colors, long/wrapping names, narrow screens, browser zoom, focus retention and quota-card grid alignment. Do not introduce unwanted header-height/row shifts or truncated names simply to fit the icon.
7. This is a **presentation-only change**: no changes to account discovery, native quotas, CCost, provider polling, URL allowlists, authentication, browser connection ownership, or Mini Watch's unrelated non-card UI.

## Implementation seams and coordination

- `src/web/assets/render.js::accountHeading()` already creates the shared `<h4>` with an `<a class="account-provider-link">` for known providers, or a plain `<span>` when no trusted destination exists. It is used from `src/web/assets/account-cards.js::Subscription.draw()` and the legacy Accounts rendering path. Implement the icon once at this shared heading boundary so **Full Watch and Accounts** remain identical.
- `src/web/assets/app.css` owns `.account-provider-link` and the account-card heading styles; use minimal styling to keep the existing centered title and focus/hover affordances intact. Keep icon position before the text even through retained DOM updates and card redraws.
- **FR000636** intentionally asked for linked text with *no standalone icon*. This new owner decision **supersedes only that earlier no-icon preference** by adding a compact icon **inside the existing linked heading**; it does not authorize a separate button or changes to the provider links.

## Acceptance criteria

1. With a known linked provider on **Full Watch** and **Accounts**, a small link icon is visible **immediately before** the account name in the heading, at rest; both icon and name open the same existing provider URL in a new tab. No extra focus stop or nested button exists.
2. With an unknown/unmapped provider, the title remains plain text **without** a link icon or click behavior. Account names and their exact provider destination mapping remain unchanged.
3. Hover/focus, Tab navigation, touch activation and screen-reader naming remain correct; decorative SVG is hidden from assistive technology. Clicking empty header padding or the rest of the card still does not navigate.
4. Long account names, normal/exhausted cards, Classic/Web light/Web dark, mobile widths and zoom preserve legibility, centering, line wrapping and aligned card rows. Updates/redraws do not duplicate the icon or lose link focus.
5. Extend the existing focused Web account-link/card DOM/browser regression coverage (including `development/tests/integration/fixtures/account_links.cjs` and the suites that invoke it, as applicable) and run relevant checks **during implementation**, not as part of this FR publication.

**Publication boundary:** add only `development/backlog/ready-to-develop/001090-000675-web-account-card-heading-link-icon/FR.md` and advance `development/backlog/identity-state.json` highWatermark **674 → 675** in a single atomic documentation-only commit on `main`. No source, tests, product docs, versions, releases or unrelated backlog entries are part of this authoring transaction.
