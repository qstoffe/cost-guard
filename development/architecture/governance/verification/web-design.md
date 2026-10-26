# Web Beta design and navigation evidence

FR 000440 · 2026-10-27 · v80.93. Baseline: `71a2e9094cc8769bb24064ee1391cffc6385525b`.

## Visual review

Open the [offline before/after gallery](web-design/index.html) from a downloaded checkout in a browser. It includes Overview, Watch, Sessions, Models and Accounts, adjustable 360px/1440px widths and light/dark modes. Table data, sort/filter/page controls and text remain selectable. Acquisition and navigation are deliberately disabled in this fixture; it never authenticates or reads real user data.

The gallery freezes baseline/current CSS, renderers and HTML around the **same canonical synthetic report/Watch DTOs**. Only static explanatory definitions fold into native details; no numeric fields, rows or warnings are hidden. The original global Live title is retained in the before preview. Current navigation uses Watch. Snapshot/Live session detail is not renamed.

Actual headless Microsoft Edge **156.0.4314.42** on this Windows workstation rendered twenty before/after sheets: five views × two themes × two content widths. These are actual browser pixels, not DOM checks called visual proof. The gallery remains the scrollable equivalent owner-review artifact, including content below each screenshot viewport. Filenames follow `<view>-<light|dark>-<1440px|360px>.png`:

| View | Light, wide | Dark, narrow |
| --- | --- | --- |
| Overview | [sheet](web-design/overview-light-1440px.png) | [sheet](web-design/overview-dark-360px.png) |
| Watch | [sheet](web-design/watch-light-1440px.png) | [sheet](web-design/watch-dark-360px.png) |
| Sessions | [sheet](web-design/sessions-light-1440px.png) | [sheet](web-design/sessions-dark-360px.png) |
| Models | [sheet](web-design/models-light-1440px.png) | [sheet](web-design/models-dark-360px.png) |
| Accounts | [sheet](web-design/accounts-light-1440px.png) | [sheet](web-design/accounts-dark-360px.png) |

Each view also has dark/wide and light/narrow sheets in the same directory. Visual inspection covered surface hierarchy, legible labels/statuses, wrapped navigation and independent table overflow. No performance improvement is claimed.

## Verification and reproducibility

- `python development/tools/run_tests.py --suite full`: **107/107 files PASS**, 42.8s, four isolated workers. The first run exposed one expected old-footer assertion; it was updated to pin Watch and exclude the old global Live link, then the entire suite passed.
- `python development/tools/validate_package.py --working-tree`: **PASS**, zero failures, four existing design-budget warnings (README and three Python owners). No hard budget was raised.
- [Rendered facts](web-design/rendered-facts.json): all twenty configurations preserve every table's text/row content; no after-preview page overflow at 360px or 1440px; correct light/dark tokens; visible programmatic text-input focus; sticky heading CSS; reduced-motion media match and zero transition duration. These are supplemental structural facts, not screenshot or physical-keyboard proof.
- Real-installation `python development/tests/integration/probe_web_live.py --detail`: **PASS**, V2, one engine/account owner, two streams, preserved run origin, first/latest detail access and consistent frozen capture. Owned HTTP/live workers closed; shared OpenCode untouched. No inference or model call.
- The broader exploratory `--detail --reports` probe reached the existing finite normal-report `result_too_large` boundary after processing 1,853 history candidates; it **did not pass** and subsequent report modes were not reached. Live/detail succeeded independently. This feature changes no report projection, acquisition or 8 MiB result policy; no limit was widened or oversized result hidden. Complete real-installation normal-report acceptance remains unproved on this history size.
- `development/tests/integration/web_views.cjs` covers the Watch alias, canonical navigation, session Live distinction and reload. The existing hosted-only actual Chromium smoke was extended for Watch deep links/reload/Back/Forward, 360px overflow/focus, dark mode and reduced motion. That optional hosted execution is not claimed by these local Edge fixture captures.

Rebuild the offline gallery from the repository root:

```text
python development/tests/integration/render_web_design.py --baseline 71a2e9094cc8769bb24064ee1391cffc6385525b --output development/architecture/governance/verification/web-design
```

`development/tests/integration/capture_web_design.py --browser <installed-browser> --profile <isolated-current-owned-scratch-profile> --output development/architecture/governance/verification/web-design` captures the sheets and asserts the supplemental facts. Browser execution requires explicit bounded UI/test authorization; it is not an automatic test, installer or product dependency. No user's browser profile is used.

## Privacy, ownership and limits

[SHA-256 manifest](web-design/sha256.json) fingerprints every generated evidence file except the manifest itself. Evidence was reviewed as synthetic-only: fixture names/prompts, test account labels, canonical costs and artificial 1970 timestamps; no installed account IDs, source paths, cookies, session/bootstrap/control secrets or real history. Browser profiles remain outside the repository and are not retained in evidence. All new evidence is outside the immutable completed FR bundle.

CLI/HTTP authentication, one-use bootstrap, session Snapshot/Live and shared-engine acquisition boundaries are unchanged. Journal assessment: **no-update** (no new reusable debugging conclusion). Architecture-boundary assessment: **no-update** (same asset/router/render owners and dependencies); current user docs and this evidence route describe the presentation change.

Not verified: physical mouse/keyboard/high-DPI desktop acceptance, assistive-technology/screen-reader behavior, macOS native UI, all real-history sizes or subjective owner approval. Page-specific Overview/Watch/Models/Accounts information-layout changes remain in their separate selected-order FRs; this delivery does not pre-implement them or hide their fields.
