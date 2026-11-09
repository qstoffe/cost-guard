# Provider-authoritative reference quota amounts

2026-11-09 · FR000640 · v80.220

## Decision and ownership

The owner-approved FR supersedes FR000585's mixed native Remaining / observed Used
contract only for verified convertible finite allowances. `application/quota_ccost.py`
now converts Used, Remaining and Capacity from one normalized quota snapshot.
The existing Copilot monthly account AI-credit mapping remains narrow; an adapter's
explicit `reference_ccost_capacity` scales native amounts by their own native limit,
or a reliable normalized raw fraction. A similarly named unit is not conversion proof.

Complements use only coherent provider facts. Zero stays zero; missing is unknown.
Contradictory amounts/fractions, over-limit facts, invalid capacities, blocked,
inactive, stale and expired native windows cannot substitute OpenCode-observed Used.
Native diagnostics/overage indicators remain intact rather than clamping facts.
Fresh partial observations with sufficient native facts remain usable. Existing
client-side retained-observation behavior stays unchanged, including removal of
stale forward pace.

The same accepted raw Remaining feeds existing Web calendar pace. Shared account
cards and Mini consume prepared tokens; no browser arithmetic, acquisition,
history, billing, CLI or settings boundary changed. Independent observed costs
(Today, prompts, sessions and period cost evidence) remain untouched. Eligible
percentage-only quotas keep their disclosed ratio guesstimates, without a fictional
provider-credit balance. Existing `ccost_amount` formatting/rounding is preserved.

## Verification

- Full bounded local suite: **178 files, zero failures**, 119.8 seconds. The existing
  `test_web_quota_pace.py` was missing from admission and is now included.
- Final focused quota/Watch/pace tests, including the read-only probe oracle:
  **36 tests passed**. Covers external-only/mismatched local usage, complements,
  verified native ratios/fractions, zero/missing, partial/unavailable/invalid states,
  precision/large amounts, independent primary/secondary mappings and reset identity.
- Hidden Edge 157 browser with shipped HTTP/assets/SSE and actual Document PiP:
  `probe_accounts_live.cjs ... --quota-only` **PASS**. Synthetic 10,000 Capacity /
  3,000 Used / 7,000 Remaining versus 450 local Credits agrees across Accounts,
  Watch and already-open Mini in all Used/Remaining × Credits/USD combinations.
  The second request-unit quota maps independently to 600/1,400/2,000 reference
  Credits. Source facts, Today, stream/report counts, progress/reset help, retained
  nodes/focus, light/dark/narrow/zoom and percentage-only controls are checked.
- Initial deterministic failures were obsolete observed-Used assertions and an
  expectation that ignored existing ceiling formatting; corrected to the requested
  semantics and existing number rules, then verified. No weakened product behavior.
- Integrated browser was disconnected; permitted isolated hidden Chromium supplied
  browser evidence, without personal browser interaction or visible desktop work.
- Final real-installation `probe_web_live.py --accounts`: **PASS**, registered V2,
  three account cards, one account-refresh owner / one Live owner, advancing
  publications, zero finite jobs or probe-started model calls. The independent
  native-fact oracle verified one convertible Capacity, one coherent amount pair
  and its matching remaining/day pace. No private identities or balances exported.
  Owned workers closed cleanly; the shared OpenCode service was untouched.
- An earlier broader Watch-card attempt lost its probe host during ongoing source
  edits; it is not a passing history-oracle result. Two subsequent oracle-only
  KeyErrors exposed missing metadata/placeholder variants, fixed with a focused
  missing-slot and deliberately wrong-local-Used regression before the final pass.
  Whole real-history ranking was not an acceptance target for this quota change.
- Final working-tree validator: **11 passes, zero failures**, seven advisory size
  warnings; no hard cap or baseline was raised. `git diff --check` passed.

Owned raw evidence: `scratch:/full-tests.txt`, `scratch:/accounts-browser.json`,
`scratch:/real-accounts-final.jsonl`, `scratch:/validation.txt`.
Browser acquisition is synthetic; it is not native desktop, assistive-technology or
macOS proof. No inference, dependency, ZIP, GitHub Release or installed-toolkit reload.
No acceptance exception or delegated waiver was required.
