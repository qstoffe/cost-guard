# FR 000537 completion — unified Models and launch handoff

Product: v80.118, 2026-11-01. The original FR is preserved unchanged. Implementation and local verification are complete; the PR's final three-platform CI disposition must be recorded before merge.

## Delivered scope

- One canonical Models page and safe legacy bookmark replacement; four full-width columns, complete document-scrolling rows and no Models account cards, native-price column, catalog tabs, search/pager or superseded fading.
- Independent selectable/full-priced and candidate-local latest-version filters over one frozen supplemental catalog. Unknown comparison prices remain rows, unverified availability remains a warning, and global selectability is not subscription entitlement proof.
- Default exact Relative CCost descending, tier-vector comparison before secondary keys, missing-last dates/prices, stable locale-aware text ties, Shift mouse/keyboard and touch additive sorting with priority/ARIA indications.
- Existing Accounts acquisition/data, CLI/Watch ranking/valuation, bootstrap/security, detached host/tray, foreground and restart/coalescing remain owned by their existing components.
- Windows synchronous status console and macOS tty-only spinner through host/browser handoff, retained safe failures, no Terminal automation or browser-first-paint promise. Finder remains no-Terminal/no-Automation; no new unverified notification mechanism was added.
- Updated user guide, owner/code map, journal and focused deterministic/browser/native regression tools. No dependencies, release ZIP, tag or GitHub Release.

## Verification actually performed

- Final local Full after latest-main integration: **119 files, 1,453 tests, 1,452 passed, one local zsh/PTY skip, zero failures/errors, 66.0 s**. This includes the six focused Models tests and route-focus/heartbeat regressions. No tests were weakened or deselected.
- Working-tree validator: 11 checks PASS, four design-budget warnings, no failures. Hard caps are unchanged; README/history wording was compacted, not retired.
- Integrated Chromium: actual iframe viewports 360/1366/1920, each light/dark using explicit CSS theme tokens, 41 default / 42 selected-all-version rows. Four columns, no document horizontal overflow, body/region client height equals scroll height, document scroll reaches collapsed More information and matching promotion. Narrow horizontal pan, complete long name, default filters, ordinary/Shift-key/additive sorting, primary-only aria-sort and filter-preserved sort passed. No OS-theme, physical-device or screen-reader proof. An additional screenshot attempt could not capture a non-visible Review tab; earlier visual inspections are retained as historical observations, not new screenshots.
- Read-only real V2 Models probe: one owner/two streams, retained origin/advanced sequence; Normal 29 catalog/25 selectable/14 selected-latest rows with Accounts, all-models 29/29/16 without Accounts as designed; workers joined and shared OpenCode untouched. No model inference.
- Decision Delegate-approved additional Windows cold/warm console-buffer sequence: all four spinner glyphs and launch/stage text observed in 40/56 samples; normal launcher exit 0 at 6.063/2.496 s, authenticated detached host still ready after status exit, warm restart replaced the prior nonce, exact own host stopped afterward. Normal OS browser requests occurred, without browser automation. This is native console-buffer evidence, not physical Explorer/paint evidence. Earlier narrower timing also passed; timings are individual observations, not benchmarks.
- The broad real-source `--reports` attempt failed on date-report polling with ConnectionResetError/WinError10054. It is not PASS; deep-history cancellation was not reached and root cause was not established. Focused Models evidence and independent regression checks do not erase that limitation.

## Authorized exception and residual uncertainty

Initial PR CI [run 41351289503](https://github.com/qstoffe/cost-guard/actions/runs/41351289503): Windows regression/native/browser PASS; both macOS native and browser phases PASS, but regression FAIL in the new shell test because activity was read only after closing the PTY slave. Exit 0/4 and stage output assertions passed. The reader now waits boundedly and reads before the last slave close, and additionally requires two distinct spinner frames. This failure is not waived; a fresh three-platform run must pass.

**Decision Delegate** explicitly approved delivery without unavailable physical Windows Explorer and macOS Terminal/Finder cold/warm/restart demonstrations, conditional on the actual Windows console verification, final Full/validator and all three normal platform CI checks passing. The new macOS zsh/PTY test must actually execute successfully on macOS, not skip. No failing gate or confirmed regression is waived.

Local Windows has no macOS host/zsh; its zsh/PTY test skip is not a macOS PASS. Hosted native/API execution and fake-interpreter shell tests are not consumer desktop/Gatekeeper/default-browser acceptance. Physical input, accessibility, native macOS visual handoff and browser paint remain unverified. The OS launch-request boundary is intentional, not first-paint synchronization.

## Architecture and knowledge

Existing reports/application/Web boundaries remain: the optional immutable catalog uses the same acquired sample and full-catalog denominator; filtering/sorting is presentation-only. No new acquisition owner, supervisor or browser calculator. Updated `modules/web.md`, `modules/reports.md`, `modules/CODE_MAP.md`, `journal/web-overview.md` and `journal/windows-startup.md`; no separate whole-repository architecture audit was needed.
