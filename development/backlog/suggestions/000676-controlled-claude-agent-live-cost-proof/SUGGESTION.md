# Suggestion 000676 — Controlled Claude Agent end-to-end live cost proof

**Non-executable owner inbox proposal; no Ready priority or implementation approval.**
Origin method: `selected-worker-deferral`, Cost Guard FR000673, 2026-11-11.
Source revision: `5f73225ccbbb0a890f3c2ff50fc0ae1862ad2395`.
Owning integration: OpenCode Claude Agent invocation/source contracts; origin and
verification consumer: Cost Guard. No change in another repository is authorized.

## Deferred capability, not an established product bug

FR000673 requested one tiny, bounded subscription-only live prompt per actually
available Claude Agent selection, then sanitized proof of recorded model/usage,
canonical prompt/session/Watch/Sessions detail/CLI/global Today CCost and qualified
Claude Pro account Today/5h/weekly contribution. **13 models were enumerated,
0 prompts submitted, all 13 live cases NOT RUN.** Catalog valuations and synthetic
browser integrations do not establish real-request route, usage or end-to-end proof.

The active Decision Delegate explicitly accepted scoped completion of FR000673
excluding these inference cases after investigating meaningful alternatives, using
the FR's safety-skip provision. It required this separable follow-up in Cost Guard.
Correctness, billing isolation, deterministic matrix, browser checks and normal
verification were not waived. FR000675's separate cross-provider/midnight work
remains required and must not treat this missing live proof as established.

## Evidence and attempted alternatives

Installed OpenCode **v2.2.7** was compared with its matching published source:

- `generate.ts::runText` takes prompt/model, uses one-shot retry and does not expose
  an output cap, deadline/cancellation or a durable test Session. Claude Agent's
  `doGenerate` rejects non-streaming calls. This is not a safe substitute.
- Native Sessions streaming uses composed agent/global/project instructions and
  tools. Its public contract does not expose the required cap/instruction isolation.
- `plugin/provider/claude-agent/claude/query-options.ts` fixes adaptive thinking;
  `claude/sessions.ts` only sets the output-token environment cap when a caller
  explicitly supplies one, without its own inference deadline. Safe SDK hooks/settings
  isolation alone does not supply all requested controls through these public paths.
- Provider `cost: []` also occurs for gateways/custom endpoints, so it and current
  CLI Pro login alone cannot certify an individual request's subscription route.

No speculative prompt, credentials/transcript access, private-history export,
shared configuration mutation, service restart or API-paid fallback was used.
Source links start at the matching
[v2.2.7 core](https://github.com/anomalyco/opencode/tree/v2.2.7/packages/core/src).
The [journal](../../../journal/claude-agent-ccost.md) retains the complete sanitized
inventory, synthetic reference results and uncertainty.

All live cases skipped: `opus`, `sonnet`, `claude-fable-5-2`, `haiku`, `fable`,
`claude-haiku-4-5-20251001`, `claude-sonnet-5`, `claude-opus-5`, `claude-fable-5`,
`claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`, `claude-sonnet-4-6`.
Eleven have supported current reference rates; Opus 4.7/4.6 are genuinely absent
from the observed reference source. This is a dated inventory, not an allowlist.

## Smallest desired future outcome

When explicitly approved, use a supported controllable invocation path (or a small
upstream integration improvement if genuinely necessary) to establish the deferred
real-request proof. No mandatory generic testing framework is proposed. First
recheck public capabilities and current model inventory; retain independent safe
skip/unknown states if controls or subscription provenance are still unavailable.

Acceptance: each eligible selection has one isolated tiny subscription-only call,
finite output/time bounds, no tools/chains/agents/project content/extended reasoning,
no uncertain retries or paid fallback; sanitized recorded identity/usage and reference
price provenance reconcile through all original FR000673 views/scopes. Unknown
prices remain unavailable, native percentages remain independent and actual billing
is never inferred from reference value. Report enumerated/submitted/skipped counts
and per-model outcomes truthfully, without collecting private conversations.

Targeted semantic deduplication found no equivalent proposal: suggestion000400 is
Legacy retirement; completed FR000651 permits catalog estimates and does not supply
controlled live execution; FR000675 owns links and cross-provider midnight tests.
This proposal retains only FR000673's independently missing controlled live proof.

## FR000687 evidence update — 2026-11-12

Origin method remains `selected-worker-deferral`; source baseline `b3e6cb4`,
reconciled default `696eaba`. The original FR000673 evidence above is preserved;
its zero-submission count is historical, not the current FR000687 outcome.

Under a bounded task-local AISDK-native guard, **13 selectable models, six admitted
submissions, five native completions, one failure, seven NOT RUN**. Sonnet/Opus/
Haiku/Fable aliases and concrete Fable5.2 completed. Exact provider/selector persisted;
observer metadata independently showed Sonnet5.5, Opus5.5, Haiku5.5, Fable5.1 and
Fable5.2. Five saved payloads reconcile through production pure normalization,
exact-location current catalogs and fresh reference pricing to nonzero CCost.
That is **owned saved-request replay**, not full-catalog native end-to-end PASS.
The [sanitized matrix and boundaries](../../../journal/recorded-model-help.md) distinguish
recorded selectors, observer execution and mutable catalog estimates.

The sixth selection, `claude-haiku-4-5-20251001`, forwarded once at cap32, emitted
four distinct response identities, then failed with native output-cap/provider error
and **no final usage**. No uncertain retry/increased cap was attempted. Four native
responses are not four owner submissions or proven billed tokens. All further
inference was stopped by the foreground Decision Delegate. Seven selections in the
matrix remain NOT RUN; the original future per-catalog acceptance remains unmet.

Production normalization of the failed saved assistant creates zero usage requests;
the unchanged empty observed aggregate displays **0** with `0 == 0` priced/observed
completeness. This is not evidence of zero consumption. P2 now retains the exact
saved **recorded selection** and says **Usage unavailable; cost unknown**, without
inventing a cost part, call or contributor. The receiving foreground Delegate
explicitly authorized retaining this numeric-display ambiguity as a nonblocking
P2-only limitation. Future controlled proof must distinguish no usage from an
explicitly reported zero, and decide a clear failed-no-usage numeric presentation
without altering actual accounting to manufacture a PASS.

Required future outcome still includes safe complete native execution/route/usage
and per-view/account reconciliation, with supported controls for native multi-response
and output-cap failure, no speculative replay. Historical private-session diagnosis
is **separate**, tracked by [Suggestion000691](../000691-authorized-historical-claude-identity-recovery/SUGGESTION.md).
No new inference or implementation is authorized by this evidence update.
