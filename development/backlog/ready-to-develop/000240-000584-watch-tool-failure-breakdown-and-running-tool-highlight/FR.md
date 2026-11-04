# FR 000584 — Full Web Watch: failed/cancelled tool breakdown and yellow running-tool status

## Owner request and backlog decision

**Owner-approved executable Feature Request, 2026-11-04.** Permanent identity **000584**; Ready priority **000240**, after FR000583 (000230). Scope: **Cost Guard Web Beta → full Watch → Running Prompts → Tool Calls / Skills disclosures and the running-tool activity line**. This FR is for backlog authoring only; **do not implement product changes now**.

The owner likes the compact Tool Calls/Skills summary but finds its expanded details insufficient: when the summary says e.g. `3 failed / cancelled`, expanding **Tool Calls** still only shows an undifferentiated `3 failed / cancelled` at the bottom. They want to see **which tools** failed or were cancelled, and which outcome applies to each, with red visual emphasis. The separate long-running tool status (`Running: <tool> <duration>`) should be **the same bright/yellow running-prompt color** as the active session and prompt row, rather than the current muted brown/gold activity color.

## 1. Expanded Tool Calls: group failed/cancelled calls by actual tool and outcome

- Keep the compact **collapsed header** succinct: total tool calls, the existing top tool groups, and a single combined **`N failed / cancelled`** indicator *when the count is supported by evidence*. This header is a summary; the expanded list provides the details. Don't add a new column or a separate top-level warning panel.
- The **expanded Tool Calls** list should show the ordinary per-tool call groups as today, then at its **bottom** show separate **red** failure/cancellation breakdown lines grouped by **tool name AND outcome**, e.g.:

```text
4 × grep
3 × execute
...
2 × grep failed
1 × execute cancelled
```

  Example counts are illustrative, not source assertions. If several physical calls of the same tool share an outcome, show `2 × grep failed` rather than two redundant identical lines; a single call can show `1 × grep failed`. For mixed outcomes, make separate rows: `2 × grep failed` and `1 × grep cancelled`, not one ambiguous `3 × grep failed / cancelled`.
- **Existing tool groups count all physical tool calls**, including failed/cancelled ones. The red breakdown represents a **subset** of those calls, **not extra tool calls**. Preserve honest total reconciliation and don't make users believe e.g. `2 × grep` means two *successful* calls unless success has specifically been counted. Tool groups can be labelled or explained concisely where needed to avoid this ambiguity; do not quietly redefine their existing totals.
- **Remove the redundant undifferentiated `N failed / cancelled` row from the expanded detail view** when the grouped breakdown fully explains it. The header remains compact, and the expanded red lines show the actual names and categories. If only some outcomes have been identified, show an honest **short unidentified/unknown breakdown bucket** for the difference instead of pretending all calls are attributable to named tools; avoid a confusing double count.
- Preserve deterministic ordering (e.g. failed before cancelled, then count descending/name as a tie-breaker) and ensure the full outcome detail is visible without the collapsed header's five-group cap. Tool names are treated as untrusted text and escaped/safely inserted; no command contents, raw output, exception traces, secrets or private paths added to the UI.

## 2. Reliable distinction between failed and cancelled

**Investigated current code:** `src/watch/tools.py::observe_tools()` already deduplicates physical calls and groups `tool_counts` by name. It recognizes cancellation from structured error information via `_is_cancellation()` and known skill-result outcomes via `src/watch/tool_contracts.py::structured_outcome()`. But it currently **excludes cancellations from its `failed_count`** and doesn't export per-name/per-outcome counts. The Web projection (`src/application/live_projection.py::card_row()`) currently exports only `counts`, `failed_count`, the running tool, background data and skill IDs/failure counts. `src/web/assets/watch.js::Card.drawActivity()` repeats the undifferentiated **`failed / cancelled`** text in both header and expanded list despite the underlying field being *failed-only*. The new request should fix that misleading mismatch as part of the presentation.

- Expand **only the existing canonical Watch observation/projection** enough to provide evidence-backed, aggregate **per-tool failed and cancelled counts**, plus an overall combined count derived from those classified calls. Keep one authoritative counting owner in Python, not a browser-side reinterpretation of logs or tool-output strings.
- **Failed:** only the existing rigorously classified genuine error outcomes. **Cancelled:** only explicit structured abort/cancel/interruption evidence as supported by the current source-normalization rules. A command printing `error`, a nonzero exit status without a trusted tool contract or an ambiguous missing status must not be inferred to be a failed or cancelled tool. Never label an ordinary completion as cancelled.
- The header `N failed / cancelled` should reflect the sum of **distinct** evidenced failed + cancelled calls. The expanded breakdown totals must reconcile with that header. If a call has both error and explicit cancellation evidence, count it **once** under cancelled rather than once in each class. Keep separate failure-only data and invariants where other existing consumers require it.
- If a source lacks enough outcome evidence, **do not invent either label or a count**. Continue showing known regular call totals and known error/cancellation groups; explain uncertainty in existing accessible help where material. If the existing source semantics fundamentally cannot distinguish a particular case, preserve an honest fallback without blocking the entire feature.
- Scope to the same focal prompt and existing causal child/subagent tool selection as today, with canonical tool call ID de-duplication, terminal updates, source corrections and retained states. No cross-prompt leakage, double counting, rescans on every SSE re-render or additional source/provider requests.

## 3. Skills disclosure compatibility

- Preserve the existing separate **Skills** summary/disclosure and its **loaded-skill identity** rules. Today's per-skill `failed_count` is backed by *direct* skill attribution (verified script/metadata); don't allocate failures to a skill merely because the skill was recently loaded or because an unrelated tool uses a similar command/path.
- Where the existing canonical evidence can **reliably attribute** a cancelled (or failed) tool call to a specific skill, the expanded Skills detail may display an equally clear **failed** or **cancelled** count next to that skill, in red. If cancelled skill attribution is not available or reliably provable, **do not guess**; the Tool Calls breakdown by tool name remains the essential acceptance criterion. Retain the source's distinction between a skill *being loaded* and a tool *executing work*.
- Keep overall tool failures/cancellations separate from the per-skill attribution; not all failed/cancelled tool calls belong to a skill, so totals need not equal the sum of skill-labelled rows. Explain this briefly in accessible help only if necessary.

## 4. Running-tool activity: yellow like the active prompt

- `src/web/assets/watch.js::Card.drawActivity()` currently creates **`this.running`** with `Running: <tool> <time>` after the shared **10-second** threshold, and `this.background` for outstanding background work. In `src/web/assets/app.css`, `.watch-activity` applies muted `--watch-activity` to all children; active prompt rows use `--watch-running` (yellow in Classic).
- **Color the entire active running-tool status line** `Running: <tool> <duration>` using the same existing semantic **`--watch-running`** foreground role as the running prompt/session header, including responsive Classic and Web light/dark variants. Keep it legible, with no new hardcoded yellow in the light theme and no background highlight/badge.
- **Do not recolor** ordinary Tool Calls/Skills group names, successfully completed activity, the red error lines, or the separate background/subagent status just because they share the `.watch-activity` parent. Keep these in their established tones unless another approved FR changes them.
- Preserve the existing runtime threshold, live duration semantics, lifecycle, hide-on-completion, display precision, dynamic updates and accessibility. The yellow status must disappear at the same authoritative terminal transition as the old one; it must not linger when a tool has completed or failed.

## 5. Implementation and validation boundaries

Likely affected: `src/watch/tools.py`, `src/watch/models.py` (`ToolObservation`), `src/watch/tool_contracts.py` *only if necessary to reuse existing outcomes*, `src/application/live_projection.py`, `src/web/assets/watch.js`, `src/web/assets/app.css`, and focused tests in `development/tests/test_watch_tool_activity.py`, `test_watch_skills.py`, `test_watch_activity_lifecycle.py`, `integration/web_live.cjs`, plus targeted browser/visual checks. The current `src/presentation/watch_activity.py` is CLI-specific and should retain CLI behavior unless a shared data contract addition requires a backward-compatible adjustment.

**Acceptance criteria:**

1. With a known prompt containing, for example, two *failed* `grep` calls and one *cancelled* `execute` call, the collapsed Tool Calls summary shows `3 failed / cancelled` (alongside the ordinary call totals). Opening it shows separate **red** `2 × grep failed` and `1 × execute cancelled` breakdown lines at the bottom, not merely `3 failed / cancelled` repeated.
2. The ordinary per-tool groups retain the intended all-call totals, while the outcome-specific red groups are a subset; no call or status is counted twice. Test same tool with successes + failures + cancellations, multiple different tools, no failures, only cancellations, unknown/nonstandard tool, repeated/copied physical call IDs, and many groups beyond the five shown in the collapsed summary.
3. Cancellations recognized from structured evidence are not silently dropped or mislabelled as failures; ambiguous/untrusted errors, ordinary nonzero statuses, prose, and result output from unverified schemas do not create fake failures. The sum and tooltip/ARIA status agree with the header under every partial/retained update.
4. Skills continue to show only proven skill loadings and verified attribution; no double accounting or false `skill failed` claims from unrelated tools. Distinguish skill-level cancelled outcomes only where directly provable; any unknown status remains honest.
5. When a tool exceeds the existing running threshold, its `Running: <tool> <duration>` line becomes **the same yellow semantic role** as the active session/prompt row in Classic; also check readable Web light/dark colors. All other normal activity retains its existing colors, and failed/cancelled detail lines are red.
6. The disclosure, focus/scroll, keyboard/touch, responsive/narrow layout, updating/reconciling existing rows, active→terminal grace, history transitions and retained source states remain stable. No additional Web connection, repeated history scan, new telemetry, provider call, raw tool output, sensitive path or user config change.
7. Update current Watch documentation/tooltip text to describe the meaning of combined failed/cancelled summary, tool-name outcome breakdown, and the separately emphasized running-tool status. Coordinate tooltip wording with queued **FR000582**, and preserve the layout/refresh changes queued in **FR000583**.

**Out of scope:** rewriting tool failure detection from loose text heuristics, inventing missing error/cancel types, showing sensitive commands or failure stack traces, changing prompt cost/attribution, altering native OpenCode source records, changing CLI Watch color/format, creating new status controls or settings, and implementation/release/version work in this FR-authoring session.
