# FR000692 — real exact-case inventory and native approval blocker

**Current backlog status after owner release (2026-11-13):
[FR000692 is Ready to Develop, priority 000001](../backlog/ready-to-develop/000001-000692-hard-gate-repair-exact-2026-11-12-claude-unverified-sessions/FR.md).**
The owner reports the native permissions fix is installed, and explicitly
released the held FR. The 87/87 exact V6 identity evidence below supersedes
earlier untested join statements, but the implementation, historical
pricing and real UI/restart verification are **NOT DONE**. Prior hold
descriptions remain chronological observations, not active constraints.

**Current source-recovery finding (v6 owner-run, 2026-11-13):** all **87/87** alias-defect saved known-usage OpenCode requests have exact native SDK reply UUID-to-executed-model evidence (**174/174** links resolved, zero conflicting models). See [V6 proof below](#v6-owner-executed-exact-per-request-identity-proof--2026-11-13). Earlier “UNTESTED” statements accurately describe the former worker's hold, and are superseded for the local investigation, **not** for the still-unimplemented product fix. FR was **On Hold** at that earlier time; it is now owner-released to **Ready to Develop**.

2026-11-13; actual-default source baseline `9176d38c101ec4828a3f2e1032e6bd14b2299ee2`,
Cost Guard v81.37, registered OpenCode **2.3.0**.
**Investigation only; no identity repair or completion.**
The Decision Delegate directed the [whole-FR hold](../backlog/ready-to-develop/000001-000692-hard-gate-repair-exact-2026-11-12-claude-unverified-sessions/attachments/HOLD-2026-11-13.md).
The owner-protected original acceptance is unchanged.

## Real source inventory

The product's authenticated registered-service catalog yielded **3,413 sessions**.
All **49** candidates created before the end of November 12 and updated on/after
its start were read; all 49 were created within **2026-11-12 Europe/Stockholm**.
There were **11** distinct source locations and **1,401** saved assistant rows.
No arbitrary sample or session-title model inference was used.

Fourteen sessions contain Claude Agent selections:

- **12 alias-defect sessions, 87 physical known-usage requests**: 84 Sonnet,
  one each Opus/Haiku/Fable.
- One successful concrete Fable5.2 control, one known-usage request.
- One failed concrete Haiku4.5 saved selection, zero recognized usage requests;
  its actual consumption is unknown.

All six FR000687 probes were identified in the native source. The five successful
I/C/W/O vectors exactly match the [previous journal](recorded-model-help.md#native-evidence-and-saved-request-reconciliation).
The failed sixth retains four native assistant UUIDs without final usage.
Those are not four submissions or proven billed requests. No old prompt was rerun.

The following pseudonyms are derived from exact session IDs; the full source-qualified
mapping stays private. Counts are physical normalized requests, not displayed
prompt rows or unique user submissions.

| Case pseudonym | Recorded `claude-agent` selector | Usage requests | Pre-repair detail identity |
| --- | --- | ---: | --- |
| `99110bafcccd` | `sonnet` — prior probe | 1 | version unverified |
| `91ef306de4bd` | `opus` — prior probe | 1 | version unverified |
| `4a3fc3853ee6` | `haiku` — prior probe | 1 | version unverified |
| `51abb3b4e34b` | `fable` — prior probe | 1 | version unverified |
| `954ee5a3a387` | `sonnet` | 23 | version unverified |
| `4bd4122f6633` | `sonnet` | 20 | version unverified |
| `34d66ff98345` | `sonnet` | 10 | version unverified |
| `53a50303afcf` | `sonnet` | 8 | version unverified |
| `1f1e8df79caa` | `sonnet` | 8 | version unverified |
| `15edb8f19dd4` | `sonnet` | 4 | version unverified |
| `2a1129a000ac` | `sonnet` | 3 | version unverified |
| `d7123274375e` | `sonnet` | 7 | version unverified |
| `2c21528c1af3` | `claude-fable-5-2` — prior probe | 1 | concrete recorded selection |
| `e52bfda4a163` | `claude-haiku-4-5-20251001` — failed probe | 0 recognized | concrete selection; usage unknown |

## First demonstrated lookup/loss boundaries

Six deleted source locations return **HTTP 404** for both exact-location
`/api/provider` and `/api/model`. `DesktopModelCatalog._models()` catches that
`SourceError`, materializes an empty observation and retains it for 30 seconds.
Consequently the selected alias remains unresolved. Five surviving locations
return the expected `{location:{directory},data:[...]}` shape and concrete catalog
labels. No response-shape mismatch was established for those successful controls.
Fresh-source acquisition already reproduces the deleted-location failure; cache
expiration or a restart alone cannot recreate the missing location.

Matching upstream **v2.3.0** source:

- [Claude converter](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/core/src/plugin/provider/claude-agent/language-model/convert-claude-stream.ts)
  emits `response-metadata.modelId` but retains exact SDK session/assistant UUIDs
  in content-native metadata.
- [AISDK `streamPartEvents`](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/core/src/aisdk.ts)
  discards `response-metadata`, leaving the selected alias in ordinary history.
- [Claude sessions](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/core/src/plugin/provider/claude-agent/claude/sessions.ts)
  and [SDK transcript use](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/core/src/plugin/provider/claude-agent/claude/fork.ts)
  establish a possible exact persisted-reply recovery route, not proof that any
  particular local transcript still exists.

Every affected saved assistant has exact SDK references in `content.native`;
top-level native metadata contains rate-limit information, not executed model.
The specific SDK UUID-to-`message.model` join remains **UNTESTED**. No title,
neighboring response, unrelated catalog, current family default or price row was
used to assign a release. A search of already-exported saved tool evidence found
43 exact-reference matches across eight review cases, but no concrete model in
those same outputs; this does not establish global historical data loss.

FR000687 P2 repaired recorded-selector help, not these lookup/persistence
boundaries. Its earlier private-history exclusion was subsequently removed by the
owner and is not the present blocker.

## Actual local browser baseline, not acceptance

An owned, unchanged v81.37 host used the real registered source through shipped
HTTP/authentication/assets. A fresh-profile **headless Edge157.0.4341.46** rendered
all **14 exact session details**. All 12 alias-defect cases remained
version-unverified; the two concrete cases had no such suffix. There were **zero
browser exceptions** and **zero inference calls**. No synthetic source replacement,
personal browser profile, visible desktop effect or shared OpenCode stop occurred.
The runner completed normal browser/server shutdown; independent OS-exit
confirmation was unavailable.

This verifies pre-repair **detail** presentation only. It is not the full Sessions
scalar-list denominator, post-fix cold/warm/restart proof, CCost reconciliation,
or identification of the owner's running managed installation. The integrated
browser was disconnected; the permitted hidden route supplied the evidence above.
The ordinary checkout's v80.66 source and cache were read only; its WAL-consistent
cache snapshot had no matching modern scalar summaries. Neither checkout version
proves the location/build of another running managed host.

## Native approval incompatibility

The task explicitly authorizes saved-history inspection, while native permissions
remain effective. An initial default-directory listing was refused before any
prompt; it was not retried. The supported `opencode debug paths` command
independently identified the database path. Native database/plugin queries were
not performed.

The exact failed-Haiku SDK transcript read was proposed through the normal native
`read` tool. The Delegate assessed alternatives and On Hold, then returned Ask user
for that one bounded operation. The first verdict heading did not match the
installed parser. After that was corrected, the **next parent tool operation**
was the exact same read with identical parameters. The guard again returned
`REPO_BACKLOG_PERMISSION_DELEGATE_REQUIRED` before any owner dialog or file read.
This is not an owner refusal or a failed transcript/model join.

Inspection of installed `lib/repo-backlog-delegate.js` and
`lib/repo-backlog-permission.js`, plus this worker's own saved native metadata,
establishes a concrete additional mismatch:

1. The wrapper requests `background:false` and calls permission completion
   immediately when the subagent executor returns.
2. The actual native subagent tool returned after **66ms** while its correctly
   parented Delegate remained running.
3. That child completed approximately **171.7 seconds later**. Its agent and
   configured provider/model/effort matched.
4. The guard requires the child already to have succeeded when the wrapper
   checks. Later completion cannot restore the discarded one-shot association.
5. The exact read after the corrected completed verdict was still suppressed.

No more transcript retries, shell/SDK alternative access to that rejected file,
permission weakening, plugin edits, installation or automatic reload occurred.
The source-backed diagnosis supports an unavailable approval mechanism in this
runtime; it does **not** prove the transcript missing, the metadata irretrievable,
or all other environments affected. The conditional up-to-48-hour real-work
allowance was not spent or claimed; repeating this demonstrated unavailable
approval route would not supply historical evidence.

## Decision, unfinished work and release condition

The same-parent **Decision Delegate**, not an alleged owner denial, directed
**On Hold for FR000692 only**, with no further retry/prompt/workaround, partial
closure or replacement Suggestion. Only this task moves; no assertion or scan of
other FR dependencies is made.

Prerequisite: owner-controlled restoration of a supported native
completion-to-approval mechanism and actual required access under normal
permissions, or sufficient exact source-qualified evidence supplied through a
supported accessible route. Only the owner subsequently releases this same FR.
Neither repair/loading nor supplied evidence alone establishes product acceptance.

Historical executed releases, the actual managed installation, native transcript/
plugin joins, product recovery, all post-fix UI/cache/cold/warm/restart checks,
the new bounded native prompt, Full suite and validator remain unfinished/
UNVERIFIED/NOT RUN as applicable. No product fix or completed progress is claimed.

The Delegate authorized no product-version or maintenance-progress increment for
this administrative hold-only delta. This scoped versioning exception and the
current development-only workflow waive **no** FR acceptance. No architecture
update: product responsibilities and implementation did not change. The branch
`fr-000692` preserves the administrative recovery point; private exact-case
evidence stays outside the public repository in this worker's retained scratch.
## Owner-supplied local checkpoint/transcript metadata follow-up — 2026-11-13

**Investigation-only evidence, supplied by the owner after the On Hold decision.**
A Python-standard-library read-only diagnostic inspected the owner's existing
OpenCode SQLite history, Claude Agent plugin checkpoint records and exact locally
named Claude SDK JSONL transcripts. The owner uploaded its bounded/sanitized v4
metadata JSON for independent counting and source comparison; the private raw
database, transcript content, session identifiers, directory paths, credentials
and prompt text were not uploaded or published. The probe is a diagnostic, not
product code or real Cost Guard after-repair evidence.

**Inventory and exact checkpoint-to-transcript model observations:**

- Same **49** candidate sessions for the 2026-11-12 Europe/Stockholm activity
  window as in the prior inventory. **19** have Claude-related selected/session
  metadata: **14** with stored assistant rows and **5** without any assistant
  rows. Those five non-execution records are not additional confirmed alias
  defects.
- The 14 assistant-bearing cases contain **89** OpenCode assistant rows, **88**
  with a positive token field (this includes one concrete Fable5.2 control).
  This matches the shape of the earlier **12 alias-defect sessions / 87 known-usage
  normalized physical requests**, plus one concrete known-usage control and
  one failed concrete Haiku4.5 case. Assistant rows and normalized physical
  requests are different units; count agreement is not an audited per-request join.
- Exact checkpoint assistant UUID to the assistant UUID **within the very same
  named Claude SDK session transcript** succeeds **48** times across **13**
  sessions: **47** matched assistant UUIDs across **all 12 alias-defect sessions**,
  plus **one** concrete Fable5.2 control. This was the previously untested
  checkpoint-to-transcript read route, now executed on owner-supplied local data.
  No matching reply UUID was assigned multiple conflicting model IDs.
- The 12 affected alias sessions each have at least one concrete matched reply
  model and a single concrete model throughout their individually retrieved
  *current referenced SDK transcript*:

  | Recorded alias | Defect sessions | Earlier normalized usage requests | Matched checkpoint assistant UUIDs | Exact SDK reply model |
  | --- | ---: | ---: | ---: | --- |
  | `claude-agent/sonnet` | 9 | 84 | 44 | `claude-sonnet-5-5` |
  | `claude-agent/opus` | 1 | 1 | 1 | `claude-opus-5-5` |
  | `claude-agent/haiku` | 1 | 1 | 1 | `claude-haiku-5-5` |
  | `claude-agent/fable` | 1 | 1 | 1 | `claude-fable-5-1` |
  | **Alias total** | **12** | **87** | **47** | |
  
- **14** exact SDK transcript files were located (from **1,408** JSONL
  filenames checked): **94** assistant entries, **93** with a parseable Claude
  model ID, one lacking that model, and **zero** contradictory models for the
  same transcript assistant UUID. The concrete Fable5.2 control has one exact
  checkpoint match. The known failed concrete Haiku4.5 case has four transcript
  assistant entries with its concrete model but **zero matched reply checkpoints**
  and no recognized final usage; it does not prove zero consumption.
- The v4 extractor reports **0** `native` reference pairs from stored
  assistant/part data, even though the earlier investigation described
  `content.native` references. This discrepancy needs schema/field-by-field
  reconciliation; a parser not finding these pairs is not proof those references
  are absent. The checkpoint-based matches are independent of that extractor.

**Strength and limits:** These are **source-qualified historical executed reply
model observations, not mere mutable current-catalog guesses**. They establish
at least one exact model-bearing Claude reply in each of the twelve previously
unverified alias sessions. They **do not yet prove that all 87 independently
normalized priced physical requests** individually map to those matched reply
UUIDs or even to all responses in the current retained SDK transcript. Some
long-running OpenCode sessions have 8, 10, 20 or 23 saved assistant rows but
their presently retained checkpoint history or SDK file covers only a subset.
A prior native session may have rotated, branched, resumed or become unavailable.
Do not assign an executed model to unmatched historical requests merely from the
single model present in a later transcript, adjacency in time or a mutable
catalog. Exact costs and completeness remain unverified.

**Cross-check of exact usage mapping:** OpenCode v2.2.7's [Claude Agent usage accumulator](https://github.com/anomalyco/opencode/blob/v2.2.7/packages/core/src/plugin/provider/claude-agent/language-model/usage.ts) takes input/cache counts from the *last* SDK API call in a turn but **sums output and reasoning across its recorded messages**; one normalized OpenCode usage row therefore need not match one transcript assistant entry's raw usage vector. Inference from equal token counts or proximity alone must not replace reply UUID/step ownership. This helps explain why raw row counts and reply/checkpoint counts differ, but does not itself prove a specific missing historical step.

**Targeted residual gap, counted from the owner's v4 metadata:** exactly **five
Sonnet alias sessions** have fewer current-checkpoint exact reply matches than
saved OpenCode assistant usage rows: respectively **8 rows / 1 checkpoint
match**, **8 / 1**, **10 / 1**, **20 / 12** and **23 / 14**. The other seven
alias sessions have one checkpoint match per assistant row or more. This is a
*coverage warning*, not a proof of forty distinct missing executed model calls:
OpenCode steps and Claude replies are not 1:1, and some SDK transcripts contain
more replies than checkpoint references. The current referenced SDK transcript
has just **one assistant reply** in each of the 8/1, 8/1 and 10/1 cases;
therefore older SDK generations/orphan transcripts or independent exact
step-level references are particularly important there.

**Read-only v5 investigation requested before implementation confidence:**
audit each saved assistant step's exact native/API response references (if any),
finish time and I/C/W/O; search bounded *other* local Claude SDK transcript files
by timestamp and source directory without exposing their content. Never promote
a timestamp/directory/model-family match to an executed-identity certificate.
Try to recover previous generations and exact step/reply lineage, and classify
each step as exact-link, candidate-only or unresolved. This v5 diagnostic has
passed **synthetic** fixture tests; real results have NOT yet been provided.

**Next implementation-worker investigations:**

1. Reconcile the actual `native` storage shape with the earlier source observation;
   inspect `session_message.data`, `session_part.data` and typed plugin checkpoint
   evidence through sanctioned read-only local tools, not old assumed paths.
2. Recover durable per-request associations for the longer sessions: earlier SDK
   transcript generations, exact UUIDs, plugin checkpoint lifecycle, forks,
   compaction and interrupted branches. Account for each of the **87** known-usage
   normalized physical requests without pretending a checkpoint UUID equals a
   physical request or accepting session-only guesses as per-request execution.
3. Identify the minimum read-only Cost Guard identity adapter that can import
   *proven* executed release per physical request; keep recorded selector,
   executing model, current-catalog estimate and reference pricing provenance
   separately. Preserve revisions and invalidate only dependent derived caches.
   Include a separate future-recording repair for OpenCode's dropped
   `response-metadata.modelId` when necessary.
4. Reconcile actual reference-price availability and I/C/W/O for every supported
   contributing request, preserving unknown usage for failed Haiku4.5. Verify
   identical exact real sessions in the managed Cost Guard Web Sessions, detail
   and Watch/Mini after the specified cold/warm/restart sequence and complete
   normal tests. No actual product or browser acceptance has run as part of this
   owner-provided metadata investigation.
5. Resolve the separately documented native approval-completion mechanism or
   establish a supported owner-provided exact-evidence path for remaining reads.
   The **On Hold** state and binary owner acceptance remain intact until the
   human owner explicitly releases the FR.

**Important chronology:** The preceding On Hold report truthfully said SDK
reads were **NOT RUN by that worker**. This later, independent,
owner-executed metadata probe supplies new evidence and does **not** retroactively
rewrite the failed native approval attempt, mark the FR Complete, repair any
historical Cost Guard label or authorize an automatic Ready promotion.
## Owner v5 metadata audit and inline-native probe correction — 2026-11-13

**New real owner-run v5 export; read-only, privately pseudonymized.**
A complete local scan within v5's explicitly bounded source window observed
**49** candidate sessions, **19** with Claude-related selections, **89** stored
OpenCode assistant steps, of which **88** retain usage. It inspected 14 referenced
SDK transcript files plus **48** other locally existing JSONL transcripts with
assistant entries whose file modification time fell within ±3 days of
2026-11-12; 1,408 JSONL filenames were examined overall. It reported zero
oversize/budget skips, read errors or invalid JSON candidate lines. The orphan
files are **potential prior generations**, *not* automatically proven to
belong to an OpenCode session.

**Cross-source usage observation (strong corroboration, not exact identity):**
For **every one of the 88 usage-bearing OpenCode assistant steps**, at least
one of v5's *eight exported nearest time/cwd candidates* has an exact
four-field numeric match: OpenCode `input`, `output + reasoning`,
`cache.read`, `cache.write` equal the SDK assistant's
`input_tokens`, `output_tokens`, `cache_read_input_tokens`,
`cache_creation_input_tokens`. **All matching candidates for any step
agree on one concrete model**: Sonnet5.5 for the Sonnet aliases,
Opus5.5/Haiku5.5/Fable5.1 for their aliases, and Fable5.2 for the
successful pinned control. No mismatching model identity appears among
the **88** token-profile matches. **64 of 88** also have a matching
candidate whose rounded recorded time delta is <0.15 seconds, but SDK
timestamps and duplicated assistant messages require care; this is not
64 authoritative UUID associations. One concrete failed Haiku4.5
selection has no saved final usage and is outside the 88.

**Discovered v3-v5 diagnostic blind spot and direct source confirmation:**
v5 tried to extract `native` UUID pairs from the assistant envelope
and separate `session_part` rows, but **did not inspect
`session_message.data.content[*].native` inline parts**. Every
v5-exported assistant step reported `part_count=0`, so the missing
inline read is consequential. Upstream OpenCode v2.2.7
[`session/projector.ts`'s `prepareAssistantParts`](https://github.com/anomalyco/opencode/blob/v2.2.7/packages/core/src/session/projector.ts)
explicitly supports older assistant rows where parts remain in the
`session_message.data.content` JSON array until a part write migrates
them. The previous **zero native UUID pairs is therefore an extractor
blind spot**, not an established absence from original data.
The previous source investigation's report of `content.native`
is compatible with this storage layout.

**Focused v6 diagnostic prepared but NOT yet owner-run:**
the new Python-only read-only probe inspects both inline
`content[*].native` and separately persisted part-native metadata,
extracts only exact UUID pairs, and checks them against the same
Claude SDK transcript assistant UUID and model. It reports each step's
raw-reference count, number found, unresolved references, observed
model IDs and conflicting direct IDs; pseudonyms and bounded usage-only
candidate metadata are exported, never contents, directories, tokens
or credentials. *Here "tokens" means secrets, not numeric token usage.*
An isolated **synthetic** SQLite/JSONL fixture with inline native
parts, two source generations and zero split-part rows passed 2/2
exact native-UUID-to-transcript model associations without copying
private text, raw UUIDs or paths. **No real v6 result yet.**

**Decision rule after owner-run v6:** Count exact native reply-UUID
links separately from OpenCode assistant steps and physical SDK calls.
A directly linked SDK reply proves that reply's model, but a
multi-response OpenCode step may have additional responses. Require
all contributing models/usage per step (including any distinct
models across multiple SDK responses) to be reconciled before
asserting a verified per-request price. Time/cwd/token matches
are corroboration and search hints, not a general exact-UUID
replacement. The previous 47 checkpoint matches remain valid.

This addendum does not implement the Cost Guard repair or modify
the current **On Hold** status, binary P0 acceptance,
native approval conditions or restart/browser test gate.

## V6 owner-executed exact per-request identity proof — 2026-11-13

**Read-only local validation from owner-supplied, pseudonymized `FR000692-read-only-metadata-v6` JSON.**
The full uploaded file (not the truncated chat preview) was independently counted.
V6 corrects the previous probe's omission of legacy inline content in
`session_message.data.content[*].native` and resolves native
`(sessionID, messageID)` pairs against exact saved Claude SDK
`assistant.uuid` and `assistant.message.model` within their named transcripts.
All data remained local except for this bounded metadata report; no
raw UUIDs, prompt text, directory paths or credentials are copied to GitHub.

| Evidence category | Exact result |
| --- | ---: |
| Same-day candidate sessions | 49 |
| Claude-related session selections (including five empty) | 19 |
| Assistant-bearing sessions | 14 |
| Alias-defect sessions | **12** |
| Usage-bearing, alias-defect OpenCode assistant requests | **87/87** with at least one DIRECT UUID-to-model association |
| Distinct native SDK reply pairs across the 87 | **174** |
| Native pairs resolving to exact SDK reply with concrete model | **174/174** |
| Missing SDK reply for alias native pair | **0** |
| Alias request with conflicting directly joined model values | **0** |
| Native pairs pointing to older-than-current plugin SDK session | **86** across **40** alias requests |
| Concrete Fable5.2 success control | 1 request / 1 direct joined reply |
| Failed concrete Haiku4.5 control | 1 saved assistant step, **zero recognized usage**, 4 direct joined replies |
| Entire assistant-bearing inventory | **89** stored assistant steps, **179/179** direct pairs resolved, zero conflicts |
| Exact SDK transcript files found | **21** |
| Other nearby-mtime transcript files surveyed | 41 (search candidates, not exact ownership proof) |
| JSONL parse errors / read failures / budget skips | 0 |

**Alias identity ledger — precise persisted source reply proof:**

| Saved Claude Agent selector | Defect sessions | Stored known-usage requests with direct reply links | Distinct directly resolved SDK replies | Actual SDK `message.model` |
| --- | ---: | ---: | ---: | --- |
| `sonnet` | 9 | 84 | 171 | `claude-sonnet-5-5` |
| `opus` | 1 | 1 | 1 | `claude-opus-5-5` |
| `haiku` | 1 | 1 | 1 | `claude-haiku-5-5` |
| `fable` | 1 | 1 | 1 | `claude-fable-5-1` |
| **Total** | **12** | **87** | **174** | |

**The previous five Sonnet gaps are closed for the saved request-to-reply
model association, not merely suggested by timing.** Original saved steps /
current checkpoint matches were `8/1`, `8/1`, `10/1`, `20/12`, `23/14`.
V6 now finds, respectively: **8 steps / 19 direct SDK reply pairs**,
**8 / 13**, **10 / 20**, **20 / 42**, **23 / 48**. Each individual step has
at least one exact matched assistant reply, and all direct replies on that
step name the same concrete Sonnet 5.5. Their 86 exact references to
earlier SDK session IDs prove why using just the plugin's last
`claudeSessionID` would miss historical execution.

**Technical handoff — source path confirmed in existing Cost Guard code:**

1. The v2.2.7/v2.3.0 upstream Claude Agent converter preserves native
   `sessionID` and `messageID` on saved assistant content even though the
   executed `response-metadata.modelId` was discarded from the stored
   assistant envelope. In the local v2.2.7 records the source native keys
   are on **inline assistant `content[*].native`**; the separate
   `session_part` table is empty for these cases. Newer split-part
   arrangements also need to be admitted.
2. Existing Cost Guard
   [`src/sources/opencode_v2_wire.py`](../../src/sources/opencode_v2_wire.py)
   `current_union_message_to_legacy_bundle` copies assistant
   `content[*]` to normalized parts; the
   [`src/sources/opencode_v2_normalization.py`](../../src/sources/opencode_v2_normalization.py)
   normalizer retains `native` inside each `NormalizedPart.data`.
   Thus the **read-only native reply references already cross the source
   boundary**. Confirm on the actual registered HTTP service during
   implementation; do not read only envelope `native`, latest plugin KV,
   or mutable `/api/model` by deleted original location.
3. Resolve each source-qualified `(sdk_session_id, sdk_reply_uuid)`
   independently, across *all referenced historical SDK sessions*, against
   exactly matching Claude JSONL `assistant.uuid`, reading
   `assistant.message.model`. This lookup must not be constrained to
   the most recent plugin checkpoint session ID. Qualify any transcript
   file ambiguity, deleted directory, missing file, bad JSON or conflicting
   UUID/model; fail closed rather than attribute a different response.
   Index referenced SDK session IDs once per bounded source snapshot;
   avoid rescanning thousands of JSONL files for every UI cell.
4. Apply an **executed-release evidence override** at the appropriate
   source identity stage before mutable DesktopModelCatalog alias
   resolution in
   [`src/sources/opencode_v2.py`](../../src/sources/opencode_v2.py)
   `_normalize_messages`. Preserve separately: source provider route,
   original recorded selector (`sonnet`, `opus`, etc.), exact executed
   model ID(s), source provenance, optional effort, and mutable
   current-catalog estimation. `ModelRef`/`ModelResolution` and cache
   validation need the right immutable/verified semantics — do *not*
   pretend SDK evidence is a `desktop-catalog-estimate`, or rewrite
   OpenCode's original SQLite rows.
5. Source-revision and derived-cost caches must treat changes in
   proven model evidence as an input dependency; invalidate dependent
   identity/price projections while respecting current cache contracts.
   Prefer reusing existing shared model-resolution surfaces, so Sessions,
   Session details, Full/Mini Watch and CCost all agree. Support later
   native part migrations and cold application restarts.
6. A saved OpenCode step can reference **1 to 6 distinct Claude SDK
   assistant UUIDs** (37 single, 25 double, 19 triple, 3 quadruple,
   3 sixfold within the 87 defect requests). Every linked UUID in
   the actual defects resolves to the **same** model within its step.
   The future general resolver must handle mixed-version steps and
   multiple replies/retries without guessing a single model or
   double-counting SDK repeated usage. Provider charge/reference CCost
   is still a **separate** verification: only apply a price when
   historical executed model, I/C/W/O usage and applicable reference
   rates are all actually supported.
7. Tests must cover the exact 12 alias histories (counts **87/87**),
   all five former multi-SDK gaps, deleted project locations,
   conflicting/unavailable transcripts, no native metadata,
   multiple executed models inside one step, old inline vs new split
   parts, failed concrete Haiku4.5 consumption remaining **unknown**
   rather than fabricated zero, cost-cache/effort/provider isolation,
   and native response metadata preservation on a new bounded test.
   The owner requires exact live installed-state readback after
   warm/cold and two normal Cost Guard restarts before Complete.

**What this proves vs what it does not:**

- **PROVEN on the owner's actual local source:** all 87 persisted
  alias-defect assistant usage requests carry one or more *direct*
  native UUID references to real Claude replies with the concrete
  executed model release recorded as above; all 174 references resolve,
  none conflict. V4's *apparent 40-request evidence-coverage gap* is
  superseded: it did not inspect inline native content and never
  established those historical requests lacked recoverable proof.
- **NOT YET PROVEN:** a fully installed Cost Guard implementation,
  final UI/cold-warm/two-restart display, availability and correctness
  of historical price rates, billed invoice equivalence, all future
  alias/fork cases, or truly zero consumption for the failed pinned
  Haiku selection. An SDK reply model is source-qualified release
  evidence, not automatically an invoice or proof that every possible
  hidden contributing SDK response was captured.

**Workflow status unchanged:** this addendum documents owner-supplied
proof only. FR000692 was **On Hold** when this v6 audit was written; the owner
subsequently released it to **Ready to Develop**. P0 acceptance has not been weakened or met.
