# FR 000470 — Sessions should immediately show recent history with simple pagination

## Owner observation

Opening Sessions currently presents a required scope input (N 1–10000 or all) and an Apply button before the user gets an intuitive browsing experience. Owner expects a straightforward table, newest sessions first, with Previous/Next and no initial form. Owner also reports that clicking Sessions appeared to open a separate CLI console; this is **not yet proven** by the reviewed browser code, so reproduce it on the Windows installed launcher/route rather than inventing a root cause.

## Required behavior

- Navigating to Sessions immediately requests and displays a table of most recent **available** sessions (including properly available archived roots), ordered according to the CLI Sessions report's recent-first semantics. No required scope field or submit button for the default view.
- Provide true page navigation (Previous, Next, current page/range, total when actually known), with an ergonomic page size such as 50 or 100; let the owner browse older sessions without typing 100/200 or restarting a report. Search/filter/sort may be enhancements but may not misrepresent the loaded slice as the entire history.
- Prefer a bounded backend **page/query contract** when fetching all history is expensive or exceeds existing 8 MiB/120 s report limits; do not merely show page 1 of an arbitrary 20/100-row truncated result while claiming the next page reaches older history. Where full immutable result is small and already acquired, existing client paging may be reused. Any new paging needs stable canonical ordering/revision/cursor semantics and truthful totals, using existing report/domain owners; avoid N+1 scans, new history ledger or browser-side model calculations.
- Preserve CLI session columns, numeric formatting, duration, incomplete/archived/running indicators and session-detail links. Detail should open in the **same Web UI** without launching a CLI terminal. Investigate and fix any actual Windows/route/launcher console-trigger symptom; explicitly distinguish legitimate managed tray process from an unwanted pop-up.
- Optional power-user all/N scope may remain in an advanced control when practical, without being required. Keep direct links and Back/Forward/reload, preserve honest empty/unavailable/busy states and the full session-detail report contract.
- Follow FR000430 formatting and FR000440 visual style; avoid automatically starting deep Token Mix scans or multiplying account acquisition.

## Acceptance

- Clicking Sessions requires **zero input** and shows recent sessions, page 2 shows the *next older distinct set*, and sort/filter semantics and completeness indicators are truthful. Exercise 0/1/100/1,000+/archived/partial sessions, added sessions between page turns, source changes and bounds/errors.
- Reproduce and eliminate any unexpected console opened from the Sessions navigation/click path on Windows, without weakening isolation or claiming a defect if it cannot be reproduced; document what was tested.
- Actual-browser visual checks and deterministic CLI Sessions parity tests cover row fields/order, page state, link/reload/Back and accessibility.

Relevant owners: `src/web/assets/reports.js`, `render.js`, `app.js`, `src/application/service.py`, `src/reports/history.py`, `src/reports/service.py`, existing Web Sessions/detail tests.