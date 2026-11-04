# FR 000581 — Normalize context column labels: Ictx, Δ Ctx and Ctx

## Owner request and backlog decision

**Owner-approved executable feature request, 2026-11-04.** Permanent identity **000581**; Ready priority **000210**, following existing Ready FR000580 (000200). Scope is a **small Web Beta presentation/terminology correction** across the full **Watch** page and **Mini Watch**. This FR is for backlog authoring; **do not implement product changes now**.

A previous full-Watch implementation introduced the column name **`ECTX`**, apparently from a misunderstanding of the owner's intended **incoming-context** shorthand. The established CLI vocabulary already uses **`~Ictx`**, **`Next Ictx`** and **`Δctx → Next Ictx`**; the owner wants the full Watch's first-request incoming-context column to use the same **Ictx** spelling convention. The owner also prefers natural capitalization instead of all-caps abbreviations. There is no reason for this nomenclature refinement to affect any computation.

## Exact display changes

| UI / position | Current heading | Required heading |
| --- | --- | --- |
| **Full Watch → Running Prompts**: effective incoming context at the start/first request of this prompt | `ECTX` | **`Ictx`** |
| **Full Watch → Earlier Prompts**: same first-request context column | `ECTX` | **`Ictx`** |
| **Full Watch → both tables**: change in context since preceding canonical anchor | `Δ Ctx` | **`Δ Ctx` (unchanged)** |
| **Mini Watch → Running Prompts**: estimated next incoming prompt context | `CTX` | **`Ctx`** |
| **Mini Watch → Earlier Sessions**: latest valid session/current-next context | `CTX` | **`Ctx`** |

**Capitalization is exact and deliberate:** `Ictx` uses a capital **I** followed by lowercase **ctx**; `Ctx` uses a capital **C** followed by lowercase **tx**. Do **not** render `ICTX`, `ECTX`, `CTX`, `ICtx` or `Δ ctx` in these headings. The delta heading remains **`Δ Ctx`** (capital C, lowercase tx), with the same space after Δ.

These are three *different meaning/scope* labels despite similar shorthand: full Watch `Ictx` stays the first-request prompt incoming context, `Δ Ctx` stays the per-prompt delta, and Mini `Ctx` stays its existing current/next estimate (with a session-level value for Earlier Sessions). Do not reinterpret Mini `Ctx` as first-request `Ictx` or make both Watch versions display the same measurement simply to standardize naming.

## Scope and implementation considerations

- In `src/web/assets/watch.js`, change the shared `columns` heading (`ECTX` → `Ictx`) and **current user-facing help**, especially the Session Context summary tooltip that contrasts next-session context with `prompt ECTX`. Keep its semantic explanation, estimation/unknown guidance, accessible column help and the ten-column table layout.
- In `src/web/assets/mini.js`, change both table headers and all associated **visible/accessibility** references `CTX` → `Ctx`, including table `aria-label`, header help mapping, row titles/tooltips and any other current display text. Do not rename the canonical data fields used to populate these values.
- Update **current** Web Beta and Mini Watch user documentation (`docs/web-beta.md`, `docs/web-mini-watch.md`) and relevant present-tense module/help descriptions. Keep historical completed FRs, completion records, past release notes and archived evidence unchanged as historical records.
- Update the active Web DOM/interaction/browser assertions and fixtures that expect the old headings, e.g. `development/tests/integration/web_live.cjs`, `development/tests/integration/probe_watch_cards.cjs`, `development/tests/integration/probe_mini_watch.cjs`, `development/tests/integration/probe_mini_sessions.cjs`, and `development/tests/fixtures/mini_sessions.cjs` as applicable. Coordinate with queued **FR000578**'s Mini first-column alignment and **FR000580**'s full Watch summary redesign so no stale heading/help text is reintroduced.
- **Presentation-only:** preserve internal field/API/DTO identifiers such as `incoming_context_tokens`, `watch_next_context_tokens`, `watch_delta_context_tokens`, their source/valuation logic, estimates, unknown states, prices, tables/columns/order, CSS measurements and viewport/scroll behavior. No CLI/other reports renaming or unintended calculation changes. The displayed value must remain identical before and after the rename.

## Acceptance criteria

1. **Full Watch** Running and Earlier tables each show **`Ictx`** immediately before **`Δ Ctx`**, neither `ECTX` nor an all-caps variant. The other eight headings and ten-column order are unchanged. Existing column descriptions and the Session Context summary contrast correctly use `Ictx`.
2. **Mini Watch** running table and expanded Earlier Sessions table both show **`Ctx`**, with correctly updated accessible table names, column help and row descriptions. Existing session/title, #, CCost and Duration column semantics remain intact.
3. Numeric context/Δ values, formatting, missing/N/A, per-prompt versus per-session meaning, warnings, totals, partial/retained updates, keyboard/focus help and tooltip contents are unchanged apart from terminology/capitalization.
4. Browser/DOM/regression checks in Classic, Web light/dark and ordinary/narrow Mini layouts pass with the new headings, including the active and expanded Earlier tables. No new columns, unintended reflow, hidden values or new backend work.
5. Documentation reflects **`Ictx`**, **`Δ Ctx`** and **`Ctx`** accurately; historical records continue to describe the originally implemented names without rewriting history.

**Boundary:** only write this approved Ready Feature Request and increment the backlog identity watermark in the authoring session. No implementation, version bump, release or test/code edits now.
