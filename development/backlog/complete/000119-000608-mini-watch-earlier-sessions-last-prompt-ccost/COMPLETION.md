# FR 000608 completion — 2026-11-06

Implemented in v80.188 from base `7843b3563e2906e80395f6b548652b951be7763f`.

- Running/recent Mini: **Session | CCost (Total) | Duration | Ctx**.
- Earlier Mini: **Activity | Session | CCost (Total) | Ctx**.
- Session contains only the name. Costs show the focal/latest canonical prompt cost
  followed by independent whole-session cost in parentheses, preserving Credits/USD,
  zero, N/A, partial/pending/retained evidence and corrections.
- Shared targeted help keeps running Prompt # discoverable on the full Session title;
  historical cost help exposes that prompt's model/provider identity, effort, finished
  duration, known calls and relevant mixed/subagent/partial/outcome facts. Stable nodes
  retain focus and coherent open help; dismissed help does not reopen on Live updates.
- Four-column empty/measurement rows and intrinsic metric CSS preserve both amounts,
  title ellipsis and narrow horizontal panning. Header-based opening width, two-row
  reserve, disclosure sizing, history selection/grace/Activity/Ctx and full Watch are
  unchanged. No backend/schema/acquisition/accounting or release-policy change.
- Updated user guide, Web/help/code-map architecture facts, release metadata and
  [Mini journal](../../../journal/web/mini-watch.md). No architecture boundary moved.

## Verification

- Focused Mini: **8 tests passed**.
- Full local suite: **152 bounded units, 1,784 passed tests, one existing macOS
  zsh/PTY skip; zero failures/errors, 95.4 seconds**.
- Working-tree validator: **11 passes, zero failures, six existing advisory warnings**.
- Chrome 156.0.8078.80 scale 1 / browser zoom 100% and Edge 156.0.4314.58 emulated
  scale 1.5 / actual browser zoom 125%: **116 rendered headless layouts each**, including
  108 paired-cost matrix cases total; actual CDP hover/keyboard/touch, live focus/help
  corrections, distinct concurrent prompt/session scopes, independent cost states,
  themes/units, narrow widths, Activity/DST and preserved opening/disclosure fit.
  Edge's six native-limited opening cases verify truthful limits/accessibility, not
  exact fit. A stale small-value overflow expectation was corrected; oversized paired
  costs still must pan without clipping. No product failure was waived.
- Fresh real V2 read-only source: 39 coherent publications, one running prompt,
  three accounts, five finished history cards with known finishes; one acquisition
  owner; 23.999 seconds, owned close 0.1 seconds. Shared OpenCode untouched; no inference.
- [Compact evidence](../../../architecture/governance/verification/mini-costs-608.json).
  Full raw run evidence remains in this worker's logical scratch:
  `scratch:/full-tests.json`, `scratch:/mini-costs-chrome.json`,
  `scratch:/mini-costs-edge-zoom.json`.

## Approved verification exception and remaining uncertainty

**Decision Delegate approved, FR 000608 only:** integrated OpenCode browsing returned
`browser.disconnected`. Despite installed physical browsers, adequate non-disruptive
headless layout/help/native-API geometry and real-source evidence make physical-only
reassurance nonessential. Omit physical Windows frame/work-area, actual OS scaling,
manual dragging, monitor transitions and screen-reader speech checks rather than
request disruptive desktop access or put useful delivery On Hold.

Those checks are **unperformed/unverified, not PASS**. Emulated device scale is not
physical scaling; browser API resizing is not manual dragging; DOM/help assertions
do not prove screen-reader announcements. Native/assistive differences remain uncertain.
No visible-desktop permission, functional-failure waiver or future exception was granted.
No ZIP, tag or GitHub Release was produced.
