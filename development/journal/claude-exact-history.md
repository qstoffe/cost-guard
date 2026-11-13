# FR000692 — real exact-case inventory and native approval blocker

2026-11-13; actual-default source baseline `9176d38c101ec4828a3f2e1032e6bd14b2299ee2`,
Cost Guard v81.37, registered OpenCode **2.3.0**.
**Investigation only; no identity repair or completion.**
The Decision Delegate directed the [whole-FR hold](../backlog/on-hold/000692-hard-gate-repair-exact-2026-11-12-claude-unverified-sessions/HOLD.md).
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

