# Claude alias identity and historical repair — FR 000629

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
