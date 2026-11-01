# Sanitized investigation: OpenAI quota TLS failure on Windows

## Provenance and bounds

- Investigated on 2026-10-30 following the owner's screenshot of Cost Guard **v80.116** Watch, started at local 20:28:10, displaying `OpenAI Quota error (network unavailable)`.
- The existing checkout was at `a554d312fecc7d7db31ae6aebe7819418c18c11c`, **v80.112**. Its diagnostic run reproduced the same normalized error. It was not updated or used as proof of the screenshot's version.
- A separate detached worktree of the actual remote `main`, `c27d49973344d57a61d910314bde3a9445091e98`, **v80.116**, reproduced the failure. The OpenAI reader, account diagnostic sanitizer and shared account presentation had no changes between those revisions.
- Runtime: **CPython 3.14.8**, **Windows AMD64**. Source selection reported healthy **OpenCode V2 service 2.2.2**. No user-config override was present in the current-main diagnostic run.
- No prompt inference, credential renewal/write, login, account switch, certificate-store change, TLS verification bypass, shared-service restart or desktop/browser automation was performed.

## Product Diagnostics

Executed the repository's collector on both revisions:

```text
py -3 development/tools/collect_diagnostics.py --snapshots 1 --skip-validation
```

The current-main run used a separate output directory. Its bundle was generated at **2026-10-30T19:32:11.115286+00:00**. Collector completion was successful; report acquisition took approximately **8.1 seconds**. This command deliberately skips full local tests and package validation; it is not evidence that either passed.

Relevant allowlisted OpenAI observation, omitting account hashes and unrelated usage:

```json
{
  "provider": "openai",
  "availability": "error",
  "status": "unknown",
  "plan": null,
  "components": [],
  "quota_shape": {
    "account_header_present": true,
    "credential_category": "legacy",
    "endpoint_family": "wham",
    "http_status": 0,
    "parser_reason": "network_failure",
    "request_attempted": true
  }
}
```

Copilot returned native quota with HTTP 200; Claude Code returned available native windows. Those observations support isolation to this OpenAI request, not a universal proof that every network route is healthy. The current-main bundle had no persisted `watch_account_refresh` evidence: no historical Watch retry/publication sequence is claimed. Diagnostic Watch rendering reuses report observations and is not a new successful quota retrieval.

## Actual product-transport exception

A temporary read-only probe constructed the normal OpenAI provider using the repository's `_account_providers` and configuration loader, then called `get_account_snapshots()`. It wrapped `urllib.request.urlopen` only to collect allowlisted exception metadata and re-raised the original exception unchanged. The product supplied credentials in memory through its existing transport to its existing fixed URL; no credentials, headers, records, account IDs, response bodies, certificate subjects or arbitrary exception strings were exported.

Two bounded attempts reproduced the same exception chain. The second took approximately **1.079 seconds** and yielded:

```json
{
  "exception_type": "URLError",
  "reason_type": "SSLCertVerificationError",
  "reason": {
    "exception_type": "SSLCertVerificationError",
    "errno": 1,
    "tls_verify_code": 10,
    "tls_certificate_verification_failed": true,
    "tls_verify_category": "certificate_expired"
  }
}
```

`certificate_expired` was emitted only after exact comparison with the known safe `verify_message` value `certificate has expired`; raw messages were not printed. The provider nevertheless returned only HTTP status 0 / `network_failure`. The failure is therefore TLS certificate verification **before an HTTP response**, not a verified OpenAI authentication rejection or exhausted subscription.

## Credential-free Windows comparison

A separate PowerShell/.NET `HttpClientHandler` probe made one GET to the **same maintained URL** `https://chatgpt.com/backend-api/wham/usage`, using default TLS verification, `AllowAutoRedirect=false`, `UseCookies=false`, and `UseDefaultCredentials=false`. No Bearer token or account header was supplied. The successfully recorded result was:

```json
{
  "probe": "credential-free Windows default TLS",
  "tls_validation": "passed",
  "http_status": 401,
  "local_utc": "2026-10-30T19:33:49.8870874+00:00",
  "server_date_utc": "2026-10-30T19:33:50+00:00"
}
```

An initial attempt reached response-processing code but its diagnostic date formatting failed; it was not treated as transport evidence. The corrected probe above is the recorded comparison. No authenticated request was retried through .NET or any other alternate route.

The Windows result shows verified reachability for that credential-free client and approximate agreement with the returned server clock. It does **not** prove which certificate Python rejected, that both clients used identical chain-building/proxy paths, or that an authenticated Windows quota request would succeed. It is an investigation lead for runtime trust/chain/transport behavior, not permission to replace production authentication or weaken TLS.

## Reproducible information-loss defect

At the checked v80.116 source:

- `src/accounts/openai_subscription.py:58-63`: `UsageResponse` has `network_error` but no retained TLS/DNS/timeout category.
- `src/accounts/openai_subscription.py:211-231`: `_default_usage_get` catches `URLError`, `TimeoutError` and `OSError` together and returns `UsageResponse(False, network_error=True)`.
- `src/accounts/openai_subscription.py:488-490`: `_request_quota` turns this into `availability=error`, `http_status=0`, `parser_reason=network_failure`.
- `src/accounts/diagnostics.py:8-18`: the export allowlist currently has no TLS verification category/code.
- `src/presentation/accounts.py:18-21,203-213`: `network_failure` becomes the visible `network unavailable` cause.

A synthetic probe patched the **real transport's** `urllib.request.urlopen` to raise each of these separately; no network or real credential was used:

| Injected failure | succeeded | HTTP status | network_error |
| --- | --- | --- | --- |
| `URLError(SSLCertVerificationError(...))`, verification code 10 | false | 0 | true |
| `URLError(socket.gaierror(...))` | false | 0 | true |
| `TimeoutError(...)` | false | 0 | true |

This establishes the deterministic information loss independently of whether a later live request recovers. Add regression coverage at this boundary, then verify normalization, safe export, visible failure and recovery rather than testing only a manually assembled `UsageResponse`.

The existing focused suite was also executed on current main:

```text
py -3 -m unittest development.tests.test_openai_account_switch
Ran 17 tests in 0.826s
OK
```

Those passing tests protect existing identity/method/error semantics but do not establish live TLS/quota success or full-suite/package acceptance.

## Retention and remaining questions

Original ZIPs remain local under `diagnostics/` and are intentionally not committed. This attachment contains only manually reviewed, minimal investigation facts, not raw workstation diagnostics, account/usage histories or executable probe files.

Still to establish: the failing certificate/chain element and its source; the Python-versus-platform trust/proxy difference; an appropriate secure remedy; and successful native quota acquisition through the production path after any authorized repair. Do not infer a subscription plan, expired OAuth credential, incorrect machine clock, upstream certificate outage, or a particular proxy from the evidence above.
