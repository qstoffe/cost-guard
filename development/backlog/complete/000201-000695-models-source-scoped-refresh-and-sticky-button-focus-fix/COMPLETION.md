# Completion — FR000695

Implemented in v81.39, 2026-11-13; delivery PR:
[#300](https://github.com/qstoffe/cost-guard/pull/300).

## Delivered behavior

- Models retains independent pricing and benchmark roots, controls and keyed rows.
  Equal data and status/date changes preserve unchanged DOM; each source owns its
  progress, errors and requests without clearing or disabling its sibling.
- Web and Mini Watch share per-document pointer/keyboard modality handling.
  Pointer activation does not inherit an extra keyboard-like outline; native
  keyboard rings, active navigation and genuine toggled states remain intact.
- Current guides, architecture and focused regression probes are updated. The
  original FR is preserved unchanged; no parked suggestion was implemented.

## Verification and limits

- Local Full: **188 test groups, zero failures**, 159.0 seconds.
- Working-tree package validation: **11 passes, zero failures**, seven existing
  advisory warnings; no budget increases or rebaselines.
- Instrumented Chrome RED reproduced sibling detachment, unchanged-row replacement
  and a same-element keyboard-to-pointer outline. Repaired Chrome/Edge source/DOM
  probes pass independent changed/equal/status, concurrent and failure cases.
- Native mouse/touch/keyboard control/style matrices pass, including all eight
  navigation links and actual Document PiP controls. Real installation probes
  verify GitHub pricing and Harbor independently, with zero model calls and owned
  teardown; the shared OpenCode service was untouched.

**Scoped verification exception:** Decision Delegate, 2026-11-13, authorized
FR000695-only completion without verified exclusive owner/PiP focus transfer or
halo behavior across genuine native-window blur/revisit (§5G). Both headless
browsers report both documents focused without distinguishing focus/blur events;
that condition remains **UNVERIFIED**, not PASS. Route return, same PiP identity,
pointer resting styles and keyboard rings are verified. Residual browser/OS focus
behavior and the owner's exact intermittent physical-desktop incident remain
unverified. No native successful Save As or physical assistive-technology proof
is claimed; export-picker cancellation is simulated.

The [primary journal](../../../journal/web/models-isolation.md) records causal
evidence, exact scope, decision attribution/reason, residual uncertainty and earlier
failed/interrupted attempts. No ZIP or paid inference was performed.
