# Completion — FR 000651

Date: 2026-11-09. Product: **v81.6**.

## Delivered scope

Implemented the owner's explicitly accepted Desktop-catalog fallback for historical
Claude Agent aliases. Exact provider/alias matching uses the request's OpenCode
location, retaining the original alias, provider, effort, tokens and tiers. A
supported concrete catalog identity enables estimated reference CCost, never a
claim of actual provider billing or verified historical execution. Missing mappings,
prices and usage remain honestly unavailable.

Recorded concrete request identities retain precedence. Catalog-dependent full
analysis, Sessions summaries, Token Mix, AI Stats/Comparisons, model groups and
root-cost contributions revalidate on access, including negative lookups and
fresh-process cache hits. Unrelated pinned history and immutable source observations
are preserved. Canonical projections supply CLI, Web Sessions/detail, Watch/Mini,
cost/model help and Comparisons without per-cell source reads or alarm badges.

The original FR and its investigation companion are preserved intact in this
bundle. Architecture navigation, usage documentation, README and version history
were updated. Maintenance progress advances ordinary delivery 105 to 106 only;
previous assessment milestones and the existing Session Learning deferral stay
unchanged. This candidate progress counts only after merge to main.

## Verification

- Focused identity/cache regressions: **19 PASS**, including exact location and
  provider wire behavior, catalog turnover, negative recovery, scoped persistent
  repair, unaffected pinned reuse, real token/effort/cost integrity and four
  child-process cold/warm/restart projections.
- Initial Full run: **180/181 test-file groups passed**. The failing AI Stats resume
  group exposed an incompatible instance-method change. Restored `_decode` as a
  static method with an optional source validator, passing the source explicitly
  from production restore callsites. The repaired group and related suites then
  passed **88 tests** without weakening expectations.
- Final complete Full repeat: **181/181 groups PASS**, 2,233 tests passed and two
  skipped, zero failures/errors; four workers, 124.1 seconds. This confirms the
  repaired final product tree rather than treating the initial failed run as green.
- Final-tree package validator: **PASS**, 11 passes, zero failures and seven
  existing/advisory design/prose warnings. Syntax, imports, layer boundaries,
  hard file budgets, public-package hygiene and v81.6 metadata are consistent.
  No budget was raised or debt baseline enlarged. `git diff --check` also passed.
- Hidden Edge shipped Comparisons/help: **PASS**, two fresh browser processes,
  stable redraw, exact Desktop label and retained alias/estimate help. This uses
  synthetic source-shaped fixtures, not a private owner-session capture or native
  desktop layout proof. Integrated browser access was disconnected.
- Real-installation Sessions/detail: **PASS**, 3,051 available roots, 34 scalar
  rows ready/16 pending, one detail row/chunk. First page 0.056 seconds, maximum
  sampled HTTP 0.264 seconds; no model calls.
- First combined live attempt: **FAILED** in Watch at the 90-second observation
  deadline, with 953/3,051 roots checked. Prompt/session-cost acceptance was not
  reached in that attempt. This is retained as failed evidence, not relabeled PASS.
- Longer focused live Watch/prompt-cost/session-cost: **PASS**, all 3,051 roots
  checked; five known finished history cards and one active card; first verified
  history at 139.814 seconds, first rows at 1.098 seconds. Prompt-cost canonical
  CLI/raw components and session-cost reports reconciled. Four requests were
  priceable. No probe-started model calls, cache writes or cleanup failures;
  lifecycle output confirms owned workers closed and shared OpenCode untouched.

Local evidence: `scratch:/full-tests.json`, `scratch:/final-full-tests.json`,
`scratch:/final-validation.log`, `scratch:/alias-desktop-browser-final.json`,
`scratch:/live-identity-probe.jsonl` and `scratch:/watch-identity-probe.jsonl`.
Published results are sanitized scalars.

## Source evidence and honest limitations

Public upstream v2.2.6 source at
`dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06` proves that Desktop uses the current
location catalog and that `core/src/aisdk.ts` discards the converter's streamed
`response-metadata.modelId` before durable publication. A real read-only current
catalog observation supplied exact `sonnet` → `Sonnet 5.5` /
`claude-sonnet-5-5`; the minimized fixture distinguishes that observation from
synthetic stream metadata. Neither is an executed-model certificate for old rows.

No exact owner historical session ID was supplied, so the narrow checkpoint/official
SDK transcript join was **NOT PERFORMED**; no arbitrary substitute session or private
history enumeration was used. Historical executed-ID recovery is **UNVERIFIED** and
future upstream persistence is **NOT IMPLEMENTED**. The latest owner-approved
fallback requirement explicitly permits delivery without those missing prerequisites;
there is no Delegate waiver or newly invented completion exception. Existing
concrete request handling remains unchanged; a separately persisted alias/response
contract was not invented or trusted without supported evidence.

The read-only Decision Delegate advised source-owned materialization, cache
dependencies and preserved recorded identity; it granted no access expansion or
acceptance waiver. See [the implementation journal](../../../journal/claude-alias-identity.md)
for detailed provenance, architecture and the retained superseded hold findings.

No installed OpenCode mutation, inference call, extra server, runtime installation,
ZIP, tag or GitHub Release is part of this delivery. Main remains the supported
distribution.
