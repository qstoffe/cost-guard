# FR 000538 — Add Web Settings with persistent Classic/Web theme switching

## Owner intent

Add a new **Settings** tab at the far right of Cost Guard Web Beta navigation. Start a small, extensible settings page with exactly one editable option, **Theme**. The user can switch themes from a dropdown; the setting is **written to the user's actual configuration file immediately** and the **whole running Web UI changes immediately without reload**.

Provide two Web-only choices:

- **Classic** (new default): a deliberately dark, polished adaptation of Cost Guard CLI's **classic** PowerShell/console color language — near-black background, light grey body text, subdued neutral surfaces, restrained vivid lime/green for positive/new information, plus semantic cyan, yellow/amber and red accents. Retain modern Web typography, spacing, cards, native controls, contrast and responsive layout; **not** a fake terminal or full monospace redesign.
- **Web**: preserve the current Web Beta design and its automatic OS light/dark preference essentially unchanged.

The CLI already has a separate `colorScheme` contract (`classic` and `modus-operandi-tinted`, with optional color overrides). The new Web setting **must not change, rename or remove CLI schemes or color overrides**. Do not expose `modus-operandi-tinted` as a third Web option in this FR. Treat Classic as a Web visual interpretation of the CLI default, not a requirement to convert arbitrary custom ConsoleColor palettes to CSS or keep Web colors synchronized with future CLI overrides.

This FR may run after **FR000537**, which replaces Overview + old Models with one Models route and alters main navigation. Rebase on the delivered navigation and avoid reintroducing the retired Overview/Models split.

## 1. Navigation and the initial Settings page

1. Add **Settings** as the **last/rightmost** item in the shared Web navigation, visibly separated by the available flexible space on wide screens; it remains logically last and keyboard-accessible when the nav wraps on small/mobile layouts. The canonical route is `#/settings`, with an appropriate title and active-navigation indication.
2. On first iteration Settings contains **only one actual setting**: a properly labeled `Theme` select/dropdown with `Classic` and `Web`. A short plain-language explanation and compact accessible success/error feedback are acceptable. Do not add CLI color-scheme editors, generic config editor, theme previews, unrelated preferences, extra cards or an Apply/Save button.
3. Navigating to Settings **must not trigger report/history/account acquisition**, restart the host, change frozen reports, or discard ongoing Watch/sessions state.

## 2. Separate Web configuration key and defaults

1. Introduce a top-level **`webTheme`** setting to the existing `config/default-config.jsonc` / validated merged configuration, with exactly two supported string values: **`"classic"`** and **`"web"`** (case policy consistent with existing configuration conventions). Default to **`"classic"`** for both new and existing installations that have not explicitly set it.
2. Keep CLI `colorScheme`, `colorSchemes`, `colors` and their defaults/meaning completely unchanged. Neither the Web dropdown nor the Web theme CSS may rewrite them. For future other settings, use the existing config validation and read boundary, not a new competing preferences store.
3. The actual writable location is only **`config/user-config.jsonc`**, which is already intentionally Git-ignored and separate from shipped defaults. Never overwrite `default-config.jsonc`. If the user file is absent, default works without creating it; the first user-initiated change may create a minimal valid override containing `webTheme`. Missing `webTheme` inherits Classic. Startup and fresh browser tabs must read the persisted **effective** setting, not assume a previous in-memory selection.
4. Persisting Web Theme changes must not change existing CLI/Watch calculation, pricing, billing, source selection or account settings. Existing command-line invocations continue to accept the config with the additional recognized Web-only field.

## 3. Immediate write and live theme behavior

1. On each *actual selection change* in Settings, issue an authenticated same-origin write for **only** the chosen `webTheme` value. There is **no separate Save action** and no browser-local persistent preference; the file is the source of truth.
2. After a confirmed successful write, immediately apply the new theme to the **entire already-loaded page and shared shell** (including other routes, loading/progress, Watch, Accounts, tables, status colors, controls and Settings) without reload, new report, browser process restart or Web host restart. The dropdown reflects the effective saved choice, and navigating among tabs retains it.
3. On failed write (invalid config, read-only file, permission error, conflict, host offline, authorization expired or server shutdown), **do not indicate success**, do not silently claim persistence and do not leave the UI in a misleading saved state. Keep/revert to the last confirmed theme, show a concise useful error, and allow a later retry. Loading/saving state should be clear without blocking unrelated pages.
4. Subsequent browser reload/new tab/Web relaunch must start from the saved value. If the user manually edits the file externally, the next settings read/launch should reflect it; avoid destructive or perpetual polling solely for theme. Concurrent tabs should not silently overwrite unrelated config settings.
5. Avoid unnecessary first-paint wrong-theme flashes where reasonably feasible. A newly opened page should look like its configured theme from its early bootstrapping/loading state, not switch only after an entire analytics report finishes. Prefer lightweight, shared CSS variable/theme selection over re-rendering reports or duplicating styles in every component.

## 4. Bounded and safe configuration mutation

This is a **narrow, explicitly authorized exception** to Web Beta's previously read-only application behavior: only `webTheme` in Cost Guard's own user override file is writable. The data source, OpenCode, sessions, pricing catalog, accounts, user credentials, CLI/Watch state and arbitrary files remain read-only.

- Add a **fixed, minimal settings read/write API** (for example authenticated `GET/POST /api/settings/theme`) returning/accepting only the `webTheme` enum and a compact status. POST must reuse existing loopback-only Host/Origin checks, authenticated HttpOnly session, strict SameSite policy, CSRF token, request length/type limits, stopping/identity guards, and sanitized errors. Never expose the whole user configuration, raw paths or secrets to the browser. No generic file-system route, path parameter, arbitrary setting name/value, unbounded JSON or arbitrary file update.
- On write: read the existing actual user config, validate it and the proposed effective result with the **canonical config validation** before committing. **Preserve all unrelated keys, values, nested objects, comments, ordering and ideally formatting in JSONC**; do not serialize the merged effective defaults back over user overrides or erase custom settings. A bounded minimal edit of the single top-level field is preferred. If safe preservation is impossible for a particular malformed/unusual input, reject without modifying it and explain the issue; never silently rewrite the whole file.
- Use safe owned-path checks (no symlink/reparse traversal outside the expected config location), current-user permissions, bounded file size, atomic same-directory replace and appropriate cleanup of failed temporary files. Detect concurrent file changes before replacing instead of silently overwriting an external editor's modifications; keep implementation proportionate and local, not a new general transaction/synchronization framework.
- The server must continue operating when `user-config.jsonc` is updated through the approved setting. The existing source-change guard excludes this file. Do not cause a code-change shutdown, restart OpenCode or recreate the server to change CSS.
- Keep error/output privacy consistent with the existing Web HTTP and diagnostics boundaries. Neither config file contents nor private paths/credentials should appear in HTTP replies, browser storage, or logs.

## 5. Classic theme visual requirements

- **Dark independent of OS preference:** near-black/charcoal page background and unobtrusive dark panels, soft light-grey primary text, readable secondary grey, visible dividers. Set the correct dark color scheme for form controls, scrollbars and focus outlines.
- **CLI-inspired semantic accents:** selective bright lime/green (for example the existing CLI classic green `ansi256: 118`) for new/positive/running completion where meaningful; complementary cyan/information, yellow/amber promotions and warnings, red critical/error. Preserve the meaning and distinctness of statuses — do not color every text element lime or represent an error as success.
- Retain a **modern Web UI**, not a pixel-perfect console. Prefer existing system font and current table/card spacing; if any monospaced or tabular digits already carry structured pricing information, keep those focused uses.
- Sufficient text/interactive-state contrast, keyboard focus, hover/selected/disabled cues, color-independent status, and reduced-motion/touch accessibility across **all** views. Do not make new-model promotions or warning text harder to read against dark surfaces.
- **Web theme stays visually equivalent to today's Web CSS**, including light/dark following `prefers-color-scheme`; adding the theme switch should not subtly rewrite its typography, spacing or colors unless needed for correctness.

## Acceptance criteria

1. Navigation contains one **Settings** item at the far right on desktop and last/reachable on 360px/mobile. `#/settings` is directly accessible and has a sole Theme dropdown; no report acquisition or implicit source refresh occurs on entering it. It composes cleanly with FR000537's unified Models route.
2. With no `webTheme` override the app starts in **Classic** on both light- and dark-OS settings. Explicit `"web"` displays the existing adaptive Web theme; explicit `"classic"` displays the CLI-inspired dark palette. An unsupported setting produces the normal safe configuration error.
3. Changing the dropdown immediately **writes** the confirmed setting into `config/user-config.jsonc` and restyles the current browser **without reload or host restart**. Moving through all routes keeps the theme; a fresh tab, reload and later launch still use the saved theme. The underlying CLI scheme is unchanged.
4. Existing JSONC user config with comments, nested settings, custom CLI color palettes, account/source settings and unrelated unknown-but-preserved text survives switching **Classic → Web → Classic** with no loss or semantic rewrite. Missing file is created only by a user change. Invalid file, unwritable path, link/reparse hazard and concurrent modification result in safe non-destructive failure, with visible truthful feedback rather than false Saved.
5. Authenticated same-origin GET and CSRF-protected POST only, strict enum and body shape, no generic editable config surface or credentials leak. Unauthenticated/foreign-origin/unauthorized/malformed requests cannot mutate files. Web/Watch/CLI data remain read-only and no source-change shutdown is triggered by legitimate theme writes.
6. Real-browser visual checks on all major routes at 360px/laptop/wide sizes, both OS theme preferences, no misleading first-load flash, accessible navigation/select/focus, and correct warning/promotion/success contrast. Focused tests cover configuration parsing/default/round-trip, HTTP write authorization and errors, JSONC preservation, live UI switching and reload. State native/assistive-technology evidence honestly.

## Boundaries and priority

This FR authorizes **only the Web theme setting** and its minimal save/read mechanism, not a general configuration editor. Future Settings fields can reuse this page and safe infrastructure in separate FRs. No new frontend framework, CSS dependency, per-user browser-storage preference, CLI color scheme or model/report logic change.

**Permanent identity:** `000538`. **Queue priority:** `000200`, intentionally after FR000537 (`000100`) so the worker finishes the unified Models/navigation work first. This publication is backlog-only and does not modify product runtime files or bump product version.
