# FR 000549 completion

Implemented 2026-11-02 in Cost Guard v80.127.

## Delivered scope

- Removed uncertified trailing quota lookbacks. Fresh provider-confirmed empty windows produce zero without borrowing old usage; expired, stale, unknown, unsupported and contradictory windows remain unavailable.
- Preserved valid active intervals, rounded-to-zero native percentages with legitimate cost, pricing/attribution distinctions, deduplication and cached prefix-index reuse. Weekly and model scopes are independent of five-hour resets.
- Delayed Web history now exports immutable indexed evidence and reprojects current accounts/windows instead of overlaying old period costs. Older native observations cannot restore an old window or regress observation time; partial lifecycle transitions cannot inherit an old active reset.
- CLI Watch/report and Web Accounts share the corrected meaning. Full Web Watch keeps **CCost Today**, and durationless monthly CLI fields keep **Today**. Supported native UTC months/Copilot residuals and configured-local calendar-month totals remain distinct; no monthly provider defect is claimed.
- Future Mini Watch can consume the corrected shared semantics. Its UI and the separate native-primary selection FR are not implemented here.
- Updated current usage documentation, architecture/code map and `development/journal/account-periods.md`. Preserved the complete original FR payload and identity; completion ordinal 000059 follows the current maximum Complete prefix, not Ready priority.

## Actual verification

- `py -3 development/tools/run_tests.py --suite full`: **126 files; 1,532 tests passed, 1 skipped, zero failures/errors**. The skip is macOS shell execution because zsh/PTY is unavailable on this Windows host, not a product PASS.
- Registered the new 11-test lifecycle file in Quick/Full. Coverage includes 604-cost prior history with repeated empty-period refreshes; active boundaries/dedup; reset → unavailable → inactive → active; delayed native/Web responses; account/model/weekly separation; monthly/year rollover and unsupported anchors; compact/plain/ANSI and credits/USD formatting; real Accounts JavaScript rendering. Existing daily Watch, account attribution, Copilot residual and bounded-index regressions pass.
- `py -3 development/tools/validate_package.py --working-tree`: **11 passes, zero failures**, four existing design-budget warnings (README, analysis context, report service, Watch coordinator). No cap was increased. Release history was condensed within its existing hard cap.
- Read-only real installation: three accounts retrieved, one bounded source root/20 requests analyzed. An available Claude Code five-hour native `window_active=false` component resolved to an empty period and exported CCost **0**. Weekly native intervals were recognized but their cost remained unavailable with this intentionally incomplete history sample. No model calls, credentials changed, provider polling increase or shared OpenCode stop.
- `git diff --check`: passed. Latest fetched main was integrated normally; its version remained v80.126 before this increment. No ZIP, release or local runtime replacement was made.

## Limits and exceptions

The broader `probe_web_live.py --watch-cards --daily --reports` failed: its three-second `/api/live` request timed out during the full-day wait, followed by owned-host `live_shutdown_timeout`. Full-day live aggregation/report behavior and live provider reset transitions were **not** proven by that probe; deterministic lifecycle/DOM tests and the narrower real-provider observation are separate evidence, not a broad live PASS. Its root cause is not established. No requirement/test exception or Decision Delegate waiver was requested or granted. The macOS shell skip remains explicitly unperformed locally.
