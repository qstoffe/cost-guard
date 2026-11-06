# FR 000597 — Web Settings: compact two-column layout and tooltip help for setting choices

## Owner request and scope

**Owner-approved executable Ready Feature Request, 2026-11-05.** Give the **Settings** page in Cost Guard **Web Beta** a substantial **visual/interaction overhaul**. The current layout is cluttered: an unnecessary **Settings** route heading sits above a framed **Web settings** section, and every field stacks a label, tall select control and a paragraph of explanatory text on separate vertical lines. The result is poorly aligned, excessively tall and inconsistent with the newly streamlined Models, Watch, Sessions and Accounts pages.

Replace it with a **clean, table-like two-column layout** — setting name on the left, compact value selector aligned on the right. Explanations belong in **contextual tooltips on the setting label, the selected value and, most importantly, on each choice while the dropdown is open**, not in persistent prose blocks between rows.

**Queue/coordination (owner clarification 2026-11-06):** this remains Ready priority **000190**, after FR000602 (000185) and reactivated FR000591 (000187). Reuse the shipped FR000590 tooltip behavior. **FR000591 is not a hard prerequisite:** implement this layout for whichever allowlisted Settings API fields actually exist in the merged default when FR000597 starts. If FR000591 has already delivered its separate Mini Watch position/size choices, display and explain them; otherwise preserve the existing combined Mini Watch placement field and its functionality. Never create invented fields, silently implement FR000591 within FR000597, or put FR000597 On Hold just because FR000591 is incomplete. The layout must remain extensible when new fields arrive.

This is **FR-only publication**. Do not implement product source, tests, docs, settings migrations or version/release changes while authoring the request.

## 1. Remove unnecessary headings, panels and vertical explanatory prose

- Hide/remove the **route-level “Settings” heading** from the shared page toolbar on `/#/settings`. Keep main navigation, document title and an accessible page name/landmark; don't globally remove page headings on unrelated routes.
- Remove the inner bordered/shadowed `section.web-settings` **card/frame** and its **“Web settings”** heading. No card-within-card effect, separate panel title, decorative frame or oversized padding. The settings rows should sit directly in the page's normal main content.
- Remove the permanently visible introduction **“Changes save immediately and apply only to Web.”** and the per-setting `p.help-copy` explanatory paragraphs that currently interrupt alignment. Keep exact relevant meaning in concise tooltips and accessible descriptions; the user should not need to read dense paragraphs to find the controls.
- Retain a **small, unobtrusive, accessible save/loading/error status** near the setting being changed or otherwise in a predictable place. Errors, failed saves and access/authorization problems must remain visible and actionable; don't remove them just because the layout is visually quiet.

## 2. A tidy two-column Setting / Value arrangement

Implement **one consistent two-column grid or semantic table-like layout**, resembling:

```text
Setting                 Value
---------------------------------------------
Theme                   [Default (Classic)  ▾]
CCost display           [Default (Credits)  ▾]
Mini Watch placement    [Default (Remember last) ▾]
Quota display           [Default (Used)     ▾]
```

The names/choices above show the four current fields as an example. If FR000591 has already delivered, render **Mini Watch position** and **Mini Watch size (Default: Fit on open)** as two corresponding rows instead of Mini Watch placement. Use the actual Settings API choices/defaults at implementation time, not a required future field inventory.

- **One setting per compact row.** Left column: clear setting label, aligned consistently. Right column: one select/combobox with the current **choice**. No description row below, no unaligned stacks, no extra “Web settings” heading.
- Optional small **“Setting” / “Value”** column headings are welcome if they aid scanability, but do not create an oversized header, boxed report table, sorting, filtering or row pagination.
- All value controls share a **consistent horizontal start position and sensible width**, large enough for actual choices such as `Default (Remember last)` without clipping or forcing the setting names to wrap unnecessarily. The right column shouldn't float unevenly per row; align row baselines/centers.
- Make the dropdowns **noticeably slimmer vertically** than today's global `min-height: 2.65rem; padding: .5rem .8rem` form controls: compact padding, text size and control height approximately **32–36 CSS px** on desktop, consistent across rows, while preserving usable focus outline, keyboard navigation and touch accessibility (reasonable touch target sizes or responsive adjustment on touch devices).
- Give rows modest, consistent spacing/separators only as useful; no thick borders, heavy shadows or broad hover backgrounds that turn the whole row into a tooltip hitbox. A label's tooltips/cursor should activate over the **actual label**, not empty space in its cell.
- On narrow/mobile/zoomed layouts, keep the page readable. Allow an accessible compact stacked **label+value row** only when two columns truly cannot fit, or adjust grid tracks without causing clipped values/horizontal page overflow. This is a responsive fallback, not a return to paragraph-heavy settings.

## 3. Context help on each setting label and selected value

- **Hover/focus the setting label** (e.g. `Theme`, `CCost display`, and the actual Mini Watch field or fields) to get a **short explanation of what that setting controls**. Rework existing explanatory strings into concise, human-friendly help with only relevant detail. No standalone tooltip question-mark button or dotted underline; use shared `cursor: help` on passive labels.
- **Hover/focus the current selector/value** to get an explanation of **the currently selected choice** (e.g. `Classic` vs `Web`, `Credits` vs `USD`, `Remember last` vs `Standard position`, `Used` vs `Remaining`; if FR000591's size field exists, also `Fit on open` vs `Remember last size`); don't just repeat the option text. Provide genuinely useful consequences, scope and limits.
- **Default (…):** distinguish a **symbolic inherited Default selection** from explicitly picking the presently equivalent concrete value. E.g. `Default (Classic)` means “follow whatever the shipped default is”, not “pin Classic forever”. Update descriptions when the actual shipped default changes; preserve the user's explicit-versus-default choice.
- The label and selection are separate help targets with **different scoped information**, not one giant tooltip on the entire row. Keep association between each visible label and form field (`label for`, accessible name), and avoid taking ordinary control focus or selection away to show a popup.
- Reuse the **existing `ContextHelp`** system, including FR000590's common ~600ms pointer hover delay and immediate keyboard/touch help where appropriate. Keep the usual pointer cursor on truly interactive controls; the selected-value explanation must not require turning a real select into a passive fake control.

## 4. Explain **every individual choice while its dropdown is open**

**This is a key requested enhancement.** Opening Theme, CCost display, the actual Mini Watch placement/position/size controls, or Quota display should allow the user to inspect **each available item**, not only the currently selected one:

- When the pointer **rests over an option in the open list**, show a concise explanation **adjacent to the dropdown/popup** of that option's effect. Examples: hovering **Web** explains system-following light/dark theme; hovering **USD** explains cost display units; hovering **Remaining** explains the native quota orientation; if the FR000591 size control exists, hovering **Fit on open** explains the two-prompt opening height and Earlier click-resize behavior (not automatic Live resizing). **No selection/save takes place merely from hovering**, and the option description changes as the actual hovered option changes.
- The focused/active option via **Arrow Up/Down and other standard keyboard navigation** must expose the same description accessibly, **before commitment**. Touch users must have a usable way to inspect the option description (e.g. a short detail line in the open picker or explicit focus state) without first committing a preference. Escape cancels the open menu without saving or stealing unrelated focus.
- Avoid opening a separate broad tooltip that obscures the option list, pushes the select out of view, jumps around or causes a hover/focus loop. Place help next to/beside the popup when the browser allows, with bounded width and viewport clamping; keep it readable in Classic/Web light/dark and narrow/zoomed windows. Do not add persistent extra explanation blocks under each setting when the menu is closed.
- **Technical reality:** standard OS-rendered HTML `<select><option>` dropdown popups do not consistently expose per-option mouse-hover/focus events or permit arbitrary adjacent tooltip painting. Test actual supported Chromium/Edge. Prefer a **feature-detected customizable native `<select>`** (`appearance: base-select`, `::picker(select)`, supported in modern Chromium) with per-option noninteractive help/presentation if reliable; otherwise use a small **well-tested, accessible custom combobox/listbox** only if needed for the required UX. **Do not claim native per-option hover works by attaching `title` to `<option>` without real browser proof.**
- **Compatibility:** where a browser lacks reliable option-level enhancement, preserve a fully functional **native select** with a compact, accessible alternative such as a description preview for the **focused/selected option**, and explicitly document the limitation rather than silently dropping the help or breaking normal selection. Prefer progressive enhancement over forcing a brittle custom widget everywhere.
- If a custom picker is needed, follow standard combobox/listbox semantics, proper active-descendant/selected state, Tab/Enter/Space/Escape/arrow/typeahead behavior, touch/pointer support, focus restoration, high zoom and screen reader parity. It is **not acceptable** to sacrifice native accessibility for a prettier dropdown or to add an external UI framework for five small settings.
- All choices must remain sourced from the **same allowlisted Settings API and actual shipped defaults**, not manually invented browser-only options. Avoid ever showing an obsolete option description following a settings update or default change.

## 5. Preserve all existing Settings behavior exactly

- Each choice continues to **save immediately on explicit committed selection** through the existing authenticated, CSRF-protected `/api/settings/<field>` API and atomic JSONC write path. Simply opening a popup, hovering an option or keyboard previewing a choice must **not save**.
- Retain the **last confirmed choice** and rollback behavior on write failure; pending saves disable/suppress conflicts appropriately. Status must be short, visible and accessible while not shifting the whole settings grid or masking tooltips.
- Retain app-specific current behavior for theme, Credits/USD, Used/Remaining and whichever Mini Watch placement/position/size fields are implemented. Do not imply hands-free Live Auto-height, and preserve next-opening semantics. Display actual choice label and **Default (concrete shipped default)** accurately after success, after reload and after external config edits discovered on read.
- **No new settings, preferences, persistence layer, telemetry, network calls, profile storage or forced refresh of Models/Watch/Accounts** beyond the earlier approved fields. Do not break existing browser-session security, no JS model inference.
- Preserve related **Settings keyboard access and navigation** while another tooltip is visible; timely tooltip dismissal on value selection/change, route exit, Escape, outside pointer movement and hidden page, including controls that rerender or are temporarily disabled.

## 6. Likely owners and acceptance

Inspect the actual merged source when selected. FR000591 is an independent backlog task, not a mandatory implementation dependency:
`src/web/assets/settings.js::View` (currently appends one `section`, heading, intro, per-field `label` wrapping `select` and `p.help-copy`),
`src/web/assets/app.css` (shared global select height/padding and `.web-settings` styles), `src/web/assets/app.js` / `index.html` (Settings toolbar heading and route-specific shell visibility), `src/web/assets/help.js` shared tooltips, current Web Settings documentation and `development/architecture/modules/web-help.md`. Reuse existing `src/web/settings.py`, `src/config.py` and `webSettingsChoices`/`webSettingsDefaults` contracts rather than rewriting storage. Update focused JS/DOM/browser interaction tests only as needed. Keep unrelated application views intact.

**Acceptance criteria:**

1. At `/#/settings`, the page displays **neither the visible generic “Settings” toolbar heading nor a framed “Web settings” box/header**. No introductory or per-setting body-text paragraphs interrupt the row layout; correct route/accessibility names remain available.
2. The healthy page looks like a **compact two-column Setting / Value grid**. Each actual setting gets exactly one aligned, single-line row; labels form a consistent left track and dropdowns align in a consistent right track. Dropdown height is visibly reduced on desktop, while narrow/touch/zoom layouts remain usable.
3. Hover/focus `Theme` etc. gives brief *setting-level* help; hover/focus the selected value provides that *choice's* explanation. Tooltips share FR000590's cursor/delay/lifecycle, without standalone `?`, dotted underlines, oversized hit areas or help-content walls.
4. In **supported real Chrome/Edge**, opening a picker and hovering **every different option** reliably displays **that option's own explanation alongside the picker** without choosing/saving it. Keyboard navigation and touch reveal equivalent info. Option help does not obscure the list or force focus changes. In browsers without support, a working native-select plus accessible choice explanation fallback is present and the known limitation is recorded.
5. Default/explicit semantics and actual existing option choices remain correct. If FR000591 is implemented, test both distinct Mini Watch settings with `Fit on open` terminology; otherwise verify the original placement field and do not require unshipped options. Values, effective defaults, descriptions and current save behavior are consistent across reloads, theme/unit toggles and failed settings reads/writes. No save from merely previewing or hovering an option; exactly one save on actual change.
6. Verify Classic, Web light/dark, browser zoom, narrow desktop, mobile/touch, keyboard/Tab/arrow/Escape/Enter/Space, screen-reader association, real picker hover, tooltip clipping, repeated save/revert and route navigation. Automated deterministic tests plus real browser option-popup interaction tests differentiate supported vs fallback behavior; no invented native-option hover PASS.
7. Update current Settings docs and tooltip guidance so no stale `Web settings` panel or permanently visible explanations are claimed; no changes to unrelated CLI/application settings, historical FRs, storage security or release workflows apart from normal later delivery.

**Publication boundary:** create this approved Ready FR and increment identity watermark only. Product implementation and verification happen later under normal backlog execution.
