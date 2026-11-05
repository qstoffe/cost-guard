# FR 000594 completion

Implemented 2026-11-05 · v80.174 · base `a75846ed6af307f0a55a7f620b8263167fd26761`.

## Outcome

Accounts retains its navigation/route but now renders only the shared Full Watch
subscription grid in the healthy view. `account-cards.js` owns both renderings,
including physical width/subgrid, primary/secondary quota tracks, Today/period CCost,
Capacity, reset/pace, provenance help and provider/freshness states. Existing app-level
Live and its latest retained observation drive Accounts without opening Watch,
submitting a Normal report, starting a new stream or creating acquisition work.

Account-keyed membership and bound metric/help/reset nodes preserve unchanged DOM,
focus, selection and ordinary scroll. Real membership/structure changes still apply.
Settings synchronize visible and detached roots using server-prepared tokens.
Models' finite cache, unrelated reports, CLI and Diagnostics remain unchanged.

The complete source FR is moved intact; no attachments were present. Maintenance
progress includes the selected next state (ordinary count 44), effective only on merge.
Current Web docs, module/code-map/overview guidance, release facts and the Web journal
are updated; no additional architecture boundary or acquisition owner is introduced.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, 145 isolated groups,
  zero failures, 93.1 seconds. Initial failures were stale test route/asset wiring;
  corrected before the complete clean rerun.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, zero failures,
  six existing advisory budget warnings. No raised limits or release ZIP.
- `node development/tests/integration/probe_accounts_live.cjs <owned-browser> <owned-output>`:
  PASS in hidden Edge 156.0.4314.58 and Chrome 156.0.8078.80. Initial Accounts/pending,
  exact Watch parity, route links, stable nodes/focus/selection/help, settings/default,
  primary/secondary/idle quotas, failed/retained/empty/recovery membership and actual
  terminal host event; one SSE and zero route-created reports. Classic/Web light/dark,
  wide/narrow, reduced motion and DPR 1.5 preserve subgrid/no document overflow.
- `py -3 development/tests/integration/probe_web_live.py --accounts --watch-cards`:
  PASS on the real V2 installation: three accounts, one refresh owner, one Live owner,
  advancing publications, preserved origin/two test streams, zero finite jobs/model
  calls; zero owned threads/processes after close and no shared OpenCode stop. The
  first stream check's two-second assumption was repaired to await a real bounded
  publication; its account-owner result and later complete PASS are distinguished.

Evidence and exact limits: `development/journal/web/accounts-live.md`; raw artifacts
remain under this session's `scratch:/` references there. Browser fault/layout checks
use synthetic accounts; real-source proof is read-only and bounded, not a guaranteed
refresh SLA or long-duration production soak. Physical desktop/touch-device,
screen-reader and macOS acceptance were not performed. No user/Decision-Delegate
requirement or test exception was requested or applied. No paid model calls.
