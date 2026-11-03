# FR 000567 — source delivery with a verification exception

Date: **2026-11-04**. Product: **v80.147**. Implementation base:
`3b74cc5d072de275a8a456d8142e45d4fd7d67bd`.

## Delivered scope

- One original, dependency-free CG source supplies physical-size Windows HICONs
  and the tested, checked-in 16/20/24/32/48px browser ICO. No font/image dependency,
  download, new process owner or separate independently maintained logo.
- Explicit versioned favicon declaration, fixed conventional compatibility route,
  correct MIME, no-store responses and image CSP limited to those two local paths.
  The in-page CG badge, dynamic section titles, routing and sensitive API guards
  are unchanged.
- Native Windows tray UI thread enters PMv2 before HWND/menu creation, restores on
  constructor failure/close, follows physical small-icon metrics and positions its
  invisible owner on the relevant popup monitor. No process-default or machine
  setting change. Existing Open/Exit, native menu and host lifecycle are retained.
- Original FR bundle moved intact to completion ordinal **000079**; permanent ID
  **000567** and original specification are unchanged. Ordinary maintenance count
  advances **17 → 18** only upon merge of this PR.

## Actual checks

- Local Full: **PASS**, all **136 runner units**, **1,617 tests**, **279.0s**,
  one macOS zsh/PTY skip on Windows. A first Full run exposed two SSE fixture origins
  needed by path-specific CSP; both were repaired and the complete suite rerun.
- Validator: **PASS**, 11 passes, zero failures, six advisory budget warnings.
- Real headless **Chrome 156.0.8078.80** and **Edge 156.0.4314.58**: favicon decoding,
  all eight section titles, reload/new tab/server restart, no external requests or
  runtime exceptions. These do not establish native tab-theme acceptance.
- Actual Windows **150% / 144 DPI**, build 26300, Python 3.14.7: original interpreter
  manifests contain no DPI declaration; baseline owner/popup unaware at 96 DPI.
  Candidate and independent original-native-menu PMv2 comparator report exact PMv2,
  popup DPI 144 and matching 270×76 physical menu geometry. Controlled anchor mapping
  is verified; physical cursor/hit-target interaction is not.
- Actual 24px production HICON inspected and drawn offscreen on light/dark DIBs;
  real shell add/re-add/delete used that handle. Targeted native Open failure/retry
  and Exit/cleanup passed; exact owned-entry loss plus `TaskbarCreated` simulated
  recovery, **not an actual Explorer restart**. OS failure notification was suppressed.
- Read-only real V2 probe: one owner, two streams, three accounts, 1.337s source view,
  zero owned workers/processes after shutdown; shared OpenCode untouched. Shutdown
  daily-history cancellation is not a claim of completed Daily acquisition.

## Explicit incomplete verification and decision

**Delivered with a Decision Delegate verification exception; physical tray appearance
and normal 150% menu contrast/full sharpness remain unverified.**

The **Decision Delegate**, not the user, authorized source delivery after reviewing
the bounded alternatives and results. The exception waives verification coverage
only for this FR, including legitimate same-task continuation. Further disruptive
desktop experimentation was unlikely to establish adequate evidence.

- Actual notification-area captures did not show a recognizable icon despite a
  successful own-icon rectangle lookup. Native HICON drawing is not tray proof;
  physical tray/favicon side-by-side acceptance is unverified.
- Menu screen captures remain unusually dark; PrintWindow is incomplete and does
  not reliably establish compositor contrast or full sharpness.
- Native Chrome has a partial 144-DPI tab-strip capture with CG test tabs, but the
  later native restart sequence **FAILED: CDP timeout Runtime.evaluate**. Its status
  remains FAIL, separate from independently passing headless restart checks.
- Actual 100%/125%/200% scales, alternate physical taskbar/tab themes, mixed-monitor
  moves/scale changes, real mouse/keyboard interactions and actual Explorer restart
  were not verified. Offscreen light/dark pixels do not replace those checks.

Canonical branding, implementation, security, lifecycle correctness, fixing known
defects, Full/validator checks, versioning and Git protections were **not waived**.
No blanket future exception, permanent gate or automatic release was introduced.

Current architecture and Code Map were updated in place. Durable results, initial
instrumentation/test failures, raw evidence and exact limitations are in the
[branding journal](../../../journal/web/branding.md) and its evidence inventory.
No release ZIP or running ordinary-checkout host was changed.
