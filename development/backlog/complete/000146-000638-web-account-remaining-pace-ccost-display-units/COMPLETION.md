# FR 000638 completion — 2026-11-09

Implemented in v80.215. Web Watch and Accounts now render remaining reference CCost
per day/workday from their quota's accepted unrounded Remaining and existing calendar
counts. Both shared live cards and the alternate/compact Accounts renderer use the
same scoped projection. Native pace/raw quota amounts and CLI/Mini semantics remain.

Unknown, stale, unlimited, inactive or expired budgets omit pace; zero and no-workdays
remain distinct. Credits rounds remaining down; USD uses normal two-decimal reference
formatting, including `$0.00` for tiny positives. Unit switches retain nodes, focus,
raw data and quota bars with no fetch. No pricing/source reads were added.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, 175 files, zero failures,
  four workers, 141.4 seconds. Includes native quota/CLI regressions, new reference math,
  same-label identity/windows, messages/no-basis rejection, rounding, calendar/DST/SE
  holidays, expiry, zero and no-workdays, plus Watch/Accounts VM integration.
- `py -3 development/tools/validate_package.py --working-tree`: zero failures,
  11 passes, seven advisory prose/module budget warnings; caps were not changed.
- Hidden Edge 157 `probe_accounts_live.cjs`: PASS for the full existing responsive/
  capacity/Mini matrix and new route/theme pace toggles, stable DOM/focus/raw figures
  and zero toggle fetches. Follow-up `--quota-only` PASS adds persisted explicit
  Credits and Default USD page reloads. The probe's request baseline now resets with
  its document counters after reload, rather than comparing different page lifetimes.
- Read-only `probe_web_live.py --accounts`: PASS against real V2 installation,
  one Live/account owner, advancing publications, no finite jobs/model calls.
  A scratch-only observer additionally checked 18 publications: 15 eligible quota
  occurrences, 44 omitted occurrences, 30 raw pace and 60 display-unit assertions.
  These are repeated observation counts, not distinct accounts. Owned workers closed;
  shared OpenCode was untouched. No private provider amounts/identities are published.
- `git diff --check`: PASS.

## Scope and evidence limits

No requirement/test exceptions or Decision Delegate waivers. Integrated browser was
disconnected; permitted hidden browsing supplied DOM/layout/input proof. This is not
physical-desktop, assistive-technology or macOS acceptance. Live observation does not
prove every provider exposes a compatible reference budget; unsupported bases omit pace.

Evidence: `scratch:/full-tests.txt`, `scratch:/accounts-live.json`,
`scratch:/accounts-final.json`, `scratch:/real-accounts.txt`,
`scratch:/real-pace-observed.txt`, and `scratch:/verify_real_pace.py`.
Current product docs, version/history, reports architecture and CODE_MAP are updated;
[engineering note](../../../journal/web/quota-reference-pace.md) records the basis.
No ZIP, release, tag, runtime install, or ordinary-checkout edit.
