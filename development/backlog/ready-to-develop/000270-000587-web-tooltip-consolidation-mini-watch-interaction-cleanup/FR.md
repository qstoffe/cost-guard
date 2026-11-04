# FR 000587 — Web tooltips: consolidate Mini Watch help, fix action dismissal, and sharpen copy

## Owner request and backlog decision

**Owner-approved executable Feature Request, 2026-11-05.** Permanent identity **000587**; Ready priority **000270**, after current Ready FR000586 (000260). This is a **second, selective UX/content pass** across Cost Guard Web Beta, with **explicit Mini Watch fixes**. Publish this FR only; **do not implement product, tests, documentation, or version changes while authoring it**.

Completed **FR000582** was a clear improvement: the shared custom tooltips feel quick, the question-mark cues are generally useful, and the full Watch **CCost (I + E)** explanation is now especially readable because it is concise and separates concepts with blank lines. **Keep that interaction model, speed, look, and valuable column-header help.** However, the application-wide rollout placed too many help cues in crowded places, introduced some duplicate explanations, and still contains overly long or diagnostic-style tooltip text. This is **not a request to remove most tooltips or rebuild the shared system**; use judgment to simplify what users actually see.

## 1. Explicit Mini Watch behavior bugs — mandatory

1. **Cost Guard · Watch:** the tooltip for the button returning to the main Watch tab must **dismiss immediately when the button is activated** (pointer click, tap, Enter/Space), including when the pointer remains over the button. Do not leave the tooltip floating after the action.
2. **Earlier Sessions:** the button's tooltip must **dismiss immediately on expand and collapse**, including when expansion changes the table layout while the pointer remains in place. An explicit activation should not cause the help to reopen merely because the button remains hovered/focused or because a Live rerender refreshes the tooltip. A *new intentional* hover/focus interaction can show the help again.
3. Keep both controls fully functional (return to existing tab; disclosure state/ARIA, keyboard and touch). Do not confuse this with disabling help on these buttons: **help before activation is still desirable**. Check the shared action/passive-trigger distinction so the same issue cannot recur elsewhere.

**Current code to inspect:** `src/web/assets/mini.js` attaches help to `this.summary` and `this.earlierToggle`; `src/web/assets/help.js::ContextHelp.attach()` currently invokes `show(target)` for non-passive action clicks. Confirm actual browser behavior before deciding the smallest robust fix; retain click/touch pinning, Escape, hover/focus and pointer transfer for *passive* information cues.

## 2. Mini Watch header: remove the adjacent-question-mark clutter

The Mini header currently places **two question-mark cues near each other in the upper-right area**:

- `CCost Today` has useful explanatory help.
- The header also adds `Update status and observation times`, largely filled with internal freshness/source diagnostics.

**Remove/consolidate the redundant header-wide observation-time `?`**, preferring to keep the useful `CCost Today` cue. Do not replace it with another adjacent icon or relocate the same diagnostic wall of text. Preserve real user-facing connection problems, stale/retained warnings, authorization/host failures and meaningful `N/A`/partial-data caveats in the established visible status or an appropriately concise, nonduplicative help surface.

## 3. Mini Watch prompt/history tables: fewer cues, better shared explanation

The constrained Mini window currently puts separate row-level `?` controls beside the **Session** title/total, the running prompt **#** cell, and the Earlier Sessions **Ctx** cell, alongside explanatory column headings. In a small table this is noisy.

- **Consolidate general table semantics into approximately one deliberate, easy-to-find table-level `?` per table**: one for running/recent prompts and one for expanded Earlier Sessions. Explain the whole table there, including the distinction between **whole-session** vs **per-prompt** CCost, prompt `#`, Duration, estimated next `Ctx`, and how to interpret unavailable/partial/retained values. The Earlier Sessions version should cover only the fields relevant to that table.
- Make these **short, human-readable sections with intentional line breaks and occasional blank lines**, not a long continuous paragraph. Example of the intended *format*, not mandated wording:

  ```text
  Running prompts — current or recently ended work.

  Session — Full session name and estimated total session cost.
  # — Prompt number within the session.
  CCost — Estimated cost for this prompt, not your bill.
  Duration — Time spent on this prompt.
  Ctx — Estimated context for its next request.

  N/A — Unavailable, not zero.
  ? — Some pricing data is missing.
  ```

- **Remove repetitive row-status/update `?` cues** when the shared help and existing readable/accessible row status convey the same meaning. Keep column-heading hover/focus help where it adds value; don't duplicate a lengthy explanation in both a heading and the new table help.
- **Do not lose the exact full session title** when a session name is truncated. Preserve an accessible, discoverable way to reveal the unmodified title (and, where genuinely valuable, its specific cost/state); a purposeful per-row reveal only where necessary is better than an unconditional stack of question marks. Do not convert selectable titles or table data into nonselectable help buttons.
- Preserve real running/completed/aborted/error meaning, per-row status accessibility, two-table separation, compact widths, scrolling, sticky headings, unit/theme behavior and live updates. **No extra table column** is required for the table-wide help.

## 4. Remove low-value technical freshness diagnostics from ordinary help

The owner explicitly does not want developer-facing/ticking details such as **`Last prompt update`**, **`Last quota update`**, `Last daily observation`, or raw `Connection: … / Source: … / prompts: …` state dumps in ordinary Web/Mini tooltips. They add noise without helping most users interpret the data.

- Remove this style of **internal update/observation timestamp and status enumeration from default tooltip prose**. Inspect the full app for equivalents, not just exact literal matches. Confirm the existing Mini call sites in `View.update()`, `drawDaily()`, `drawPrompts()`, `drawHistory()`, `drawSession()` and `drawAccounts()`.
- Keep meaningful *user* concepts where relevant: **Live vs retained/not current**, genuinely unavailable data, estimated values, partial pricing, source/authorization failures, and CCost vs provider-native quota. Express them in one short sentence or a clearly separated status line rather than an internal telemetry log.
- **Do not remove actual user-data timestamps** such as a prompt's real start/finish date/time or a provider's quota reset time. Those answer a user question; `Last prompt update`-style polling/observation diagnostics generally do not.
- If raw timestamps/source states are still useful for debugging, do not surface them as default help. This FR does **not** require adding a new diagnostic UI or changing underlying observations/acquisition.

## 5. Curated second-pass UX audit across the rest of Web

The explicit fixes above are mandatory; also **personally review remaining Web tooltip/help placements** in full Watch and other views before changing them:

- Spot **clusters of adjacent `?` cues**, redundant column-vs-row explanations, per-value boilerplate, repeated warnings, and help on obvious controls. Retain the cues that answer a real question; consolidate or remove those that merely restate nearby text.
- **Sharpen language**: a simple explanation should normally fit one sentence; a multi-part one should use brief named lines, grouping/blank lines when it improves scanning. Avoid dense prose, technical implementation names, repeated "not your bill" disclaimers in the same local grouping, and needless internal status detail.
- Treat the completed full Watch **CCost (I + E)** presentation as a positive benchmark. Especially **preserve valuable help on table headings** and the fast, consistent custom hover/focus/tap treatment. Improve other dense explanations to that standard without making every tooltip the same length.
- Do not blindly remove essential meaning: `N/A` is not zero, `?` can mean partial pricing, CCost is reference cost rather than a bill, prompt/session/day scopes differ, next context is not accumulated tokens, and native quota is separate from reference cost. Keep advanced details only where users need them or in a deliberate optional disclosure.
- Reuse `src/web/assets/help.js` and the existing styles/semantics rather than introducing a second competing tooltip system. Make the final cue count and wording a purposeful UX decision, not mechanical global deletion.

## Acceptance criteria and verification

1. **Action dismissal:** hover then click **Cost Guard · Watch** and **Earlier Sessions** (both open and close). Their help disappears promptly, stays dismissed despite stationary hover/focus and Live rerenders, and reappears on a new intentional interaction. Cover mouse, keyboard activation, touch, actual Document PiP and no loss of the actions.
2. **Mini header:** the two adjacent upper-right `?` cues are no longer present together; `CCost Today` retains helpful guidance. Genuine disconnection/staleness remains discoverable without visible or tooltip debug spam.
3. **Mini tables:** the running and Earlier table each have a clear consolidated explanation and substantially fewer unconditional per-row question marks. The full truncated session name remains obtainable and accessible. Test multiple running prompts, long session names, collapsed/expanded history, narrow/resized/zoomed PiP and both CCost units.
4. **Copy audit:** no default Web/Mini tooltips expose `Last prompt update`, `Last quota update`, `Last daily observation` or equivalent raw internal freshness dumps. Real prompt dates, quota resets, actionable failures, retained/partial/estimated meanings and truthful `N/A` remain correct.
5. **Quality and regressions:** sample all tooltip-bearing Web surfaces, record which cues were kept/consolidated/removed, and check succinct wording, purposeful blank lines and absence of accidental dual help. Test hover, focus, Escape, click/tap, pointer transfer, dynamic text refresh, theme/Classic/light/dark, viewport clipping, copy/selection, screen-reader naming, fast re-render behavior and no duplicate native `title` help. Add focused deterministic UI tests and browser probes (notably `development/tests/integration/web_help.cjs`, `probe_web_help.cjs`, `probe_mini_sessions.cjs`), and update `development/architecture/modules/web-help.md` and relevant Mini/Web user docs when implemented.

**Relationship to other work:** build on completed FR000582 without undoing its shared-help improvements. Coordinate with Ready **FR000583** (Mini Earlier Sessions resize/session-cost header) and **FR000586** (quiet transient full Watch status) so this work doesn't reintroduce their layout or noisy-progress problems. Review current code when selected: Ready work may land first.

**Out of scope:** rewriting canonical metrics/CCost, native quota semantics, source acquisition or cadence, CLI behavior, browser-owned PiP chrome, global tooltip removal, building a new tooltip framework, and any implementation/version/release changes as part of this FR-only publication.
