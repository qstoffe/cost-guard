# FR 000581 completion

Implemented 2026-11-04 for v80.162.

## Delivered scope

- Full Watch's shared Running/Earlier heading is `Ictx`, immediately before unchanged `Δ Ctx`; the Session Context summary help uses the same terminology.
- Mini's Running/Earlier Sessions headings, accessible table names and row descriptions use `Ctx`. Header help retains its prompt-next versus session-current meaning.
- Internal fields, canonical values/formatting, unknown states, warnings, columns, CSS, acquisition and CLI behavior are unchanged.
- Current Web/Mini guides and module descriptions are updated. The original specification, historical completed tasks, past release notes and archived evidence are preserved.
- README/version history/runtime metadata identify v80.162, dated 2026-11-04. Ordinary progress advances from 31 to 32 only when this PR merges.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: 140 files; 1,658 passed, zero failures/errors, one expected platform skip (macOS zsh/PTY unavailable on Windows). Elapsed 98.5s. An initially added delta assertion was corrected to read the existing `live_context` display field before this successful run.
- `py -3 development/tools/validate_package.py --working-tree`: zero failures, six existing advisory budget warnings; no budgets raised and no release ZIP generated.
- `probe_watch_cards.cjs`: Chrome 156.0.8078.80, all 12 Classic/Web light/Web dark cases at 2560/1920/1366/360px passed. Both tables retain ten-column order, header focus/hover/click help, metric visibility, responsive panning and retained focus/selection. An initial fixture-start race was resolved by waiting for its ready line before launching the probe; no product change was needed.
- `probe_mini_watch.cjs`: the same headless Chrome, 16 checks and 108 layout cases passed, including active/expanded Earlier tables, Classic/Web light/dark, ordinary/narrow layouts, title/cost alignment, unchanged source-formatted context/N/A/zero, keyboard help/disclosure, partial/retained updates, single SSE and Document PiP ownership.
- `py -3 development/tests/integration/probe_web_live.py --watch-cards`: actual V2 installation passed; one acquisition owner, two verified streams, preserved run origin, one active and two historical one-row cards, bounded four pending captures. All owned workers closed; shared OpenCode was untouched. Daily-history publication was not requested or established; the probe recorded transient history-work errors during shutdown without leaking workers.

## Limits and documentation assessment

No requirement/test exception was requested or approved. The platform skip is not a passing macOS shell test. Headless checks do not establish physical desktop/native chrome or screen-reader acceptance; no such proof is claimed. Browser fixtures are synthetic, while the separate live probe is read-only real-source evidence, not real-source browser rendering.

Architecture module terminology is updated in place; no boundary or owner changed. Journal assessment: no update, because this is a terminology-only correction and the current guides/module facts plus this completion record capture the relevant evidence and limitations.
