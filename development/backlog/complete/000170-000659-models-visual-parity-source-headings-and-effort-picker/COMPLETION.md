# Completion — FR 000659

Implemented 2026-11-10 in v81.9.

- Shared heading/source structure, matching responsive left Refresh/date/status and
  right filter groups, and one semantic table skin in Classic/Web light/dark.
- Compact Settings-like multiselect with one vertical checkbox row per exact
  source effort; descending known priorities, alphabetical extras, no invented
  choices or changed selection keys. Solved is left-aligned in its elastic track;
  Relative Task Cost stays right-aligned. Existing defaults and data math remain.
- All 181 test files executed: 179 passed initially; two old heading assertions
  were corrected and their focused reruns passed. Package validation passes.
- Authenticated Chrome: 36 same-page parity cases plus 240 toolbar stress cases,
  mouse/keyboard/touch, effort subsets/refresh, long-list scrolling and screenshots.
  Six frozen-report layout cases pass. Real workstation Models/Harbor probe passes
  without inference or stopping the shared OpenCode service.
- Updated user guide, version/history, code map, journal and ordinary progress 109.

[Detailed evidence and limits](../../../journal/web/models-parity.md).
No physical desktop, assistive screen-reader or other-engine/macOS proof is claimed;
integrated Browser was disconnected and hidden Chromium provided actual rendering.
No acceptance waiver, backend change, dependency, archive, tag or GitHub Release.
