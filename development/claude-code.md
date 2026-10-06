# Claude Code account and reference identity contract

## Summary

v78.25 discovers the CLI-owned Claude account independently of experimental quota collection. OpenCode owns selectable models; pricing owns exact/verified reference identities; shared report/Watch projections need no Claude-specific branches. No Claude credentials are read/copied and current login is not historical account/billing evidence.

## Account and transport

- `accounts/claude_code.py` uses `claude auth status --json` to normalize current login, backend, plan and a hashed source/account identity. First-party `claude.ai` proves subscription semantics; API/external backends do not inherit a Pro plan. Registration alone proves neither login nor plan.
- `accounts/claude_transport.py` invokes only the optional installed official CLI, resolved from PATH. It uses the published Agent SDK's `initialize` and experimental `get_usage` control requests over stream-json. The latter is equivalent to `Query.usage_EXPERIMENTAL_MAY_CHANGE_DO_NOT_RELY_ON_THIS_API_YET({skipBehaviors:true})`, with `skip_behaviors: true` on the wire. It sends no user messages or model prompts. No JS runtime or third-party Python package is needed.
- This is an unstable SDK/CLI control contract, not a guaranteed API. A successful matching control response detects support; explicit unknown-request errors mean unsupported capability. Changed shapes, transport errors and timeout fail softly. Account discovery does not depend on quotas. The helper disables hooks, MCP, Chrome and persistence, uses empty setting sources, closes pipes and reaps its private process after collection. It never stops OpenCode.
- `accountInfo.organization` is an organization **name**, whereas auth status supplies both `orgId` and `orgName`. Match email/name for quota provenance; retain the distinct organization ID for account identity. Do not equate the two fields or expose them in reports/diagnostics.
- Native percentages and timezone-qualified ISO reset times normalize inside the Account Provider. Missing/malformed windows remain partial/unknown; supported model-family and OAuth-app windows keep model/surface scope, without invented request-model IDs. No quota-to-dollar extrapolation or extra-usage billing inference occurs.
- `anthropicQuota.enabled` gates both API and Claude discovery; `authJsonPath` remains API-inventory-only. Watch's normal minute cadence, five-minute stale TTL and bounded 5/10/20-second recovery retries own scheduling. No helper runs per redraw/source event. Durable auth/capability failure clears stale quotas but preserves the account row. A window with utilization `0` and an explicit null `resets_at` has not started yet (`window_active=False`) and is complete, not partial.

## Model identities

`sources/model_availability.py` accepts opaque enabled selectable `id` values, including `[1m]`, and rejects controls/bidi/whitespace/malformed contracts. The working registered API never needs model CLI fallback. Empty/disabled-only responses are authoritative; actual failures retain the explicit full-pricing-catalog warning.

`pricing/identities.py` owns reviewed aliases, not generic date/suffix stripping. Haiku 4.5's pinned `20251001` ID maps to its documented base alias. A bounded set of documented Claude versions recognizes `[1m]` as context capacity. Exact catalog variants win before alias resolution; ambiguous matches return unknown. Existing input-token thresholds select long-context rates, not the suffix by itself. Availability/reference valuation never replaces actual billing. Unsupported Fast/other variants still have no guessed price.

## Evidence and limits

Synthetic tests cover parser/control safety, dated/context/explicit-rate identity, tier boundaries, method absence, changed format, timeout/private-helper cleanup, auth failure, missing/scoped windows, account swaps, discovery failure/logout, report/Watch visibility and shared cadence/stale expiry. Neighboring OpenAI/Copilot/API accounts coexist without attribution changes.

Read-only workstation evidence on 2026-10-04 used installed official Agent SDK **0.3.289** types/method and Claude CLI control behavior. The metadata-only probe observed **zero model usage**, Pro, five-hour/weekly utilization and ISO resets, then closed its process. The current OpenCode list had **42 models**, **14 Claude IDs**, **eight `[1m]` IDs**; parsing/filtering succeeded without model CLI fallback. Twelve Claude selectable IDs had reference prices; `claude-opus-4-7` and `claude-opus-4-6[1m]` lacked prices in the current catalog and stayed omitted. Live report/Watch showed Claude Pro/windows; process-local timeout/capability simulations retained stale/account semantics and normal redraw made no quota call. Event-stream hints were disabled for this bounded authoritative-snapshot check; it is not a new SSE/restart/sleep claim.

The user's older external diagnostics/probe paths were absent locally. They were not reconstructed or packaged. Fixtures contain synthetic data only. Live Pro success does not establish every plan/backend/SDK version; unsupported installations must continue to show unavailable quotas safely.

References: [TypeScript SDK](https://code.claude.com/docs/en/agent-sdk/typescript), [SDK changelog](https://github.com/anthropics/claude-agent-sdk-typescript/blob/main/CHANGELOG.md), [usage command](https://code.claude.com/docs/en/costs#using-the-usage-command), [model configuration](https://code.claude.com/docs/en/model-config), [pinned model IDs](https://platform.claude.com/docs/en/about-claude/models/overview).
