# FR 000576 — Mini Watch placement mode and explicit Default inheritance for Web Settings

## Owner request, identity and scope

**Owner-approved executable feature request, 2026-11-04.** Permanent identity **000576**; Ready priority **000160**, after the currently queued FR000570–FR000575.

Make one coherent **CostGuard Web Beta → Settings → Web settings** improvement:

1. Add one **Mini Watch placement** dropdown with two actual behaviors: **Remember last** and **Standard placement**. The application default is **Remember last**.
2. Improve **all three Web Settings dropdowns** so **Default (current default name)** is a selectable, persistent *inherit-the-application-default* choice distinct from explicitly selecting either actual value. Apply this to the existing **Theme** and **CCost display** preferences as well as the new Mini Watch preference.

The owner specifically wants the **Mini Watch geometry** (window size and position) remembered **only while the current Web server instance is alive**, *not* written persistently or revived after a server restart. **The user's selected placement-mode preference itself is a normal persistent Web setting**, just like Theme/CCost display. These are different lifetimes.

This is an approved backlog request only. It does not authorize implementation during FR authoring.

## 1. Exact Settings controls and default semantics

Use the existing one-column Web settings section and immediately-saving dropdown UX. Each dropdown has **three visible choices**, with **Default first**, followed by the two explicit choices:

| Setting / visible label | Option 1 — inherited | Option 2 — explicit | Option 3 — explicit |
| --- | --- | --- | --- |
| **Theme** | **Default (Classic)** | **Classic** | **Web** |
| **CCost display** | **Default (Credits)** | **Credits** | **USD** |
| **Mini Watch placement** | **Default (Remember last)** | **Remember last** | **Standard placement** |

These are the **current shipped defaults**, not hardcoded eternal text. If a later version changes a default, the label must show that version's newly resolved name, e.g. **Default (Web)**, without changing the stored intent.

- **Default** means *follow the application's current default for this particular preference*. It is a real **selected state**, not a synonym for writing today's resolved value. Thus if the application later changes Theme's shipped default from Classic to Web, someone who selected **Default** gets Web on their next launch of that version. Likewise for CCost or Mini Watch's default if changed in the future.
- **Explicit choice** means *pin the selected behavior* independently of future shipped defaults. Selecting **Classic** explicitly remains Classic even when **Default (Classic)** is presently the same effective behavior; similarly explicit **Credits** and explicit **Remember last** remain pinned if their application defaults change later.
- **Never collapse an explicit choice into Default merely because its value currently equals the default**; never silently write the resolved value when the user selects Default. The dropdown must show **which state the user chose**, not just the currently effective theme/unit/placement.
- An untouched install with no user override shows **Default (Classic)**, **Default (Credits)** and **Default (Remember last)** selected; all resolve to their currently shipped behavior. Opening Settings or reading defaults does not create or rewrite a user config file.
- Preserve a valid explicit choice already in **config/user-config.jsonc** as explicit on upgrade, including values equal to today's shipped defaults. Missing overrides inherit as before. Respect existing legacy theme **webTheme** fallback; do not mislabel an old explicit Web/Classic override as Default or cause a regression. A new explicit **Default** selection must be able to override/bypass a still-retained legacy webTheme without deleting/reformatting it.
- Immediate effect: Theme restyles Web and Mini Watch as before; CCost re-renders the existing Web CCost displays as before; Mini Watch placement changes the behavior of the **next opening**, not the geometry or existence of an already-open PiP window. No extra Apply button, restart or report acquisition.

**Technical contract:** Settings read responses must expose **both the saved choice/source (default vs explicit)** and the **effective resolved value/default description**. Effective merged config values alone cannot answer whether Classic or Credits was explicitly selected. Implement a stable symbolic inheritance representation: absence of an override and/or a narrowly validated **default** sentinel are acceptable, provided an explicit Default beats legacy theme fallback where necessary and current shipped values are resolved *before* regular consumers use them. Do not bake the effective value into the saved Default choice. Keep old valid configuration files readable and treat unsupported enum values as errors.

## 2. Mini Watch placement: the two real behaviors

The new preference is **Web-only**, under the existing narrow **webSettings** configuration namespace (proposed key **miniWatchPlacement**; e.g. **remember-last** / **standard**). Default **remember-last**.

### Remember last — new application default

- **First Mini Watch opening on a fresh CostGuard Web server instance:** use the established standard initial PiP size and browser-default placement. The current measured design is **560 × 250 screen-DIP request**, visually appearing near the **bottom-right** of the display on the supported Windows Chrome setup. Browser/OS may clamp the size or choose its own position; do not promise direct site control over exact screen coordinates.
- **Close and reopen while that same server instance is still running:** use the **last size and screen position the user left the PiP window at**, including manual move and resize, rather than requesting a new standard placement. Reopen should preserve both dimensions and position as the supporting browser permits, not just one of them.
- **After restarting the Web server:** forget the previous server instance's PiP geometry. The next **first** Mini Watch opening begins from the standard size/placement again; later closes/reopens in that new instance may remember its own geometry. This is true even though the user's **Remember last** *mode preference* remains selected persistently.
- Do **not** write position/size to **config/user-config.jsonc**, SQLite, a server state file, browser localStorage/sessionStorage, cookies, URL, or disk-backed alternative. Reuse browser-native nonpersistent PiP bounds behavior and, if genuinely necessary, only minimal live-instance-scoped state. Do not create a cross-server persistent window geometry preference.

### Standard placement — explicit alternative

- **Every opening**, even after the user moved/resized the previous Mini Watch, requests the established **standard 560 × 250 screen-DIP opening** and **browser-initial placement**, instead of restoring its previous bounds.
- In Chrome on the owner's target workstation this should normally be the designed bottom-right placement; exact monitor coordinates are **browser/OS-owned** and may differ across browser versions, available work areas and monitors. Do not attempt pixel-perfect scripted movement.

The choice affects **Mini Watch only**. It does not auto-open it, save the On/Off state, open extra windows, or change ordinary full Watch or session/account tables. Preserve normal manual moving/resizing while PiP is open in **either** mode.

## 3. Inspected baseline, browser support and feasibility boundary

At inspected CostGuard `main` on 2026-11-04:

- **src/web/assets/mini.js::Controller.toggle** always calls **documentPictureInPicture.requestWindow({width: 560, height: 250, preferInitialWindowPlacement: true})**. This **explicit true** is why it currently always prefers initial placement/size. The owner wants an explicit setting for this behavior, with **Remember last** as new default. Keep the call in the direct user-activation opening path.
- The **Document Picture-in-Picture API** already provides the pertinent option. Chrome documents **preferInitialWindowPlacement=true** to avoid reuse of previous bounds; **false** permits reusing previous size/position. [Chrome developer documentation](https://developer.chrome.com/docs/web-platform/document-picture-in-picture); [MDN requestWindow](https://developer.mozilla.org/en-US/docs/Web/API/DocumentPictureInPicture/requestWindow).
- Chromium's [PictureInPictureBoundsCache](https://chromium.googlesource.com/chromium/src/+/HEAD/chrome/browser/picture_in_picture/picture_in_picture_bounds_cache.h) describes a **per-opening-WebContents nonpermanent cache**, keyed by origin and requested size; origin navigation clears it. This is a strong candidate to meet close/reopen within the same opener without storing geometry ourselves. It is **not proof** of every host-restart/tab-reload/monitor scenario; test those boundaries rather than assuming a browser cache is keyed to the Python host instance.
- The API **does not allow websites to set PiP screen position arbitrarily**. [MDN API limitations](https://developer.mozilla.org/en-US/docs/Web/API/Document_Picture-in-Picture_API). Thus the target is the browser's original/bottom-right-like placement, **not** a new site-defined absolute X/Y coordinate or OS HWND manipulation.
- **src/web/assets/settings.js** currently has only two actual enum choices for Theme and CCost and stores only resolved **confirmed** values. **src/web/settings.py** reads merged config and performs serialized, safe **allowlisted JSONC** edits; **src/web/http.py** exposes fixed authenticated Settings read/write endpoints. **config/default-config.jsonc** currently ships **webSettings.theme=classic** and **webSettings.ccostDisplayUnit=credits**. **src/config.py** normalizes legacy **webTheme** before merging defaults and then validates enums. All these places need a **source/choice versus effective value** distinction.
- Settings writes currently persist to **config/user-config.jsonc**, not browser storage. Preserve that architecture: new *preference selection* persists; *PiP window geometry* does not.

**Implementation investigation before claiming PASS:** verify actual Chrome native PiP behavior of both `preferInitialWindowPlacement` modes **with width/height present**, the original lower-right position, resizing/moving, host restart and switching modes. In particular, do not silently mistake **same browser tab/origin** caching for **same server process** identity. Reuse existing host-instance identity where useful. If the browser automatically forgets placement on a new opener/origin, use that natural boundary; if it retains stale bounds after a server restart, establish whether a supported **first-open initial-placement** request can reset the effective geometry without ruining subsequent Remember last behavior. Do not promise that page JS can read, persist or position arbitrary screen coordinates. Any browser-imposed limitation must be documented and validated, not hidden by an unsupported native workaround or a misleading PASS.

## 4. Preserve Web Settings security, JSONC and compatibility

- Extend only the existing **fixed allowlist** and validated Web Settings backend; use a dedicated narrow endpoint or equally bounded typed action for **miniWatchPlacement**. Extend read semantics to return default-vs-explicit choice, resolved value and displayed default for all three preferences. Keep same-origin authentication, HttpOnly sessions, Origin/CSRF checks, request size bounds, stopping/host-identity guard, private atomic writes and sanitized failures. No generic config editor, arbitrary field/path write, secrets in responses or external requests.
- Preserve **unrelated JSONC** bytes/comments, nested values, old CLI CCost display setting, terminal colors, and legacy webTheme. An explicit Default should be stored as a symbolic inheriting selection, e.g. validated **default** under the nested Web preference where necessary; alternatively safe removal of an override is fine only if it cannot reveal a stale legacy override or misrepresent user intent. Avoid destructive migration or rewriting all settings with current effective defaults.
- A stale/failed read/write never claims to be saved. A rejected save restores the last **confirmed selected state** (Default or explicit) *and* correct effective value, not only the last resolved color/unit. Concurrent tabs and external JSONC editors must not overwrite unrelated changes; a fresh Settings read should reflect authoritative user intent.
- Existing installs with saved explicit Classic, Web, Credits or USD retain the same visible/effective behavior and now display their **explicit** selection, even if it matches the shipped default. Missing overrides remain inherited. Future shipped defaults can change one preference without altering another explicit choice, CLI behavior, prompt/session accounting, model pricing or provider quota usage.
- Do not make selected Mini Watch mode browser-local/persistent outside the user settings file; the application default changes only when the shipped default changes. Do not store current geometry as a setting value.

## 5. Dependencies and acceptance

Coordinate with queued **FR000570** (Mini native icon), **FR000571** (Mini CTX and daily label), **FR000572** (full-Watch session context/cost), **FR000574** (Mini tables/session totals) and **FR000575** (full-Watch prompt CCost split) without undoing their table/layout work. The Mini Watch placement change is orthogonal to these changes and must retain the established **560 × 250 DIP** standard opening, native Document PiP controls, one shared live/SSE owner, browser security, resizing, narrow-window scrolling and 150%-scale constraints. No effect on CLI, other Web report tables or historical accounting.

Acceptance criteria:

1. Settings has exactly **three dropdowns**: Theme, CCost display and Mini Watch placement. Each displays exactly **Default (<current default>)** first, plus its two **explicit** options. An unmodified user config selects **Default (Classic)**, **Default (Credits)** and **Default (Remember last)**. Current default labels come from canonical app defaults, not hardcoded permanent UI strings.
2. **Default versus explicit** is observed and round-trips across Settings navigation, reload/new browser tab and Web host restart. An explicit value identical to the present default remains explicit; selecting Default follows a changed shipped default on a simulated later-version config while the explicit value does not. Existing saved overrides and legacy webTheme retain correct precedence. Selecting Default never snapshots the current resolved value.
3. Theme/CCost existing immediate appearance/formatting changes continue across loaded Web content and Mini, with CLI independent. No report fetching, host restart or extra Web application storage is triggered by changing settings. Save errors/conflicts and focus/accessibility remain honest.
4. **Remember last:** using actual native Chrome PiP, open Mini at standard size/placement, move **and** resize it, close via the app and via native close in separate tests, then reopen with the **same server alive**. It visibly returns to the final moved/resized bounds within browser-supported tolerance. No user dragging/resizing is disabled.
5. **Standard placement:** after manual move/resize, every subsequent open visibly restores the intended standard 560 × 250 DIP request and browser-default location instead of reusing the last bounds. Switching between modes applies on the next open, without forcibly changing an existing PiP.
6. **Server-instance boundary:** verify server stop/restart with the same browser profile: first Mini opening in the new instance uses standard placement/size, *not* the previous instance's custom bounds; subsequent reopens remember the new instance. Verify actual opener tab/origin/browser-reload behavior and record limitations if browser semantics differ. No JSONC/SQLite/browser-storage geometry record survives restart. A persisted explicit or Default **mode choice**, however, does survive restart.
7. Verify physical **Windows Chrome at 150% display scaling** with actual native PiP move/resize and window bounds, including usable display edges, closing/reopening, monitor/work-area changes where available, and Chrome/Edge/browser-support differences where practical. Browser-emulated DPI or a DOM width assertion is not proof of exact native placement. Do not touch unrelated personal browser windows, native OS state or host installation without existing applicable authorization. Record honest UNVERIFIED / supported-browser limitation rather than a fabricated physical PASS.
8. Extend focused canonical config/legacy/default-selection and settings-HTTP security/JSONC preservation tests, JS settings DOM/focus/save/error cases, and Mini native-PiP/opening/close tests. Update current **docs/web-beta.md** and **docs/web-mini-watch.md** with the three controls, selection inheritance, supported PiP behavior and the distinction between persistent preference and nonpersistent geometry; leave historical complete FRs intact.

**Out of scope:** a new window-coordinate editor, manual X/Y positioning, a desktop OS window manager, popup/PWA replacement, remembering PiP On/Off, changing standard geometry, broad user-config CRUD, generic settings framework, account/source/pricing/CLI behavior, or any version/release implementation now.

**Authoring boundary:** publish only this approved Ready FR plus advance the permanent backlog identity high-watermark to **576** on CostGuard **main**. Do not edit product code, version/history or the user's running browser/server in this authoring session.
