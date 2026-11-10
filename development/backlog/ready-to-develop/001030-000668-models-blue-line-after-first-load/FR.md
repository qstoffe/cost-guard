# FR 000668 — Models: remove the stray blue horizontal line after first loading

**Owner-approved Ready Feature Request, 2026-11-10.** Permanent identity **000668**; Ready priority **001030**, following existing Ready work. **FR-only publication:** create this FR and atomically advance `development/backlog/identity-state.json` highWatermark **667 → 668** on `main`. Do not implement the UI fix, run product tests, change versions/releases or touch unrelated backlog entries in this publication.

## Owner-observed problem

When **Cost Guard Web** first opens on **Models** and loads the page for the first time, a **normal blue horizontal progress bar** is shown roughly in the middle of the content area. Once the page has finished loading, the owner observes **another very thin blue horizontal line (approximately 2 px, visual estimate)** near the **top of the page, immediately below the main navigation menu**. It resembles a leftover progress/loading line or a rendering artifact, rather than an intentional Models component.

After navigating to another page and back to Models, the thin blue line **disappears**. The owner wants the visual inconsistency investigated and fixed, without removing the useful centered loading progress bar.

**Expected:** On a clean first startup, display the one intended centered progress bar and its percentage/status only while the Models report is genuinely loading. After a usable Models result appears, the loading UI goes away cleanly and there is **no unexpected blue stripe under the navigation**. Returning to Models should look the same as the first completed display. Do not flash or keep a stray line at 100%, after asynchronous host/status updates, or during an ordinary cached re-entry.

### Source-backed diagnosis to verify (not a reproduced browser incident)

A particularly plausible cause is **page-focus styling, not an orphaned progress bar**:

1. `src/web/assets/index.html` defines `<main id="content" tabindex="-1">` just below the navigation and a centered initial `#result > .report-loading > progress`.
2. `src/web/assets/app.js::navigate()` on entry into Models executes `document.getElementById('content').focus({preventScroll: true})` followed by `window.scrollTo(0, 0)` when the route state changes, **including first startup**. This was added to preserve top-of-page navigation semantics.
3. `src/web/assets/app.css` globally applies `:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }`. Thus a programmatically focused, full-width `main` may paint a **3 px blue outline at its top edge**, positioned immediately below the main menu. Browser focus heuristics can differ on automatic first startup versus click-triggered re-entry, which is consistent with the owner's sequence.
4. Conversely, `src/web/assets/app.js::show()` uses `ReportLoading.show()` while waiting, and the normal completed Models `ReportView.render()` begins with `parent.replaceChildren()`, which should remove the actual centered progress element from `#result`. This makes a leftover loading `<progress>` **less likely**, but not impossible without a real DOM/visual reproduction.

**First investigate actual evidence rather than assuming the cause.** Capture DOM/computed style and screen geometry at these transitions: initial Models load, loader visible, first successful paint, later status/SSE updates, navigate to another route, and return to Models. In particular inspect `document.activeElement`, `#content.matches(':focus-visible')`, computed `outline-style/width/color/offset`, `#content` bounding rectangle, all visible `progress` elements and the suspicious line's screen coordinates. Check whether a native focus outline, loading/progress artifact, scrollbar or another element is actually painted; state clearly which explanation was confirmed.

## Requirements and non-goals

1. **Resolve the verified cause with a small, precise fix**. If the blue stripe is an incidental outline on the programmatically focused page container, preserve page focus/scroll handling without drawing the unwanted huge full-width outline on automatic startup. Do not globally disable `:focus-visible` or break clear keyboard focus indicators on interactive elements.
2. **Preserve accessible navigation:** keyboard-only users and the **Skip to report** control must still have a meaningful, discoverable focus target and appropriate visible focus semantics; do not silently discard focus or cause unexpected scroll. Distinguish incidental programmatic page-container focus from intentional keyboard navigation. Preserve FR000658's new-route Models top-of-page policy and same-route scroll/interaction behavior.
3. **Loading remains correct:** only the real centered `ReportLoading.View` bar belongs to Models first-load waiting/progress. Keep determinate percentage and text, valid error/wait/recovery behavior, refresh-pricing status, existing layout, and no fake progress or extra load. A completed first result removes any obsolete loading element/visual; no residual `progress` or focus line should remain as a loading affordance.
4. **No route-dependent visual leftovers:** opening Models through fresh bootstrap/deep link or ordinary navigation produces consistent post-load visuals. Avoid relying on visiting another route to clean a CSS state, cached view, animation, focus owner or DOM node. Source/update/health events must not resurrect a stale line.
5. **Scope restraint:** UI/focus/progress lifecycle only. No changes to model valuation, prices, sampling, data dispatch, source performance, backend retries, actual report completion semantics or unrelated page styling. Keep Classic/Web light/dark and sensible narrow/wide layouts.

## Acceptance criteria and verification at implementation time

- With a **controlled slow first Models load**, assert the intended centered determinate progress component is visible and positioned within the content region. On completing an authenticated valid Normal result, the Models table appears, the centered bar is removed/hidden and **no thin blue stripe appears directly below the navigation**; check actual computed boxes/styles and screenshots, not only element counts.
- Reproduce the focus scenario by comparing initial script/programmatic Models entry, click/touch route entry and keyboard route entry. Specifically assert the `main#content` focused/`:focus-visible` state cannot create an unintended page-width outline while buttons, links, controls and the Skip-to-report interaction retain correct visible keyboard focus and navigation accessibility. Do not solve by setting a blanket `outline: none` on all focusable elements.
- Test direct `/#/models` launch, first completed report, switch to Watch or Sessions then back, cached Models re-entry, same-route filters/sorts, pricing Refresh, delayed source/health updates, and an interrupted/error→Retry path. End-of-load presentation must be visually consistent without a second loading track or stale line.
- Extend the existing real-browser Models loading/navigation and Web layout regression probes (e.g. `development/tests/integration/probe_models_startup.cjs`, relevant report-loading/browser tests, plus shared routing/focus probe as appropriate). Cover Classic/Web light/dark, at least narrow and desktop widths, and mouse/keyboard navigation, without paid model requests. Run normal relevant repository validations **when implementing**.

**End state:** The centered loading bar works as intended; the completed Models page has no anomalous thin blue rule under the navigation, including on the very first startup, and keyboard accessibility remains intact.
