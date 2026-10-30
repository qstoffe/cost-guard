# Restore working OpenAI quota display on the owner's Windows computer

## Problem

On the owner's Windows computer, Cost Guard v80.116 Watch displays `OpenAI Quota error (network unavailable)` instead of subscription quota. OpenCode and the other detected quota integrations remain usable. This was reproduced with current `main`, not inferred only from the screenshot.

The OpenAI reader's actual failure is `URLError` wrapping `SSLCertVerificationError`, with TLS verification code **10** and the allowlisted message **`certificate has expired`**. No OpenAI HTTP status or quota payload is received by Python. The transport discards this distinction and reports `network_failure` / HTTP status 0, which Watch renders as `network unavailable`.

A separate **credential-free** request to the same maintained WHAM URL, using Windows/.NET default TLS validation, reaches HTTP 401. This establishes that this client can validate TLS and reach the endpoint without credentials; it does **not** establish successful authenticated quota retrieval or justify changing authentication. The response Date and local UTC agreed to approximately one second. The particular expired certificate, chain-building difference, and any proxy involvement remain unproven.

See [sanitized diagnostic evidence, commands and limitations](attachments/diagnostic-findings.md).

The owner explicitly clarified that model requests to OpenAI work in OpenCode and that **restoring visible quota is the required fix, not merely improving the error message**. The owner previously used a ChatGPT Plus account and recalls a legacy-sign-in workaround on another computer. That history is user-reported, not a verified diagnosis of this computer.

## Required functional outcome

**Cost Guard Watch must again acquire and display the real, current OpenAI subscription quota for the owner's intended account on the affected Windows computer.** Resolve the actual transport/authentication/account-selection problem through the production integration, then demonstrate the native quota end to end on that machine. Preserve working OpenCode model access.

A renamed error, better Diagnostics, a suggested login, a successful unauthenticated request, or passing mocked tests is **not** completion. If a necessary external repair or owner-performed sign-in is blocked or pending, this FR remains unfinished until quota retrieval and Watch display are verified. Document the concrete prerequisite and obtain any required authority instead of weakening TLS or inventing a successful result.

Better failure classification is supporting work only. It must help reach and protect the functional outcome, not replace it.

## Authentication and account-selection investigation

- Treat **subscription tier** (for example ChatGPT Plus) separately from **sign-in method**. The current [OpenCode V2 provider guide](https://opencode.ai/v2/docs/providers#chatgpt) supports Plus/Pro with either Sign in with ChatGPT or legacy Codex methods; that does not make all credentials interchangeable for quota access.
- The observed quota request already used a credential classified as `legacy`, with an account header and a WHAM attempt. In Cost Guard this category includes `chatgpt-browser`, `chatgpt-headless` and historical methodless OAuth. It does not by itself establish the exact current OpenCode sign-in method or prove that the selected quota credential matches the connection serving the owner's model calls.
- Verify the current OpenCode connection, intended account, method/resource eligibility and quota-reader selection using bounded read-only metadata, comparing identifiers only in memory. Establish whether an old Plus connection, inactive credential, alias or account switch is relevant; do not presume that a stored eligible credential is the intended active account.
- Preserve the existing distinction documented in `docs/account-support.md`: token-sharing/API-resource credentials are not automatically eligible for WHAM. Successful model calls are a reason to investigate why the integration fails, not proof that the same credential authorizes a separate quota endpoint.
- Do not prescribe another legacy login just because it helped elsewhere. The verified Python failure is certificate validation before any HTTP response, so changing login alone is not an evidenced repair for that failure. Fix that path and continue investigating any subsequently exposed authentication/account issue until real quota is shown. If a particular supported sign-in is genuinely necessary, establish why, ask the owner to perform the explicitly approved manual action, and verify quota afterward; advice alone cannot close this FR.

## Scope and implementation leads

- Start with `src/accounts/openai_subscription.py`: `_default_usage_get` catches `URLError`, `TimeoutError` and `OSError` together; `UsageResponse` retains only `network_error`; `_request_quota` converts all of these into `parser_reason=network_failure`.
- Trace the shared presentation in `src/presentation/accounts.py` and the allowlisted evidence in `src/accounts/diagnostics.py`, plus the existing refresh policy and Watch reconciliation. Preserve error facts across those boundaries without leaking exception text.
- Compare the affected Python runtime's verified TLS chain/trust/proxy behavior with the platform-default observation. Select a bounded, maintainable secure remedy supported by the evidence; do not assume that swapping HTTP clients or adding a CA bundle is sufficient. No new dependency is required by this specification.
- Preserve source-aware account identity, method eligibility, credential ownership, capacity/CCost separation and bounded scheduler behavior. Use verified compatible maintained read-only quota sources; do not send credentials to guessed endpoints or incompatible resources. Correct any proven selection defect without silently switching identities. Failed acquisition must not become successful or fresh quota data.

## Acceptance criteria

1. **Live functional acceptance on the affected computer:** the production OpenAI acquisition path successfully retrieves native quota for the owner's intended current account, and actual Watch displays the returned quota windows/values and available reset information instead of `Quota error`. Record sanitized evidence that distinguishes acquisition from Watch publication/display. A later normal scheduled refresh and a fresh Watch start still show real quota without an ad hoc probe, hand-entered data or a special one-off command. No percentage change is required if the provider returns unchanged values.
2. Verify that displayed quota belongs to the intended current account, not an old Plus connection, inactive credential or another account. Resolve any proven identity/method mismatch, verify that the owner's existing model access is preserved, and document whether legacy sign-in was actually relevant. Do not infer this from account tier, the `legacy` category alone, or the credential-free Windows HTTP 401.
3. Resolve the observed Python TLS failure securely and investigate any additional failure revealed after it. An external certificate/environment prerequisite or required owner action is a **remaining blocker**, not an alternative completion criterion. Do not mark the FR delivered while this computer still cannot retrieve and show quota. Keep unverified chain/proxy/authentication explanations explicitly separate from established causes.
4. Regression tests exercise the **real transport exception handling** with synthetic `URLError(SSLCertVerificationError(...))`, DNS/connection errors and timeouts, not only preconstructed `UsageResponse` objects. Cover the demonstrated root-cause repair, production acquisition through Watch publication/rendering, recovery, account selection and existing HTTP/auth-method behavior. A certificate failure retains a safe typed category through normalization and Diagnostics; absence of an HTTP response remains distinct from HTTP 401/403/429. Better error text and these tests are necessary supporting evidence, never substitutes for criterion 1.
5. TLS certificate and hostname verification remain enabled. Do not accept expired/untrusted certificates or disable verification/revocation safeguards. Cost Guard must not install certificates, alter the machine clock/proxy/trust store, silently choose another account/credential source, refresh tokens, or automate sign-in as a workaround. A genuinely required external environment repair or owner-performed sign-in needs separate explicit authority and subsequent functional verification.
6. Diagnostic export uses bounded allowlisted categories/numeric codes only. No tokens, authorization headers, account identifiers, certificate subjects, raw responses or arbitrary exception messages are persisted or published. Keep the existing per-provider isolation and bounded retries; a persistent certificate failure must not cause request storms or block other quota integrations, and normal refresh recovers after repair.

## Non-goals

No implementation is included in this authoring request. Do not change quota semantics, resurrect old OpenAI capacity after a failed lookup, probe guessed quota endpoints, perform paid inference, restart shared OpenCode, or broaden this into a general account/HTTP rewrite. Do not add a permanent release gate or reserve a release version.
