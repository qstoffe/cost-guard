# Claude Agent reference pricing and Claude Pro CCost — FR000673

2026-11-11, v81.24; base `5f73225ccbbb0a890f3c2ff50fc0ae1862ad2395`.
This is scoped completion, **not full all-model live execution acceptance**.

## Independent reproduced causes and repairs

**A1:** exact Desktop catalog entries can retain an alias as `modelID` and a short
label such as `Opus 5.5`. The old fallback handed that unbranded label to the exact
reference catalog, producing N/A even with supported rates. A source-shaped
Opus/Haiku/Fable/future-family matrix reproduced four unavailable valuations before
the fix. Opaque selections now use exact location/provider/id catalog observation;
concrete upstream modelID wins, otherwise the observed name is branded `Claude `
without guessing a version. Recorded releases bypass this path. Unknown catalog
entries/rates remain unavailable. Token dimensions, efforts and prices are unchanged.

Catalog signature 2 and model identity semantics 3 repair dependent short-label or
negative cached projections. Pinned/unrelated entries retain reuse; raw history,
physical request deduplication and actual billing are unchanged. No family allowlist,
fuzzy price substitution, global rate-signature reset or cache purge was added.

**A2:** canonical `claude-agent` usage was indexed separately from `claude-code`
account scopes. The source-shaped $0.06 / independent native 1% fixture reproduced
positive session cost excluded from the Pro period. Reference-only compatibility
now combines lanes for an authenticated first-party subscription and marks sole
compatible unassigned usage **estimated**, never verified billing. Exact account
references win and can survive current sign-out. Billed or foreign-account Agent
entries cannot become Pro estimates; multiple compatible accounts remain ambiguous.
API/Anthropic/Bedrock/Vertex/OpenRouter publishers are not blanket-remapped.

Today, 5h and weekly reuse canonical unrounded reference costs and one shared account
projection, with unchanged quotas/polling and strict actual-billing path. Tests cover
exact interval bounds, changed reset, partial price/history, removed/other/signed-out
accounts, zero reported cost with UNKNOWN disposition, clone dedup and mixed routes.
Positive stored OpenCode dollar costs become BILLED in causal normalization and are
conservatively excluded from Pro compatibility; no live request here proves the
unseen subscription record shape or explains the owner's dollar display.

**B:** main v81.23/FR000674 already supplies measured source phases/work and 500ms
visible pending reads, reverting to normal 5s/hidden 30s cadence. The FR's earlier
static trace is stale. No redundant runtime loader patch was needed. A deliberately
delayed real supervised capture now tests first readiness between polls; see
[the separate loading evidence](web/session-loading.md#first-load-measurement-fr000673).

## Actual read-only inventory and synthetic valuation

The location-qualified official connected catalog enumerated **13 selections**.
The normal public [reference article](https://docs.github.com/api/article/body?pathname=/en/copilot/reference/copilot-billing/models-and-pricing)
had SHA256 `c5bf130105d8186e055bba1c19b54f8ee6d59b56ad73c73826d339c6ffe1cb5b`.
For synthetic I1000/C2000/W100/O10 tokens the following credits were computed against
that actual catalog/reference source. These are **not executed prompt costs**.

| Selection | Observed modelID | Observed name | Synthetic CCost | Live inference |
| --- | --- | --- | ---: | --- |
| `opus` | `opus` | Opus 5.5 | 0.5100000 | NOT RUN |
| `sonnet` | `claude-sonnet-5-5` | Sonnet 5.5 | 0.2550000 | NOT RUN |
| `claude-fable-5-2` | same | Fable 5.2 | 0.9800000 | NOT RUN |
| `haiku` | `haiku` | Haiku 5.5 | 0.0137500 | NOT RUN |
| `fable` | `fable` | Fable 5.1 | 1.2250000 | NOT RUN |
| `claude-haiku-4-5-20251001` | same | Haiku 4.5 | 0.1375000 | NOT RUN |
| `claude-sonnet-5` | same | Sonnet 5 | 0.2750000 | NOT RUN |
| `claude-opus-5` | same | Opus 5 | 0.6875000 | NOT RUN |
| `claude-fable-5` | same | Fable 5 | 1.3750000 | NOT RUN |
| `claude-opus-4-8` | same | Opus 4.8 | 0.6875000 | NOT RUN |
| `claude-opus-4-7` | same | Opus 4.7 | N/A: model_absent | NOT RUN |
| `claude-opus-4-6` | same | Opus 4.6 | N/A: model_absent | NOT RUN |
| `claude-sonnet-4-6` | same | Sonnet 4.6 | 0.4125000 | NOT RUN |

Eleven priceable selections; Haiku5.5 exposes two reference tiers, other supported
entries one. The deterministic 13-shape matrix uses explicitly synthetic rates
and checks prompt/session/Watch/detail/CLI/global Today parity and unavailable
diagnostics, independently of these dated public rates. Future unknown-family and
catalog-turnover/cache tests prevent the inventory becoming a production allowlist.

Official CLI metadata also discovered one authenticated first-party Pro account
with supported 5h/weekly reset/fraction metadata. The observed Fable-specific window
lacks an exact model_id and remains unsupported for model attribution. No account
identifier, native private percentage or transcript was copied into this evidence.
Current login and empty provider prices do not prove the route of an old request.

## Live-proof exclusion and decider

**13 enumerated / 0 submitted / 13 NOT RUN.** The active foreground **Decision
Delegate** authorized scoped completion excluding all live inference cases under
the FR safety-skip provision after investigating alternatives. It required the
published, non-executable [Suggestion000676](../backlog/suggestions/000676-controlled-claude-agent-live-cost-proof/SUGGESTION.md).
This is a substantial excluded acceptance item, not 13 failed executions or full
live PASS. Other correctness/browser/normal verification requirements were not waived.
FR000675 remains independently required and inherits no claim of actual live proof.

Installed OpenCode v2.2.7 and the matching published
[core source](https://github.com/anomalyco/opencode/tree/v2.2.7/packages/core/src)
were inspected: `generate.ts::runText` is prompt/model-only, retries one-shot, lacks
test Session/output cap/deadline, and Claude Agent `doGenerate` rejects non-streaming.
Native streaming Sessions compose agent/global/project instructions and tools with
no public safe cap/isolation controls. `plugin/provider/claude-agent/claude/query-options.ts`
fixes adaptive thinking; `claude/sessions.ts` only forwards an output cap when
explicitly supplied and has no own inference deadline. Safe hook/settings isolation
does not fill these gaps. Empty provider `cost: []` also covers custom gateways;
current Pro auth alone cannot prove request-specific subscription routing.

Initial guessed package/npm URLs returned404; known FR000651 source references led
to the matching successful monorepo reads. No speculative inference, shared config
mutation, new agent install, service stop, API-paid fallback or credential/private
transcript recovery followed. The follow-up asks for the smallest supported safe
proof, not a mandatory new framework.

## Verification and limits

- Inherited completed Full: **183/183 test-file groups PASS**, zero failures,
  147.7s, four workers, 240s/file timeout. Its native completion notification is
  retained; checkpoint quiescence separately marked it finished but exit-unconfirmed,
  not a new OS process-exit audit. No conflicting expensive rerun was started.
- Final focused alias/account/cache run after the added 13-shape test: **41 PASS**,
  4.798s. Its first run failed assertion shapes (Decimal serialization precision and
  internal known subtotal versus unavailable comparison), not a product regression;
  corrected assertions now check public completeness/unknown diagnostics explicitly.
- Additional quota lifecycle/Web quota/detail regression run: **44 PASS**, 11.117s.
- Working-tree validator: **PASS**, 11 passes, zero failures/seven pre-existing
  advisory design/prose warnings; `git diff --check` passed. No hard cap was raised.
- Hidden Chrome157 authenticated host/HTTP/SSE Accounts/Full plus actual Mini renderer:
  **PASS**, synthetic source-shaped Opus alias -> canonical $0.06 -> qualified Pro
  5h/weekly/Today alongside independent 1%. Mini renderer integration is not native
  PiP/OS interaction proof; no duplicated browser-side cost calculation was added.
- Existing loading/layout probe: **PASS**, 48 real Chrome Classic/Web light/dark
  layouts, 360/768/1366/1920 widths, 100/125/150% CSS zoom and reduced motion;
  1001-row authenticated capture, controlled 220/1/0 rows, cancel/hidden/back/focus/
  selection/outage checks. No new native-page-zoom, physical input or macOS claim.
- Delayed first load: **PASS**, 7654.2ms total, publication-to-begin224.8ms and
  publication-to1001-row-DOM1172.1ms. First attempt failed an arbitrary DOM<1500ms
  gate at1602.3ms during Full. Final gate distinguishes readiness discovery<1250ms
  from bulk1001-row transfer<3000ms; no product timeout was enlarged.

Local sanitized artifacts: `scratch:/catalog-evidence.json`, `scratch:/claude-account.json`,
`scratch:/first-load.json`, `scratch:/loading-layouts.json`. An earlier `--all-models`
CLI probe unexpectedly performed ordinary report history sampling; it was not
repeated or presented as history-free. No raw history was published. Source/billing
unknowns and the owner's exact private incident remain unproven. Final validator
and release/delivery results are recorded in the completion report.
