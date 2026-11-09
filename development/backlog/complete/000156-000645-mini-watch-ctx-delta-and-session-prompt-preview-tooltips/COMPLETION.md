# FR 000645 completion

Implemented in v80.225 (2026-11-09). The original specification is preserved intact.

- Mini Ctx help shows the exact visible Next Ctx token and the selected prompt's
  prepared signed Δ Ctx. Historical next uses the session summary; historical Δ
  explicitly belongs to the representative prompt, potentially from an earlier sample.
- Canonical threshold wording and price/refresh guidance remain, including exceeded.
  Zero, negative, missing and source-retained values are not re-estimated in JavaScript.
- Session help retains the full title/ordinal and adds at most 25 graphemes from
  its existing bounded preview. Unicode/emoji boundaries, empty/unknown cases,
  whitespace/control normalization and literal text are covered. Unsupported grapheme
  segmentation safely omits the optional preview rather than splitting it.
- No extra source/API/persistence, visible column/value, size, color or full-Watch change.

Verification: local Full passed 179 test files in 124.8s, zero failures, with one
existing macOS zsh/PTY test skipped on Windows. Package validation passed 11 checks,
zero failures and seven advisory warnings. Real headless Edge Document PiP passed
91 layouts plus the new hover/Tab/touch/Escape/open-refresh help checks. A read-only
real V2 probe checked bounded preview and prepared context fields, then closed its
owned acquisition; shared OpenCode was untouched. Real history was not present in
that probe, so historical cases are proven by deterministic and synthetic browser
fixtures, not a natural personal-session transition. Physical desktop/work-area,
macOS and screen-reader behavior are not claimed.

Details, exploratory fixture correction and evidence:
[Mini Watch journal](../../../journal/web/mini-watch.md#value-help-additions-fr000645).
User and module documentation and functional release metadata were updated. No
acceptance exceptions, inference calls, Release/tag or local ZIP were introduced.
