# FR 000570 — completed with an approved verification exception

Date: 2026-11-04. Product: **v80.150**. Implementation base:
`ce7859fcb8df3fe713c85519a7739242fc60fe6c`.

Mini's shipped controller adds one explicit `rel=icon`, `type=image/x-icon` link to
the existing absolute same-origin `/favicon-cg1.ico` when setting up each PiP head.
The original artwork/HTTP route, normal-tab icon, Windows tray, browser controls,
560×250-DIP request, accessibility and shared Live ownership are unchanged.
No new dependencies, endpoints, native bridge, permission or application fallback.

## Actual evidence

- Pre-implementation native feasibility: **Chrome 156.0.8078.80**, Windows build
  **26300**, actual DPI **144 / 150%**. Same PiP HWND changed from a generic globe
  to recognizable CG in successful small/large/small2 `WM_GETICON` reads. Immediate
  attachment/reopening retained identical candidate icon pixels on a new HWND.
  Borrowed icons were not modified/destroyed. Native controls and 428px DWM-visible
  height were retained. Owned-window captures are not shell-surface screenshots.
- Final shipped controller, without candidate wrappers: hidden Chrome and
  **Edge 156.0.4314.58**, emulated scale **1.5**, passed opening/reopening favicon
  requests, normal-tab preservation, HTTP/CSP/style/layout/lifecycle/hidden-opener
  updates and separately verified **exactly one EventSource**.
- Focused Mini VM, HTTP/favicon and shared-icon regressions passed. Final local
  **Full: 138 bounded units, zero failures, 88.4s**. Validator: **11 passes, zero
  failures**, six pre-existing advisory design/prose warnings. No gates weakened.
- Real installed V2 read-only probe: **seven coherent publications**, two running
  prompts, three accounts/two primary-period costs, two known-finish cards;
  **9.567s**, owned close **0.126s**. No inference/shared OpenCode stop.

Evidence/method, raw results/captures and test logs:
`development/architecture/governance/verification/mini-watch-icon/`.
Detailed findings/attribution: `development/journal/web/mini-watch.md`.
README/history/current Mini help updated. Architecture boundaries are unchanged;
no architecture-contract update is necessary. The proposed ordinary progress
advances to 21 only when this PR is merged. The original FR is preserved intact.

## Decision Delegate exception and remaining uncertainty

The **Decision Delegate**, not the owner, authorized the crucial finite own-profile
Chrome native feasibility experiment; total visible work was **4.551 seconds**.
After independently inspecting its JSON and four images, the same delegate approved
omitting actual **taskbar-preview, Alt+Tab and grouping observation** for FR 000570:
the demonstrated native adoption and link-only fix do not justify disruptive shell
interaction. The unused visible authorization ended. Final-code verification was
hidden only; no shared desktop input, taskbar hover/Alt+Tab invocation, unrelated
window capture, native-window mutation or personal-profile access occurred.

**Verified:** native PiP HICON adoption in this Windows Chrome build at 150%.
**UNVERIFIED:** actual taskbar-preview/Alt+Tab rendering and grouping, native Edge
and macOS. Shell caching or platform/browser-specific representation remains unknown;
untested environments are not labeled unsupported. Native experiment `streams: 0`
was a DOM count, not SSE evidence; the normal final-controller harness proves SSE.

This is **delivery with an approved verification exception**, not unconditional
primary/full acceptance PASS. No behavioral or failing-test exception was granted.
The decision is limited to this FR/legitimate continuation unless superseded, not
future tasks or desktop permission. No release ZIP/tag/GitHub Release was built.
