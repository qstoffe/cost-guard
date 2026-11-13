# FR 000698 — Sessions: show latest main-thread model with mixed-model asterisk and role-separated tooltip

**Owner-approved Ready to Develop — 2026-11-13.** Permanent FR identity **000698**. Queue priority **000006**, immediately after FR000697 (000005). **FR-only publication:** add this requirement and advance the backlog identity watermark in one documentation-only commit. Do not implement Web/source code, modify runtime data, run paid model calls, change versions/releases or begin product testing during FR authoring. Implementation belongs to the subsequent selected backlog worker/PR.

## Owner request and current problem

In **Cost Guard Web → Sessions**, the **Model** table column currently shows **Multiple models** whenever several model contributors are detected anywhere in the session tree. This hides the model the owner actually used to interact with the **main conversation**, especially when additional models were called only by subagents.

The owner instead wants the **model used by the most recent main-thread prompt** as the visible value. When several distinct models were used in that session, append a literal **asterisk (*)**. On hover, explain which models were used in the main conversation and which were used by subagents, in two clearly separated bulleted groups. Omit the subagent group altogether when there were no attributable subagents.

This is a **Sessions catalog Model-cell change**, not a request to alter model attribution, CCost, token usage, subagent charging, Watch/Mini Watch, AI Stats or Session Detail.

## Verified repository findings (static review, not live reproduction)

- **src/reports/service.py::_session_rows** currently chooses the visible representative from the highest per-model reference spend, falling back to observed model identities / saved main prompt selections. The **multiple_models** flag counts distinct provider/model identities across the entire canonical root-tree request trace, including attributable child/subagent requests. Therefore neither the visible representative nor the mixed flag currently denotes the *last main prompt's model*.
- **src/reports/models.py::SessionUsageRow** carries **model**, **multiple_models**, **contributor_models** and **contributor_models_complete** as scalar session data. Existing contributors are a bounded, deduplicated provider-qualified list without a main-vs-subagent role partition.
- **src/web/assets/sessions.js::View.rows** replaces the value with the literal **Multiple models** when the flag is true. It already attaches shared **ContextHelp** to the value itself and updates keyed rows in place; do not add a separate '?' button or browser-native title.
- **src/application/model_help.py::session_model_tokens** currently prepares a single newline-separated contributor list plus an honest incomplete-coverage notice. **src/application/session_catalog.py::sort_value** currently sorts mixed sessions by the synthetic text **multiple models** instead of their displayed model.
- **src/reports/session_summary.py** owns versioned/disposable scalar cache validation (currently algorithm **session-summary-4**) with exact dataclass parity. **src/application/projection.py**, Web catalog transport and existing tests carry the model/help data to the table.
- **FR000616** established bounded canonical contributing-model lists, incomplete-state qualification and stable/shared ContextHelp. **FR000687** established recorded provider/model selector help and separation from friendly/catalog-derived labels. **FR000694** (Ready) adds resolved-default-effort explanation in model/effort tooltips, and **FR000696** (Ready) adds a Sessions Effort column and period-scoped sorting. Preserve and integrate those contracts when they land, rather than overwriting their new fields or semantics.

## Required visible Model value

1. **Representative = the latest actually used main-thread model.** For each root session, find the latest source-backed **main conversation** prompt with an attributable, actually executed/request-bearing main model; use that prompt's provider/model identity and existing friendly display-label rules for the Model cell. **Do not choose a model from child/subagent requests**, and do not choose the largest-CCost model. When main prompts switched from A → B, the visible model is B even if A had much greater cost. If the latest recorded user action never dispatched a model call, do not present that saved-but-unexecuted choice as confirmed model usage: use the latest attributable used main prompt and preserve truthful pending/unknown qualification.
2. **Mixed-model indicator.** If **two or more distinct source-backed provider/model selections were actually used anywhere in the same canonical root session tree**, including either multiple main-thread models or a different attributable subagent model, display **Friendly Model Name*** (asterisk directly after the visible name). This replaces **Multiple models**, not the model's identity. A single distinct model across all main and subagent calls has **no asterisk**; using the same model repeatedly or in both roles is not multi-model usage. Do not manufacture the star from an unexecuted saved selection, an unresolved model, pricing alias, available-model list or a child of another root.
3. **Missing main proof.** If no main-thread executed model can be established, show the existing truthful pending/unavailable **N/A** behavior as applicable; **never substitute a subagent's model** for the main model. If the contributor set is incomplete, don't falsely claim the visible model or star exhaustively describes all final usage. Live changes must update the cell and help together from one source-qualified snapshot. The asterisk reflects confirmed distinct known models, not speculative unknown contributors.
4. **Model sort** must use the displayed **main model's normalized identity/label**, with the asterisk ignored as punctuation, stable tie-breaking and unknowns last; don't group all asterisk rows at **multiple models**. Integrate cleanly with FR000696's period-scoped server sort, pending/retained keys, paging/epochs and its separate Effort sort. No client-only sorting of the visible 25 rows (FR000696's revised page size).

## Required hover/focus/touch tooltip

Use the **existing model-value ContextHelp** on the entire text, including the asterisk. Present two visually separate paragraphs/sections, each with a heading and **bulleted distinct model entries**:

~~~text
Main models used in session
• Provider A / Model A
• Provider B / Model B

Sub-agents used in session
• Provider C / Model C
• Provider D / Model D
~~~

- **Main models used in session** contains only distinct models actually used by root/main-thread prompts (not child calls). **Sub-agents used in session** contains only distinct models used by canonically attributed subagent/child requests. A model used by both roles belongs in **both** role-specific lists. Use a stable deterministic order (prefer first observed use within each role), deduplicate within each group, and preserve recorded provider/model identities (and existing friendly labels/effort detail when applicable) so same-name models from different providers remain distinguishable.
- **Conditional headings:** show each section only when the corresponding source-backed role has entries. For a main-only session, show **only** the main section; no empty second heading, placeholder subagent bullets or unnecessary separator. For a session with subagents, show the two sections with a blank-line/paragraph break. If main attribution is missing but real subagent activity is known, never mislabel subagents as main; explain absent main evidence truthfully beside the actual known group.
- **Availability:** show this explanatory model help for both single-model and mixed-model cells (the value need not have an asterisk to be useful). Don't leave an old undifferentiated contributor list, a bare '*' explanation or a tooltip that merely repeats **Multiple models**.
- **Incomplete evidence:** for running, retained, source-partial, model-unknown or truncated sets, retain the existing **observed so far / coverage incomplete** qualification. Do not silently discard known identities or claim complete role separation when parent/child provenance cannot be established. Preserve bounded list/length limits, escape source text safely, and do not expose prompt contents, raw traces, session titles, private identifiers beyond existing bounded provider/model help or whole source records.
- Preserve shared ContextHelp pointer-hover delay, keyboard focus, touch activation, Escape/leave dismissal, focus/selection stability and refresh of an *open* help popup while live model data changes. Do not add competing popovers, extra icons, native titles, new columns or further source acquisition on hover.
- Preserve FR000687 recorded-selector/catalog-provenance distinctions and FR000694's effective-default-effort formatting within relevant model tooltip details. The asterisk here means **multiple distinct models** only; it is unrelated to any default-effort asterisk/disclaimer confined to an explicit **Effort** value tooltip by FR000694.

## Illustrative behavior matrix (synthetic examples, not private-session evidence)

| Main-thread models actually used (chronological) | Attributable subagent models | Visible Model | Tooltip |
|---|---|---|---|
| A | none | A | Main group: A only |
| A, B | none | B* | Main group: A, B; no subagent heading |
| A | C | A* | Main: A; Sub-agents: C |
| A, B | B, C | B* | Main: A, B; Sub-agents: B, C |
| A | A | A | Main: A; Sub-agents: A (two groups, no star) |
| unknown/unexecuted selection only | C | N/A / pending as justified | No invented main model; known subagent evidence qualified |

## Data, integration and acceptance

1. Derive **role-separated, source-backed actual usage** from existing canonical prompt/request and parent/child attribution evidence; avoid inferring roles from title, model label, price contribution or a naive final trace event. Treat compactions, parallel tool calls, child sessions, main-model switches, failed/unexecuted selections, same effective model with distinct recorded provider selectors and provider-identical display labels correctly. Where attribution is genuinely missing, state uncertainty instead of fabricating a main model or role.
2. Extend only the smallest needed bounded session scalar row / model-help DTO and Web allowlist. Update **src/reports/service.py**, **src/reports/models.py**, **src/application/model_help.py**, **src/application/session_catalog.py**, **src/application/projection.py** and **src/web/assets/sessions.js** as appropriate. Revise **session_summary** cache algorithm/schema/identity validation to reject or lazily rehydrate obsolete records without relying on old undifferentiated contributors for new-role claims. Preserve source revisions, prior-cost snapshots, canonical request accounting, CCost and duration computations.
3. Synthetic unit/integration coverage: exact matrix above; latest-main-not-highest-cost; most recent main used versus last child; multiple main prompts / one main prompt; same model across roles; different provider same friendly label; recorded aliases, incomplete/truncated/retained/running sources; no-use saved selection; missing main identity; schema/cache migration; and source-revision updates without stale model/help disagreements.
4. Rendered Web/browser checks: Model cell, literal trailing '*', two grouped bullet paragraphs and omission of absent heading; hover, keyboard focus, touch and open-tooltip live updates, long names and narrow viewport. Verify sort ascending/descending by displayed main model with stars ignored, 25-row pagination and FR000696's selected-period sort path, pending/retained states and stable row keys. Preserve Effort-column help and any existing global focus fix from FR000695.
5. **No business-logic expansion:** no changes to physical child attribution for costing, no token/CCost recomputation policy change, no new model API calls or background crawlers, no new persistent user ledger, no change to session detail/Watch/AI Stats/CLI and no model-version guessing. Perform normal implementation verification only when this FR is selected; FR authoring itself is documentation-only.

**Desired outcome:** The Sessions **Model** column immediately answers **“Which model did I last use for my own prompts?”**; '*' means at least one other distinct model actually participated, and the tooltip reveals exactly which models were used in the main thread versus subagents without merging their roles.
