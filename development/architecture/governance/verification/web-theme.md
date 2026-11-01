# Web Settings / theme verification

Historical FR 000538 evidence. FR 000539 moves the preference to `webSettings.theme`
and adds persisted Web CCost; see [current verification](web-settings.md).

FR 000538; Windows workstation, Python 3.14; 2026-11-01; v80.119.

## Delivered scope and deterministic checks

The far-right/last Settings route contains only Theme. Classic defaults to dark
independently of OS preference; Web retains the original adaptive palette.
Successful writes change shared CSS variables without reloading reports or the
host. CLI colors, acquisition, valuation and account settings remain independent.

`test_web_theme.py` covers omitted/default/persisted config, canonical validation,
byte-preserving JSONC round trips (comments, CRLF, nested source/account/CLI colors),
escaped top-level keys, absent-file creation only on write, malformed/ambiguous
config and oversized numeric values. Readonly/oversize/hardlink/reparse/symlink
hazards, external-edit conflicts, stopped admission, failed atomic replacement and
temporary cleanup have non-destructive checks. An actual WebHost remains running
after writes while its source guard stays unchanged. HTTP tests exercise session,
Origin/Host/content-type/CSRF, exact body/enum, safe errors, early shell selection
and absence of report jobs. The common HTTP parser retains framing/size/duplicate
key rejection. `web_theme.cjs` checks confirmed-only application, failure rollback,
retry, unchanged-selection suppression, focus recovery and external-read refresh.
`web_views.cjs` checks routing/navigation and retained frozen observations without
settings polling or hidden report acquisition. Quick and Full register the new file.

Full: 120 test files, zero failures; 1,462 cases passed and one normal platform
skip (macOS zsh/PTY shell execution unavailable on Windows). Package validation:
zero failures; existing README/context/report-service/Watch design-budget warnings
remain. Hard caps were not increased. The current history's old FR-registration
paragraph was condensed to accommodate this release within its existing cap.

## Actual integrated-browser observations

Shipped assets and the real `ThemeSettings` file writer were served over synthetic
transport/data with a disposable configuration, never the owner's real user file.
`serve_web_remaining.py` provides the fixture; `web_theme_browser.js` is its bounded
reproduction script. An iframe supplies genuine 360/1366/1920 CSS-pixel viewports.
Its `color-scheme` changes the child's actual `matchMedia(prefers-color-scheme)`
signal without changing the owner's OS settings or rewriting theme stylesheets.

An initial successful matrix measured **108 combinations**: both themes, both
preferences, three widths and nine views (Settings, Models, Accounts, Sessions,
captured date/range, captured Token Mix, initial Cost per Active Hour scope, Watch,
and session detail). No document overflow or preference-signal mismatch occurred.
Settings was the last navigation link and had exactly one visible select in every
case. Desktop flexible separation and 360px wrapping were inspected. Major views
retained their data; the Cost per Active Hour browser case was its explicit,
not-yet-captured scope, not a captured period report.

Classic background was `rgb(16,17,18)` for both preferences; Web was
`rgb(238,242,248)` light and `rgb(12,20,34)` dark. All 96 semantic text/surface
comparisons exceeded 4.5:1 (minimum 5.53:1). Classic panel ratios included primary
13.71, secondary 8.17, cyan 10.86, amber 11.78, error 7.83 and lime 13.43.
Actual screenshots of mobile Classic Settings and laptop Classic Models were
inspected; laptop iframe scaling fitted the Review viewport without changing its
layout width. This is browser rendering evidence, not physical device proof.

Entering Settings initially submitted zero report jobs. Native HTML dropdown
click/keyboard End+Enter saved Web and restyled the loaded shell; after fixing the
disabled-control blur, focus returned to `web-theme` with a visible solid outline.
Making the disposable file readonly produced a truthful permission error and kept
Web in the file, dropdown and page; restoring permissions and retrying saved
Classic. Reload and a new browser tab read Classic. Responses already carried the
saved HTML theme before analytics. This demonstrates early selection, not a measured
cold-start first-paint timing guarantee.

## Final selector verification and approved visual exception

After the successful matrix, Classic's new-model rule was narrowed from `.new` to
`.new:not(tr)`: marked cells/notices stay lime, while a whole new-model row retains
ordinary inherited text. A final integrated-browser **computed-style check passed**:
row/plain cell `rgb(229,229,229)`, marked cell/new notice/running `rgb(135,255,0)`;
Web retained plain `rgb(23,37,59)` and marked/notice `rgb(36,87,197)`. The last backend
refinement sanitized configuration numeric overflow and has a regression case.

Fresh full-matrix attempts did **not** pass: two awaited runs timed out at 60s;
the event/DOM-based reproduction then reached Models' 100%-ready presentation but
timed out waiting for deferred animation-frame painting. A focused screenshot call
after explicit tab focus reported that Review needed a visible desktop window.
The existing successful matrix is not replaced by these failures.

The **Decision Delegate** explicitly authorized a narrow AC6 exception: omit a
fresh complete visual matrix/screenshots after this final selector refinement,
given the prior comprehensive browser evidence plus focused final computed-style
verification. It did not waive implementation, backend tests or delivery gates,
and did not authorize external desktop automation. The reason was low incremental
value versus external-browser disruption/owner interruption. Final post-change
appearance has not been freshly visually inspected. Native OS/physical input,
assistive-technology/screen-reader and real-source visual behavior were not proved.

## Hosted CI follow-up

After canonicalizing trusted disposable test roots and correcting obsolete
default-theme/raw-label test expectations, hosted run
[41358018350](https://github.com/qstoffe/cost-guard/actions/runs/41358018350) passed
Windows 2025, macOS 15 ARM and macOS 15 Intel. Each job passed Full/package,
isolated native and actual rendered Chromium phases. Browser checks now use actual
Settings saves to disposable config, Classic in both preferences, adaptive Web,
reload/new tab, no Settings report acquisition, network recovery and clean shutdown.
Windows Full: 1,462 passing cases/one platform skip; macOS: 1,456/seven platform skips.
Local Full also passed 120 files after these test-only repairs; validator passed
11 checks with four unchanged design warnings. No production path guard changed.

Original Actions job logs returned HTTP 401. Structured jobs/Checks annotations
were retrieved; original detailed macOS traces were not. The Decision Delegate
authorized this evidence path and narrow repairs, requiring fresh passing CI,
not an access bypass or backend waiver. Initial run 41356409265 and intermediate
41357257423 remain failed evidence, not PASS. A batch-status fixture failure in the
intermediate Windows run did not recur; its assertions/deadlines were unchanged.
Hosted headless smoke supplements, not replaces, the scoped visual exception and
the physical-device/AT/real-source visual limits above.

## Separate read-only real-installation evidence

`probe_web_live.py --models` used the installed V2 source: one acquisition owner,
two streams, three observed Watch rows/three account rows, retained engine-start
origin and advancing sequence. Shell startup was 0.009s; first source view 9.663s.
Normal completed in 6.827s (29 catalog/25 selectable/14 selectable-latest rows,
accounts present); all-models completed in 2.035s (29 catalog rows, no account
acquisition). The owned live/HTTP workers closed and shared OpenCode was untouched.
This is live acquisition evidence, not synthetic-browser/real-source visual parity.

No paid inference, credential changes, real user preference changes, host install,
shared-service stop, native launcher acceptance, release ZIP or packaged release
was performed. Path/byte checks detect ordinary editor conflicts; they are not a
new hostile same-user filesystem transaction guarantee.
