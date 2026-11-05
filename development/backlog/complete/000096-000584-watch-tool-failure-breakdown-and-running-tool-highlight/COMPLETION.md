# Completion — FR 000584

Implemented 2026-11-05 in Cost Guard v80.165.

## Result

- Canonical physical-call observation now exports ordered tool-name failed/cancelled subsets, with cancellation precedence and a combined total. Inclusive all-call groups, failure-only CLI data and directly attributed skill failures are preserved.
- Full Watch keeps a compact combined header and shows all red named outcome groups below ordinary totals. Unidentified aggregate differences remain explicit. Header/detail counts are retained coherently during focus/selection and update together afterward.
- Only the active running-tool line shares the existing prompt/session semantic running foreground; other activity/background lines retain their colors. The threshold, terminal lifecycle and native disclosures remain intact.
- Current Watch documentation/help, architecture routes and engineering evidence are updated. The whole specification bundle is retained intact. Maintenance next state advances ordinary count 34 → 35 only through this delivery.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: **141 files passed**, zero failures, final run 89.4s.
- `py -3 development/tools/validate_package.py --working-tree`: **11 checks passed**, zero failures; six existing/advisory prose/module-budget warnings.
- `probe_watch_tool_outcomes.cjs`: hidden fresh-profile Chrome 156.0.8078.80, **six cases passed** (Classic/Web light/Web dark × 1366/360px). Keyboard disclosure, focus stability, accessible help/Escape, literal names, full red detail, semantic color equality, no overflow and terminal hiding checked. Representative screenshots inspected.
- `probe_web_live.py --watch-cards --tool-outcomes`: **passed** read-only real V2; one activity card with four failures and zero observed cancellations, all subsets/totals reconciled. One owner, two advancing streams, one active/two history cards; shared OpenCode untouched, owned workers closed.
- Deterministic/VM regressions cover mixed/cancellation-only/unknown outcomes, copied calls, canonical child scope, untrusted schemas/output/exit codes, skill attribution, corrections/retention/expiry, >5 groups, partial aggregates, focus/selection coherence and existing CLI behavior.

## Limits and exceptions

No user/Decision Delegate requirement or test exception was needed. Real mixed cancellations were not observed; canonical fixtures and synthetic browser checks cover them. The real probe's independent account-history work was interrupted on owned shutdown, so Daily completeness is not claimed. Integrated browser access was disconnected; adequate hidden Chromium checks were used. No personal browser profile, native desktop input, screen reader, Firefox/Safari/macOS browser or end-to-end real-account paint is claimed. No inference, provider mutation, shared-service stop, local release ZIP or config change was performed.

Evidence: `development/journal/web/watch-polish.md`, v80.165 section. No architecture boundary changed; the existing observation → immutable projection → Web presentation ownership is preserved.
