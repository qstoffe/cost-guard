# FR 000589 — Web tooltips: remove dotted underlines and restrict header help/hover to text

## Owner request

**Owner-approved Ready feature request, 2026-11-05.** Follow up on the completed tooltip overhaul **FR000582** and consolidation/lifecycle fixes **FR000587**. The remaining tooltip styling and table-header hover behavior still need two concrete UX refinements. **Keep existing useful help and the standalone question-mark (`?`) cues for now.** Do not revert the new shared tooltip system or its rapid-exit bug fixes.

This is **FR authoring only**. Do not implement source code, tests, documentation or product/release changes while publishing this request.

## 1. Remove dotted/dashed underline decoration on all tooltip targets

- Remove the **dotted/dashed underline** (including `text-decoration: underline dotted`, dotted/dashed bottom borders and equivalent rules) from **every Web Beta tooltip/help trigger**: table headings, other headings/labels, `?` help cues and any other affected surfaces in the main app and the separate **Mini Watch Document PiP**.
- The owner finds this treatment visually distracting. A label may still have help and a help cursor, but **no dotted/dashed underline** should mark it as tooltip-enabled.
- Audit shared `src/web/assets/app.css` / `mini.css`, markup produced by `help.js`, and view-specific selectors; do not simply hide one instance while another style still adds it. Update the current `development/architecture/modules/web-help.md` tooltip guideline, which presently recommends a dotted underline, and current user documentation as applicable.
- Do **not** remove genuine normal link styling, selection indications, semantic warnings or other unrelated underlining/borders. Existing standalone `?` symbols remain until a separate decision.

## 2. Header tooltips, help cursor and highlight only when actually over header *text*

The owner observes that merely hovering **unused space inside a column header** currently activates a tooltip, changes the cursor to the question-mark/help cursor, highlights the inner header region/column, and can highlight the heading text. This feels wrong: **only the actual visible header label text** should produce those help/hover effects.

- For relevant tables in **full Web Beta and Mini Watch**, attach the tooltip hover target to a **text-sized inline heading/label element**, not the entire `th`, full-width button/container, padding area, whitespace or row/column region.
- When the mouse is **directly over the visible heading text**, its tooltip may appear, the cursor becomes **`help`**, and the **heading text itself** may receive the intended highlight.
- When the pointer is over **empty/dead space elsewhere in the same column header**, no tooltip is activated, **no `help` cursor** is shown, the heading text must not become highlighted, and there must be **no hover highlight of the inner header/background/whole column** attributable to header help.
- Moving from the text into dead space must end pointer-owned help with the shared bounded exit grace, just as moving outside the trigger does; moving into the tooltip panel intentionally still follows the existing readable-pointer-transfer rule. Re-entering text triggers help again only via genuine new hover.
- Keep accessible keyboard focus/help, Escape, touch/tap, ARIA descriptions, tooltip viewport behavior and the hover/focus/pinned-origin ownership implemented by FR000587. Don't turn a label into a larger invisible hitbox via CSS stretching or pseudo-elements. Preserve relevant **sorting, navigation and click behavior** where those are separate actions; scope this FR to their hover/help styling and hit area without silently breaking functional controls.
- Apply the same principle to any other header-like help targets where container-wide hit detection yields the same problem, even if the underlying DOM structure differs. Do not change unrelated hover styling for regular data rows unless it is incorrectly coupled to the header help state.

## Acceptance criteria

1. **No tooltip-triggered dotted/dashed underline** remains anywhere in the main Web app or Mini Watch (all themes), including heading labels and standalone `?` cues. The `?` symbols themselves and useful help content remain.
2. In full Watch tables and both Mini tables, moving the cursor across **left/right padding and other dead space of a header** does not open help, show a question-mark cursor, highlight label text or highlight the header cell/column. Hovering the actual label text produces the existing tooltip and help cursor and **text-only** hover highlight.
3. Moving text → adjacent dead space, text → tooltip panel, text → outside window and fast boundary exit all dismiss or retain help according to the **correct shared hover lifecycle**; no stuck popovers, focus-origin conflation, flicker or delayed resurrection. A tooltip may not appear merely because the pointer stayed somewhere in the `th`.
4. Keyboard Tab/focus, screen-reader descriptions, Escape and touch/tap still expose the same help, with suitable focus indications **without reintroducing dotted underlines**. Sort actions, selection/copy, sticky headers and other genuine controls behave as before.
5. Test representative full Web views (especially Watch Running/Earlier), Mini Running/Earlier, other tooltip-bearing labels and `?` cues in Classic and Web light/dark, narrow/zoomed layouts, scrolling and real PiP browser pointer geometry. Update focused JS/DOM and browser regression assertions to verify **text-only hit testing**, cursor and computed style.

**Publication boundary:** create this separate Ready FR and advance the identity watermark; no implementation or release change in this session.
