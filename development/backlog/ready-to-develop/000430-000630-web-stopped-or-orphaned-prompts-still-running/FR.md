# FR 000630 — Reconcile stopped/orphaned prompt attempts still shown as RUNNING in Web Watch and Sessions

**Owner-authorized Ready correctness investigation and conditional fix, 2026-11-07.** Permanent identity **000630**; Ready priority **000430** (after the already-Ready/ongoing FR000624 at 000420 and before FR000625 at 000520). This is a **backlog-only authoring change**: do not implement code, run a real model prompt, interrupt OpenCode, alter product versions, or touch other FRs in this publication.

## Reported symptom and evidential status

On **2026-11-07**, the owner supplied two views from **Cost Guard Web Beta v80.203** of the same resumed OpenCode session. A checkpoint-related **save-context-then-pause** prompt, submitted around **21:16 local time**, was still displayed in yellow as **RUNNING** after approximately **65–66 minutes**:

- **Web Sessions → session detail:** `[RUNNING]`, continuously increasing duration, **0 observed calls**, `CCost 0`, unavailable running-only breakdown, and total session duration inflated by that elapsed time.
- **Full Web Watch:** the same prompt and similar continuously increasing duration, **0 observed tool calls**, **0 confirmed custom skills**, and an unpriced/unknown whole-session cost.
- The owner believes actual execution has ended, but screenshots alone **do not establish a native terminal outcome**, provider state, exact completion time, whether OpenCode is genuinely blocked in an in-flight request, or source freshness. Do not claim the exact prompt is proven stopped based on its age or zero calls. Omit the personal session ID and full prompt/working context from the public repository.

This is a **cross-surface lifecycle concern**, not simply a yellow CSS row or a single Web Watch card. The displayed product version matches current main at inspection; that does not prove the host's exact code revision or that every source observation is fresh.

## Concrete code concern to investigate first

The current shared logic has a potentially indefinite false-running path:

1. `src/sources/opencode_v2.py::_list_native_sessions` reads `/api/session/active` and makes `SessionInfo.active` explicitly `False` when a successfully read active-map excludes the session.
2. `src/analysis/causal.py::_attempt_in_progress` nevertheless returns `True` for an assistant attempt with `completed_at_ms is None`, even without active-work evidence and even when `snapshot.root.active is False`. The existing `development/tests/test_opencode_terminal.py::test_inactive_and_unavailable_status_do_not_prove_completion` explicitly preserves that conservative rule. It protects incomplete evidence but can label an abandoned/unclosed record **RUNNING indefinitely** if the source never persists a conventional end.
3. `src/reports/session_history.py::SessionHistory.acquire` increments elapsed running duration on an unchanged fresh snapshot; `src/watch/cards.py::WatchCards._card` similarly projects a running row's duration against the current clock. Thus the same shared classification can produce the two observed displays and grow the session total.
4. Other known cases are missing/late terminal evidence, incomplete/retained captures, invalid session-status mappings, checkpoint/compaction continuation attribution, a stuck native provider request, or a stale active Web host. These are **hypotheses**, not established root causes for this incident.

Prior related deliveries are **FR000546** (terminal reconciliation), **FR000551** (four-slot capture starvation), and **FR000559** (failed pre-response continuation); consult their completions and `development/journal/web/watch-terminal-lifecycle.md`. Do not reopen/duplicate them without a newly demonstrated gap.

## Desired outcome

For a **fresh, authoritative, complete** source observation that supports a stopped/failed/cancelled/abandoned attempt, Cost Guard must not indefinitely show **RUNNING**, grow its running elapsed duration, retain live tool/background indicators, or count it as executing. Preserve any observed requests, usage and supported failure/cancellation cause; do not invent success, a terminal timestamp, final tokens, a price or an unsupported reason.

If the source contains an unfinished assistant but native lifecycle evidence says the session is not active, **reconcile the contradiction explicitly**: determine whether the negative native signal is authoritative for execution or merely a hint in that OpenCode generation. If genuinely indeterminate, represent the **unverified / stale / uncertain** state distinctly from confirmed ongoing execution, rather than permanently asserting RUNNING. Such a state must remain honest about missing end time and costs and should not silently become a successful completion. Do not reclassify all inactive-but-unfinished records as ended without source-contract proof.

Real long model calls, active local tools, child/subagent/background work, pending checkpoint continuations, resumptions and valid newer attempts must remain correctly active. No arbitrary duration/no-token/no-call timeout, forced abort or quota inference is a substitute for lifecycle evidence.

## Investigation and implementation requirements

1. **Establish actual status and comparison.** Identify the running Web host revision, OpenCode V2 source generation/version, and the affected canonical prompt/attempt (using privacy-safe IDs/evidence). Compare OpenCode native active status, source message/attempt terminal and continuation records, complete snapshot/freshness, CLI Watch, Web Watch and Web Sessions detail at comparable observations. Specifically inspect `/api/session/active` and persisted assistant `time.completed`, finish/error/idle events without requiring the owner to disclose private prompt text. If access to the actual source is unavailable, explicitly state that limitation; reproduce the plausible source shape with a minimal sanitized fixture.
2. **Find the real ownership boundary.** Determine whether the source says running, idle, unknown or stopped, whether captured terminal evidence is lost/misattributed, whether the Web worker is stale, or whether current canonical policy treats an orphaned unfinished assistant as live forever. Address the source/causal/retention owner, not a page-local timeout or browser-only cosmetic filter. If OpenCode itself continues to report a truly running request, do not claim Cost Guard can know it has ended; characterize upstream/request-hang uncertainty.
3. **Shared lifecycle and truthful display.** Correct classification and duration/total behavior consistently in CLI, Web Sessions detail, Full Watch, and Mini Watch. Distinguish *confirmed running*, *confirmed terminal* and any justified *unknown/stale* state. Use one canonical source of truth and sensible refresh/recovery semantics. Never keep incrementing a **confirmed live-execution** clock solely because an orphaned persisted assistant record exists.
4. **Checkpoint/resume coverage.** Explicitly cover a save-and-pause checkpoint prompt resumed into a new session, with zero completed calls and no final assistant event, plus later clean response, failure, interruption, compaction, new attempt, and background-task completion. Prevent old retained rows, missing records, delayed generations or refresh/reconnect from resurrecting a retired prompt.
5. **Conservative source handling.** Do not treat `active=False` from a missing, partial, failed or unsupported native status response as authoritative. Preserve existing protections against incomplete data and legitimate quiet-but-live attempts. The source adapters and tests should express why a given negative status is trustworthy.

## Acceptance and evidence

- A **pre-fix failing regression** from the actual observed source shape or a sanitized equivalent reproduces a demonstrable false RUNNING/indefinite duration across canonical analysis and at least the affected Web export/detail path. If no false-running defect can be reproduced, record the competing explanation and **do not claim a bug fix** merely because a heuristic or UI color was changed.
- After repair, the same stopped/contradictory case no longer appears as **confirmed RUNNING** forever; elapsed execution display and aggregates are accurate or explicitly uncertain, without fabricating an end timestamp or losing known usage. Both shown pages agree, as do CLI and Mini when consuming the same source evidence.
- Verify unchanged/partial snapshots, cached history, cold host start, page reload, long-lived SSE refresh, restart/reconnect, new attempts, already-delivered FR000546/551/559 cases, legitimate long-running provider/tool/child/background work, and checkpoint continuation.
- Focused source/analysis/retention/Web tests must demonstrate the full lifecycle; document real-source and browser checks separately, along with the actual cause, versions and remaining uncertainty. Preserve bounded capture scheduling and performance, cost/token accounting and supported context/session totals. Do not modify the owner's live OpenCode session to test a display bug.

The owner's original screenshots are evidence of a **plausible regression**, not proof of the exact completion/stop mechanism. This FR is intentionally evidence-led: fix what can be established, preserve uncertainty otherwise.
