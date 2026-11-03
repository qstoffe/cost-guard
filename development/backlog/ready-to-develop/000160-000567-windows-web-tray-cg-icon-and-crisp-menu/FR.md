# FR 000567 — Windows Web Beta tray: branded CG icon and crisp native context menu

## Owner request, scope and queue

**Owner-approved executable feature request — 2026-11-03.** Permanent identity **000567**, Ready priority **000160**, after currently Ready FR000565 and FR000566. This is a focused **Windows Web Beta notification-area/tray** visual polish request. Both outcomes below are required; the icon is the most visible change, but the menu sharpness is not optional.

The owner reports that the current tray icon feels generic and does not visually identify Cost Guard. They want a distinctive, polished **CG** monogram/emblem resembling the existing **CG** badge immediately before “Cost Guard” in the browser header. The specific drawing technique is not prescribed: choose a simple maintainable way to create and ship an original recognizable icon.

The owner also reports that the tray right-click menu’s **Open Cost Guard** / **Exit Cost Guard** text looks noticeably **blurry/soft** compared with ordinary native Windows context menus (e.g. Microsoft Copilot) on their **Windows display scaling set to 150%**. The actions and menu structure are otherwise fine. These are owner visual observations, not a reproduced root-cause diagnosis.

## Inspected source baseline and likely investigation

Current repository main source inspected on 2026-11-03:

- `src/web/assets/index.html` includes `<span class="brand-mark">CG</span>`; `src/web/assets/app.css` defines the rounded badge, accent color, border and compact bold lettering. Use this as the *visual reference*, not a mandate to use browser rendering at runtime.
- `src/web/tray_icon.py::icon_bits` draws an original but unrelated **32 × 32 shield-and-bars** pixel icon. `src/web/win32_tray.py` passes it to Win32 `CreateIcon(..., 32, 32, ...)`. A single-size source can also be a quality constraint at some tray sizes / DPI values.
- `src/web/win32_tray.py` already builds a **real Windows menu**, using `CreatePopupMenu`, `AppendMenuW` and `TrackPopupMenu`. The labels are **not HTML, browser text or a custom owner-drawn bitmap menu**. `src/web/native_windows.py` integrates the tray with the existing same-process host lifecycle.
- The inspected tray modules do not explicitly establish a Windows DPI-awareness mode. **Hypothesis, not established fact:** the process/window/thread may be DPI-unaware or otherwise bitmap-scaled by Windows at 150%, making even the native menu text look soft. The Python interpreter's manifest, process context, monitor DPI, menu HWND and actual OS behavior must be checked before changing anything.

Microsoft reference: [High DPI Desktop Application Development on Windows](https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows) and [Setting the default DPI awareness for a process](https://learn.microsoft.com/en-us/windows/win32/hidpi/setting-the-default-dpi-awareness-for-a-process). Windows can bitmap-stretch DPI-unaware UI, while a manifest/API-based DPI mode has ordering and coordinate-handling consequences. Do not simply call a DPI API late or globally assume the same mode is safe for every Python entry point.

## 1. Replace the Windows tray icon with a recognizable CG mark

- Create or generate an **original, visually distinctive Cost Guard `CG` icon** that feels consistent with the browser header's current CG badge: compact monogram, deliberate geometry, coherent palette and clear silhouette. It need not reproduce the CSS literally; optimize the actual **very small Windows tray rendering** first. Avoid simply renaming/recoloring the existing shield/bars.
- The letters/monogram must remain recognizable at real notification-area sizes, including on the owner's 150%-scaled Windows setup, without becoming a tiny illegible wordmark. Choose proportions, padding, stroke weight, contrast and transparent edges accordingly. Work in both light and dark taskbar/system themes; handle Windows accent/contrast variation reasonably.
- Provide crisp rendering at practical tray icon sizes and DPI scales (at least 100% and 150%, with 125%/200% where feasible). Inspect the installed Windows icon at its *physical display size* rather than relying only on a large source preview. Prefer appropriately sized source variants or correct native icon loading if a single 32px raster is being resampled poorly.
- Keep resources **original, source-controlled, offline and maintainable**. Preserve the existing product's no-extra-runtime-dependency / no-download / no-admin requirements. The implementation may use checked-in image resources or source generation; no particular image library or format is required. Do not introduce a second tray owner or server process.

## 2. Render the existing Windows tray context menu sharply at 150%

- Keep the **native Windows right-click popup menu** with the same two items and behavior: `Open Cost Guard` and `Exit Cost Guard`. The desired change is visual fidelity: normal Windows font rendering, clean edges, appropriate menu/item sizing and spacing, not a custom skinned HTML or bitmap menu.
- **Measure the root cause** in the actual Web Beta host: effective Python process/thread/window DPI awareness, monitor DPI and scale, icon/menu DPI context, and whether Windows is bitmap-stretching the popup. Compare to an ordinary sharp native tray menu at the same OS settings. Use real screenshots/crops or direct inspection with stated physical-versus-logical pixels; do not guess from a CSS pixel count or from the source's native Win32 API usage alone.
- If DPI virtualization is responsible, apply an appropriately scoped and **early** native Windows DPI-awareness solution, consistent with Windows' documented manifest / `SetProcessDpiAwarenessContext` / mixed-mode constraints. If another cause is proven, fix that instead. Avoid indiscriminately modifying the DPI awareness of other Python tools or introducing a machine-wide setting. Account for the requirement that process DPI defaults must be established before creating affected windows.
- Confirm the popup position, cursor coordinates and click hit targets remain correct; `TrackPopupMenu` must anchor at the actual cursor on high-DPI and mixed-monitor setups. Do not regress icon placement, text size, Explorer taskbar recreation, menu callbacks or keyboard accessibility.

## Acceptance and boundaries

1. **Physical Windows 11 check at 150% display scaling (required for full visual acceptance):** before/after evidence of the actual Cost Guard tray icon and right-click menu, under the owner's effective scale or a demonstrably equivalent Windows environment. The icon is recognizably branded **CG**, and the menu labels are **as sharp as normal Windows native tray-menu text** at the same scale. State the DPI contexts, monitor scale and evidence; do not declare this fixed solely from code inspection, synthetic tests or a 100% screenshot.
2. Verify light/dark tray backgrounds and practical icon sizes. Compare 100% and 150% scaling and, where available, 125%/200%, monitor moves and scale changes. Record which physical environments were and were not tested instead of assuming Per-Monitor v2 or bitmap handling is correct everywhere.
3. Existing native lifecycle remains intact: single tray/host ownership, Open opens the current browser host without restart, Exit cleanly stops only that instance, browser-open failure can still be retried, icon cleanup on shutdown/fault/source change, taskbar/Explorer restart recovery, and native resource cleanup.
4. Add proportionate focused regression coverage (including `development/tests/test_windows_web.py` and native UI verification where available). **If the owner's 150%-scaled desktop cannot be physically exercised, explicitly mark the actual visual result unverified**, not PASSED. Do not add a new permanent release gate.

**Out of scope:** changing the browser's existing CG header, redesigning Web reports or Mini Watch, changing macOS status-bar appearance, modifying CLI/report/accounting semantics, Windows autostart/service registration, installer/package downloads, or adding optional menu items.

**Publication only:** creating this FR and advancing the backlog identity counter changes no product source, tests, version, release or running Web host. Implementation is a separate future delivery.
