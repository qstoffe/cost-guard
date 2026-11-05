# Retired Web Reports verification

2026-11-05 · FR 000595 · v80.175 · base `7d2565a7eb98a17f00d80f942aa7082a50588e3d`.

## Hidden browser

`integration/probe_web_sessions.cjs` passed in fresh-profile headless Edge
`156.0.4314.58` against the shipped HTTP/auth/assets and synthetic history.
No personal browser profile, visible desktop effect or inference call was used.

- Plain Reports, valid single-day/range, impossible date and malformed query hashes
  all replace their entry with scope-free Sessions. No date job or date filter;
  canonical activity descending remains applied.
- Cold legacy reload starts no finite report (including Normal). Browser Back/Forward
  returns through Sessions/Settings without a Reports entry or redirect loop.
- Actual navigation has exactly Models, Watch, Sessions, Accounts, Token Mix,
  Cost per Active Hour and Settings at 1920px and 360px. No Reports link, date input,
  date form or old date snapshot is present.
- Both surviving deep-history pages remain explicit. Capture and Refresh request
  only their own kind; HTTP cancellation of a held synthetic capture retains the
  last result. No date request was submitted.
- Existing Sessions checks still pass: six columns, exact global metric ordering,
  stable older-page membership, live arrivals, 1,001 complete chronological prompts,
  selected text/scroll retention, completion, outage and recovery. Arrival discovery
  was 5,092ms in this run. Classic/Web light/dark, narrow/wide and zoom cases passed.
- No browser runtime exception or fixture stderr was recorded.

This is real browser/HTTP/DOM proof over synthetic data, not physical desktop,
screen-reader, macOS or long-term production acceptance. The real-source probe and
deterministic regression outcomes are recorded in this task's `COMPLETION.md`.
Historical Date UI matrices remain unchanged as historical evidence.

## Deterministic checks

- Full bounded suite: 145 files/groups, 1,709 tests, 1,708 passed, zero failures or
  errors, one existing platform skip (`zsh`/PTY unavailable on Windows in
  `test_macos_web.py`); 98.9 seconds, four workers. Shared date/core/CLI, report API,
  security, cancellation, Sessions and surviving Web regressions remain in the suite.
- `validate_package.py --working-tree`: zero failures, 11 passes and six advisory
  size warnings (Web guide, README, version history and three existing Python owners).
  No budget was raised; version consistency passed for v80.175. No ZIP was built.
- Changed JavaScript files passed `node --check`.

The removed date-UI assertions were replaced by retired-hash/no-job/navigation
assertions. Shared session display tests now use the session fixture; canonical
date-report fixtures and core/API tests were not removed. Historical optional
browser probes no longer navigate to Reports as an active page.

## Real installation (read-only)

`probe_web_live.py --sessions --reports` completed in 247.5 seconds against V2.
One owner, two streams and advancing publication IDs preserved the Live run origin.
The first Sessions page took 64ms; sampled catalog/detail HTTP requests peaked at
128ms. A naturally changed first page was observed without creating a session.
Revision-pinned detail returned two rows (13,718 bytes) in 56.1 seconds.

Shared API reports completed: Normal 60.4s, all-models 8.8s, Sessions 4.6s and date
79.1s. A subsequent deep-history job cancelled; none changed Live ownership.
Shutdown left zero owned threads/processes and no cleanup failure. OpenCode was
untouched; the probe started no inference.

Limits: the existing cold scalar index stayed pending (0→4 of 2,720 roots during
the bounded observation). This is not proof of complete real-catalog metric-sort
readiness; synthetic global-sort proof remains separate. Probe instrumentation
counted two history-stage exceptions during ongoing acquisition, while the requested
report/stream/detail checks completed; no claim of exception-free history or a new
root-cause finding is made. No backend/index behavior was changed in this FR.
