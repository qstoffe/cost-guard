# FR 000529 — Web Beta long-table scrolling

Delivered in v80.113 (2026-10-30). The specification was moved intact; no attachments
were present. Web remains optional Beta, with no promotion or source/provider,
valuation, full-history totals or security-boundary changes.

## Implementation

- Retain the visible session row in its owning table after HTTP returns, rather
  than undoing user scrolling through a document-level compensation in `finally`.
- Disable Live follow when browsing away from the internal table's bottom.
- Keep unchanged frozen report DOM during host-health checks, across all finite
  views rather than Overview alone. Keep an already-attached session root connected.
- Add deterministic response/geometry/attachment/heartbeat regressions and an
  approval-only isolated Chromium acceptance harness. Native browser scrolling,
  sticky headers and 50-row paging remain; no input interception/overflow removal.

## Verification

- Real Chromium 141 / Playwright 1.56.0 over shipped HTTP/security/SSE/assets and
  synthetic application observations: complete run **PASS**, 18 cases at 1000px
  and 360px covering Watch, Models/all Models, Sessions, Accounts, deep Token Mix,
  date reports and Snapshot/Live detail. Wheel, PageUp/PageDown/arrows, horizontal
  movement, reachable ends, sticky headings, filters, boundary chaining and no
  page overflow were checked. Narrow screenshots were inspected.
- Pending actual HTTP response: old session.js moved the document 578→228 after
  a 350px wheel moved the internal table 500→850. Candidate retained 578/850.
  This isolates a source-bound scrolling failure, not the colleague's unknown
  original browser, route or device.
- Actual synthetic Watch SSE covered idle/live changing rows, visible anchors,
  canonical nodes, horizontal/document offsets, selected text and focused controls.
  Detail covered first/middle/latest 50-row pages with unchanged whole-session
  summaries, deferred selection/focus updates, frozen revisions, resizing and
  reduced motion. Stable-controls growth retained document/horizontal 900/100
  with -0.25px visible-row drift; inner scroll compensated the preceding growth.
- `run_tests.py --suite full`: **115/116 files passed**, 1,418 tests reported,
  four PowerShell failure subcases, zero errors, two symlink-privilege skips.
  All relevant Web files, including the new causal regressions, passed.
- `validate_package.py --working-tree`: **11 passes, zero failures**, four existing
  design-budget warnings. Release notes were shortened to retain the existing
  hard caps; no validator/test weakening.

## Decisions and remaining uncertainty

Decision Delegate authorized only isolated browser provisioning/testing against
owned synthetic loopback hosts, because this session exposed no integrated browser
tools. No personal profile, desktop identity, actual source/provider, model call
or shared-service mutation was used. Owned browsers and server threads closed.

Decision Delegate approved a **narrow verification exception** for the four
unchanged Windows PowerShell 5.1 subcases in `test_launcher_feedback.py`:
`probe.ps1` was rejected because script execution was disabled (`SecurityError` /
`UnauthorizedAccess`, exit 1 instead of expected 9009/17). Corresponding pwsh.exe
coverage passed. Intended 5.1 launcher behavior remains unverified; the failure
is not claimed proven pre-existing. No execution policy or unrelated test was
changed/circumvented. The full suite is **not** labeled PASS.

Decision Delegate also directed anchor-aware assertions, not an FR waiver: when
the existing new-activity label expanded narrow controls by 47.25px, native page
anchoring moved 47px while preserving the row within 0.25px, focus, selection and
horizontal offset. A blanket raw-scrollY assertion failed and was replaced by a
measured-layout explanation. Stable controls require unchanged document/horizontal
offsets; neutral geometry requires all raw offsets unchanged. The corrected focused
and complete runs passed; earlier failed runs are not reclassified.

Physical mouse/touchpad/touch, assistive technology and the original colleague's
installation remain unverified. Automated trusted input over synthetic observations
is not full physical-device acceptance, real-source acquisition or OS browser proof.

## Knowledge and evidence

Architecture/module continuity facts and the Web snapshot journal were updated;
no dependency-boundary or validation-flow change required a system diagram update.
Current evidence: `development/architecture/governance/verification/web-table-scroll.md`
and `web-table-scroll-2026-10-30.json` beside it. Historical partial browser evidence
is retained separately. No automatic installation, Toolkit reload or runtime restart.
