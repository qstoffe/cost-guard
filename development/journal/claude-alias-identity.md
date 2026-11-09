# Claude alias identity and historical repair — FR 000629

## FR 000651 — owner-approved Desktop catalog estimates (v81.6)

2026-11-09, implementation base `9fda560e05a88345996a25c1e3d98b325e4d927a`.
This supersedes the **earlier hold and conservative alias-only valuation** below,
not its source findings. The selected FR expressly accepts a potentially historically
wrong current-catalog release and matching reference CCost. That is the delivered
behavior; it is not a new claim that old executed response metadata was recovered.

### Fresh evidence and remaining source boundary

- Read the public v2.2.6 source at `dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06`:
  `gui-plugins/src/context/catalog.ts::catalogModel` requires the location's provider
  and model lists, exact provider/alias matching, and skips deprecated entries;
  `tab.tsx:136` displays `entry?.model?.name ?? message.model.id`.
- `claude-agent/provider.ts` keeps current SDK names/resolved IDs, not historical
  response certificates. The converter at `convert-claude-stream.ts:35` emits actual
  `response-metadata.modelId`; `core/src/aisdk.ts:748–753` explicitly drops this event
  with `Effect.succeed([])`. No installed binaries, databases or upstream records
  were changed. No speculative future history field is accepted as verified input.
- A fresh authenticated **read-only current catalog** observation at the repository
  location returned `providerID=claude-agent`, `id=sonnet`, `name=Sonnet 5.5`,
  `modelID=claude-sonnet-5-5`. This is live mapping evidence, **not** a historical
  assistant capture. No prompt or private session content was exported.
- The exact owner historical session ID was not supplied. The checkpoint/official
  SDK transcript join was **NOT PERFORMED**; another session was not substituted.
  Actual historical recovery and future upstream response-model persistence remain
  **UNVERIFIED / NOT IMPLEMENTED**, respectively. The revised fallback delivery gate
  explicitly permits this useful result without those unavailable prerequisites.

| Available evidence | Result |
| --- | --- |
| Recorded concrete request model | Existing exact identity/pricing wins and has no mutable alias dependency. |
| Alias plus source-proven executed response | Still requires a supported response-qualified upstream contract; no real capture or arbitrary native-field trust is claimed. |
| Alias plus exact current location provider/model entry | Desktop label and supported exact reference rate are an explicitly accepted estimate. |
| Missing entry, unsupported concrete price identity, or incomplete usage | Real unavailable/partial cost; never guessed generic Sonnet pricing or manufactured zero. |

### Ownership and dependency design

`opencode_v2_model_identity.py` reads only supported location-qualified provider/model
GETs, at most one pair per location/30 seconds within a reader (bounded 256-location
observation cache). There is no catalog-sync mutation, CLI fallback, inference,
daemon or per-cell read. `ModelRef` keeps the effective identity/display name and an
optional `ModelResolution` with the recorded alias, location mapping dependency and
`desktop-catalog-estimate` provenance. Provider and request effort stay unchanged.
Native observations are not rewritten. Catalog labels without supported rates may
still display, but reference valuation never uses fuzzy matching for those rows.

Model resolution is separate from native-history consistency brackets and the global
price signature. `MODEL_IDENTITY_SEMANTICS=2` repairs prior affected conclusions on
access. Derived analysis validates compact model dependencies before reuse; Sessions,
Token Mix, AI Stats and matched-run caches do likewise, including failed exact lookups.
Cold-process hits validate before returning old values. Pinned roots need no catalog
read and keep their cached entries; mixed root-cost checkpoints revalue only changed
request fingerprints. Clone deduplication uses the **recorded alias**, never a mutable
catalog identity. Alias-only availability filters retain their resolved requests.

Shared canonical projections supply CLI, Sessions/detail, Full/Mini Watch, model/cost
groups and Token Mix. Cost/model help and Comparisons retain alias/estimate explanation;
ordinary rows have no new alarm badge. Catalog estimates never enable monetary billing
fallback. Recorded concrete models and other providers retain their existing behavior.

The read-only Decision Delegate recommended source-owned materialization, explicit
cache dependencies, original-identity clone deduplication and alias availability
preservation. No acceptance waiver or access expansion was requested or granted.

### Verification

- Focused alias/cache tests: **PASS**, 19 cases, including source-shaped V2 HTTP,
  exact location/provider matching, Desktop find-last/deprecated behavior, alias
  turnover, failed-lookup recovery, cost/effort/token integrity, all compact caches,
  unaffected pinned reuse and four real child-process restart runs.
- Hidden Edge shipped Comparisons/help: **PASS**, two browser process restarts,
  exact `Sonnet 5.5` label, stable redraw, selected `sonnet` and historical-estimate
  help. Integrated browser was disconnected; no external desktop was disturbed.
- Real-installation Sessions/detail: **PASS**, 3,051 available roots, 34 scalar
  rows ready/16 pending and one detail row/chunk. The first combined probe's Watch
  phase timed out at 90 seconds after checking 953 roots; its overall result was
  a failure, not a successful whole-probe acceptance.
- The focused longer Watch probe completed **PASS**: all 3,051 history roots
  checked, five known finished history cards and one active card, first verified
  history at 139.814 seconds. Prompt-cost CLI/raw components and session-cost
  reports reconciled. It started no model calls or cache writes; final lifecycle
  output reports no cleanup failures and confirms owned workers closed with shared
  OpenCode untouched. This is bounded integration evidence, not an exact private
  owner-incident recovery or a new historical execution certificate.
- Final Full repeat: **181/181 groups PASS**, 2,233 tests passed and two skipped,
  zero failures/errors, 124.1 seconds. The earlier 180/181 run and causal static
  decoder compatibility repair remain recorded in `COMPLETION.md`.
- Final-tree validator: **PASS**, 11 passes, zero failures, seven existing/advisory
  warnings; no hard cap or debt baseline was raised. `git diff --check` passed.
- Final Full-suite, validator and live read-only installation outcomes are recorded
  in the task's `COMPLETION.md`; no unperformed check is implied by this section.

Evidence: `scratch:/alias-desktop-browser-final.json`, `scratch:/full-tests.json`,
`scratch:/final-full-tests.json`, `scratch:/live-identity-probe.jsonl` and
`scratch:/watch-identity-probe.jsonl`. No ZIP, tag, GitHub Release or paid model call.

## Historical FR 000629 findings (retained)

Scoped v80.218 implementation, 2026-11-09, based on main
`1294998ccf8cf9eaf7aff0e50958c4ba422e5de5`. This is not a new whole-tree
architecture assessment or proof of the owner's underlying executed Claude release.

## What can establish a concrete model

The reported completed V2 assistant selected
`{"providerID":"claude-agent","id":"sonnet","variant":"default"}`.
The wire adapter and normalizer faithfully retain that alias. The old display
path discarded its provider and picked a shortest substring match from the current
catalog, inventing Claude Sonnet 4. Exact reference CCost correctly stayed unknown.

The public OpenCode API documents assistant `model` as a selected `Model.Ref`, not
a dated binding to the executed backend. Public upstream source inspected at
`12a661ea40cd5863b271a89bb06b8a3ddb7ab5a0`:

- `packages/core/src/plugin/provider/claude-agent/language-model/convert-claude-stream.ts`
  emits actual response `modelId` as streamed response metadata, but finish provider
  metadata carries rate limits, not an established persisted resolved-model mapping.
- `packages/core/src/plugin/provider/claude-agent/provider.ts` uses current catalog
  `resolvedModel` for current prices. It is not a historical per-request certificate.
- `packages/core/src/plugin/provider/claude-agent/sync/record.ts` concerns native
  session/checkpoint identity, not dated executed-model proof.
- Session runner `step.ts` and `publish-llm-event.ts` retain selected assistant model
  and finish provider metadata; no supported persisted resolved-ID mapping was found.

An explicit concrete ID on the individual assistant request remains usable under
the existing source/pricing contract. No arbitrary native field, mutable session
selection, current provider catalog, picker name or release date is promoted into
that evidence. The [Claude model-config documentation](https://code.claude.com/docs/en/model-config)
describes moving aliases, route/version differences, overrides and fallbacks.
Today's default cannot resolve an older `sonnet` call. Existing account SDK transport
is quota/initialization metadata, not request history. No credential probe, private
transcript scan, new source API, paid call or inference was added.

## Shared identity and pricing

`pricing/identities.py::unverified_alias` recognizes moving family/latest/context
selections and route-specific defaults. Known Claude routes display, for example,
**Claude Sonnet (version unverified)**. A custom route's bare `sonnet` stays visibly
unverified without assigning its publisher. Provider, selected alias and request
effort stay unchanged. `PricingCatalog.display_name` is shared by timelines,
prompt/cost groups, Sessions and Token Mix; Token Mix retains its prior exact-name
lookup for unrelated identities. Comparisons exports a separate `model_label`
alongside raw request/contributor IDs. Browser help retains both.

Alias guards precede fuzzy/reference estimation, category/context valuation and
diagnostics. CCost stays unknown/partial without concrete identity; FR000628 help
reports identity uncertainty rather than an invented missing Sonnet 4 rate. Pinned
4/4.5/5.5 identities keep exact reference rates and heavy cache-write coverage.
Display never drives billed spend or native quotas. Token Mix keeps provider-qualified
unresolved groups and independent unknown publisher attribution.

## Persisted dependency repair, not cache deletion

`MODEL_IDENTITY_SEMANTICS=1` is optional per-entry admission, not a broad generation
change. Existing namespaces, source revisions, analysis algorithm and retention
remain unchanged:

| Persisted layer | Affected legacy admission / rebuild |
| --- | --- |
| Full derived analysis | Check original trace/prompt/compaction provider/model IDs; an alias-derived entry misses and reanalyzes that root on access. Current-marked entries avoid another identity scan. |
| Scalar Sessions summaries | Check original contributor IDs. A legacy non-N/A label with no contributors is also unproven and reacquires that root. |
| Shared Token Mix facts | Reject old alias facts; preserve raw provider/model, tokens and original prompt/request identity. |
| AI Stats and Comparisons | Shared facts and encoded matched-run main/contributor IDs carry the same semantic admission; old affected roots rebuild, unrelated facts remain reusable. |
| Root-tree CCost checkpoints | Salt only moving-alias request fingerprints, revaluing those contributions without discarding the aggregate checkpoint or pinned siblings. |

Raw source snapshots are never rewritten. Normal canonical projections repair CLI,
Sessions/detail, Watch/Mini, model/effort timelines, cost help, grouping and fresh
process projections. Retained Web views and SessionHistory are process-local, not
a separate persisted browser authority; assets do not retain these reports in browser
storage. Restart/source-change lifecycle/reload obtains the new backend derivation.
There is no unconditional history scan, purge, manual reset, paid replay or TTL wait.

## Verification and limits

- `test_claude_alias_identity.py` and `test_claude_alias_cache.py`: focused PASS,
  eleven cases. Current V2 shape, positive 25,050-token/cache-write-heavy usage,
  catalog order, pinned releases, request-local turnover, provider grouping,
  shared display/effort/reason, poisoned previous-schema SQLite, independent
  projection repair, unaffected legacy hits, warm no-reanalysis and two actual
  subprocess restarts. Synthetic pinned reference valuation is 6.89 credits;
  unresolved aliases are not silently priced. Counts/tokens/raw IDs remain intact.
- `integration/probe_claude_alias.py`: PASS with hidden Edge and two fresh browser
  processes using the same disposable profile. Canonical V2-derived Comparisons
  projection plus shipped renderer/help assets preserve alias label, refreshed row
  identity and raw `[sonnet]` provenance help. This is synthetic DOM proof, not the
  owner's private historical session or native window-layout proof.
- Stable-tree real-installation `probe_web_live.py --sessions --detail`: PASS,
  V2, 3,004 available roots, 50 scalar rows ready, two detail rows/one chunk,
  revision-pinned freeze consistent, one Live owner and advancing publications.
  First page 0.077s; Sessions observation 36.020s; HTTP maximum 0.1382s;
  complete probe 37.8772s. No model calls, pending cleanup work, owned threads,
  owned processes or cleanup failures; shared OpenCode untouched. No exact
  owner-incident session or natural-arrival latency was established. This is bounded
  live integration proof, not whole-history alias resolution or a performance claim.
- Earlier live attempt failed after 30.33s with connection reset while production
  files were being edited. Source-change shutdown is plausible but not proven.
  It remains a failed attempt; the stable-tree repeat above is separate evidence.
- Final Full-suite and final-tree validator results are recorded in COMPLETION.md.
  No release ZIP, tag or GitHub Release is part of this delivery.

Local detailed evidence: `scratch:/live-alias-probe.jsonl` (failed attempt),
`scratch:/stable-live-alias-probe.jsonl`, `scratch:/alias-browser-evidence.json`
and `scratch:/final-full-tests.log`. Only sanitized scalar results are published.

## FR 000651 — executed identity investigation and hold

2026-11-09, Cost Guard base `d2d22ea9faea5fa3ddd9b4a941010ce14a4cfc4d`.
This section is a fresh source investigation, not an extension of the earlier
PASS claims. **Decision Delegate authorized On Hold for FR 000651 only**: the
existing safeguard is not the requested recovery, and no useful independently
verified product subset was identified. The original requirements remain open.

### Exact loss boundary

Read-only upstream checkout: `a17fab50a151c602243d31b4be1f5b4915d6437e`.
The running service reported OpenCode 2.2.6; its public `/openapi.json` exposes
assistant `model: Model.Ref` and optional `native`, without a dedicated executed
model field. Source comparison with
[v2.2.6, dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06](https://github.com/anomalyco/opencode/tree/dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06)
confirmed the following behavior also exists in that release. This is a
release-source comparison, not proof of the installed binary's build hash.

| Stage | Fresh source finding |
| --- | --- |
| Claude stream conversion | `packages/core/src/plugin/provider/claude-agent/language-model/convert-claude-stream.ts` emits `{type:"response-metadata", id:messageID, modelId:event.message.model}` at main-session `message_start`. Nested parent-tool streams are excluded by its guard. |
| **Loss** | [`packages/core/src/aisdk.ts::streamPartEvents`](https://github.com/anomalyco/opencode/blob/dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06/packages/core/src/aisdk.ts) explicitly handles `response-metadata` with `Effect.succeed([])`. Neither response model nor response ID survives as an LLMEvent through this branch. |
| Durable publication | `session/runner/step.ts` passes selected `input.model.ref` to `createLLMEventPublisher`; `publish-llm-event.ts` writes that selection in `Step.Started`. Claude finish provider metadata contains rate limits, not the executed model. |
| Projection/storage | `session/message-updater.ts` creates/updates the assistant using the started event's selected model; terminal updates add native/usage/cost. `session/projector.ts` encodes that envelope and assistant parts into SQLite. It cannot restore an event already discarded by the adapter. |
| Transfer/history | `session/transfer.ts::export` exports the same settled session messages. This is not an independent provider-response archive. Public history/export does not repair the above loss. No private database was inspected. |
| Desktop | `packages/session-ui/src/message/message-content.tsx::modelItems` reads `provider.models[model.id].name` from the current catalog. A changed catalog can therefore change a historical alias's visible name without changing its request evidence. |
| Current catalog | `claude-agent/provider.ts` refreshes saved `id/name/resolvedModel` on provider-ready state and uses `resolvedModel` for current prices. This has no demonstrated individual historical response binding. |

These are full-chain source findings, not an inference from a missing schema
property or a publisher switch alone. There was **no actual captured Claude
history fixture or end-to-end historical recovery demonstration** in this run.

### Evidence classes and remaining alternative

| Request evidence | Permissible conclusion | Status in this investigation |
| --- | --- | --- |
| Concrete ID persisted on the individual assistant | Existing explicit-ID handling remains usable; do not borrow a session-wide selection. | Source inspection only; no fresh execution test. |
| Selected alias plus separately persisted executed ID at the exact response scope | Could establish that response's version, preserving the alias/provider/effort separately. | No supported real historical example established; this is a required case, not implemented or verified here. |
| Alias plus today's catalog display name/resolvedModel | Does not establish the old execution; keep it unverified and unpriceable. | Desktop/catalog and adapter source explain the discrepancy; no claim of actual owner-row recovery. |

The [official TypeScript SDK reference](https://platform.claude.com/docs/en/agent-sdk/typescript#getsessionmessages)
documents `getSessionMessages(sessionId, {dir, limit, offset})`, returning transcript
UUID, native session ID, parent IDs and `message: unknown`. This is a plausible
**different** recovery path, not evidence that all transcripts lack model data.
OpenCode's converter attaches native session/message UUIDs to tool calls and
nonstreamed text; streamed response IDs differ from transcript UUIDs, and ordinary
streamed text cannot be assumed to retain the join. `sync/record.ts` saves native
session/checkpoint IDs for continuation, not executed models. Forks can change
transcript UUIDs; side calls need not persist transcripts. The fork helper is
mutating, not a history-read workaround.

No authorized exact historical target, supported bounded transport and complete
source/request join were established. No enumeration of private Claude sessions,
other-session storage, raw prompts, credential access, SDK/Claude execution,
paid replay, new server or installed-source modification was attempted. The
public OpenCode history path's loss does **not** establish irrecoverability of
every SDK transcript. Sanitization after collection would not grant access.

### Minimal integration prerequisite, not an invented implemented field

Upstream must preserve actual response model and response correlation through the
AI-SDK adapter, durable events, projector and supported historical API/export,
separately from selected `Model.Ref`. It must attribute **each physical response**,
not simply overwrite a step with its last observed model: retries, fallback,
multiple responses, tool continuations, compaction and subagents need correct
ownership and usage association. Interrupted/failed responses must not lose
already observed evidence. A versioned optional response-evidence record can
carry this contract; no such hypothetical field is accepted by Cost Guard here.

For older history, a supported request-qualified recovery path to retained
executed identity is additionally necessary, potentially through an exact SDK
transcript join. Prospective persistence alone cannot backfill old requests.
Reconsideration needs that path and an authorized exact historical target, or
an explicit owner scope change; only owner release restores Ready status.

Historical/new recovery is **UNVERIFIED**. Cache reconciliation, cold/warm/restart,
reference-cost and rendered parity acceptance are **NOT RUN**. No product source,
cache semantics, architecture boundary, version or maintenance progress changed;
no upstream issue/patch was published. Development-only hold documentation needs
no product test/release gates under the active workflow and Delegate decision.
The FR and branch are retained, with no completion record or duplicate Suggestion.
