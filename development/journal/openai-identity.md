# OpenAI identity and quota evidence

Source revision: 22f0bff2df29d57de05c12c9586e6a6640771175
Checked revision: 22f0bff2df29d57de05c12c9586e6a6640771175
Last checked: 2026-10-25
Status: current

## Summary

An upstream 401 establishes request rejection, not failed model authentication or paid-tier incompatibility. The earlier affected OpenCode 2.1.4 connection used API-resource ChatGPT token sharing; the latest FR 000160 read-only observation instead found a legacy connection with successful WHAM quota retrieval. Neither result generalizes to another method or account. Classify the method/scopes before sending credentials. Cost Guard never repairs auth or retries another identity.

## Evidence

FR 000120's sanitized v80.65 observations showed duplicate Watch rows, then a single rejected account after restart. Source at the parent baseline retained removed unavailable rows and allowed per-integration legacy fallback across OpenAI aliases. The checked source fixes both without changing provider/Watch boundaries: `src/accounts/credentials.py` suppresses legacy aliases after V2 family records; `src/accounts/openai_subscription.py` deduplicates only proven source-aware OAuth identities; `src/accounts/acquisition.py` pins generations and explicitly observes removed keys; `src/watch/accounts.py` consumes those removals and clears failed OpenAI capacity. Unknown plans cannot inherit the prior tier.

Reproduce with `py -3 -m unittest development.tests.test_openai_account_switch`: synthetic SQLite/auth records, old-to-new identities, blocked old responses, alias and two-account cases, rejection/recovery, expiry and nonsecret failure evidence. At the historical FR 000120 check, Full passed 91 files and the product working-tree validator passed. Local read-only Diagnostics with network disabled found healthy V2/source selection; it did not test upstream quota.

FR 000150's historical candidate based on `7af187a71c455a70a6eec9e7c79da1af985fb20d` was checked on the affected Windows installation on 2026-10-25. A bounded local inspector used OpenCode's authenticated read-only `api get /api/info`, `/api/integration/openai`, `/api/provider/openai` and `/openapi.json`, plus a SQLite `mode=ro` / `query_only` query restricted to integration `openai`. It compared connection IDs only inside the process. One active record matched the integration connection, was unexpired, had method `chatgpt-token-sharing`, token-sharing/invoke scopes, API-resource audience and no account header. The effective provider base URL matched `https://api.openai.com/v1`. No IDs, tokens, token hashes, raw responses or headers were retained. The installed schema had no usage/limits routes; the newer documented experimental usage route was not available locally. No compatible supported quota source was established.

Pinned current OpenAI records were passed separately through real `AccountAcquisition` report/Watch paths, Watch reconciliation and both account renderers. Both returned one method-specific unavailable account without old quota or reconnect advice; request count was zero. This is headless account acceptance, not a full Desktop/terminal capture or a live quota 200. WHAM probing was deliberately NOT RUN with the known API-resource token. No paid inference, auth refresh, account switch, database write or service restart occurred. The earlier 401 was not re-probed; its precise server-side cause remains unproved.

Source comparison: [OpenCode token sharing](https://github.com/anomalyco/opencode/blob/1743d1a24e2356b3f631d3d384f44cb9d8359add/packages/core/src/plugin/provider/chatgpt.ts) explicitly binds the method/scopes to the API resource and migrates browser credentials with token-sharing metadata. It defines no quota fetch. The public [Codex client](https://github.com/openai/codex/blob/970111f6cb62cc02fe36a82ea7d71b37a2889c97/codex-rs/backend-client/src/client.rs) supports legacy WHAM, not arbitrary token-sharing credentials. Public source is supporting evidence; local method/route/schema checks establish the installed contract.

FR 000160 acceptance at the source revision above used `py -3 development/tools/collect_diagnostics.py --snapshots 1 --skip-validation` on the same Windows OpenCode V2 2.1.4 installation. The normal report returned three accounts; the sanitized OpenAI observation classified the current connection as legacy, attempted WHAM, returned HTTP 200 and retained native quota. Headless Watch reused acquired observations with zero free-flowing overflow at 80/120/160 columns. A separate real-source report/Watch-history probe passed ANSI/plain account rendering at those widths, including known-empty daily CCost. Separate Full passed 93 files and the working-tree validator passed with nonblocking design-budget warnings. No paid inference, auth changes or shared-service restart occurred. Private Diagnostics output was not committed; the FR completion retains the sanitized result. This supersedes the old lack-of-live-legacy-success limitation, not the token-sharing gap.

## Next investigations

Actual token-sharing quota retrieval remains an external functional gap. Reassess only when OpenCode/OpenAI exposes a supported read-only source for that resource; do not guess URLs, import another account or switch identity to get a 200. Legacy WHAM success is now live-observed for the current connection, not guaranteed for future accounts, plans or credentials. Token-sharing method advice is fixture-tested on both surfaces and names the legacy browser/device-code options only as attempts for now. A 403 may be endpoint policy, and a 401 does not establish model login failure. Reproduce deterministic method, alias, expiry, generation, status and Watch cases with `py -3 -m unittest development.tests.test_openai_account_switch development.tests.test_step6_pricing_accounts`. For future local acceptance, inspect only current OpenAI metadata in-process and emit allowlisted booleans/categories; never print credential/API output directly.

## Rejected hypotheses

- Subscription price proves a protocol plan or quota: unsupported.
- Restart alone fixes quota rejection: the sanitized observation still showed 401.
- Every OpenAI alias is a distinct subscription, or all same-provider records should merge: both lose identity truth.
- Successful deterministic recovery proves the historical user's token now works: it does not.
- Successful API model invocation authorizes WHAM quota access: token-sharing resource/method evidence contradicts that inference.
- Missing ChatGPT account header justifies guessing/importing one: unsupported; legacy requests may omit it and token sharing is not repaired by an unrelated identity.
