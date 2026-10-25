# OpenAI identity and quota evidence

Source revision: 38ad8e20880e1b81cc740a028a91c258e913068f
Checked revision: 38ad8e20880e1b81cc740a028a91c258e913068f
Last checked: 2026-10-25
Status: current

## Summary

An upstream 401 establishes request rejection, not paid-tier incompatibility or valid current authentication. Investigate canonical source selection, account headers, expiry and generation ownership before attributing a subscription upgrade failure to OpenAI. Cost Guard never repairs auth or retries another identity.

## Evidence

FR 000120's sanitized v80.65 observations showed duplicate Watch rows, then a single rejected account after restart. Source at the parent baseline retained removed unavailable rows and allowed per-integration legacy fallback across OpenAI aliases. The checked source fixes both without changing provider/Watch boundaries: `src/accounts/credentials.py` suppresses legacy aliases after V2 family records; `src/accounts/openai_subscription.py` deduplicates only proven source-aware OAuth identities; `src/accounts/acquisition.py` pins generations and explicitly observes removed keys; `src/watch/accounts.py` consumes those removals and clears failed OpenAI capacity. Unknown plans cannot inherit the prior tier.

Reproduce with `py -3 -m unittest development.tests.test_openai_account_switch`: synthetic SQLite/auth records, old-to-new identities, blocked old responses, alias and two-account cases, rejection/recovery, expiry and nonsecret failure evidence. Full passed 91 files and the product working-tree validator passed at this revision. Local read-only Diagnostics with network disabled found healthy V2/source selection; it did not test upstream quota.

OpenAI's moving public Codex client reference, inspected 2026-10-25: <https://github.com/openai/codex/blob/main/codex-rs/backend-client/src/client.rs>. It retains backend-api usage routing, bearer auth/account header and recognizes additional plan variants. This is supporting source evidence, not a stable compatibility contract.

## Next investigations

If a current canonical request still receives 401, obtain newly authorized, minimized status/expiry/generation evidence without tokens or raw account IDs. The historical user's actual credential validity and upgraded-tier success remain unverified. A 403 may be endpoint/account policy rather than invalid sign-in. No paid or real-credential test is required by the deterministic regression suite.

## Rejected hypotheses

- Subscription price proves a protocol plan or quota: unsupported.
- Restart alone fixes quota rejection: the sanitized observation still showed 401.
- Every OpenAI alias is a distinct subscription, or all same-provider records should merge: both lose identity truth.
- Successful deterministic recovery proves the historical user's token now works: it does not.
