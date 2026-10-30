# Fix Windows OpenAI quota TLS validation and misleading network errors

## Problem

On the owner's Windows computer, Cost Guard v80.116 Watch displays `OpenAI Quota error (network unavailable)` instead of subscription quota. OpenCode and the other detected quota integrations remain usable. This was reproduced with current `main`, not inferred only from the screenshot.

The OpenAI reader's actual failure is `URLError` wrapping `SSLCertVerificationError`, with TLS verification code **10** and the allowlisted message **`certificate has expired`**. No OpenAI HTTP status or quota payload is received by Python. The transport discards this distinction and reports `network_failure` / HTTP status 0, which Watch renders as `network unavailable`.

A separate **credential-free** request to the same maintained WHAM URL, using Windows/.NET default TLS validation, reaches HTTP 401. This establishes that this client can validate TLS and reach the endpoint without credentials; it does **not** establish successful authenticated quota retrieval or justify changing authentication. The response Date and local UTC agreed to approximately one second. The particular expired certificate, chain-building difference, and any proxy involvement remain unproven.

See [sanitized diagnostic evidence, commands and limitations](attachments/diagnostic-findings.md).

## Desired outcome

Restore secure OpenAI quota acquisition on the affected supported Windows installation when a valid, intended certificate chain is available. Investigate the Python-versus-Windows transport difference rather than treating this as a generic internet outage, exhausted quota, or a request to sign in again. If the underlying chain really requires external repair, identify that verified prerequisite and provide actionable guidance instead of bypassing validation or promising a product-only fix.

Retain enough safe transport detail for Watch, normal reports and Diagnostics to distinguish certificate validation/expiry from DNS, connection and timeout failures. Users should be able to understand the failure and see normal recovery after it is resolved.

## Scope and implementation leads

- Start with `src/accounts/openai_subscription.py`: `_default_usage_get` catches `URLError`, `TimeoutError` and `OSError` together; `UsageResponse` retains only `network_error`; `_request_quota` converts all of these into `parser_reason=network_failure`.
- Trace the shared presentation in `src/presentation/accounts.py` and the allowlisted evidence in `src/accounts/diagnostics.py`, plus the existing refresh policy and Watch reconciliation. Preserve error facts across those boundaries without leaking exception text.
- Compare the affected Python runtime's verified TLS chain/trust/proxy behavior with the platform-default observation. Select a bounded, maintainable secure remedy supported by the evidence; do not assume that swapping HTTP clients or adding a CA bundle is sufficient. No new dependency is required by this specification.
- Preserve current account identity, method eligibility, fixed quota endpoint, credential ownership, capacity/CCost separation and bounded scheduler behavior. Failed acquisition must not become successful or fresh quota data.

## Acceptance criteria

1. A nested certificate-verification failure, including the observed expiry case, retains a safe typed category through transport, provider normalization and Diagnostics. Watch/report clearly identify a TLS/certificate problem rather than showing only `network unavailable`, claiming quota exhaustion, or recommending an unverified login repair. The absence of an HTTP response must remain distinguishable from HTTP 401/403/429.
2. Regression tests exercise the **real transport exception handling** with synthetic `URLError(SSLCertVerificationError(...))`, DNS/connection errors and timeouts, not only preconstructed `UsageResponse` objects. Verify the resulting provider evidence and visible account state, existing HTTP/auth-method behavior, and recovery on a later successful response.
3. Investigate the affected Windows failure and document the established cause and secure remediation, separating verified facts from remaining chain/proxy hypotheses. Re-run a bounded live quota check through the production acquisition path after any authorized remediation. A valid-chain, eligible-account success must publish native quota normally. If an external certificate/environment issue still prevents this, retain the precise limitation; neither the unauthenticated Windows 401 nor passing fixtures count as a successful quota fetch.
4. TLS certificate and hostname verification remain enabled. Do not accept expired/untrusted certificates, disable verification/revocation safeguards, install certificates, alter the machine clock/proxy/trust store, silently choose a different account/credential source, refresh tokens, or automate sign-in as a workaround. Any genuinely required external environment repair needs separate explicit authority.
5. Diagnostic export uses bounded allowlisted categories/numeric codes only. No tokens, authorization headers, account identifiers, certificate subjects, raw responses or arbitrary exception messages are persisted or published. Keep the existing per-provider isolation and bounded retries; a persistent certificate failure must not cause request storms or block other quota integrations, and normal refresh can recover after repair.

## Non-goals

No implementation is included in this authoring request. Do not change quota semantics, resurrect old OpenAI capacity after a failed lookup, introduce another quota endpoint, perform paid inference, restart shared OpenCode, or broaden this into a general account/HTTP rewrite. Do not add a permanent release gate or reserve a release version.
