# FR 000545 completion

Delivered scope: compact Web Watch prompt cards, v80.126 (2026-11-02).

## Implementation

- Exactly one focal row for every active/grace card and one latest actual prompt for each of the five eligible historical sessions. Existing canonical lifecycle, grace, distinct-session ranking and context anchors remain authoritative.
- Started contains the canonical sequence and configured-timezone clock/date. Prompt is preview-only, with ellipsis/full-preview title and accessible row state; additional-model attribution remains on Model. Intrinsic metric tracks remain complete while Prompt takes remaining width, with narrow horizontal overflow.
- Removed card aggregate acquisition, publications, retained state and DTO fields, not just labels. Independent daily/account and Sessions totals remain intact. Revision refresh retains visible historical membership and coherent metrics; collapsed history uses unchanged bounded scheduling.
- Separate theme roles for running yellow, activity gold/brown, red failure fragments and context gold/orange; historical/terminal titles are neutral. Canonical background activity is exported alongside long-running tools, with explicit Running labels and terminal clearing. History has a restrained frame and viewport-aware 40vh maximum.
- Updated Web Beta help, release facts and existing Web/Watch architecture/navigation. Journal: no update; these owner facts and this evidence capture the change without rewriting historical verification.

## Verification performed

- `py -3 development/tools/run_tests.py --suite full`: all 125 files passed, zero failures, 60.8s. Focused card/lifecycle/context/daily/live checks also passed. Initial Full caught an old positional card fixture and obsolete totals assertions; repaired fixtures now assert one-row/no-totals/accessible-state behavior.
- `py -3 development/tools/validate_package.py --working-tree`: 11 passes, zero failures. Four existing design warnings remain for README, analysis/context.py, reports/service.py and watch/coordinator.py. Shortened the new history entry to respect the unchanged hard cap; no budget was raised.
- Integrated Chromium browser, actual shipped assets over synthetic loopback fixtures: Classic/Web light/Web dark at 1920×1080, 1366×768 and 360×800. All nine cases checked one-line rows, visible ellipsis for long multiline/unbroken URL previews, complete metric tracks, narrow horizontal overflow, no page horizontal/table vertical overflow, history frame, unframed active cards, useful active space at 1080p, semantic colors and focus/disclosure/history-scroll stability. Native Enter opened the history disclosure. A rendered Classic screenshot and accessibility tree were inspected; table/header/cell semantics and the Running row label remain present. Additional large-count DOM check retained complete non-Prompt cells. Context fixture confirmed footer-only warning and distinct yellow/activity/red/orange colors.
- `py -3 development/tests/integration/probe_web_live.py --watch-cards --daily --detail`: passed on this Windows workstation against real V2. One owner, two streams, three accounts, preserved run origin/advancing sequence. Two active/two historical cards (three already acquired), maximum one row/card, four bounded pending captures; first rows 4.140s. Daily publication reconciled 2,429 requests and 217 prompts with truthful partial prompt attribution and complete cost; category costs reconciled. Detail first/latest/freeze passed with two available rows. Probe-owned workers closed; shared OpenCode untouched. An earlier attempt timed out while runtime files were changing; the passing rerun held runtime source fixed.

## Limits and decisions

No requirement/test exception or Decision Delegate waiver was used. Browser checks used synthetic frames, not real-source browser/SSE, physical native-fullscreen/input, screen-reader or macOS acceptance. Real-source transport and deterministic lifecycle/compaction/warning tests are complementary evidence, not those unperformed platform checks. No inference, login, credential mutation, native UI automation, ZIP, install or runtime reload was performed.
