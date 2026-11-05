# Completion — FR 000585

Implemented 2026-11-05, v80.166.

## Delivered scope

- Python-owned Decimal reference Used/Remaining/Capacity variants, including both
  Credits/USD units. Verified Copilot included AI credits use native limits and
  remaining credits, independently of observed Used CCost. Other valid windows
  extrapolate same-window cost / raw fraction Used without hardcoded plan values.
- Honest unknown, partial/unpriced, stale/reset, ambiguous, zero and Unlimited states;
  identity-bound primary/secondary/model windows never borrow Today or old costs.
- Full Watch's clean quota parentheses switch modes, with a Capacity row before
  each bar, seven-row primary alignment and the existing secondary-only divider.
  Native ratios, money and source/attribution detail remain in accessible help.
  Mini stays compact. Accounts adds reference figures only with matching period
  costs already present in its report, without new scans or provider polling.
- Provider-confirmed idle rolling zero displays native 100% Remaining/full healthy
  bars while reference Capacity/Remaining stay unknown; Used zero and Window not
  started remain intact. Unknown/stale/inferred/rounded-zero counterexamples remain
  distinct. CLI, native accounting, daily costs and provider acquisition are unchanged.
- Updated user guides, module map/overview, quota journal, release history and README.
  Included selected progress nextState (ordinary count 36); it counts only on merge.

## Actual verification

- `py -3 development/tools/run_tests.py --suite full`: **142 files passed**, zero
  failures, 88.4s. Nine focused new projection/normalization tests join the suite.
- `py -3 development/tools/validate_package.py --working-tree`: **11 passes**, zero
  failures, six existing advisory/design warnings; no limit or baseline raised.
- Hidden Chrome **156.0.8078.80**: the actual shipped HTTP/CSP/SSE/PiP probe passed
  native 25000/22912 versus observed 1814, ratio 100/900/1000 and USD variants,
  already-open Accounts/Watch/Mini mode switching, idle primary/secondary windows,
  native bar/reset accessibility, seven-row card alignment, themes/narrow/zoom,
  retained DOM and one SSE/no browser storage.
- Bounded read-only installed V2 probe: 20 coherent publications, three accounts,
  four quota projections and two numeric capacities in 11.728s. Owned acquisition
  closed in 0.088s; shared OpenCode was not stopped or changed.
- Initial fixture failures were repaired: missing test-DOM event support and the
  synthetic Accounts clock predating its refreshed quota. Final reruns passed.

Evidence and limitations: [sanitized verification](../../../architecture/governance/verification/web-quota-ccost.json)
and [quota journal](../../../journal/web/quota-display.md).

## Limits and exceptions

No requirement/test exception was requested or approved. Live running source/pricing
coverage was partial, not a complete-cost proof. No idle window happened to occur
in the real probe; exact idle boundaries were proved with normalized provider,
deterministic and browser fixtures. Physical desktop/native chrome, screen-reader
speech and macOS-native behavior were not newly certified. No release ZIP, tag or
GitHub Release was generated. The ordinary checkout was left untouched.
