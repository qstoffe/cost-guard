# Web Watch verification — 2026-10-27

FR 000460 / v80.95. Source base: a532e032ec6bac5275deb8c1bbe256a0fc46d1ab.

`browser.json` is the sanitized receipt from the explicit installed Edge headless probe,
using only synthetic canonical Watch fixtures. Both 1200px/light and 360px/dark pass:
one table with two session dividers, canonical row values/order, selection, focus, filter,
50-row pagination/scroll anchor, abort/compaction/idle, source recovery, duplicate/gap,
offline/reconnect/terminal and overflow assertions. Fixture transport exercises the shipped
connection client; it is not real-source browser SSE integration. The desktop browser pane
was disconnected, not passed. No physical, screen-reader or native macOS acceptance is claimed.

The independent read-only real-installation probe (`probe_web_live.py --detail --reports`)
observed V2, one acquisition owner, two HTTP streams, four retained rows, three accounts,
preserved host-start run origin, advancing publications, detail freeze consistency,
completed Normal/all-models/Sessions/date reports and cancelled deep history. Owned workers
closed and shared OpenCode was untouched. No user data or credentials are retained here.

Deterministic CLI/DOM comparison uses the identical Watch projection, not asynchronous runs.
See `test_web_live.py` / `integration/web_live.cjs` and `test_web_display.py`.
