# FR 000540 completion — 2026-11-02

## Delivered scope

- Removed the Models mode button, additive state/event and unused pressed-button CSS. Only the two filter checkboxes remain. Ordinary click/touch replaces sorting; Shift+click/Enter/Space retains ordered keys, exact tier sorting, priorities and primary-only ARIA.
- Windows Beta prints one `Starting CostGuard web...` label and updates one spinner cell at a throttled 120ms cadence. Discovery and startup share it; internal stages drain without printing. No `Write-Progress` panel, whole-line repaint, screen clear or success transcript remains. Redirected/noninteractive output is plain, and finally cleanup precedes failures/exit.
- Existing discovery bounds, private diagnostics, failure status/dialog fallback and detached/tray lifecycle are retained. No macOS, CLI/Watch, report-acquisition, valuation, authentication or host-lifecycle implementation changed.
- Product v80.121, README, version history, Web documentation and architecture owner facts updated. Older history prose was condensed to retain the existing hard cap; no cap raised and no release ZIP/tag/publication generated.

## Actual verification

- Local `py -3 development/tools/run_tests.py --suite full`: **121 files, zero failures**, 54.6s. Includes CLI/Watch, foreground, macOS synthetic contracts and new PowerShell redirected checks. The Windows-only skip of macOS zsh execution is not native macOS PASS.
- `py -3 development/tools/validate_package.py --working-tree`: zero failures, 11 passes, four existing design warnings (README and three unchanged Python modules).
- Real PowerShell redirected success, startup/browser failures, missing Python and launcher exception: one plain label, no stage/control/secret-bearing output, truthful status and private allowlisted failure records. Existing missing/unsupported/multiple-interpreter and stalled-discovery regressions pass.
- Integrated Chromium, frozen canonical Models fixture: **19 checks at 1366px/light and 20 at 360px/dark**. Two filters/no additive state, ordinary replacement, Shift mouse/Space/Enter, tertiary direction toggle, primary-only ARIA, retained filter sorting, exact tiers/missing rows, document scrolling and narrow overflow passed. Synthetic dispatched events are not physical touch or assistive-technology acceptance.
- Approval-only `probe_windows_activity.py`: delayed discovery plus streamed startup, **169 success / 174 browser-failure animated samples**, all four glyphs, unchanged non-spinner buffer cells/attributes, preserved existing output and cleanup before error/exit. A first probe overconstrained the transient cursor position; it now accounts for non-atomic buffer reads and the cursor moving inside/just after that one cell. Final probe passed.
- Actual Windows `.cmd` cold/warm launches: **41 / 62 samples**, all four glyphs, stable other cells/attributes, no stage accumulation; natural exit 0 at **1.644 / 2.229 seconds**, detached authenticated host still ready and warm nonce changed. Exact owned host stopped afterward.
- Existing targeted native timing/lifecycle probes passed: cold/warm success, detached survival/no inherited console, Open, concurrent coalescing, deliberate restart, failed browser keeping the host and owned source-change cleanup. No shared OpenCode stop.
- PR platform CI is reported by the PR's actual checks, not inferred from these local results.

## Decision and remaining limits

Decision Delegate authorized only task-scoped native console/tray, owned buffer capture and registered-browser requests for delayed fixtures and targeted startup/lifecycle probes. This was **delegate authorization, not a fabricated user approval**; no full opt-in native bundle or unrelated desktop inspection was performed.

Direct native visual flicker/color observation, physical Explorer/touch/keyboard/accessibility acceptance and browser first paint were **not performed/verified**. Stable console-buffer characters/attributes are not visual proof; the FR explicitly permits this distinction. No failing/unrun test is called PASS, and no product-requirement or required-test waiver was used. Hosted macOS/native checks, if run by normal CI, remain distinct from consumer desktop acceptance.

Architecture boundaries are unchanged; current owner facts and `development/journal/windows-startup.md` record the change. No further architecture split or unrelated journal update is needed. Optional scratch cleanup is skipped; one failed probe's locked temporary fixture was retained rather than force-deleted.
