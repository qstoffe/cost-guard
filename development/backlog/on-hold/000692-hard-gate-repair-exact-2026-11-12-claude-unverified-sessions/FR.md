# FR 000692 — P0 BLOCKER: Fix the EXACT 2026-11-12 Claude "version unverified" sessions on the owner's PC, or move THIS FR to On Hold

**Highest-priority, explicitly owner-approved Ready to Develop (2026-11-12).** Permanent identity **000692**. Priority **000001** — **above every other Ready item**. This request responds to a **verified failed delivery boundary** in completed FR000687: the user upgraded/restarted Cost Guard and still sees **many of the SAME November 12, 2026 local sessions** labelled **`Claude Sonnet (version unverified)`**, plus **new Claude Agent model-test sessions** also labelled **`version unverified`**. Both prior historical and newly generated affected records must be investigated and corrected against the **actual installed local OpenCode source**.

## Owner clarification and verified reactivation — FR000693, 2026-11-13

The owner authorizes **read-only inspection/export of all relevant saved OpenCode
session records**, including sessions created by other agents, and relevant
SQLite, provider plugin records and native Claude SDK transcripts, where normal
installed access permits. These saved records are legitimate Cost Guard product
input. **This does not authorize reading other implementation workers' scratch,
stashes, private workflow checkpoints or live processes.** Native SDK transcript
and reply/checkpoint references are source evidence, not permission to enter
another worker's private Checkpoint/Resume workspace. Native `ask`/`deny`,
credentials, identities and read-only/privacy boundaries remain effective.

The owner requests deep, sustained troubleshooting **up to 48 hours of real work**
before declaring the technical problem insoluble where the environment reasonably
supports it. Use supported Checkpoint/Resume and a private exact-case evidence
ledger across sessions as needed. This is not idle waiting, a requirement to
generate paid model tokens, or permission to bypass native denial. Report actual
avenues and effort honestly; do not claim work that was not performed.

Reactivation is authorized by FR000693 after [Toolkit PR #406](https://github.com/qstoffe/opencode-toolkit/pull/406)
merged the reviewed rule and a fresh ordinary worker received the corrected
installed command. [Verification and scope](../../../journal/recorded-model-help.md#fr000693--verified-rule-loading-and-held-task-reactivation-2026-11-13)
and [the superseded original hold](PRIOR-HOLD.md) retain the evidence. This is
**reactivation, not a model-identity fix or verification of any historical case**.
The original binary acceptance below is unchanged: all exact affected November 12
and owned native test sessions must be individually diagnosed, correctly resolved
and verified after genuine cold/warm Cost Guard restart, or this same FR returns
On Hold with the first demonstrated specific remaining technical/access blocker.
No cosmetic/P2-only closure, synthetic PASS, replacement Suggestion or delegate
waiver of that affected-records gate is authorized.

**THIS REQUEST HAS EXACTLY TWO PERMITTED FINAL DISPOSITIONS:**

- **A — COMPLETE / PASS:** Identify, causally diagnose, repair and **individually reverify ALL currently affected exact real sessions** from the local **2026-11-12 (Europe/Stockholm)** date window and the recent FR000687 native model tests. After cold Cost Guard restart and opening Web → Sessions, every target record that had the alias defect shows a **correct source-supported concrete Claude release**, e.g. **`Claude Sonnet 5.5`**, or a genuinely different correctly evidenced executed model, and any supported token usage is priced with the right model. The target rows no longer read `(version unverified)` because the underlying identification was repaired, **not because the UI string was hidden or guessed**. The fix persists through warm/cold cache, restart and future similar Claude Agent requests. Publish exact sanitized per-case before/after evidence; then and only then mark the FR Complete.
- **B — ON HOLD:** If **any** target session cannot be genuinely resolved, cannot be verified on the owner's actual installation, lacks irretrievably recoverable executed/config/source evidence, or if access/tooling cannot be made to work after thorough investigation, **do not mark the FR complete**. Move **the entire FR000692** to `development/backlog/on-hold/000692-hard-gate-repair-exact-2026-11-12-claude-unverified-sessions/FR.md` with a `HOLD.md` containing precisely the unresolved real cases, what was tried, the lowest demonstrable blocker, existing source/SDK loss boundaries and the concrete owner/upstream prerequisite. Keep recoverable code/branch work intact, but **do not ship/merge a partial product release as completed FR000692**.

**No third disposition.** No “P2-only done,” “scoped acceptance,” “nonblocking exception,” “Decision Delegate authorized partial closure,” “report remaining as Suggestions,” “delegate/safety skip,” “leave old entries unverified but complete,” or “all synthetic tests green, done.” No splitting the *mandatory* historical outcome into a new proposed FR to escape the gate. Independent already-completed improvements (FR000687 tooltip P2) remain intact, but cannot count as this FR's success. Neither an internal agent/delegate nor a more recent *interpretation* of the prior task may dilute this explicit **current human-owner acceptance contract**. The worker can keep investigating across multiple development sessions/checkpoints as necessary; **no arbitrary small investigation or effort budget** overrides this binary result.

## 1. Owner authorization: READ THE REAL LOCAL HISTORY BY ANY LEGITIMATE AVAILABLE MEANS

**New explicit human permission superseding the earlier privacy constraint used to skip FR000687 P0/P1, and superseding the restrictive scope in parked Suggestion000691.** The owner affirmatively authorizes the implementation worker running on **the owner's own computer** to inspect **ALL relevant historical OpenCode sessions**, **including sessions created by other agents/workers, live tests, review tools, unrelated projects/temporary workspaces and old prompts**, not just scratch sessions created by the implementing worker. **DO NOT REJECT THESE READS AS UNAUTHORIZED. DO NOT ASK FOR PER-SESSION PERMISSION AGAIN.**

For purposes of solving this issue, the owner expressly permits **any locally available legitimate read method** needed to obtain accurate evidence:

- The installed OpenCode service's authenticated read-only HTTP APIs (`/api/session`, per-session messages/parts, `/api/provider`, `/api/model`, full catalogs, source instance/config/location), including read paths for **all** the owner-identified past sessions, not just the current one.
- **Direct read-only access** to the owner's existing OpenCode SQLite database, WAL-consistent snapshot/backup or sanctioned query path, including session/message/part/provider/plugin KV tables and other relevant local source records; it is **not restricted to one user-created scratch session or one narrow SQLite key** if broader same-day indexing is needed.
- Read relevant Claude Agent provider plugin storage (including the `opencode.provider.claude-agent` namespaced session/checkpoint records), official Claude Agent SDK session/transcript/assistant message reads, native reply/checkpoint UUIDs, accessible source-owned logs/telemetry, installed provider model/config profiles, prior exact request records, and the installed **OpenCode Toolkit live-test/review configuration and owned run evidence**. Where needed, inspect original prompt/test titles and raw local content to establish a precise join or distinguish candidate sessions; **there is no blanket restriction against reading private historical prompts on the owner's machine for this FR**.
- Cross-check other same-day successes, previous models and nearby dates, across all relevant accessible session directories and model routes; do not let deleted temporary project directories or a different worker's owning identity defeat investigation. Read the exact running OpenCode version and source code against the installed build. Normal read access for the current authorized owner applies irrespective of another prior selected worker.

**"By any means" here means any legitimate read of the owner's existing local information through the available source/program interfaces; it is not permission to acquire unauthorized third-party accounts, bypass computer security, leak credentials, destructively rewrite SQLite or mutate OpenCode's original session history.** Investigation may use the complete existing content locally, but **public GitHub evidence must stay sanitized**, with private session IDs/paths/titles/prompts and secrets kept off public commits. A locally retained exact-ID evidence ledger is encouraged to prove that **the SAME records**, not lookalikes, were fixed. No user approval needed merely to query/inspect historical local records.

**Access is a P0 requirement, not a reason to redefine acceptance.** If a task runner has no local file/database access, it must use the permitted local host/shell/source tools or arrange the work in an owner-authorized local implementation context. If truly inaccessible despite the owner's permission, the result is **ON HOLD**, never a P0 “NOT RUN” combined with Complete. Do not claim that GitHub-only synthetic fixtures reproduce the local defect.

## 2. Mandatory P0: exhaustive enumeration of the actual affected 2026-11-12 rows

Use the local calendar **2026-11-12 Europe/Stockholm** (00:00–next midnight in the configured zone) and the owner's exact current Web Sessions result, **including sessions created that day but with subsequent activity outside the window if relevant**. Inspect all available source entries to ensure the denominator is complete, not an arbitrary ten-row sample.

**Start from the same actual database/session catalog that Cost Guard displays.** Search/filter/inspect all relevant records whose current model presentation contains **`version unverified`** for Claude families; include every `Claude Sonnet`, `Claude Opus`, `Claude Haiku`, `Claude Fable` or other Claude Agent alias with this state, regardless of whether they are Review/Live-Test sessions, normal owner prompts or subagents. Do not limit to session titles saying Sonnet. Include failed/zero-usage selections where a model label is still shown, and separate them clearly from requests that actually consumed tokens.

**Also enumerate the actual new FR000687 live-test sessions**, including the five successful native responses and the failed sixth, whenever they are stored in the user's source. Their outcomes and persisted selected aliases were reported in the FR000687 completion journal; they are not a substitute for verifying their Web Sessions/CCost presentation. Examine later tests created on the same date and any relevant sessions that the owner reports still show the phrase after restart.

For each exact affected **session and its contributing request(s)**, retain an internal source-qualified case record (not public raw data) including:

- Local observed date, immutable OpenCode source generation/instance, session ID and session/tree revision, creation/workspace directory and source registration, latest observed active source state; whether ephemeral run directory was later deleted.
- Every recorded `providerID/modelID` pair, `variant/effort`, whether the model is a selected alias or concrete pinned release, and whether the request represents a real executed response, a tool-continuation clone, a child agent, an aborted request or a failed-saved selection with zero/unknown usage.
- Installed native **actual executed** response-model evidence if present (per-response `message.model`, SDK transcript reply UUID, checkpoint identity, trusted task-local model observer), or absence with the exact loss boundary and provenance; historical current-catalog mapping qualified separately, never misrepresented as an execution certificate.
- Exact source/config/location catalog `id/name/modelID`, supported resolved/recorded model, reason why `DesktopModelCatalog.resolve()` did/did not return a usable label, downstream normalized request, scalar Session model row, detail, cached summary, and **CCost diagnostic reason** (identity vs absent I/C/W/O usage vs unsupported tier/reference price).
- A before/after state and latest verification after actual Cost Guard cold restart **for EACH target**, with a local exact-ID match. A sanitized public summary may use hashed pseudonyms and totals by cause; do not expose private prompts.

Prove the inventory is complete: count **all affected actual sessions / affected physical requests / contributed models** in the date window; track resolved, incorrect label, truly different provider, unpriceable-from-missing-usage and not-yet-resolved separately. Do not close after fixing only one impressive example.

## 3. Diagnose WHY FR000687 did not fix this, and why new tests also appear unverified

Read these prior documents first; they are not new acceptance waivers:
- `development/backlog/complete/000194-000687-claude-agent-identity-recovery-and-raw-provider-model-help/COMPLETION.md`: **P0 NOT RUN; P1 not delivered; P2 raw tooltips shipped; P3 13 catalog choices, 6 attempted, 5 successes, 1 native error, 7 NOT RUN**. Completion was limited to P2 by a delegate over a privacy boundary the **owner now explicitly removes**.
- `development/journal/recorded-model-help.md`: native recorded `claude-agent/sonnet` and an observer-seen `claude-sonnet-5-5` on an owned test; **replaying a saved owned source shaped payload** did NOT prove actual 2026-11-12 existing sessions were resolved by the installed app.
- `development/backlog/suggestions/000691-authorized-historical-claude-identity-recovery/SUGGESTION.md`: parks exactly the missing historical P0/P1; **superseded by this newly approved executable FR, not a permissible remaining outcome**.
- `development/backlog/suggestions/000676-controlled-claude-agent-live-cost-proof/SUGGESTION.md` and FR000651 `SOURCE-INVESTIGATION.md`: the six native tests, failed Haiku4.5 response, previous false Sonnet-4 guess, exact provider catalog semantics and potential SDK transcript joins.
- `src/sources/opencode_v2_model_identity.py::DesktopModelCatalog`, `src/domain/model_identity.py::desktop_catalog_candidate/unverified_alias`, `src/pricing/catalog.py`, `src/pricing/reference_diagnostics.py`, `src/analysis/model_identity.py`, `src/reports/session_summary.py`, `src/application/{session_catalog,model_help,live_projection}.py`, `src/web/assets/{sessions,session,watch,mini}.js`, archive/cost/analysis identity caches.

**Key known pitfalls that must be tested, not assumed as the owner's cause:**
1. The installed OpenCode Claude Agent stream converter has emitted executed response model metadata, but the upstream AI SDK-to-saved-session path has historically **discarded `response-metadata.modelId`**. The stored model selector can remain `claude-agent/sonnet` despite the SDK using `claude-sonnet-5-5`. Distinguish runtime execution certainty from a mutable catalog-based presentation estimate.
2. Cost Guard currently uses **exact directory-qualified** `/api/provider` and `/api/model`, requires the matching `claude-agent` provider, and caches absence for 30 seconds. A temporary live-test directory, a deleted workspace, a moving model alias, a config overlay mismatch, `location` response-shape incompatibility, source generation change or a stale cached negative can all cause `Version Unverified`.
3. The owner’s OpenCode Toolkit Private configuration has declared **`claude-agent/sonnet#low`** plus a concrete **`claude-sonnet-5-5`** pin for supported test routes. Inspect what the **actual November 12 run** selected, what provider executed, which config scope applied and whether a different model/fallback/effort was actually used. **Session name alone never proves this**.
4. A saved test selector without final usage is not equivalent to successful inference. The FR000687 sixth test failed after native response events and produced no recognized final usage; its current `0`/CCost metadata may be ambiguous. Fix raw recorded model display when source-supported, price only real evidence, report true absent usage separately, and never declare the missing usage a legitimate proof of zero tokens.
5. An unchanged source snapshot can still be displayed from a wrong derived cache: check `MODEL_IDENTITY_SEMANTICS`, cached `ModelResolution` selected scope/signature, summary algorithm, latest source epoch/price catalog, root-cost projection, Full/Mini Watch and real Sessions HTTP/browser. Verify both cold rebuild and warm reuse, without requiring the owner to delete the original database or manually fix rows.

**MANDATORY root-cause answer:** document for each distinct type of still-unverified November 12 session whether the underlying SDK ran a different version or the display resolver failed, with exact supporting source fields. Identify the first loss/lookup boundary and why completed FR000687’s P2 helped tooltips but not that boundary. Do not merely cite the previous privacy choice, say “Claude does not provide data,” or stop at a fake fallback alias.

## 4. Repair: identity first, then all derived Web and cost views

- Prefer **actual per-request executed-model evidence** from an exact session-to-Claude SDK checkpoint/assistant UUID join, provider response metadata already retained elsewhere or durable local config/pinned-routing evidence. Query all owner-authorized relevant local sources, including native SDK transcript, plugin KV, installed policy and test harness logs. If an internal OpenCode read-only endpoint is insufficient, a **safe read-only database/transcript investigation** is explicitly authorized. Do not treat HTTP-only restrictions in an older document as absolute.
- Check current installed code/versions. If an **upstream** record genuinely drops executed version, evaluate an approved minimal durable recording/read-only source adapter for **future** calls, while independently recovering the owner’s actual historical records using whatever trustworthy evidence survives. A future-only change alone **does not PASS**; old identified sessions must also be corrected.
- Resolve existing selected aliases via the **best supportable exact provider/config/location/revision model mapping** when historical per-response data are absent, consistent with the owner’s FR000651 approval of **explicitly qualified current-catalog estimates**. The owner wants a usable concrete Sonnet/Opus/etc. label **when defensible for that exact session**; do not globally rewrite every `sonnet` into Sonnet 5.5 based on today's default, one title, nearest pricing row or an unrelated project. Keep raw `claude-agent/sonnet` for tooltips, keep estimated vs directly executed identity internally, and do not claim certainty not present. If even a defensible session-specific concrete version cannot be recovered for one target, **ON HOLD** is the required final disposition.
- Remove the **demonstrated** catalog lookup/normalization/caching/endpoint gap, not just the UI “unverified” substring. Persist correct derived identity/valuation dependencies and invalidate stale negatives without global source-data destruction. Fix relevant missing real contribution/cost mappings where I/C/W/O + reference pricing genuinely support them; distinguish independent missing usage and pricing blocks.
- Ensure **all historical affected Session rows actually change** after replay/read-only source acquisition, plus Session detail, model/CCost tooltips, Full/Mini Watch and other downstream users of those canonical requests. Preserve GitHub Copilot vs Claude Agent vs direct Anthropic provider distinction, correct effort settings and genuine model/version changes across historical dates. A fresh probe that displays correctly while all old rows stay unverified **fails the FR**.

## 5. Hard evidence / test gate on the owner's installation

**Execution sequence:**
1. Establish the exact installed source OpenCode version and Cost Guard build. Capture the genuine UI/JSON `(version unverified)` baseline against **all** target local 2026-11-12 cases, plus freshly created FR000687 probe sessions.
2. Reproduce and repair the earliest incorrect transition with real source bytes/provenance, using unit/fixture tests **in addition** to, not instead of, real local reads. Add cases for temporary/deleted project directory, per-location catalog and plugin config overlays, source revision, after-restart cache invalidation, native SDK alias selected/executed identity, exact transcript joins and missing telemetry.
3. After implementation, restart the **Cost Guard application normally** (not necessarily the shared OpenCode service), reopen the same Sessions list and detail; for **every target exact persisted session**, compare its source/raw model and corrected friendly label and tooltip. The owner must not have to clear browser/SQLite cache, edit native rows or rerun the original paid prompts.
4. Repeat cold/warm paths and **a second Cost Guard restart** (or an equivalent independently verified fresh process/client) to ensure no stale alias conclusion returns. Then create **at least one tiny, bounded, safely owned new Claude Agent prompt in an equivalent test configuration/directory** and verify its saved selector/version/CCost and the actual browser display **after restart**. Reconcile already executed FR000687 tests without replaying them. If broader all-model testing is needed, respect the explicit prior owner authorization while preserving finite per-model calls/time/cost and no switch to an unrelated paid provider. Record unrun cases honestly; do not claim a full catalog test merely because 5/13 passed.
5. Preserve a private exact-record case ledger and publish a sanitized **counted before/after matrix**: target count, number of Sonnet/Opus/Haiku/Fable/other aliases, resolved model identities, cost-known vs usage-incomplete, provider route, changed cache, browser observation, reboot verification and count still unverified. **Any affected source-supported target remaining as `version unverified`, any failure to inspect a target, or a nonmatching "similar" session = NOT PASS.**
6. Perform existing Full suite/validator and browser/session/cost integration tests, but **no quantity of green synthetic tests overrides failure of the exact local-session readback**. Do not leak raw historical prompt/session metadata into a public GitHub diff.

**No arbitrary time-box as a hidden escape hatch:** continue source-based investigation, compare historical backups/transcripts and installed OpenCode internals where needed, and use checkpoints/next implementation sessions to retain progress. Bounded CPU/I/O, no destructive database writes, no credential exfiltration and no uncontrolled paid inference remain in force; these are normal execution safety boundaries, **not privacy restrictions on reading the owner's records and not a reason to mark a partially delivered FR complete**.

## 6. Closing protocol — choose one AND ONLY ONE

**A: VERIFIED COMPLETE.** Keep `FR.md` in `ready-to-develop` until the exact-case matrix and cold/warm/restart real browser verification have passed. Only then move it to `complete/CCCCCC-000692-hard-gate-repair-exact-2026-11-12-claude-unverified-sessions/`, attach a truthful `COMPLETION.md` with observed case counts, cause, fix, actual model route and results. **No exception waives the real cases.**

**B: ON HOLD.** If true missing historical executed metadata, absent SDK transcript, permanently deleted necessary source data, unrecoverable config/source provenance, model-specific unavailable evidence, or local access constraints make the exact-case goal impossible, do **not** claim completion/waiver. Move **FR000692 itself** to `development/backlog/on-hold/000692-hard-gate-repair-exact-2026-11-12-claude-unverified-sessions/FR.md` and write a companion `HOLD.md` with (a) exact issue count and private references held privately, (b) attempted methods including API, SQLite, SDK, catalogs and tests, (c) failed specific evidence join, (d) evidence demonstrating why no safe correct current/historical release can be assigned, (e) the minimum feasible upstream/local prerequisite, and (f) the partial work/recovery branch pointer. Do not convert to Suggestion, another Ready FR, a performance exception or a fake completed milestone. Only the human owner can later release it from hold.

**Owner's explicit veto:** *Do not let a Decision Delegate or another agent unilaterally narrow this acceptance scope to a cosmetic, tooltip-only or partial success.* If the requirement cannot be met, report the facts and **ON HOLD**. This choice is deliberately strict because the same defect has survived multiple prior FRs.

**Non-goals:** cosmetic string suppression, inventing a Claude release to make a cell look green, misattributing an unrelated model/provider or historical cost, deleting/rebuilding the owner's raw native data, unsafe modifications of the shared OpenCode service, creating another proposal instead of resolving the work, or changing unrelated application features.

**Done means:** the owner's precise 2026-11-12 and FR000687-generated affected local sessions display the correct sourced model release and supported costs **after a real Cost Guard restart**, or **FR000692 is formally ON HOLD with technical proof why that exact result cannot be achieved**. Nothing between these two is approved.
## Owner-supplied local checkpoint/transcript metadata follow-up — 2026-11-13

The owner supplied a new, local, **read-only and sanitized** OpenCode SQLite +
Claude Agent checkpoint + SDK JSONL metadata probe after the hold. The exact
checkpoint-to-transcript hypothesis is now **positively demonstrated on real
local saved records**, independent of the previously blocked native approval
route: **47 distinct assistant-UUID/model joins across all 12 affected alias
sessions**, plus one concrete Fable5.2 control (48 total, 13 sessions).
Alias observations are **9 Sonnet 5.5, 1 Opus 5.5, 1 Haiku 5.5 and 1 Fable 5.1
session**, with zero conflicting matched reply model IDs. The failed concrete
Haiku4.5 session still has unknown final consumption, not established zero
usage. The local probe found 14 exact SDK JSONL transcript files.

**Do not overclaim this as recovered identities for all physical calls.**
The affected twelve sessions previously had **87 normalized known-usage physical
requests**; 47 exact *reply-UUID* joins are a different count/unit and do not
yet establish per-request completeness. Long-running saved sessions can have
more OpenCode assistant rows than retained checkpoint reply references.
Current session transcript membership alone must not certify an older
unmatched reply, especially across forks, turnovers and compactions. The
probe's `native` metadata extractor also reported zero pairs despite earlier
claims that such fields exist; reconcile the source shape rather than
silently declaring the fields absent.

**Use this as the first recovery lead on reactivation**: account for all 87
physical requests using exact durable records where available, separate
selected aliases/current catalog estimates/executed reply identities,
recalculate only supported costs, then complete the original real
same-session browser/cache/restart acceptance unchanged. The sanitized
counted matrix, evidence qualification and ordered next steps are in
[the 2026-11-13 follow-up journal](../../../journal/claude-exact-history.md#owner-supplied-local-checkpointtranscript-metadata-follow-up--2026-11-13).

**Status is still On Hold.** This addendum does not alter mandatory P0 acceptance,
change the current HOLD chronology, authorize any paid inference or product
implementation, or promote the FR to Ready; explicit owner release and remaining
source/access verification are still required.

