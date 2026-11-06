# FR 000608 — Mini Watch: latest-prompt CCost and details in Earlier Sessions

**Owner-approved Ready Feature Request, 2026-11-06.** Permanent identity **000608**; Ready queue priority **000260**, after FR000607 (000250). **Backlog authoring only:** do not implement the product, change versions, run product gates or move other FRs during publication.

## Owner request

In **Cost Guard Web Beta → Mini Watch**, the expandable **Earlier Sessions** table currently shows **Activity | Session (Total CCost) | Ctx**. Add a narrow standalone **CCost** column **between Session and Ctx**. Its value is the estimated reference **CCost of the latest actual prompt in that historical session**, not the total cost of the session.

The resulting historical table has **exactly these four visible columns**, in this order:

```text
Activity | Session (Total CCost)     | CCost | Ctx
08:05    | Refactoring work (562)    | 49    | 85K
22:41    | Debugging issue (1 204)   | 173   | 91K
```

Amounts are illustrative. **Session (Total CCost)** remains a *single existing column*: the name stays left, with the **whole-session total** at its right edge. The new **CCost** shows only that row's **last prompt**. Do not swap the meanings, derive the prompt cost from the difference between session totals, or make the last prompt's cost appear to be the whole-session cost.

The separate **running/recently ended prompts** table must stay unchanged: **Session (Total CCost) | # | CCost | Duration | Ctx**. The new column is historical-only.

## Contextual help instead of more visible columns

- **CCost column-header tooltip:** say clearly, in concise user-facing English, that this is the *latest prompt's estimated reference cost*, not the session total or the actual provider bill. Preserve the existing truthfulness of `N/A` (unavailable) and `?` (partial pricing).
- **Each historical CCost value has its own contextual tooltip**, opened from the **value** by pointer hover, keyboard focus or touch using the app's shared `ContextHelp` behavior. Use a short, scannable set of genuinely available facts about **that same latest prompt**, preferably:
  - **Prompt:** its canonical session-local number, when known.
  - **Model:** the actual main/provider-qualified model identity when available.
  - **Effort:** the supported selected reasoning effort, or an honest unavailable/default state as warranted by evidence.
  - **Duration:** that prompt's canonical finished duration, not the total session's age or the Activity clock.
  - **Calls:** attributed model-request count if available, plus only a brief relevant note when linked subagents/other contributing models or a meaningful failure/partial state affect interpretation.
- If the cost includes linked agents or multiple models, do **not** falsely attribute the whole amount to the single displayed main model. Reuse authoritative model/cost-detail semantics where helpful; avoid a long raw breakdown or repeated explanations on every row.
- No permanent **Model**, **Effort**, **Duration**, **Calls** or **#** columns in Earlier Sessions, no separate help icon, no row-wide hover popup, no browser-native duplicate `title` tooltip and **no raw prompt text/payload** in the help. Information must remain understandable for keyboard and assistive-technology users; when a field is unknown, do not invent it.

## Data and layout boundaries

- Reuse the **canonical representative actual prompt** already supplied with each `history_cards[*].rows` entry (today the first historical row), as used for the historical Activity display. The existing Live projection in `src/application/live_projection.py` already exports its prompt-local `ccost`, prompt number, calls, completion/status information, and the row's model, effort and `watch_duration_ms`. Reuse shared server-prepared display/price semantics rather than browser-side valuation, new history scans or a second source of truth. If a representative prompt or a specific metric is absent, show truthful `N/A`/unavailable help instead of accidentally taking data from a different prompt.
- Use the same configured Credits/USD selection and rounding conventions as the running prompt CCost. Preserve zero versus unknown, partial pricing/attribution, retained or corrected data and historical session status. Live corrections should update both the value and its tooltip coherently without focus/hover flicker.
- Preserve the **three newest eligible, distinct finished sessions**, their **oldest-to-newest** presentation, Activity's `HH:mm` and full local-time tooltip, session-title ellipsis and nontruncating whole-session total, historical **Ctx** meaning, running/history exclusion, grace period, resumption behavior, and one shared scroll region for both tables.
- Keep **CCost** as a compact nonwrapping, right-aligned numeric metric, with concise nonwrapping header. Let **only the session title** surrender horizontal space before clipping any cost, time or Ctx value. Adjust historical-only table row creation, header help, empty/loading `colSpan`, cell indices, CSS and accessibility from **three to four historical columns**; do not accidentally alter the running table's five-column layout.
- Coordinate with **FR000607**, which targets the smallest *collapsed opening* PiP width that fits the three top-header items on one line. This fourth historical table column must **not** force a larger initial Fit-on-open width or undo FR000607's header-based sizing criterion. At genuinely narrower achieved/manual widths, preserve readable horizontal panning within the existing Mini prompt/session region instead of hiding metrics or wrapping values. Earlier Sessions expand/collapse must retain the existing click-driven height-fit behavior, not introduce passive resizes.
- This is a small **Mini Watch presentation change**, not an accounting, history selection, Web Watch, settings, CLI, subscription, persistence or API redesign. Prefer the existing `mini.js`, `mini.css` and shared help/display facilities.

## Acceptance / implementation checks

1. Expanded Mini Earlier Sessions reads **Activity | Session (Total CCost) | CCost | Ctx**, with values and headers correctly aligned, and the running table remains its original five columns. Verify the last prompt's CCost can differ markedly from the whole-session total for multi-prompt sessions.
2. Header help identifies **latest prompt** versus **full session**. Hover/focus/tap on each **CCost value** reveals that specific historical prompt's model, effort and duration, plus its number/calls when available; no raw prompt text or long duplicate tooltip. Mixed/linked-model details and unavailable information remain honest and accessible.
3. Confirm genuine zero, unavailable/partially priced, linked-subagent and multi-model cases, Credits/USD switching, corrections/retained Live observations, and source data without a trustworthy representative prompt; do not fabricate a model, effort, duration, cost or completion.
4. Verify multiple earlier sessions, latest-prompt choice, session resumption, empty/loading/unavailable four-column rows, Activity's existing time help, Ctx, and both tables' keyboard/scroll behavior. Earlier remains collapsed by default.
5. Exercise compact/default and manually narrowed Picture-in-Picture windows, FR000607's narrow Fit-on-open mode, Classic/Web themes, zoom and scaling. Preserve nonwrapping complete CCost/total/Activity/Ctx values and an accessible horizontal overflow path when needed; do not enlarge the header-based default width solely for the extra historical column.
6. When implementing, update `docs/web-mini-watch.md` and focused Mini tests/fixtures (such as `development/tests/test_mini_watch.py` and relevant `development/tests/integration/mini_*.cjs` / browser probes). Record actual verification, without claiming physical Windows proof from headless emulation.

**Publication boundary:** publish this Ready FR and advance `development/backlog/identity-state.json` highWatermark from **607** to **608**. No implementation, product docs/tests, release or version changes belong to this authoring step.
