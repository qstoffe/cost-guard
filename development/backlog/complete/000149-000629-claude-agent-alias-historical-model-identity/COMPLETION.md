# Completion — FR 000629

Implemented in v80.218, 2026-11-09. Original specification preserved unchanged.

- Moving Claude aliases show version-unverified labels through shared identity rules,
  not a fuzzy Sonnet 4/current-default guess. Raw provider/model/effort provenance
  remains separate; exact pinned request IDs keep normal reference pricing.
- Automatic on-access semantic admission repairs affected persisted full analysis,
  scalar summaries, shared Token Mix/AI Stats/matched-run evidence and root-tree
  CCost contributions. Unaffected cache reuse, counts, tokens, source snapshots,
  retention and bounded acquisition remain intact; no purge, paid replay or reset.
- CLI, Sessions/detail, Full/Mini Watch and historical projections share canonical
  labels and identity-specific unavailable-cost reasons. Comparisons retains raw
  model IDs separately from its new display label.

## Verification

- Final Full suite: **PASS**, 177 files, zero failures, four bounded workers,
  132.5 seconds, including eleven new identity/cache regression cases.
- Package validator: **PASS**, eleven checks, zero failures; seven existing advisory
  size/design warnings. No caps/baselines raised and no new dependency.
- Hidden Edge canonical synthetic Comparisons DOM: **PASS**, two browser process
  starts, unchanged alias label after refresh, raw identity in contextual help.
- Stable-tree real V2 Sessions/detail probe: **PASS**, 3,004 available roots,
  50 ready scalar rows, complete pinned detail/freeze, single preserved Live owner,
  advancing publications, no inference and clean owned-resource shutdown.

The earlier live attempt failed with connection reset during source edits; its
cause remains unproven and it is not counted as PASS. No supported persisted
request-time resolved-ID mapping was established for alias-only Claude Agent
messages. Such historical requests remain honestly unverified; the owner's actual
executed release is not asserted. No acceptance waiver or Delegate exception was
needed. [Source findings, cache dependency map and precise proof limits](../../../journal/claude-alias-identity.md).

Release metadata/current docs and ordinary maintenance count updated in the same
delivery. Current main remains the supported source distribution; no ZIP/tag/Release.
