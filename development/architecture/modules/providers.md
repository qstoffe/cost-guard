# Providers source contracts

[Architecture overview](../OVERVIEW.md) · [Owner/test routes](CODE_MAP.md). Source remains authoritative.

## Account and Pricing Providers

These are intentionally separate roles.

- **Account Provider:** account/subscription quota, usage windows, balances and reset metadata.
- **Pricing Provider:** model price/rate metadata used for repricing/comparison/fallback valuation.

`accounts/credentials.py` reads only the selected installation: V2 wins per integration, legacy applies without V2 rows, explicit overrides are file-only, read errors fail closed and secrets stay memory-only. Proven account IDs/source locators distinguish accounts, never provider alone; inactive quota visibility changes neither inference nor history.

`accounts/discovery.py` shares source/WAL views; other identities retain probes. `accounts/acquisition.py` owns generation-checked work: reports use four workers/45s deadlines and 15s final wait; Watch reserves one bounded lane per configured adapter/20s deadlines. `refresh_policy.py` owns start-anchored 30s healthy cadence and bounded recovery; pinned retries observe failed credentials while periodic full inventories preserve healthy neighbors. `refresh_loop.py` owns one account-only scheduler, five-second local discovery and a coalesced mailbox independent of source hydration. Stuck lanes never multiply; workers cannot render or mutate analysis/credentials. Main-thread publication uses cached local usage and completion timestamps, not mailbox drain time. [Account contracts](../../../docs/account-support.md#watch-freshness-budget) define budgets and limitations.

Providers return independent native account/quota/billing components. Copilot preserves degraded evidence; unlimited/blocked requires explicit native state. OpenAI owns rolling/model windows/credits. Anthropic API and Claude Code logins stay separate; [Claude contracts](claude-code.md) own SDK, identity and privacy boundaries.

First-class adapters (including MiniMax) own complex auth; Simple HTTP handles DeepSeek/OpenRouter. `http_account.py` owns per-record acquisition, `http_transport.py` network/JSON safety, `simple_http_mapping.py`/`simple_http.py` mapping/definitions. [HTTP contracts](simple-http-accounts.md) prohibit custom HTTP/scripts, inferred capacity/CCost, attribution, renderer branches and duplicate polling/cache; local estimates must be visibly distinct.

`pricing/github_copilot.py` normalizes GitHub Docs tiered I/C/W/O rates, release dates and explicit promotion dates into reconstructible metadata. Refresh uses age, UTC month and expiry; expired rates revert to verified standard rates or are withheld. `pricing/promotions.py` owns structured validity/recency; unknown starts never imply recent offers. Reports retain active promotions for their full lifetime; Watch notices require a start within seven days. Presentation owns markers/alignment and label-only notice color, not validity.

`pricing/release_metadata.py` owns date sources/merging; `pricing/metadata_health.py` owns health/backoff/events. `cache/metadata_state.py` persists cache/state/, copying legacy logs/recovery/model-metadata.json without deletion/overwrite; Diagnostics never migrates. Failures log to logs/errors/, recoveries to logs/recovery/. Dates keep prices. `PricingCatalog` memoizes identity resolution per immutable instance. Watch price acquisition, including cold/expired caches, carries verified dates locally without fetching optional metadata inline. Discovery runs metadata and network checks (price/V2 model list) on one bounded worker each; the main thread applies results. Reports retain inline enrichment.

