# FR 000690 completion

Implemented in v81.35, 2026-11-13. Original specification and attachments retained
intact; source-owned session Ctx continuity replaces FR000666's one-shot permission.

Mini, Full Watch's Context footer and Sessions catalog now share canonical
pending/current/invalidated session observations. Missing handoffs, partial captures,
unknown new models, Stop/error and execution uncertainty retain valid same-session
context. Fresh numbers (including equal numbers) replace immediately; explicit
source/epoch/model/history invalidation clears it. Fresh Mini/reopening can seed from
the legitimate source summary, independent of a predecessor DOM row or history scope.
Prompt-local Ictx/Δ, prices/accounting, acquisition cadence and PiP geometry remain
independent. No new watcher, history read, timer grace, browser storage or inference.

## Verification

- Source-shaped V2 normalization/capture/Live replay: original renderer
  **230k → N/A → N/A → 235k**, fixed **230k → 230k → 230k → 235k**.
  Eight focused source/renderer cases cover partial/missing permission, repeated
  prompts, stopped/error history, bounded row slices, genuine invalidation and source
  identity. Current prompt's raw Ctx remains null during the pending publications.
- Actual hidden Chrome 157 Document PiP and Full Watch passed that sequence with
  0.5s/5.1s gaps, yellow new prompt, native timer, stable row, focus/AX, hover/touch,
  mixed-input touch→keyboard→hover, history restart, reopen and exact same-number update.
  Isolated history readiness passed. Lifecycle/Fit passed 25 layouts, four theme/scheme
  combinations, Credits/USD, narrow/wide sizes and pointer/keyboard/touch actions.
- Final local Full: **186 bounded groups, 2323 passed tests, zero failures, 155.6s**.
  Four existing native macOS zsh/PTY tests skipped on Windows. A prior final run
  caught old prompt rows leaking into an active refresh placeholder; repaired to
  retain only session Ctx, with empty prompt membership. The complete rerun passed.
- Package validator: 11 passes, zero failures, seven existing advisory warnings.
- Read-only installed V2: context export/formatting and two coherent streams passed,
  zero owned threads/processes after close, shared OpenCode untouched. **Zero natural
  rapid handoffs observed: owner's live transition NOT VERIFIED.** Earlier history
  stayed loading and a background history batch/advance error was not claimed PASS.

## Authorized verification exception and limits

**Decision Delegate**, not the owner, approved an FR000690-only minor exception for
the known unrelated **Total-heading mixed-input hover opening failure** and the
consequent **unrun later Duration subprobe cases**. The broad portfolio remains
**FAIL**, the failing assertion remains enabled, and those later cases are **NOT RUN**.
Ctx's same mixed-input order, independent history lifecycle and Fit/layout checks
passed; no original Ctx acceptance was waived. The Total defect is not fixed.
Existing [Suggestion000684](../../suggestions/000684-mini-help-mixed-input-hover-opening/SUGGESTION.md)
owns it; no duplicate proposal or whole-portfolio PASS.

See [journal evidence, fixture repair, decision and uncertainty](../../../journal/web/mini-watch.md#persistent-session-ctx-fr000690).
Physical desktop/work-area frames, macOS pixels and screen-reader speech were not
tested or changed. No paid requests, source writes, ZIP, tag or GitHub Release.

User guide, architecture/code map, release metadata/history and ordinary progress
(134→135) updated together. Current `main` remains the supported distribution.
