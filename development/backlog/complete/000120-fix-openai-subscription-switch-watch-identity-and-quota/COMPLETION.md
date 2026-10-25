# FR 000120 completion — OpenAI account replacement

Implementation candidate: [38ad8e20880e1b81cc740a028a91c258e913068f](https://github.com/qstoffe/cost-guard/commit/38ad8e20880e1b81cc740a028a91c258e913068f). Native delivery records the verified PR and squash merge separately.

## Delivered behavior

- Canonical V2 inventory suppresses stale legacy OpenAI aliases; proven OAuth aliases collapse by source-aware account identity, preferring canonical V2 records. Distinct configured accounts remain visible.
- Authoritative OpenAI removal publishes explicit removed keys through the existing coalesced mailbox. Watch drops superseded rows instead of preserving unavailable tombstones. Requests remain pinned to immutable discovery generations; obsolete in-flight output is discarded.
- Failed OpenAI retrievals clear prior quota; partial payloads cannot restore missing prior windows or an unknown former plan. Safe novel returned plan identifiers preserve successful native windows without price/tier inference.
- HTTP 401 retains actionable rejection status; 403 reports endpoint access denial rather than claiming a bad login. Unrecognized successful payloads report parser failure. Credential expiry includes nested/JWT evidence; no auth refresh, write or alternative-identity retry was added.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, 91 test files, final run 75.3 seconds. This includes the new deterministic switch/alias/generation/recovery regressions and unchanged provider suites.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, zero failures; existing design-budget warnings remain, no caps raised.
- Focused repair recheck: 46 tests PASS. Initial Full detected a README hard-cap overrun (shortened current-version summary) and legacy OpenAI stale-retention assertions. The generic retention regressions now explicitly retain Copilot coverage with unchanged assertions; dedicated OpenAI regressions prove the newly required clearing behavior.
- Local read-only Diagnostics collection (`network=False`, zero session snapshots): V2 available/healthy and source selected; V1 available but not healthy. No paid requests, external quota calls, service restarts or auth/database writes were performed. No diagnostic archive or private machine evidence is committed.

## 401 investigation and limits

The sanitized v80.65 evidence establishes an upstream 401, not a valid replacement token or paid-tier compatibility. Source inspection found per-integration fallback could resurrect a legacy alias, while acquisition intentionally retained superseded unavailable rows. Those software defects are fixed and synthetic stale/current token-and-account requests prove 401-to-200 recovery only after external credential replacement.

OpenAI's public Codex backend client still uses ChatGPT backend-api usage routing, bearer auth and `ChatGPT-Account-Id`; it also recognizes new plan variants. Reference inspected 2026-10-25: <https://github.com/openai/codex/blob/main/codex-rs/backend-client/src/client.rs>. This moving upstream reference is supporting context, not a stable API guarantee. The historical user's exact 401 cause and real upgraded-tier quota success remain unverified; no unsupported root-cause or success claim is made.

## Scope and knowledge

Cost Guard v80.72, dated 2026-10-25; no ZIP, tag or GitHub Release. FR 000130 and FR 000140 remain independent and pending; no CCost, timing or terminal geometry changes. Architecture assessment: no boundary changes, no architecture update. Journal assessment: retain the reusable distinction between identity-selection defects and insufficient 401 evidence in the account-identity topic, with source/tests authoritative.
