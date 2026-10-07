# Maintained HTTP Account Providers

## Ownership and domain

The Account Provider protocol is unchanged. First-class adapters own complex authentication and semantics: Copilot, OpenAI, Anthropic/Claude Code and MiniMax. Simple HTTP providers are reviewed application-owned definitions for fixed GET + Bearer API-key + JSON APIs; the initial registry contains DeepSeek and OpenRouter. Neither implementation uses a presentation-oriented result hierarchy.

```text
configured CredentialRecord (read-only inventory)
  -> provider acquisition/normalization
  -> AccountSnapshot
       QuotaComponent: real provider capacity/limit/percentage
       BillingComponent: native balance/spend/informational budget
  -> shared Report / Watch projection and renderer
```

`http_account.py` owns acquisition per credential and sanitized snapshot construction. `http_transport.py` owns network/JSON safety. `simple_http_mapping.py` owns bounded declarative normalization; `simple_http.py` owns maintained metadata/definitions. `minimax.py` is a first-class adapter reusing acquisition/transport, not an attempt to generalize every provider behavior.

Historical Usage, CCost, actual billing, quotas, balances and availability remain separate. Current account credentials never prove historical request attribution. No local usage estimates become provider-reported capacity. Any future estimate feature requires a separate design and visible provenance; Berget is not implemented without a supported contract.

## Definition/mapping contract

A definition declares stable provider ID/display label, exact OpenCode integration IDs, fixed endpoint, root and optional bounded row path, optional explicit reported plan/status and component mappings. Paths are tuples of at most eight field names; no wildcard searches, executable expressions, eval, response scripts or JMESPath. The registry is runtime code/data, not user config.

Supported primitives are remaining/used percentage, used + limit, remaining + limit, enforced spend + budget, remaining + budget, and standalone balance/spend/informational budget. Percentages are explicitly declared remaining or used and normalized into remaining fractions. Valid native amounts are retained; only real denominators derive a fraction. Standalone values use billing and never manufacture bars. Monetary capacity remains native money, never CCost.

Optional reset timestamps declare ISO-8601 with timezone, Unix seconds or Unix milliseconds. Formats are never guessed. Currency/unit is fixed or selected from a maintained row-field allowlist; no FX or cross-currency addition. Plan and boolean/text status mappings use explicit maintained allowlists, never arbitrary provider strings or paid-plan inference. Missing/null/malformed numbers do not become zero; finite Decimal-compatible values are bounded to 1e18 and 64-character numeric strings. Invalid denominators preserve usable native fields but do not create a percentage.

Rows have an explicit maximum (engine hard maximum 16); the account hard maximum is 32 generated components. Invalid rows/components produce partial/error evidence, not a crash. Unrecognized response roots are schema errors. Optional mappings must explicitly permit absence; required missing fields remain evidence of partial data. An explicit null OpenRouter limit means no capacity row, not a zero-dollar budget.

## Credentials and transport

Inventory uses `credentials.py` unchanged. V2 rows win per integration, including inactive or unusable rows; legacy auth fallback follows the existing rules. Explicit `authJsonPath` stays file-only. Each record uses its existing source-aware `AccountRef`, never provider ID or secret bytes as identity. One failing record cannot hide another account. OAuth is never sent as an API key; unsupported configured credentials remain visible as unavailable without requests.

Only maintained HTTPS endpoints and GET are supported. Requests send Bearer authentication and `Accept: application/json`. The stdlib transport does not use ambient proxies, redirects, cookies, request bodies, arbitrary headers or login/refresh. All 3xx responses are rejected without contacting the destination. TLS uses standard certificate verification. Keys remain memory-only, are excluded from repr/diagnostics and are never cached, rewritten or refreshed.

Network operations use an eight-second timeout/deadline, including bounded incremental body reads. Bodies are at most 128KiB; compressed content and non-JSON MIME types are rejected. JSON nesting is checked before decoding (16 levels); traversal is limited to 4096 nodes. Duplicate object fields, invalid/non-finite JSON and changed schemas fail softly. HTTP/auth/network/timeout/schema errors are classified without raw exception text or response bodies. DNS resolution remains subject to host resolver behavior, as with stdlib HTTP generally.

No user configurable URL, method, header, cookie, body, authentication scheme or mapping exists. The only new settings are each provider's `enabled` and existing-style read-only `authJsonPath` controls.

## Provider contracts and evidence

### OpenRouter

[Official current-key contract](https://openrouter.ai/docs/api/reference/limits): `GET https://openrouter.ai/api/v1/key`, root `data`. Native `usage_daily`, `usage_weekly` and `usage_monthly` become separate USD spend components for current UTC windows. No organization/team aggregation, management key, observed-history substitution or inferred BYOK addition is used.

`limit` + authoritative `limit_remaining` become a monetary capacity component. `limit_reset` maps daily/weekly/monthly to Day/Week/Month; null means non-resetting Limit. Unknown periods are partial and never silently called Month. The API's period label is not a reset timestamp, so no reset instant is invented. Remaining and used are derived from the key limit, not all-time or monthly spend (which can have different BYOK/scope semantics). Null limit produces only textual spend. `is_free_tier` is not an explicit plan label and does not establish a paid plan.

### DeepSeek

[Official balance contract](https://api-docs.deepseek.com/api/get-user-balance): `GET https://api.deepseek.com/user/balance`, `is_available` and bounded `balance_infos` rows. Each row retains currency (USD/CNY), total, granted and topped-up remaining balances as billing components. No original deposits/budget, percentage, conversion or progress bar is inferred. Several currencies remain separate native components within the credential's account observation.

### MiniMax Token Plan

[Global FAQ](https://platform.minimax.io/docs/token-plan/faq), [CN FAQ](https://platform.minimaxi.com/docs/token-plan/faq) and [OpenCode setup](https://platform.minimax.io/docs/m-plan/opencode.md) document subscription keys, 5h/weekly windows and the Token Plan Bearer usage endpoint. The maintained requests use the FAQ's fixed `www.minimax.io` / `www.minimax.cn` `/v1/token_plan/remains` URLs, selected only by explicit `minimax-coding-plan` / `minimax-cn-coding-plan` integration IDs, never a configured URL. Generic MiniMax API accounts remain visible but do not establish Token Plan entitlement or trigger subscription lookup. No OAuth refresh/session/cookie fallback exists.

Response evidence comes from MiniMax's own public CLI [quota schema](https://github.com/MiniMax-AI/cli/blob/main/src/types/api.ts), [fixture](https://github.com/MiniMax-AI/cli/blob/main/test/fixtures/quota-response.json), and [count interpretation tests](https://github.com/MiniMax-AI/cli/blob/main/test/utils/quota.test.ts), reviewed as API evidence, not copied source. Legacy `*_usage_count` means remaining; when an explicit remaining percentage exists, only a count interpretation agreeing within one percentage point supplies native counters. Otherwise preserve the authoritative percentage with partial evidence rather than invent counters. Percentage-only responses do not invent allocations. Raw `usage_percent`/`usagePercent` is a remaining-percentage compatibility form, not consumed percentage. Millisecond absolute end times take precedence over declared millisecond reset offsets.

A general bucket supersedes repeated chat buckets only when all maintained window fields agree. Different/native video, speech, image or maintained MiniMax buckets are not combined; bucket names never become invented request-model IDs. Explicit native status can prove unlimited/exhausted, but the zero-total/both-status-3 form is no entitlement, not unlimited. Unsupported boosts/window shapes remain partial rather than inventing a new denominator. Reported allowlisted plans are retained; key/integration presence alone never yields a paid tier.

The response shape is less stable than the documented endpoint. Unknown buckets/forms are actionable partial/schema evidence; a response with no quota entitlement stays MiniMax/unavailable, not a subscription claim. [Documented API error codes](https://platform.minimax.io/docs/api-reference/errorcode.md) classify 1004/2049 as authentication failures, 1008/2056 as native rejection/exhaustion, and timeout/rate-limit/internal errors as transient—even at HTTP 200—so Watch retains its existing recovery behavior. Raw error messages are never retained. Personal live accounts are not required by deterministic tests; Diagnostics reports actual credential/request coverage separately.

## Lifecycle, presentation and diagnostics

Providers participate in the existing report and independent Watch account refresh. There is no second polling/cache mechanism and no request on every redraw. Existing stale TTL, bounded recovery and auth rejection behavior applies per full account key. Model availability, pricing, CCost and source lifecycle are unaffected by failed account observations.

The shared account renderer owns alignment, remaining bars, money, balances and narrow fallback. No OpenRouter/DeepSeek/MiniMax renderer branches exist. Capacity with a real denominator or explicit provider-reported percentage gets a bar; balance/spend without capacity remains text. Existing zero/unknown balance visibility rules are preserved.

Diagnostics records credential discovery/category/qualification (never values), attempted request, HTTP status, normalized error/schema class, matched mapping, component category counts, ignored/malformed counts and partial/available/unavailable/error outcome. MiniMax adds recognized form and quota-window labels. Account/source identity is hashed using the existing non-secret full key; raw locators, credential labels, keys/headers/cookies/raw responses/unrelated fields are excluded. Provider inventory remains observable without network or qualifying accounts.

## Adding another maintained simple provider

Add a reviewed definition/metadata, exact credential aliases, documented fixed endpoint and bounded mappings to the registry. Add synthetic documentation-based fixtures covering valid, malformed, missing, multi-account, transport/privacy and shared-rendering cases; register tests in the bounded runner and document support/evidence. Do not duplicate transport/credential plumbing, add arbitrary user config or widen bounds simply to accommodate an unknown API. Use a first-class adapter when authentication or interpretation is not cleanly declarative.

`test_simple_http_engine.py` covers generic mapping, transport, multi-account inventory/precedence, numeric/timestamp/iteration bounds and privacy. `test_http_account_providers.py` covers each maintained provider, wiring, shared rendering and existing Report/Watch lifecycle. Full regression and clean-extract gates protect existing integrations and accounting.
