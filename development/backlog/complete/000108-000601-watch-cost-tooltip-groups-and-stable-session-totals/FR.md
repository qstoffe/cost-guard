# FR 000601 — Model-grouped Watch cost tooltips and stable incremental session totals

**Owner-approved executable Ready Feature Request, 2026-11-05.** Cost Guard Web Beta (Full Watch, including Running and Earlier cards, plus shared session-total behavior used by Mini Watch). Permanent identity **000601**, Ready priority **000170**, following FR000600 (priority 000160). This FR is **not** a second causal child-attribution implementation.

## Owner observation and desired behavior

A completed OpenCode Toolkit `/repo-backlog` root session containing only one user prompt displayed **prompt CCost 161** but **Total CCost 270**, with an invoked Decision Delegate subagent. FR000600 already owns the identified OpenCode V2 `subagent`/`sessionID` causal-attribution defect. That missing association can also hide the linked agent from the existing per-cell tooltips. **Do not move or rewrite FR000600**; consume its canonical attribution in this FR.

The owner wants detailed, *useful* value-hover breakdowns, but grouped by the **models and effort levels** doing the work rather than duplicated for every subagent instance. The owner specifically **withdraws the idea of a per-cell Token Mix % tooltip**.

A separate recurring observation is the unexpected footer text **“session total updates delayed; retained observation, not current”** next to a known session cost, including an old unchanged card in **Earlier Prompts**. This can persist and looks like a stuck total even though the session had previously shown a complete amount. The owner expects **Loading… only when no usable total has yet been established**, a quiet stable total otherwise, and cheap incremental updates if new work starts in that session.

## Checked existing behavior and boundaries

- **Delivered FR000590** already implemented value-targeted CCost/Model/Calls help, actual I/C/W/O reference-priced categories, effort attribution, source-owned detailed breakdowns, hover delay, keyboard/touch access and long-tooltip sizing. Current `src/application/prompt_costs.py::detail_tokens` emits a **separate section per linked agent + model/effort**, plus per-agent subtotals, not the requested consolidated **Subagents per model/effort**. `src/web/assets/watch.js::Card.update` already attaches `cost_detail_help`, `model_detail_help` and `calls_help` to each corresponding cell value. This FR refines existing capabilities; it must not duplicate them.
- **Delivered FR000572** already implemented the reusable `src/analysis/session_cost.py` SQLite `session-ccost-v1` incremental root-tree cost cache. Existing measured fixture behavior values 2,000 requests once, then values only 1 additional request; an unchanged replay values 0. **Do not replace or recreate that accounting engine.**
- **Delivered FR000583/FR000586** quieted routine transient refresh text; **FR000592** removed a separate false page-level “Still loading Watch data” warning. Neither proves this persistent session-total condition fixed.
- Current `src/watch/cards.py` sets `cost_state = "refreshing"` when a row capture arrives and when an already-known cost is queued for checking, including routine/periodic rechecks. A **single shared cost worker** (`src/watch/session_costs.py`) services the visible cost jobs. `src/web/assets/watch.js::Card.drawSummary` starts a 30-second display timer on `loading/refreshing/retrying` and subsequently prints the quoted delay/retention warning even when reusing a previous known amount. This supports a **plausible mechanism**, not independent proof of which internal state caused the owner's original live incident.
- Whole-session CCost is **not** always mathematically identical to a displayed prompt row or its delta: it also includes separate compaction, late child usage, other root-tree requests and corrections. Pricing/catalog changes, revisions/deletions and initially incomplete data can change a previously seen value without a brand-new user prompt. Any optimization must retain those cases and source integrity.

## A. Group CCost hover by producer role and model/effort

On the **visible `CCost (I + E)` prompt-cell value** in both Full Watch tables, keep the existing detailed cost breakdown, but display **one section per distinct (producer role, provider-qualified model identity, actual effort/variant)** instead of one section per individual subagent session.

Desired example (illustrative only; use actual observed data and current Credits/USD):
 
~~~text
Main prompt — GPT-6.1 Sol · Extra High
• Input: 4
• Cached input: 2
• Cache write: 0
• Output: 15
Subtotal: 21

Subagents — GPT-6 Astra · Max (3 agents)
• Input: 1
• Cached input: 0
• Cache write: 0
• Output: 80
Subtotal: 81

Subagents — GPT-6.1 Terra · Low (2 agents)
• Input: 2
• Cached input: 1
• Cache write: 0
• Output: 13
Subtotal: 16

Total CCost: 118
~~~

- **Main prompt** and **Subagents** must remain distinct even if they used the exact same model and effort. Multiple subagent sessions using one model/effort become one aggregated *Subagents* section with a trustworthy count of contributing sessions when available. Different models or different efforts/price tiers remain separately identified. If a main prompt switched model/effort, represent its real main groups rather than mislabeling all usage as the first model.
- Derive each category amount and subtotal from the **canonical unrounded individual physical-request valuations** and causal agent ownership, then group them. Do **not** infer percentages, spread an aggregate difference across agents, double count nested/parallel child requests or invent a missing child.
- Keep **Input, Cached input, Cache write, Output, per-group Subtotal and overall Total**. These lines are **reference cost contributions**, not raw token percentages, and are distinct from the existing first-request `I + E` split. Apply current unit formatting and explain independent rounding only where useful. Partial pricing, absent category telemetry, zero versus N/A, unmatched child activity and genuinely missing attribution must remain honest.
- Retain FR000590's ~600-ms pointer-open behavior, direct value hitbox, focus/touch accessibility, stable view updates, scrolling/clamping and compact sections. Support many distinct groups without silently dropping evidence; a justified payload bound must report real omitted group/count/cost/calls evidence accurately, not fabricate completeness. Never trigger backend/model work on hover.

## B. Model-cell and Calls-cell tooltips

**Model cell:** display the normal **main model** value as today, including FR000590's positive-evidence linked-agent `*` marker where applicable. **If there is only one distinct provider-qualified model used across the main prompt and its attributed subagents, do not open a model-cell tooltip**, even when several subagents used that same model. When **two or more distinct models** contributed, hovering/focusing the **model cell value** lists the actual main model group(s) and subagent model group(s), with **effort levels** and clear headings. Avoid duplicate identical entries; multiple efforts under a listed model can be shown distinctly inside its group. Do not misrepresent a model switch without a subagent as linked-subagent participation. Preserve the linked-star accessibility meaning even if the one-model rule suppresses the popup.

**Calls cell:** when there is a meaningful main/subagent or multiple-model breakdown, hovering/focusing the **Calls value** shows the number of **physical model requests**, grouped using the exact same main-versus-subagent and provider/model/effort keys as the cost tooltip. Repeated subagents on one model/effort aggregate their Calls, not one repeated line per agent. Show a reconciled total matching the cell's Calls number when request evidence is complete; partial/missing evidence must not be presented as full counts. Do not confuse model requests with tool calls or billable summaries. Omit a redundant single-group tooltip with no extra information.

**Token Mix %:** **NO additional per-cell Token Mix tooltip**. Retain the existing column-header explanation and percentage calculation unchanged.

## C. Stable, correct and cheap Total CCost for historical sessions

- A **complete, source/valuation-revision-matched cached session total** is a stable number. For an unchanged **Earlier Prompts** session, display that number **without routinely marking it `refreshing`, delayed or retained/not-current** merely because a capture is republished, the UI is redrawn, earlier disclosure changes, another session is running, the view reconnects or the periodic Wake occurs. Do not repeatedly schedule a full historical snapshot/revaluation for a known unchanged Earlier session. Retain its baseline across normal Earlier eviction/re-entry and restart using the existing derived cache.
- **When the initial total is unknown**, show **`Loading…`** locally in Full Watch and the existing Mini session-total place (not a fabricated zero, a naked dash, or a misleading 30-second “delayed” warning). After it becomes available, replace Loading with the actual amount. Normal checking of an already-known amount should not flash a loading state or attach a new delayed warning. **Remove the quoted session-total-delay text and its timer-driven equivalence** for ordinary pending checks.
- On new running work in an older session, use the **prior validated full-session cost as a baseline** and incrementally reconcile new/changed canonical request contributions as they are observed, rather than rebuild all previous prompt costs. Use the existing `SessionCost` request-identity/fingerprint cache; **do not simply add the visible prompt-cell cost delta**, which can lag attribution and omit compaction/children/corrections (including FR000600's bug).
- **Event-driven invalidation:** legitimate root-tree membership/source revision, changed physical usage, late child or compaction requests, corrected/deleted history, cost valuation/catalog identity and observed completeness changes can require reconciliation or full invalidation/rebuild. A mere timestamp/card generation/refresh tick is **not evidence that the known amount became wrong**. Only label a retained value as not current when a genuinely relevant revision/source error prevents validation. Sustained confirmed failure, auth/source loss and partial/unpriced data must remain honestly distinguishable (ideally via the existing source/health surface or a concise localized state), never quietly masquerade as verified current. Do not hide a real correction behind an indefinitely reused stale number.
- Investigate/fix queue fairness and completion transitions so a static Earlier session cannot remain indefinitely `refreshing` simply because a single shared cost lane repeatedly services busy roots, a different generation supersedes a result, or a periodic recheck is requeued. Prefer no unnecessary job over increasing uncontrolled parallelism. Keep one SSE owner, bounded backend resources, no extra polling/provider calls and no UI-blocking full-root scan.
- Full Watch and Mini Watch must agree on the same canonical total/state for the same root and revision; the main Sessions/report/CLI cost semantics remain unchanged. Keep direct per-prompt CCost computation and Full Watch's prompt-row responsiveness independent of the session-total cost lane.

## Acceptance and verification

1. **Tooltips:** synthetic canonical root plus multiple `subagent` sessions of identical model/effort yields one **Subagents** cost section and Calls line with aggregated counts; different models/efforts yield distinct labeled groups. Main-role and child-role never merge, and sums match independent unrounded request valuation. Test child sessions with different prices, corrected requests, nested agents, incomplete pricing, missing category data and zero calls.
2. **Model conditionality:** one distinct model with zero, one or many same-model subagents has **no Model-cell tooltip**; at least two distinct models shows deduplicated main/subagent lists including effort. Marker `*` still follows authentic subagent participation; in absence of a subagent, a main-model switch does not invent one. Check focus/touch, keyboard, long-scroll bounds and both Watch tables.
3. **Calls:** same role/model/effort grouping as CCost and valid sum equal to physical model-request count, not tools; no extra Token Mix **cell** tooltip.
4. **Static Earlier regression:** render a historical session with a complete known cost, run repeated healthy Live publications, other active-session updates, ordinary re-entry, and >3 minutes simulated/wall clock. The total remains stable and **the “session total updates delayed; retained observation, not current” text never appears**. Instrument no-op snapshots/valuation/cache writes/job submission to demonstrate no unnecessary work, not just silenced UI.
5. **Running continuation:** a cached old session becomes Running: only genuine new/changed contributions are valued, and the visible total advances coherently with the existing prompt activity. Test late child requests, compaction, concurrent focal prompts, cost corrections and authoritative deletions. Compare final total against independent complete root-tree reference valuation, not a forced sum of currently visible prompt rows.
6. **Real invalidation/failure:** changed catalog pricing, source revisions, actual source outages, lost completeness and restart/cache miss trigger correct revaluation or truthful `Loading…` / partial / unavailable states. A permanently failed worker cannot masquerade as a successfully current total or remain an endless fictitious refresh. Other sessions' progress must not change unrelated Earlier values/states.
7. Add focused model-free Python request/cache/scheduler/projection tests and JS/real DOM/browser rendering tests for Full Watch and Mini where affected, including existing Credits/USD, partial `?`, zero vs N/A, headings/hover/accessibility, narrow themes and SSE cadence. Update current docs and journal/architecture as appropriate. Do not copy the owner's private session dump into the repository or initiate paid model evaluations merely to create this FR.

**Scope relationship:** FR000600 corrects **which child requests belong to a prompt**. FR000601 corrects **how already-attributed requests are grouped and exposed**, plus session-total freshness/scheduling. The acceptance tests that rely on repaired `subagent` attribution must run after or against FR000600; do not implement a second ad hoc child parser here. This FR deliberately supersedes only FR000590's per-agent tooltip grouping and over-eager one-model hover, and FR000583/FR000586's insufficient session-total quieting, while retaining their other delivered behavior.

**Authoring boundary:** publish only this executable Ready FR and the permanent identity watermark to 601. No implementation code, tests, deployment, runtime reload or version/release changes at FR creation.
