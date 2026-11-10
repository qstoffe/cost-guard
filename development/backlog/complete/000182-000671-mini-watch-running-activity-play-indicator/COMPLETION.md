# FR 000671 completion

Implemented in v81.21, 2026-11-10. Mini Watch's Activity time now has a small
decorative ▶ only for its genuinely running representative prompt. Every draw
recomputes it from canonical in-progress and terminal/verification flags; success,
abort, error, unverified work and history have no retained cue. Unknown times stay
unknown. No additional control, help, focus stop or accessible status is introduced.

The existing five columns, row colors, configured-local start/finish help, native
width, opening measurement and explicit Fit behavior are unchanged. The glyph fits
inside the current Activity header minimum; no dependencies or resize workaround.

## Verification

- Local Full: 182 bounded test groups, zero failures, 145.0 s; focused Mini: 13 tests.
- Package validator: 11 passes, zero failures, seven existing advisory warnings.
- Actual hidden Chrome Document PiP: 131 full-portfolio layouts at 100%/DPR 1;
  another 40 lifecycle/Activity layouts at 125%/DPR 1.5. Four themes, both units,
  narrow widths, row reuse/terminal transitions, help/focus/touch/selection,
  sticky alignment, scrolling/Fit and no passive native resizing were verified.
- Deterministic fixtures additionally pin unknown times, simultaneous sessions,
  contradictory terminal flags, source corrections, older snapshots, repeated
  draws, row replacement and the next prompt in an existing session.
- Read-only installed V2: 62 coherent publications, one running prompt, three
  accounts; owned acquisition closed and shared OpenCode untouched. No real
  terminal/history transition was observed, so no such live-source claim is made.

Evidence and synthetic screenshots: [Mini Watch journal](../../../journal/web/mini-watch.md#running-activity-indicator-fr000671).
Integrated browser was disconnected and the first hidden Edge launch timed out
before rendering; the working hidden Chromium route supplied native PiP proof.
Physical desktop frames/work areas, macOS and screen-reader speech were not tested
or changed. No acceptance exception or deferred product scope. No inference,
source writes, ZIP, tag or GitHub Release. Architecture boundaries are unchanged;
the code map and user guide document this presentation-only delta.

The intact original specification is retained in `FR.md`. The delivery includes
the selected maintenance nextState, advancing ordinary progress only on merge.
