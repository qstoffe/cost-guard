# FR 000636 — Web account cards: link account headings to provider usage/settings pages

**Owner-approved Ready Feature Request, 2026-11-08.** Permanent identity **000636**; proposed Ready priority **000818** (after FR000635 at 000815, before the existing FR000629 at 000820). **Backlog-only authoring now:** add this FR and advance the identity high-watermark. Do not implement, test, release, restart the host, modify existing tasks, or disturb the running application in this publication.

## Owner request and intended experience

On **Cost Guard Web Beta → Watch and Accounts**, the subscription/account cards display a provider/account heading. Make that heading a useful external hyperlink to the account provider's **usage, subscription, billing or settings page**, with usage preferred. The owner can then click the account name in Cost Guard to reach the provider's own account/usage view.

- The **existing visible heading** itself is the link. Hover should clearly indicate a link with **underline and hand/pointer cursor** (and normal browser link behavior). Also give a visible keyboard focus style and a sensible hover/focus contrast in Classic, Web light and Web dark. No extra "Open" action, standalone icon, permanent underline, banner or explanatory text is necessary.
- It must work **wherever the same account cards are rendered**, especially the **Full Watch subscription cards** and the **Accounts page**. Do not implement a feature only in one route.
- Open the external destination in a **new tab** so the user's live Watch remains available. Let the browser handle its existing provider session/login; no attempt to authenticate to the provider is made by Cost Guard.
- Keep all account names, card placement, provider-specific plans, quota graphs, daily costs, tooltips, warnings and existing data intact. **Navigation only**, no changes to accounting or API polling.
- Multiple Cost Guard cards from one provider can share the same provider URL: the browser's signed-in account/workspace determines the actual provider session. **Do not imply the link is silently authenticated as a particular Cost Guard source account** when there is no trustworthy provider-native account-specific deep link.

## Requested exact destinations — primary acceptance cases

These are the owner's explicitly selected direct links. Use the actual provider/integration identity and plan type, **never substring-matching the displayed heading**.

| Supported card / provider | URL | Details |
| --- | --- | --- |
| **GitHub Copilot** individual / personal | `https://github.com/settings/copilot/features` | Explicit owner choice; GitHub's official documentation recognizes this personal Copilot features/settings URL. |
| **GitHub Copilot Business / Enterprise** | `https://github.com/settings/copilot/features` | The **same owner-specified destination** for GitHub subscriptions, unless a properly verified organization-specific destination is already available. Account permissions may affect what GitHub displays; never invent an organization slug or claim admin access. |
| **Claude Code / Claude subscription** | `https://claude.ai/settings/usage` | Explicit owner choice, with usage limits/settings. Claude's documentation identifies Settings → Usage; public guidance corroborates this direct path. |
| **OpenAI / ChatGPT / Codex subscription** | `https://chatgpt.com/settings/usage` | Explicit owner choice, to the ChatGPT Usage settings page. Do not substitute the older `/codex/settings/usage` route or conflate this with unrelated API billing. |

**Provider identities verified in the repository:** `github-copilot` and `github-copilot-enterprise` are supported Copilot account identifiers; `claude-code` is Claude Code; `openai` is used by the ChatGPT/Codex subscription reader. Some providers can also represent API/pay-as-you-go credentials, so inspect supported plan/account type before choosing a **subscription-specific** URL. For example, if the source clearly identifies an Anthropic **API** account, its console is a better destination than the unrelated personal Claude usage page; similarly for OpenAI API usage. For a supported Claude Code subscription, however, always prioritize the user's Claude usage link.

## Best-effort destinations for other supported accounts

The owner also wants **other provider account headings** to be useful links, even where a highly targeted usage deep link is not confirmed.

1. Inspect actual supported account providers in `src/accounts/`, the canonical `observation.provider_id` field, and any supported source-owned account type/plan. Maintain one **small static, reviewed HTTPS destination map** for known providers; choose a **verified direct usage or billing page** if possible, otherwise a **verified official provider home/console page**, not an invented internal URL.
2. **OpenRouter**: use `https://openrouter.ai/activity`, confirmed by OpenRouter's own product documentation as its usage/spend Activity dashboard.
3. **Anthropic API**: use the official Anthropic Console (`https://console.anthropic.com/`) unless a documented working account-usage deep link is confirmed. Do not mislabel API credit expenditure as a Claude Code subscription.
4. **OpenAI API-only**: prefer the provider's official API usage dashboard if a stable current deep link can be verified (`https://platform.openai.com/usage` is a candidate), otherwise the official OpenAI Platform entry. Do not route a clearly API-only account to ChatGPT just because `provider_id` is `openai`.
5. **MiniMax**, including supported global/region-specific integration IDs: target the matching official MiniMax account/console/plan management site with the deepest stable verified URL, or the provider's official landing page. Respect global vs CN account endpoints where supported; **do not fabricate a subscription plan path or add account identifiers**.
6. **DeepSeek** and any additional supported provider: prefer a verified usage page, otherwise the official provider platform/homepage. Look up the correct maintained domain rather than guessing from a provider display label.
7. If a truly unknown/third-party account has **no trusted mapped provider domain**, retain a normal plain heading. Do not create a misleading link to an unrelated site, search URL, API endpoint, arbitrary URL supplied by a provider response, or the account ID itself. The best-effort policy is for **known provider destinations**; unknown does not authorize open redirects.

**Freshness of destination mapping:** check current official providers' public pages during implementation, document only genuinely verified fallback choices, and test all **actually supported** provider IDs. Do not turn this simple static navigation feature into an ongoing website scraper, login validator or background URL-health monitor. If a destination redirects based on a user's login/workspace, that's normal external-site behavior.

## Confirmed repository implementation seams

- `src/web/assets/account-cards.js::Subscription.draw()` currently creates the heading using **`el('h4', () => item().observation.label)`**; it is not interactive. Its `Subscription`/ `AccountCards.View` owns the shared responsive account-card presentation. The same `View` is used by **Watch** and the dedicated **Accounts** route (with route-specific loading). Attach a link at this shared boundary so both locations behave identically.
- The account `observation` projection in `src/application/projection.py::account()` already exports an allowlisted `provider_id`, stable opaque `id`, display `label`, `provider_label` and `plan`. Navigation can ordinarily select destinations from this already-available safe metadata, without exporting raw credentials, native account addresses, or source instance secrets.
- `src/web/assets/app.css` defines `.watch-subscription > h4` with a colored full-width heading background, centered text, rounded top corners and a special exhausted-state color. Put the link **inside** the existing `h4` and style its text/interaction without losing the card's current background, exhaustion severity or subgrid row alignment.
- `src/web/assets/render.js::overviewAccounts()` contains an older/alternate account-card renderer with its own plain `h4`. Check whether any supported route or fallback still uses it; if so, reuse the same destination helper there to honor "everywhere account cards appear." Do **not** alter unrelated ordinary model/prompt headings.
- Account card updates can redraw on shape changes, while the shared View retains keyed card identities during ordinary observation updates. Avoid unnecessary full-card rerenders solely to update href and keep existing quota/today help, focus, selection and responsive geometry stable.

## Implementation requirements

1. **One provider destination decision:** implement a maintainable `provider_id` → verified destination mapping, with a narrow plan-type distinction only where necessary. Prefer a shared frontend helper for Watch/Accounts/legacy card layouts or a minimal server-prepared allowlisted display-only destination if that gives better account-type provenance. The URL must be static/trusted, `https:` only; never construct an unvalidated host from source/plan/label/input or interpolate secrets.
2. **Link the heading text, not the entire card.** Use an actual `<a href="…">` within `<h4>`, with `target="_blank"` and `rel="noopener noreferrer"`. Hover uses `text-decoration: underline` and `cursor: pointer`; a clear `:focus-visible` indication works for Tab navigation, mouse focus, Classic/Web themes, reduced motion and narrow widths. Preserve the heading's visible text, truncation/wrapping, readable ink and exhausted colors. Nonlinked unknown providers remain plain heading text without pointer/hover decoration.
3. **No bogus click targets:** keep normal card background and internal quota links/help/buttons independent. Clicking blank card/header padding, progress bars or nested account quota text should not unexpectedly open the provider. Do not nest interactive elements. A screen reader should identify the account heading as a link to the provider's usage/settings page (e.g., accessible name with purpose) while the visible heading remains unchanged; no extra visible label or warning.
4. **Safe direct navigation:** external browser tab only; no implicit background requests to destination hosts, no URL containing local session IDs, OAuth credentials, account email, user tokens, organization names or private source details, no bypass of Cost Guard's CSP/authenticated loopback boundary. Link works equally if the provider quota data is incomplete/unavailable: availability isn't an excuse to disable external account navigation.
5. **Multi-account and workspaces:** if several provider accounts are displayed, every relevant card independently gets its appropriate link from its provider/type. When a provider allows multiple signed-in browser profiles/workspaces, the destination opens according to **browser** state, not inferred Cost Guard credentials. For Copilot Business/Enterprise keep the explicit fixed GitHub URL unless reliable account-specific routing is genuinely supported; never guess organization paths.
6. **Non-goals:** no embedded provider websites, iframe/WebView, account login, provider-usage API integration, scraping/health probes, account switching, data aggregation/recalculation, new subscription types, extra status banners or new settings. No changes to Mini Watch's account *list* unless it renders an actual shared account card; the owner specifically requested the card headings on Watch and Accounts.

## Acceptance tests

1. Full Watch and Accounts: synthetic cards for `github-copilot` personal, business/enterprise, `claude-code` subscription and `openai` subscription have the **exact three requested URLs**; clicking the heading is a standard new-tab link. Test other supported provider IDs and at least one unsupported provider (plain heading).
2. Copilot business account keeps the same `github.com/settings/copilot/features` URL, without injecting an organization/enterprise name. Claude API-only and OpenAI API-only cases use an appropriate approved console/platform fallback rather than falsely pointing to consumer subscription usage. OpenRouter uses the official `openrouter.ai/activity`.
3. Hover on heading text underlines and has a hand cursor; pointer leaving removes underline; keyboard Tab focus is visible; touch taps open the provider link; the current Watch page keeps its existing live state. Test Classic/Web light/dark, exhausted/normal cards, narrow phones, long provider names and browser zoom.
4. Check DOM `a[href]`, `target`, `rel`, accessible link name, no nested interactive targets, no click activation when touching non-link card/heading padding. A card with stale/unavailable quota still links normally.
5. Update/refresh source: when a card is reused or redrawn, its link maps correctly to its current provider/plan and is never stale or duplicated. Opening link does not create a new Live/SSE connection, make Cost Guard background provider API calls or cause local auth changes.
6. URL safety regression: provider label/account ID containing HTML, whitespace, slashes, an arbitrary `https://` host or a `javascript:` string never changes or injects the destination. Never emit account-specific identifiers in href. External target uses HTTPS and `rel="noopener noreferrer"`.
7. Extend focused shared account-card/Watch and Accounts DOM/browser tests, including `development/tests/integration/web_watch_summary.cjs` and relevant `development/tests/test_web_*.py`, plus responsive/tooltip tests as warranted. Update the current Web Beta guide with a **short** description of linked account headings during implementation, without adding a verbose warning in UI.
8. This delivery must not regress FR000634's quiet background refresh policy or the existing CCost/quotas layout. Verify ordinary account card data and performance unchanged; no new paid model requests or source mutations.

## Verified link references available for implementation

- GitHub Copilot personal features/settings (also applied to Business/Enterprise **by explicit owner preference**): https://docs.github.com/en/copilot/get-started/where-to-use-github-copilot
- Claude paid-plan Usage page: https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work
- ChatGPT Settings → Usage: https://learn.chatgpt.com/docs/sign-in-with-chatgpt
- OpenRouter Activity dashboard: https://openrouter.ai/blog/announcements/activity-dashboard/

**Coordination:** FR000634/FR000635 precede this FR and may edit shared account/Watch or Mini styling; implement on their resulting components. FR000629 is queued after this request and can change model identification; these account navigation links must not be based on mutable model labels or interfere with that work.

**Publication boundary:** add only `development/backlog/ready-to-develop/000818-000636-web-account-card-provider-usage-links/FR.md` and advance `development/backlog/identity-state.json` highWatermark **635 → 636** together in one optimistic documentation-only commit to `main`. No implementation, tests, other FR modification, version or release changes during FR authoring.
