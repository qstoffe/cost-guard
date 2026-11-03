# FR 000558 — Refine Web Watch prompt tables and add live per-prompt Token Mix %

## Owner request and backlog decision

**Owner-approved executable Web Beta feature request, 2026-11-03.** Permanent identity **000558**; Ready priority **000070**, after the currently queued FR000555 (000050) and FR000556 (000060). Scope is **both** the *Running Prompts* and *Earlier Prompts* session-card tables in Web Beta Watch. The owner wants a closer visual match to CLI prompt numbering, clearer column order and explanations, and the same per-prompt Token Mix % as the CLI session report, preferably updating as model calls accumulate.

This is a UI and existing-data projection feature, **not** a change to CLI reports, canonical token accounting, model invocation, pricing, session membership or active-prompt lifecycle. Publication of the FR itself changes only the backlog.

## Inspected baseline and relevant existing behavior

At inspected `main` commit `8c96f5c9f7e41ed7dd205e1471294d13780df776`:

- `src/web/assets/watch.js::Card` renders nine columns in this order: `Started | Prompt | Model | Effort | CCost | Model Calls | Duration | Δ Ctx | Context`. Its Started cell currently embeds `Prompt N` and either a clock or, for Earlier rows, a full date/time. Its Prompt cell contains only the preview. Only Context currently has a header `title` tooltip.
- `src/web/assets/app.css` uses a subgrid Watch table, with the second column as the truncating Prompt preview, and adds a separate border/padding around `.watch-history`.
- CLI Watch (`src/presentation/watch.py::_row_label`) already places `#N` immediately before the prompt preview. The CLI session report (`src/presentation/report.py::_render_prompt_block`) already has `Token Mix %` and renders **Input / Cached input / Cache write / Output** as four slash-separated percentages.
- The canonical per-prompt report DTO already has `token_mix_percent` (`src/reports/models.py`, `src/reports/prompt_rows.py`, `src/application/projection.py`). The Web Watch *card* export in `src/application/live_projection.py::card_row` does **not currently include** that field. Live per-prompt availability and refresh must therefore be verified along the real source → analysis/capture → Watch cards → export route; a new browser-only calculation is not sufficient.

## 1. Exact shared table order and cells

Apply the **same column order and behavior** in both Running Prompts and Earlier Prompts:

| Position | Column heading | Required cell content |
| --- | --- | --- |
| 1 | **Started** | Only the prompt's local start time in `HH:mm` (e.g. `20:09`); no prompt number or `Prompt` prefix. |
| 2 | **Duration** | Existing prompt duration, moved directly after Started; still advances only for truly active work and freezes appropriately when terminal. |
| 3 | **Prompt** | `#1`, `#2`, etc. **at the start of the Prompt cell**, followed by the existing prompt preview, in the CLI Watch style. |
| 4 | **Model** | Preserve existing model identity/multiple-model disclosure. |
| 5 | **Effort** | Preserve existing effort. |
| 6 | **CCost** | Preserve existing per-prompt CCost, unit/provenance and display preferences. |
| 7 | **Calls** | Rename existing `Model Calls` header; do not change counting semantics. |
| 8 | **Token Mix %** | **New column** in the **old Duration position**, immediately after Calls and before Δ Ctx. |
| 9 | **Δ Ctx** | Preserve existing delta-context meaning. |
| 10 | **Context** | Preserve existing next incoming context estimate. |

**Prompt numbering is session-local canonical ordinal**, not row index, card position or a new sequential number assigned to the currently visible five rows. For example, a session's twelfth prompt displays `#12` even if only that prompt is visible. Keep existing tool/compaction, abort/error status, preview, color semantics and accessible full-text disclosure. Prompt numbering should remain visible when the preview is truncated; only the preview should ellipsize. Each data row should remain a single line as before.

For Earlier Prompts use the same visible `HH:mm` format; because dates can differ, retain the full local timestamp in an accessible tooltip/details text or another non-disruptive disclosure, without putting the date back in the visible Started cell. Preserve correct timezone and daylight-saving handling.

## 2. Token Mix %: same semantics as the CLI session report

- Render a compact, readable **four-part percentage mix** in the existing CLI report order `I/C/W/O`, separated by `/` (for example `12/78/0/10` with the percent unit provided by the heading/tooltip). Do **not** confuse this with four shares of CCost. The shares represent **raw token volume** using the same canonical prompt-attributed physical model requests as the session report.
- Header tooltip must spell out the **position and meaning**: **1 = Input (ordinary input tokens); 2 = Cached input (cache-read tokens); 3 = Cache write (tokens written to cache); 4 = Output (including reasoning tokens under existing canonical rules)**. Say that values are percentages of observed tokens, not billed cost. Follow the report's rounding and coverage/completeness rules; do not invent zeros for missing categories or an unknown denominator.
- Reuse the shared Python analysis/projection (`src/analysis/token_mix.py`, `src/reports/prompt_rows.py`, established PromptProjection semantics) where possible. Do not reimplement token attribution, deduplication, category rounding or pricing in JavaScript. A mixed-model, child/subagent or compaction scenario must use the report's canonical inclusion rules, not just whatever happens to be shown in the focal row's browser text.
- **Live running prompt:** Whenever a fresh, accepted Watch capture contains additional or revised **known model-call token usage** for that same prompt, update the displayed Token Mix % from **all currently attributable observed calls**. It should be possible to watch the mix change during a long-running prompt as new calls arrive, without a separate refresh button. Later snapshots may correct earlier observations according to source truth. The completed value should agree with a corresponding CLI session-report snapshot with comparable source observations.
- Do not promise intra-call token streaming where the source supplies no such data: a mix is updated at the next available authoritative model-call/usage observation. Show an honest `N/A`, pending or unknown state before sufficient usage is present, and for partial/unavailable category evidence; do not show a fake `0/0/0/0` or stale mix as current. One complete known sample can validly be `100/0/0/0` and later change as more calls are observed.
- Keep live updates within the **existing bounded capture cadence and SSE publication**. No new model calls, provider polling, extra history scans on each browser tick, browser-side token reconstruction or sensitive prompt/token payloads are authorized.

## 3. Tooltips on all table headers

Give **every column heading** a concise, useful explanatory tooltip, on both tables, including the already-described Context column. Distinguish easily conflated metrics: Started vs elapsed Duration, Calls vs tool calls, CCost vs billed money, Token Mix % vs cost mix, Δ Ctx vs Context. Preserve existing context tooltip meaning and established approximations/provenance. Tooltips must be usable with pointer hover and keyboard focus; provide a reasonable accessible/touch path rather than relying exclusively on a mouse-only CSS hover. Do not obscure the column labels or make them unreasonably bulky.

## 4. Earlier Prompts framing and separation

When Earlier Prompts is **expanded**, remove the **additional outer frame/background-box effect** that currently surrounds its `.watch-history` content. Historical session cards should sit in the same unframed page flow as the Running Prompts cards. Preserve the disclosure's title, collapse/expand action, card/table borders, spacing and normal document scroll (no new nested vertical scrollbar).

Instead provide **one slightly more visible, theme-aware horizontal divider between the end of Earlier Prompts and the beginning of Running Prompts** when expanded. It should make section boundaries obvious, not box in individual historical cards or create a permanent divider for the collapsed/empty state. Verify Classic and system light/dark appearances, responsive/narrow layouts and horizontal table overflow.

## Acceptance and verification

1. Both tables expose exactly the **ten columns in the specified order**. Started contains only `HH:mm`; Duration is second; Calls has its shortened name; `#N` is inside Prompt with the preview. Test session-local ordinals, Earlier timestamps across dates, compactions and long preview truncation.
2. Every header has correct tooltip content and a usable hover/focus/touch-accessible explanation; in particular Token Mix % clearly documents I/C/W/O order, raw-token percentages and reasoning folding.
3. Deterministic canonical source fixtures yield the **same Token Mix %** in Web Watch and CLI session report at equivalent snapshots, including a completed prompt, multiple calls, cache-heavy usage, multi-model/child contributions, missing/partial telemetry and zero-usage. Unknown values never become invented 0%.
4. An active prompt with two accepted model-call observations and then additional calls **changes its Web Token Mix % without page reload**, with correct cumulative share recomputation and no duplicate calls. Stale/out-of-order captures, interrupted activity, disconnect/reconnect and terminal freeze do not regress to older mix or manufacture a current state. Changes are driven by accepted new source data, not merely a client timer.
5. The expanded Earlier section has **no extra outer box** and has a clear separator from Running Prompts. Collapsing, scrolling, DOM reuse, accessible labels, text selection, full preview, all existing fields and live styles continue to work. Check representative desktop/narrow windows in Classic/light/dark themes.
6. Use existing focused Python Watch/report/export tests and Web DOM/browser CSS verification, plus applicable ordinary product/package checks. Report honestly if real source timing or physical-browser behavior could not be verified; do not fabricate live proof.

**Out of scope:** changing CLI or the normal Reports table, redefining token percentages, adding source acquisition owners, changing lifecycle/quota detection, changing prompt accounting or altering historical selection. This is one FR for the requested Web table presentation and its required per-prompt live data route.
