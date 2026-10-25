# FR 000150 completion — method-compatible OpenAI quota lookup

Implemented in Cost Guard v80.75 (2026-10-25), based on default revision `7af187a71c455a70a6eec9e7c79da1af985fb20d`.

## Delivered behavior

- OAuth `methodID` and metadata/JWT token-sharing scopes classify the credential before a quota request. Explicit token sharing, including migrated browser metadata, never sends the bearer to legacy WHAM. Unfamiliar OAuth methods also fail closed; historical methodless Codex storage and browser/headless methods retain existing supported retrieval.
- Token-sharing accounts remain configured but show a specific unavailable-for-this-sign-in-method explanation. They do not inherit a plan, native quota or a failed-login/reconnect diagnosis. Actual model authentication is neither changed nor inferred from quota availability.
- Legacy requests retain real returned plans, windows and credits, optional account headers and generation/alias/removal behavior. A 401 establishes quota-request rejection only; 403 access denial, 429 throttling, expiry, parser and network outcomes remain distinct. Sanitized Diagnostics exposes only method category, endpoint family, header presence and request-attempt state.

## Real-machine evidence and explicit limitation

Read-only inspection ran on the affected Windows installation with healthy OpenCode 2.1.4. It queried only OpenAI credential rows using SQLite read-only/query-only mode, and inspected the supported OpenCode integration/provider APIs and installed OpenAPI schema inside a local process. The active integration connection matched the current active credential record. The record was unexpired, used `chatgpt-token-sharing`, carried token-sharing/invoke scopes and an API-resource audience, and had no ChatGPT account identity. The effective provider route was `https://api.openai.com/v1`, whereas the previous quota reader unconditionally selected ChatGPT WHAM.

The installed schema contained no usage/limits routes. The newer documented experimental usage route was unavailable locally. Public upstream token-sharing source corroborates the distinct API-resource flow but is not assumed byte-identical to the installed binary. No supported compatible read-only quota source was established for this installed method.

Headless checks pinned the freshly read OpenAI records and exercised separate real account acquisitions for report and Watch, Watch reconciliation, report account rendering and Watch capacity rendering. Both produced one method-specific unavailable account, no stale quota, no reconnect instruction and **zero quota HTTP requests**. These are bounded real-installation account checks, not a complete terminal/GUI capture.

**Functional gap remains:** real token-sharing quota values are unavailable. An authenticated quota 200 was NOT demonstrated, and a legacy account was not probed because it is not the current eligible identity. WHAM probing with the known API-resource token was deliberately NOT RUN. The server-side reason for the historical 401 remains unproved; the incompatible client method/resource selection is established. No guessed endpoint, identity switch, token refresh, credential write, paid inference or shared-service restart was performed. This delivery fixes compatibility and false authentication diagnosis, not missing upstream quota support.

## Verification

- Focused account regressions: 40 tests PASS after updating the obsolete blanket-401 wording assertion to enforce the new quota-vs-model-auth boundary.
- Full repository suite: **93 files PASS**, zero failures (81.0 seconds, four workers). Working-tree validator: **PASS**, zero failures, four existing/design-budget warnings. The README release summary initially crossed its hard byte cap; it was shortened without changing the cap, and focused foundation checks plus the complete suite passed afterward. No ZIP was built.
- Coverage includes token-sharing methods/scopes, unknown methods, legacy browser/headless methods, missing headers, active/inactive independent accounts, alias suppression, externally changed generations, expiry, 401/403/429, unknown plans, Watch/report parity and secret-free observations. Existing synthetic read-only database/auth checks remain intact.

## Knowledge, privacy and scope

Updated the existing OpenAI identity journal and account-support documentation with verified method/resource evidence and remaining limits. Architecture assessment: **no-update**; responsibility/dependency boundaries remain unchanged inside the existing account adapter and allowlisted diagnostics. No generic helper, dependency, endpoint, provider polling or CCost behavior was added.

No screenshot, diagnostic ZIP, raw API body, credential/token/token hash, personal account identifier or local machine path is included. The specification is preserved unchanged; the bundle contains only FR.md and this reviewed completion report. No retained completions were selected for pruning and no cross-FR dependency is needed to preserve this repair.
