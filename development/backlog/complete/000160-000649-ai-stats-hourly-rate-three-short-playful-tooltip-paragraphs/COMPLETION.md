# FR 000649 — completion

Implemented 2026-11-09 as v80.229. The original FR and bundle are preserved intact.

## Outcome

- AI Hourly Rate uses exactly three short plain-text paragraphs, separated by one blank line: around-the-clock tab, the same tab over scheduled eight-hour days excluding weekends/configured holidays, and an explicitly imaginary robot shift.
- Display-only tiers use the existing raw eight-hour reference-Credit cost: positive shifts below 80 get the bargain/parking-spot joke, 80 through below 800 get the charging-dock joke, and 800 or more get the extravagant/job-application joke. These synthetic copy bands bracket the existing 240/960-Credit regression examples; they are not salary or employment evidence. All private uncertainty reasons select neutral hypothetical copy instead of a replacement comparison. Missing/zero cost, shift or active-hour basis selects idle copy.
- Both units share the same copy and raw tier boundaries. Empty/failure fallback and pre-result title help also use three playful idle paragraphs. The existing retained ContextHelp/DOM/CSS, three amounts, traits and other cards are unchanged.
- Current Web documentation no longer promises equations in title help; its numeric definitions and example remain. Version/date/history/README and the selected ordinary progress state are included. No ZIP, tag, Release, new setting, model call or acquisition path.

## Verification

- Full registered suite: all 179 files executed in 133.2s. One failure was the superseded `No active-hour basis` copy assertion in `test_ai_stats_recovery.py`; it now asserts the idle joke/no replacement claim. Its final focused rerun passed (11 tests, 3.0s). The other 178 Full-suite files passed. Final focused Stats/rates/recovery/resume execution passed all other 61 tests before that one assertion repair.
- Rate tests cover raw tier boundaries and tiny positive values, zero/missing/weak basis, no workdays, all five selections/both units, three short paragraphs, unchanged original trait and existing calendar/DST/active-rate arithmetic.
- Frozen before/after comparison of all 12 canonical browser fixture views: exact equality after removing only `rate_help`, including raw facts, three rate tokens, every trait, other nine metrics and AI Working Time. Evidence: `scratch:/stats-invariants.json`.
- Working-tree validator: 11 passes, zero failures, seven existing advisory warnings; no raised budget. Full evidence: `scratch:/full-tests.log`, `scratch:/recovery-tests-final.log`.
- Read-only real installation: four complete/error-free requests, each with five periods and both-unit/rate checks. Cold 30-day completion 137.430s, fresh warm 30-day 5.561s, All reuse 0s (not a scan), fresh warm All 5.813s. Disposable owned cache, no OpenCode writes/stops or model dispatch. Overlapping workload/mutable history means these are not comparative performance claims. Evidence: `scratch:/ai-stats-live.jsonl`.
- Final hidden Edge browser probe: PASS, 17 checks, 72 canonical state/theme/unit cases, nine layouts, 80 text layouts, 1,350 contrast samples, zero runtime errors. The new title-help matrix adds 216 combinations (six scenarios × three themes × two widths × three scales × both units), checking actual text-range paragraph gaps, literal newlines, panel bounds/no scrolling, retained focus/cards, live tier/period changes, currency independence, Escape suppression, hover and emulated touch. Cold failure also renders three idle paragraphs. Production slices/two-tab reuse and owned host/browser cleanup passed. Evidence: `scratch:/ai-stats-browser-delivery.json`. Initial harness failures were a nested-JavaScript newline escape and a selector assuming heading-style label markup on a title button; both were corrected without product changes or relaxed assertions.

## Documentation assessment and limits

No architecture or journal update: no boundary, acquisition, accounting or reusable runtime finding changed; this copy policy and its tests are self-contained above and in the current Web guide. Historical completed FR000644 and its completion record were not edited. No acceptance exception or deferral is requested.

The integrated browser is disconnected. Headless Edge is the non-disruptive rendered test route; physical touch, actual screen-reader speech, external desktop and non-Chromium rendering are not claimed.
