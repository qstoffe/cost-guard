# FR 000651 — On Hold, not completed

Decision: **Decision Delegate**, 2026-11-09. Scope: FR 000651 only. The
specification is preserved unchanged; no other Ready task is declared blocked.

## Reason

OpenCode emits the actual Claude response model, but its AI-SDK adapter discards
`response-metadata` before durable session events. The ordinary history/export
chain retains the selected alias, while Desktop displays its current catalog
name. Substituting that name would not establish the historical executed model.

Fresh source tracing covered upstream `a17fab50a151c602243d31b4be1f5b4915d6437e`
and release tag v2.2.6 (`dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06`), matching
the installed service's reported version. The relevant metadata-drop behavior
is the same. See [the investigation](../../../journal/claude-alias-identity.md#fr-000651--executed-identity-investigation-and-hold).

The official SDK's exact transcript-UUID lookup remains a possible alternative,
**not disproved**. No authorized exact historical target and usable bounded,
source-qualified recovery transport were established. No private transcript,
other-session storage, credentials or model calls were accessed for this work.

## Prerequisites for reconsideration

- A supported source path must retain actual response-model identity and response
  correlation in durable events, projection and historical API/export, separately
  from the selected alias, for each physical response across retries, fallback
  and subagents.
- Existing history also needs a supported bounded request-qualified recovery
  path and an authorized exact historical target. Future persistence alone
  cannot recover already lost identity; retained SDK transcripts may help only
  where an exact join can be proved.
- An owner must explicitly release this FR, or explicitly accept changed scope.
  Dates or upstream availability never automatically restore Ready status.

Historical and new-session recovery: **UNVERIFIED**. End-to-end recovery,
cache-repair and presentation acceptance checks: **NOT RUN**. FR 000629's safe
unverified labels remain unchanged. No product changes, version bump, completed
progress increment, upstream publication or completion claim accompanies this
development-only hold. The existing `fr-000651` branch is retained.
