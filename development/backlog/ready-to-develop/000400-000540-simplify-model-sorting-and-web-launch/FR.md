# FR 000540 — Simplify Web Beta Models sorting and eliminate Windows launch-console flicker

## Owner request and inspected baseline (2026-11-01)

Make two small Web Beta usability refinements: remove the **Add sort keys** toggle from Models while retaining modifier-key multi-column sorting, and make the brief **Windows Web startup console** quiet, visually steady, and nearly text-free. A single `Starting CostGuard web...` label with a small spinner is sufficient until the browser handoff.

FR 000537 introduced both the unified Models sorting and the visible OS launcher handoff. This FR deliberately revises **only** its optional touch/additive toggle and launch-console presentation, not its underlying sorting, host readiness, or browser handoff contracts.

Code observations:
- `src/web/assets/render.js::overviewModels` creates an `Add sort keys` button, `choice.additive` mode, and tooltip text. Header activation already supports `Shift+click` and `Shift+Enter/Space` independently of that mode; ordinary clicks replace the sort. `development/tests/integration/web_models.cjs` presently exercises the toggle.
- `windows/Beta/Cost-Guard-Web.cmd` prints `Launching web...` and waits for `src/web/windows_launch.ps1`. That script prints several `Write-Host` stage lines, repeatedly calls PowerShell `Write-Progress` (during Python discovery and streamed stages), **and** draws a separate text spinner. The owner's observed blue panel and repeated redraw/flicker are consistent with this competing progress rendering; the exact visual cause has not been independently reproduced.
- `src/web/windows_launch.py` / `src/web/startup.py` already supply sanitized allowlisted stage and failure messages. The successful endpoint remains verified detached-host readiness plus a successful OS browser-open request, **not** guaranteed browser first paint.

## 1. Remove the extra Models sort control

1. Remove the visible **Add sort keys** button completely, including its pressed state, persistent-in-page additive-mode state, toggle event, and obsolete references in tooltips, help and documentation. Do not replace it with another dedicated sort-mode control.
2. Keep the two existing Models filter checkboxes in their current role and simplify the control row's spacing. Preserve **ordinary header click/tap = single-column sort**, including its ascending/descending toggle, and **Shift+click = add/toggle a secondary/tertiary key** without discarding earlier keys. Preserve the current Shift+keyboard activation (Enter/Space).
3. Preserve default **Relative CCost descending**, current arrow and priority numbers, primary-only `aria-sort`, descriptive accessible header names, stable/tier-aware numeric sorting, missing-last behavior, and filters retaining the selected sort. Update the header hint to mention **Shift**, not the deleted button.
4. Removing the touch-only additive mode is an **intentional owner-approved simplification**: ordinary touch still sorts one column, but there is no requirement to invent a replacement multi-sort control for devices without Shift. No new setting, server endpoint, table dependency, or acquisition.

## 2. One non-flickering Windows Beta Web launch line

1. In the interactive Windows Beta `.cmd`/PowerShell launch path, display **one fixed, short line**, e.g. `Starting CostGuard web... |`. Print the label once; during startup update **only the spinner character in place** at a modest rate. The rest of the line, console background, cursor position outside that cell, and existing output must not be continuously repainted or scrolled. Do not redraw an entire console frame or clear the screen/scrollback for animation.
2. Eliminate PowerShell's **`Write-Progress` rendered panel** from this launch path, including its indeterminate/blue-background progress overlay, and suppress redundant `Write-Host` status/stage lines on **successful** launches. Do not introduce any other colored-background box, splash panel, multi-line progress table, fake percentage, or verbose startup transcript. The existing allowlisted Python stage stream may still drive readiness/activity internally; it need not be printed.
3. Show the fixed line and animate continuously from initial invocation through bounded Python discovery, validation/native preflight, instance arbitration/restart as applicable, verified host readiness and OS browser-opening request. Stop and clean up the spinner on all exits. After successful handoff, let the console close naturally; do **not** wait for browser painting or keep the console open just to display success.
4. For **redirected/noninteractive output**, avoid carriage-return/backspace/ANSI animation, PowerShell progress graphics and other terminal control sequences; emit minimal readable, deterministic text instead. No added background colors or automatic terminal-theme changes. Handle normal console widths without wrapped/trailing stale glyphs or accumulated output.
5. On missing/unsupported Python, timeout, configuration/preflight failure, browser-open failure or any launcher exception, **stop animation before presenting the error**, and retain concise sanitized actionable feedback, the existing private diagnostic record/path, failure exit code and supported Windows dialog/interactive fallback. Never turn failure into a silent disappearing window or print raw paths, tokens, bootstrap URLs, credentials or exception internals.
6. Keep the Windows status process **short-lived** and the web host **detached/tray-owned**. Preserve verified-instance safety, coalesced launches, deliberate restarts, port and browser-auth handling, source-change protections and the readiness-versus-browser-paint distinction. Do not use an extra worker/service, kill unrelated processes, or add a new dependency merely for spinner animation.

**Scope boundary:** This is the transient **Windows Beta Web launcher**, not the long-running CLI/Watch console, developer `--foreground` mode, or the Web page's own loading indicator. The macOS `.command`/Finder handoff and all stable launchers must not regress; cross-platform spinner redesign is not required.

## Affected areas and verification

Likely product paths: `src/web/assets/render.js`, optionally `src/web/assets/app.css`; `windows/Beta/Cost-Guard-Web.cmd`, `src/web/windows_launch.ps1` (and minimal launcher plumbing only if necessary). Update relevant documentation including `docs/web-beta.md` and `development/architecture/modules/web.md` where it describes the removed toggle or stage-rich Windows console.

Use or extend `development/tests/integration/web_models.cjs`, `development/tests/integration/web_models_browser.js`, `development/tests/test_windows_web.py` and focused Windows native launch probes. Do not alter valuation, report acquisition, config defaults, pricing, host lifecycle or source security for a presentation-only request.

## Acceptance criteria

1. Models shows **only the two intended filter checkboxes**, with no `Add sort keys` button or trace of a hidden additive mode. Ordinary mouse/touch sorting replaces earlier keys; Shift+mouse and Shift+keyboard retain ordered multi-sort (including direction flips, priority arrows/numbers and correct ARIA). Existing exact ratios, missing values, defaults and filter behavior remain unchanged. Focused DOM and real-browser checks cover this.
2. On Windows interactive cold **and** warm Web Beta launch, the console shows one stable `Starting CostGuard web...` line with changing spinner glyph, **no PowerShell colored progress rectangle**, no stage-line accumulation and no full-frame redraw/flicker. Exercise a realistically delayed startup, not only an instant-success mock. Console-buffer/PTY evidence can check one-row updates; visual flicker/color claims need direct native observation when available, and otherwise must be marked unverified rather than claimed PASS.
3. On successful Windows browser-open handoff, the status console exits normally, returning success, while the authenticated detached/tray Web host remains alive. Concurrent and intentional-restart behavior, default-browser request and absence of browser-first-paint promise remain intact.
4. Redirected output is clean plain text with no animation escapes. Unsupported/missing Python, stalled discovery, startup/readiness failure and browser-open failure retain bounded behavior, truthful nonzero status, diagnostic record and actionable user-visible feedback; no secret-bearing output.
5. Existing CLI/Watch, `--foreground`, macOS launch paths and Web report behavior pass relevant regressions. This FR alone does not authorize a release/promotion or unrelated refactor.
