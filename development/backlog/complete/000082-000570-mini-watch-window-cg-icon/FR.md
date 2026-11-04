# FR 000570 — Show the existing CG icon for the Mini Watch window when browser-supported

## Owner request and scope

**Owner-approved FR, 2026-11-04.** Permanent ID **000570**, Ready priority **000100** (Ready queue empty at authoring).

CostGuard Web Beta now shows the correct CG favicon in normal Chrome tabs and uses the same original CG emblem for the Windows tray (FR000567). However, opening **Mini Watch** creates a separate Document Picture-in-Picture (PiP) window whose **Windows taskbar/window-preview and Alt+Tab icon looks generic**. The owner wants **that Mini Watch window** to show the existing CG icon too, **if technically supported**. Do not change Chrome's normal application/taskbar icon, the main browser-tab icon or the Windows tray.

The requested deliverable is the **actual browser-created native window icon**, not an extra image in the page, a renamed document, a successfully fetched ICO or just a favicon node.

## Inspected current implementation and feasibility

- `src/web/assets/index.html` already contains `<link rel="icon" href="/favicon-cg1.ico" ...>`. FR000567 generated this multiresolution ICO from the same canonical CG artwork as the native tray. `src/web/http.py` already serves it on fixed allowlisted loopback routes with scoped CSP. **Reuse it**; no new icon art or resource route is needed unless demonstrated otherwise.
- `src/web/assets/mini.js::Controller.toggle` opens `documentPictureInPicture.requestWindow({width:560,height:250,preferInitialWindowPlacement:true})`, sets `win.document.title = 'Mini Watch · Cost Guard'` and adds the existing CSS stylesheets to the independent PiP `document.head`. **There is no `rel="icon"` in that PiP document**. Adding the existing same-origin favicon to that document is the natural first candidate, **not a proven OS fix**.
- [Chrome's Document PiP guide](https://developer.chrome.com/docs/web-platform/document-picture-in-picture) and [MDN's documented `requestWindow` options](https://developer.mozilla.org/en-US/docs/Web/API/DocumentPictureInPicture/requestWindow) provide size, placement and return-to-opener controls, **not a direct taskbar/window-icon property**.
- Chromium [BrowserView::GetWindowIcon](https://chromium.googlesource.com/chromium/src.git/+/refs/heads/main/chrome/browser/ui/views/frame/browser_view.cc) can use a current-page icon for a non-normal browser window. Whether the specific PiP `about:blank` document/favicon is propagated to Windows taskbar/window metadata is browser-version/platform dependent. Chromium's [Windows shortcut/taskbar documentation](https://chromium.googlesource.com/chromium/src/+/main/docs/windows_shortcut_and_taskbar_handling.md) explains that taskbar grouping and application identities are browser/OS-owned. Neither source guarantees this behavior in CostGuard's Chrome build.

## Implementation

1. **Establish native feasibility first.** Reproduce the owner's generic/iconless Mini Watch representation in Windows Chrome. Inspect the **actual separately opened PiP window** in the taskbar preview and Alt+Tab (including grouping) rather than the main Chrome application button or a browser security icon in PiP chrome. Determine whether its favicon, current-page icon or OS window icon can be influenced by the standard PiP document.
2. Prefer the **smallest first-party Web fix**: add an explicit `<link rel="icon" type="image/x-icon" href="/favicon-cg1.ico">` to `win.document.head`, with a correct same-origin absolute URL if necessary, alongside the existing title and styles. Test when this is attached relative to window creation; do not assume an image download or DOM inspection proves native icon adoption.
3. If that is ineffective, explore only a **supported, bounded browser-level alternative** that preserves the same Document PiP UX, browser controls and current architecture. Do not launch a substitute regular popup/PWA, inject into Chrome or modify other-process HWNDs, alter Windows AppUserModelID/taskbar grouping, start another local application, install an extension, use OS privileges or weaken CSP/auth to create an artificial icon.
4. Verify the **physical visible native icon** in Windows Chrome at the owner's 150% display scaling with before/after evidence and recorded browser version. Also inspect Edge and macOS if realistically available, distinguishing supported/unsupported behavior. Physical desktop/OS interaction still requires the existing applicable authorization and must not disturb unrelated owner browser windows. Headless/HTML/CSP checks are supporting evidence only.
5. If the browser simply **does not permit** changing its native PiP window icon through a supported web interface, document the blocker and actual experiments instead of falsely claiming success or widening the scope to a native desktop application. In active Repo Backlog, ask Decision Delegate for the appropriate truthful completion/hold/block outcome, retaining its established authority and the user's right to decide.

## Acceptance and regression criteria

- **Primary PASS:** On a genuinely supported Windows Chrome setup, the **Mini Watch native window/taskbar preview/Alt+Tab icon** shows the same recognizable CG mark as the normal CostGuard tab, verified by actual Windows-native evidence. If the OS groups PiP with Chrome, inspect the *window-level* preview/icon; do not require changing Chrome's normal taskbar app icon.
- Existing normal-tab CG favicon and Windows tray branding remain unchanged. Use the same canonical source/ICO; no second independent icon to maintain.
- Preserve Mini Watch's 560×250 screen-DIP opening, the verified 150% height cap from FR000565, initial/reopening size, browser native PiP security/return/close controls, one shared authenticated Live/SSE owner, state/tables/quiet updates from FR000569, permissions, origin/CSP, and accessibility.
- Add proportionate focused Mini Watch/favicons/HTTP/browser regressions. A `link` presence assertion or successful icon HTTP request **cannot** replace a real taskbar/window icon check. Missing native verification is **UNVERIFIED**, not PASS.
- Record browser/OS version support and what the browser owns. No demand for a universal solution in unsupported PiP implementations, no new dependencies/endpoint, no changes to full Watch, normal Chrome branding, installation or privacy model.

**Authoring only:** Publish this FR with its identity bookkeeping on CostGuard `main`. Do not implement code, bump the product version, build a release or alter the user's running desktop/server in this authoring session.
