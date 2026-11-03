# Shared CG branding and Windows DPI — FR 000567

Source delivery: v80.147, 2026-11-04. Base:
`3b74cc5d072de275a8a456d8142e45d4fd7d67bd`. This is implementation delivery,
**not full physical visual acceptance**.

## Owners and maintained design

- `src/web/tray_icon.py` is the single original CG artwork: a cyan monogram, dark
  tile, pale rim and transparent margin on a 16-unit pixel grid. It generates
  physical 16/20/24/32/48px variants without fonts or image dependencies.
- `python development/tools/generate_web_icon.py` regenerates
  `src/web/assets/favicon.ico`. Regression tests assert exact generator/asset
  equality and that every ICO DIB contains the same BGRA pixels as its tray size.
  Artwork changes require regeneration; incompatible favicon changes should also
  advance the explicit design-version path in HTML/routes/tests.
- `http.py` serves only `/favicon-cg1.ico` and conventional `/favicon.ico` through
  the existing asset allowlist. MIME is `image/x-icon`, responses remain no-store,
  and image CSP names only those two full same-origin paths. No wildcard image
  origin, query-string exception, generic filesystem handler or sensitive API
  authentication exception was introduced. No external image request is needed.
- `win32_tray.py` scopes `SetThreadDpiAwarenessContext(PER_MONITOR_AWARE_V2)` to the
  tray UI thread **before** creating its HWND/menu. Close and constructor-failure
  cleanup restore the previous context. It never sets the process default; another
  thread's context is regression-tested unchanged. Windows lacking the required
  native APIs fail preflight rather than silently advertising a blurry fallback.
- Native small-icon metrics select the matching source size. The hidden owner
  follows the shell icon's monitor, then the physical cursor for popup placement.
  DPI/display/settings messages schedule refresh outside the callback. Native menu
  labels/actions, single host ownership, in-page badge and dynamic titles are intact.

## Executed evidence and what it establishes

Raw observations and unrescaled PNGs are in
[`web-branding/`](../../architecture/governance/verification/web-branding/).
Workstation: Windows build **26300**, installed Python **3.14.7**, effective monitor
**150% / 144 DPI**. Helpers remained hidden; no personal browser profile, global
input, cursor movement, display/theme/tray-setting change or Explorer restart.

| Observation | Actual result and limit |
| --- | --- |
| Installed interpreters and original hidden Tray | `python.exe` and `pythonw.exe` both have a CreateProcess manifest but no `dpiAware`/`dpiAwareness` declaration. Installed `pythonw` process/thread/window awareness query 0, window DPI 96 while monitor scale reports 150%. Manifests were read as PE data resources without executing them. |
| Original real popup, controlled probe anchor | Unaware popup DPI 96; `(100,100)` logical anchor becomes `(150,150)` physical; popup bounds 284×75 physical pixels. DPI virtualization is measured, not inferred from native API names. |
| Candidate real popup | Exact PMv2 context equality, window/popup DPI 144; anchor `(100,100)` remains physical `(100,100)`; bounds 270×76 physical pixels. No cursor was physically moved. |
| Independent native reference | The saved **original** tray implementation, with PMv2 established externally before construction, produces 270×76 physical popup bounds. It is not a second invocation of candidate source. |
| Production HICON | `GetIconInfo`: 24×24, 32-bit color bitmap; successful `DrawIconEx` into offscreen light/dark 24px DIBs visibly shows CG. This is native-resource evidence, **not notification-area proof**. |
| Native same-process host | Real synthetic HTTP/WindowsHost, successful shell add/re-add/delete using its production HICON; two native items; targeted `WM_COMMAND` Open failure then retry, and Exit shutdown. The failure notification was suppressed, not shown. Exact owned shell-entry deletion plus `TaskbarCreated` simulated recovery, not an actual Explorer restart. Resources closed. |
| Chrome **156.0.8078.80** and Edge **156.0.4314.58**, headless | Real shipped HTTP/CSP/assets and disposable profiles: ICO decoding, all eight sections with unchanged titles, reload, reopened tab, full server restart; zero observed external requests or runtime exceptions. These are browser/route checks, not native tab-theme proof. |
| Native disposable Chrome | Actual 1000×75 physical tab-strip capture at DPI 144 contains the CG marks in Settings/Watch test tabs. The capture is unusually dark. Sections/reload/new tab ran before capture; the later restart sequence **FAILED: CDP timeout Runtime.evaluate**. Passing headless restart is separate evidence, not a relabelled native PASS. |
| Real installed V2 read-only probe | One owner, two streams, three accounts; source-view readiness 1.337s; owned shutdown left zero workers/processes and shared OpenCode untouched. Shutdown cancellation appeared in daily-history observations; no Daily result or shutdown-with-complete-Daily proof is claimed. |

The original notification-area rectangle lookup succeeded, but its bounded 48×72
physical capture did **not** show a recognizable icon. It was not repeatedly
recaptured or made visible by opening/promoting shell UI. The actual tray appearance
therefore remains unknown, regardless of successful shell registration.

Screen `BitBlt` with `CAPTUREBLT` still produced unusually dark popup captures;
`PrintWindow` produced a white background but did not faithfully capture all labels.
The unaware PrintWindow image also retains a logical-size footprint inside the
physical rectangle. These are not reliable normal-contrast/compositor acceptance
images. No HDR or other cause is asserted without measurement. Geometry/context
proof does **not** establish full sharpness or mouse hit-target correctness.

Initial instrumentation issues were corrected rather than hidden: incompatible
ctypes identifier classes; a comparator accidentally using candidate source; and
a naive `TaskbarCreated` simulation which tried adding an already-existing shell
entry. The corrected independent comparator and explicit owned-entry loss are the
retained results. The first HTTP regression run also exposed a misplaced existing
assertion in the new test, which was restored before final testing.
The first Full run then exposed two SSE test doubles lacking the server origin now
needed to construct the path-specific image CSP. Both fixtures were supplied with
their explicit loopback origin, and the idle-stream test now asserts that CSP;
production did not gain a permissive fallback and no assertion was weakened.

## Decision Delegate verification exception

### Final local regression gate

- **PASS:** `py -3 development/tools/run_tests.py --suite full --jobs 1 --file-timeout 120`:
  136 bounded runner units, 1,617 tests, zero failed units, **279.0s**. One macOS
  zsh/PTY-specific case was skipped on Windows; it is not claimed executed here.
- **PASS:** `py -3 development/tools/validate_package.py --working-tree`: 11 passes,
  zero failures, six advisory warnings (README/Web guide/history prose and three
  existing Python design budgets). No hard cap was raised.
- Focused coverage pins icon pixels/ICO equality and margins, unsupported sizes,
  DPI context ordering/restoration/failure and other-thread isolation, negative
  monitor coordinates, HICON replacement/rollback, fixed asset MIME/CSP and public
  image versus protected API boundaries, plus existing lifecycle/browser behavior.
- The earlier Full run failed only the two missing-origin SSE fixtures; these were
  repaired and the entire Full suite rerun, not merely relabelled successful.
- No model inference, product-release ZIP, installation or shared-service stop.

### Scoped decision

The active **Decision Delegate**, not the user, authorized the finite own-menu and
disposable Chrome verification after hidden/static alternatives could not establish
physical acceptance. All owned windows/icons were closed between short batches and
foreground was restored only while the test still owned it. No broad launcher probe,
default-browser shell association, notifications or global desktop input was used.

After inspecting the consolidated evidence, the same delegate explicitly authorized
protected source delivery with a **verification-only exception for FR 000567**.
It superseded the earlier provisional non-waiver because further desktop disruption
was unlikely to provide adequate evidence. The following remain unperformed or
unverified, **not PASSED**:

- Recognizable actual notification-area CG and physical tray/favicon side-by-side.
- Reliable before/after normal menu contrast and full sharpness at actual 150%.
- Completion of the failed native Chrome restart sequence.
- Physical 100%/125%/200% scales, alternate taskbar/tab themes, mixed-monitor moves
  and scale changes, real mouse/keyboard interaction, and actual Explorer restart.

Implementation, canonical branding, security, lifecycle correctness, correction of
known defects, Full/validator checks, versioning and Git protections were **not**
waived. No new permanent release gate or future blanket exception was created.

**Delivered with a Decision Delegate verification exception; physical tray appearance
and normal 150% menu contrast/full sharpness remain unverified.**
