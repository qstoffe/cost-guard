# FR 000655 completion — 2026-11-09

Implemented as v81.4. The first AI Stats card now has Calendar average, Workday
average and Active AI average, consistently per hour. Active uses the existing raw
Decimal rate, without a shift multiplier. Calendar/workday math, unioned active
time, best-effort fallback, other nine cards and raw compatibility fields remain.

Title help has exactly three short playful paragraphs with matching labels and
trailing formulas. Neutral idle/uncertain help, retained updates and existing safe
ContextHelp interactions remain. Updated the Web guide, scoped architecture map,
release metadata/history/README and explicitly registered the focused rates tests.
The entire original task bundle is preserved here; no attachments were present.

## Verification

- Focused Stats/rates/recovery/resume: 64 tests passed. A new overlap fixture first
  reused a request identity; correcting the synthetic identity retained the intended
  independent 100-Credit oracle. No production calculation change was needed.
- Full: 181 files, 2,217 passed, two macOS-only skips, zero failures/errors, 133.9s.
- Package validator: 11 passes, zero failures, seven existing advisory warnings;
  no file-budget increase.
- Hidden Edge: PASS, 17 checks, 72 state/theme/unit cases, nine layouts, 80 text
  layouts and 1,350 contrast samples. Exact 5/21/30 and USD examples, independent
  active/workday changes, five periods, ten retained cards, help/keyboard/hover/
  emulated touch, live focus/refresh, cold/warm failures and finite-process slices
  passed. No runtime errors, text clipping or tooltip scrolling; clean owned exits.
- Real installation: four complete/error-free requests, all five periods and
  both-unit active tokens/raw rate identities checked. Cold30 135.612s, warm30
  5.054s, All reuse 0s, fresh warmAll 5.462s. Disposable cache and read-only source;
  mutable/overlapping workload means no comparative performance claim.

See [the FR000655 journal section](../../../journal/web/ai-stats.md#comparable-hourly-rates--fr000655)
for ownership, evidence references and limitations. Scratch evidence:
`scratch:/full-tests.log`, `scratch:/full-tests.json`, `scratch:/validation.log`,
`scratch:/ai-stats-browser.json`, `scratch:/ai-stats-live.jsonl`.

## Scope and remaining uncertainty

No acceptance exception/deferral or new Suggestion. Integrated browser was
disconnected; existing hidden Edge provided browser proof. Physical touch,
screen-reader speech, non-Chromium rendering and native macOS behavior are not
claimed. No model inference, shared OpenCode stop, account/source mutation,
dependency, ZIP, tag or GitHub Release. Existing maintenance deferral is unchanged;
the selected next progress state advances the ordinary count from 103 to 104 only
when merged. Hosted CI results belong to the PR, not an invented local PASS.
