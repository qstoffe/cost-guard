# FR 000628 completion — reason-specific unavailable CCost help

Implemented in v80.208, 2026-11-08. The revised explanation-only scope is
authoritative; the original upstream Claude Agent model-selection/valuation
repair was withdrawn and is not claimed fixed.

## Delivered behavior

- Actual reference-CCost N/A text in Full Watch, Mini prompt/session/day,
  Sessions catalog/detail and other Web cost cells uses shared contextual help.
  Existing rich breakdown and compact prompt details remain available.
- Bounded typed canonical contributing-request facts distinguish verified
  available-catalog model absence (including Claude Sonnet 4), uncertain identity,
  missing required rate/tier, missing usage, unverified/failed catalog and neutral
  fallback. Child contributions are not blamed on the visible main model.
- Mini prompt and parenthesized session amounts are stable independent targets.
  Reason refresh, units and N/A-to-known daily updates preserve focus/DOM and
  remove obsolete help without reopening dismissed panels.
- Rate signatures and pricing decisions are unchanged. Diagnostic freshness uses
  a separate cache revision; metadata refresh cannot clear a failed price
  observation. No alternate rates, aliases, provider/SDK fix, repricing ledger,
  hover acquisition, paid inference or model/default/quota/billing change.

## Actual verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, all 172 files,
  four workers, 120.9s. Includes new reason cases and stale-metadata regression.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, 11 checks,
  zero failures, seven existing advisory prose/design warnings, version 80.208.
- Actual hidden Chrome 156 `probe_web_help.cjs --ccost-unavailable`: PASS,
  Full/Mini/PiP and production Sessions catalog/detail/footer text targets,
  real keyboard/Escape/hover/touch, independent components, pending/partial/zero,
  reason/unit/focus identity and N/A-to-known daily help removal; no JS errors.
- Existing `probe_web_help.cjs --watch-only`: PASS, rich help, three themes,
  narrow/150% zoom, delayed pointer interactions, touch and real Document PiP.
  Its Credits expectations now select Credits explicitly; shipped USD is unchanged.
- Focused real `probe_web_live.py --sessions --daily`: PASS. It validated 53
  exported cost values, including three actual N/A values with identity reasons;
  2,974 roots, 49 ready/one retained visible summaries and two detail rows. Daily
  3,278 requests/109 prompts reconciled category costs while retaining partial
  coverage. One Live owner/two SSE streams, zero model calls, shared OpenCode
  untouched and no owned workers/cleanup failures after close.

## Honest limitations

An earlier real-installation attempt passed Sessions but reset during unrelated
whole-Earlier proof. The source-frozen combined parity attempt passed Sessions
(2,974 roots; visible index 0→50; two detail rows), then timed out without an
eligible fully-priced Earlier prompt. Prompt/session parity phases are not
claimed passed by that attempt. No shared OpenCode service was stopped; owned
probe cleanup completed without remaining workers.

Browser fixtures are synthetic canonical snapshots, not a reconstruction of the
historical owner incident. Headless PiP does not restore opener native focus;
Sessions keyboard checks explicitly use CDP focus emulation after closing PiP.
No physical desktop, screen-reader, other-engine or paid-model proof is claimed.
Token Mix and insufficiently proven causes intentionally retain neutral wording.
No Decision Delegate exception was requested or granted for this task.

See [classification/evidence journal](../../../journal/web/ccost-unavailable.md)
for the semantic boundary, actual failures and local sanitized artifact references.
The bundle retains its original FR unchanged. This PR's prospective ordinary
progress is 78; only its actual merge to main advances the durable count.
