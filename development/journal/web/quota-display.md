# Web native quota orientation

FR 000577, 2026-11-04, v80.157. This is a Web presentation preference, not a
provider/accounting change. `webSettings.quotaDisplayMode` stores `default`, `used`
or `remaining`; the shipped effective default is Used. Explicit Used stays pinned.

## Owners and protected distinctions

- `application/quota_display.py` projects both native orientations, retaining raw
  quota fields. Trust native Remaining first, otherwise complement reliable finite
  usage/fraction evidence. A normalized explicit percentage-only quota is valid
  fraction evidence, not permission to invent an absolute limit.
- Unlimited, zero/missing denominators, missing usage and unstarted windows fall
  back to existing Used/unknown presentation. Overage stays visible through native
  Used/limit evidence and explanation; visual fills alone are clamped.
- Remaining exhaustion uses unrounded evidence. Zero-fill exhausted summaries
  retain red/status/accessibility; tiny positive Remaining is not exhausted.
- Native money is provider evidence, not CCost. The same-period observed CCost,
  completeness/estimated provenance and Credits/USD tokens never become a
  remaining budget. Remaining labels it `CCost used` and omits unknown Mini cost.
- Shared renderer bindings update text, accessible labels and bars in place.
  Detached Watch roots and an open Mini update after confirmed saves; failure
  retains confirmed state. No browser storage, new SSE, source mutation, refresh,
  history scan, CLI preference or geometry change is introduced.

## Verification evidence

Deterministic regression routes: `test_web_watch_quota.py`, `test_web_theme.py`,
`test_web_accounts.py`, `test_mini_watch.py`, `test_web_views.py` and their existing
DOM integration scripts. They cover independent same-label windows/accounts,
0/10/90/100%, just-below exhaustion, overage, native amount/fraction-only evidence,
Unlimited/unknown fallback, native money, independent period cost and symbolic
inheritance. The final suite result is recorded in the completed task.

Hidden Chrome **156.0.8078.80** passed the extended
`integration/probe_mini_watch.cjs` / `probe_quota_display.cjs` test. At device scale
1.5, all eight Remaining combinations (light/dark × 360/560px × 100/125% zoom)
had no document overflow in Accounts, full Watch or the actual PiP document.
The browser verified native 22912/25000, 91.6% Remaining, fill 0.91648, unchanged
1814/$18.14 CCost, accessible exhaustion, retained bar/cost nodes, one EventSource
and zero local/session storage entries. Settings use the actual authenticated
HTTP path and disposable JSONC; no installation preference is changed.

Read-only real installation command:
`py -3 development/tests/integration/probe_web_live.py --watch-cards --daily`.
It passed against V2 with one acquisition owner, three accounts, one active and
two history cards, advancing verified streams and preserved run origin. First
source view was 1.111s, first card rows 4.953s, daily publication 24.976s. Daily
cost/category reconciliation was complete; prompt-count attribution was partial
(`prompt_count_complete=false`) and is not represented as complete coverage.
Owned workers closed (zero threads/processes and cleanup failures); the shared
OpenCode service was untouched. This live probe checks acquisition/publication,
not real-provider exhaustive quota boundaries; those use deterministic fixtures.

During development, the browser fixture's new projection import initially
collided with its density-command local variable; the alias was corrected. A
later full suite identified two exact-string assertions missing the newly
required native-money suffix. Expectations were corrected, not removed; the
36-test focused rerun passed. Final full-suite/validator results belong in
`COMPLETION.md`.

Final local verification: Full passed all 140 files in 89.5s; working-tree
validation had 11 passes, zero failures and six existing advisory/design warnings.
No limit/baseline was raised. Whitespace validation also passed. The final Mini
tooltip fix distinguishes known observed period spending from truly unavailable
cost, with a focused assertion and inclusion in that final Full run.

No test/requirement exception was requested or approved. Browser evidence is
headless Windows Chromium, not physical desktop placement, native chrome,
screen-reader speech or macOS-native certification. Existing unrelated physical
placement exceptions remain confined to their original FRs.
