# FR 000440 — Modern, polished Web Beta design system and navigation

## Goal

The delivered functional Beta currently has a plain, dense, dated visual treatment. The owner wants a distinctly **modern/high-tech but professional** site, not a terminal screenshot: cohesive spacing and typography, attractive native-feeling tables, subtly rounded controls, restrained surface depth/gradients, smooth hover/focus/active transitions and clear status hierarchy. Improve the global CSS/components without sacrificing accessibility, density or CLI information parity.

## Required behavior

- Build a light/dark, responsive visual system with deliberate surface hierarchy, color tokens, spacing scale, comfortable information density, consistent rounded corners on buttons/inputs/panels, modern typography, restrained shadows and hover/focus/active transitions. Avoid gaudy effects, gratuitous movement and busy decorative text; respect `prefers-reduced-motion`, keyboard focus, contrast and mobile narrow widths.
- Improve shared navigation/headers and scrolling tables: clean active-state tabs, prominent useful action/progress areas, readable sticky headings, stable column alignment, legible numeric columns, predictable per-table sort/filter/pagination controls, overflow handling and empty/loading/error states. Decoration must never obscure numbers, statuses or selectable/copyable content.
- Rename the global **Live** navigation label to **Watch**, matching the existing CLI mode and owner's vocabulary; preserve `/#/live` deep links as a backwards-compatible alias or redirect to the canonical Watch view and preserve users' Back/Forward behavior. Keep Overview, Sessions, Models, Accounts; retain discoverable Reports/Token Mix and Snapshot/Live *session-detail mode* distinctions without conflating global Watch with one session's Live mode.
- Use CLI's semantic color/emphasis roles as a design input: warn/error, running, source stale/offline, provisional/unknown, price thresholds, model highlights and subtotals. The Web theme may choose different hues; preserve meaning beyond color alone with badges/text/icons accessible to screen readers.
- Do not turn the Overview into a prose dashboard merely to fill space. Information architecture should prioritize tables and concise labels; contextual explanations can be folded into unobtrusive help/details.
- No CDN, Node/frontend build, third-party analytics, account editing, auto-login or new product installation dependency.

## Acceptance

- Consistent polished appearance across all existing routes and in both light/dark modes, including 360px/narrow screens and wide desktop layouts, with useful keyboard/tab order, visible focus, safe scroll/select and reduced-motion behavior.
- Before/after actual-browser screenshots or an equivalent owner-review visual artifact of Overview, Watch, Sessions, Models and Accounts are recorded. Automated DOM checks alone must not be called visual proof. Match field/row parity in FR000430 and do not hide information to make a screenshot pretty.
- Navigation naming and URL compatibility are tested (including deep links, reload and Back/Forward). The existing independent CLI, security/session bootstrap and report engine are unchanged.

Relevant owners: `src/web/assets/app.css`, `index.html`, `app.js`, `reports.js`, `render.js`, tests for Web views. May be implemented alongside parity foundation FR000430.