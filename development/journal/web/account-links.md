# Account heading navigation — FR000636

2026-11-09; implementation base `55afeaa6e77df79e17bd5734556f8c46980bc5c0`.

## Ownership and safety

`render.js::accountHeading` owns one reviewed static destination decision, shared by
Watch/Accounts' `account-cards.js` and the still-exported legacy account renderer.
The existing safe `provider_id` and source-owned plan select the URL, never label,
account ID, provider response URLs, model name or credentials. Exact API plan values
select OpenAI Platform/Anthropic Console; Anthropic's known subscription plans use
Claude usage unless the canonical account explicitly reports credit capacity.
MiniMax's four integration IDs preserve global/CN and subscription/API distinctions.
Unknown IDs, including object-prototype names, remain unlinked.

Only heading text is an inline anchor (`_blank`, `noopener noreferrer`); header
padding/card/quotas have no added handler. The accessible name supplies purpose and
new-tab behavior without changing visible labels. Bound updates preserve heading/link
identity for ordinary label/plan changes, switch plain/linked children only when
needed, and map correctly after quota-shape redraw. Inherited ink keeps exhausted
severity and theme colors. Hover underlines, focus has a current-ink outline.

No DTO, credential, accounting, polling, CSP, source, host, Mini list or authentication
change. There are no destination probes in the application. Provider login/workspace
is the browser's own state, not an inferred Cost Guard source identity.

## Public destination checks

Fresh unauthenticated public retrieval on 2026-11-09; no provider login attempted:

- [GitHub's surface guide](https://docs.github.com/en/copilot/get-started/where-to-use-github-copilot)
  links personal `https://github.com/settings/copilot/features`; the same URL for
  Business/Enterprise is the owner's explicit choice, not invented org routing.
- [Claude usage limits](https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work)
  links `https://claude.ai/settings/usage` directly.
- [Sign in with ChatGPT](https://learn.chatgpt.com/docs/sign-in-with-chatgpt)
  documents Settings → Usage; `https://chatgpt.com/settings/usage` is the exact owner
  choice, not the older Codex path. [OpenAI production guidance](https://platform.openai.com/docs/guides/production-best-practices)
  directly links API `https://platform.openai.com/usage` separately.
- [OpenRouter Activity announcement](https://openrouter.ai/blog/announcements/activity-dashboard/)
  directly links `https://openrouter.ai/activity`.
- `https://console.anthropic.com/` resolves to the official Claude Console entry;
  retained as the requested API fallback, without claiming a logged-in usage view.
- [MiniMax global preparation](https://platform.minimax.io/docs/guides/quickstart-preparation)
  explicitly links `/user-center/payment/token-plan` and `/user-center/payment/balance`
  on `platform.minimax.io`. [CN preparation](https://platform.minimax.cn/docs/guides/quickstart-preparation)
  explicitly links the same paths on `platform.minimax.cn`. Bare platform requests
  encountered HTTP307; the destination choice comes from these current official
  documents, not an inferred plan path or successful authenticated validation.
- [DeepSeek's official authentication docs](https://api-docs.deepseek.com/api/deepseek-api/)
  identify `platform.deepseek.com` as the account platform. Its root is the conservative
  official fallback; no deeper usage route was confirmed or invented.

These checks establish official routing, not account access, billing permissions or
per-account sign-in correctness. Normal provider redirects remain browser behavior.

## Verification and limits

- Full local runner executed all 175 file entries. Its initial two failures were
  causal test-harness issues: a missing `replaceChildren` in the period-cost VM's DOM
  double, and the version changing while the foundation subprocess compared it.
  After adding the native DOM operation and stabilizing v80.217, both affected files
  passed their focused reruns. The other 173 entries passed in the full run; this is
  not a claim that the initial full command exited successfully. Of 2140 discovered
  tests, one macOS command/PTY test was skipped because zsh/PTY is unavailable on
  Windows; native macOS CI owns that shell execution.
- The account-links matrix runs through `web_watch_summary.cjs` with actual shared
  Watch/Accounts and legacy renderers: all supported IDs, both API/subscription
  families, multiple accounts, unavailable quota, unknown/prototype/hostile IDs,
  literal HTML labels, safe HTTPS/new-tab attributes, input nonmutation, retained
  plan/label updates, plain/linked transitions and shape redraw.
- Hidden Chrome 156 shipped-app probe passed the complete Accounts/Watch/Capacity/
  Mini compatibility driver. The new 48-case heading matrix covers both routes,
  normal/exhausted states, Classic/Web light/dark, 360/1280 viewport requests and
  100/125% CSS zoom. A second run uses the disposable profile's real browser 125%
  zoom (read back through `chrome.settingsPrivate`), passing the same heading
  matrix plus quota compatibility; the already-passed wider Capacity matrix was
  not repeated. Native mouse hover/leave, Tab/Shift-Tab focus, AX link purpose,
  text-only hit testing, pointer and touch each opening one actual new tab, and
  retained Live connection/CSRF/route all passed. Only existing `/api/live` snapshot
  and `/api/interest` heartbeats are permitted during popup checks; neither starts
  provider acquisition. Existing quotas/cost/help, stable selection/focus, single
  SSE, no route-report jobs, quiet stale/failed updates and subgrid geometry passed.
  Initial probe assertions were corrected for browser fractional-pixel rounding
  under compounded zoom and independently scheduled health snapshots; no production
  behavior or required regression was weakened. Evidence: `scratch:/account-browser.json`,
  `scratch:/account-browser-zoom.json`, `scratch:/full-tests.json`; inspected narrow
  dark screenshot retains heading ink and card/help geometry.
- Working-tree validator: 11 passes, no failures; seven existing advisory prose/design
  budget warnings, no raised limits. Version/current README/history and short Web
  guide updated; no ZIP/Release generated.
- Real installation: `probe_web_live.py --accounts` passed on V2, one Live owner and
  one account-refresh owner, advancing publications, no finite jobs/model calls,
  verified stream identities and clean owned-worker shutdown. Shared OpenCode was
  not stopped. The supplemental `--accounts --watch-cards` run verified Accounts
  but reached its 90s history-observation cap (1085/3002 roots); Earlier-history proof
  remains INCONCLUSIVE, not PASS or a claimed history/performance fix.

Integrated OpenCode browser was disconnected, so browser verification uses a fresh
hidden Chromium profile and owned synthetic host/config; no personal browser state.
Provider-account authenticated pages and physical desktop behavior are outside the
navigation proof. No paid requests, shared source mutations or service restart.
