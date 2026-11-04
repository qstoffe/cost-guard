# FR 000570 icon evidence — 2026-11-04

`native/result.json` records the pre-implementation feasibility experiment on
Chrome 156.0.8078.80, Windows build 26300, actual DPI 144 (150%). All referenced
PNG files are retained beside it. The baseline globe and same-window/reopened CG
HICON images were inspected by the worker and Decision Delegate. The three native
frames are owned-window PrintWindow captures, not taskbar/Alt+Tab screenshots.

The retained `native/probe-icons.cjs` and `probe-icons.py` are the exact experimental
sources, using the repository's synthetic `serve_mini_watch.py`, private CDP pipe,
fresh owned profile and read-only owned-PID Win32 icon queries. They deliberately
inject candidate links to compare timings; they are **not final-code acceptance**.
Their native mode creates visible windows and needs new applicable authorization:
the FR-scoped permission ended after 4.551 seconds of visible work. No routine
execution, personal-profile attachment, OS input or HWND mutation is authorized.
Native results' `streams: 0` is an owner-document DOM count, not an SSE counter.

`browser/chrome.json` and `edge.json` are final shipped-controller runs of
`development/tests/integration/probe_mini_watch.cjs`, without candidate injection.
Both use headless browsers and emulated scale 1.5; screenshots are document-only.
They verify favicon-loader requests on opening/reopening and separately check
exactly one EventSource, lifecycle, styles and layout. They do not prove OS icons.

The initial hidden scratch probe timed out because its user-data path was relative;
an absolute path repaired the test harness. No product failure was hidden.

The Decision Delegate approved omitting actual taskbar-preview/Alt+Tab/grouping
observations for this FR only. Those surfaces, native Edge and macOS remain
**UNVERIFIED**; shell caching/representation is uncertain. No unconditional primary
acceptance PASS, universal browser support or future desktop permission is claimed.
See `development/journal/web/mini-watch.md` for attribution, scope and final checks.
