# FR 000699 — completion

Implemented in v81.43 (2026-11-13).

- Accounts and Full Watch period/monthly Capacity help uses concise normally
  formatted raw amounts, not the card's five-percent-rounded estimate. Inferred
  values retain `~`; verified native allowances do not. Usage, Remaining and pace
  help is numeric with only meaningful short exceptional warnings.
- Mini retains Capacity → Next reset, with useful numeric Remaining/status once.
  Both units, primary identity, accessibility and open-help Live refresh remain
  coherent without browser arithmetic or extra fetches.
- Web resets show duration, local HH:mm then today/English weekday through
  exactly seven elapsed days, otherwise local date after the clock. CLI reset
  conventions and all quota/accounting calculations remain unchanged.

Verification: Full **192/192 groups**, working-tree validator **11 passes / zero
failures** (seven existing advisory warnings), hidden Chrome/Document PiP
**12 check groups / 63 layout records**, final read-only V2 installation probe
and `git diff --check` passed. Live observed zero eligible inferred capacities;
their raw-number behavior is covered synthetically, not claimed as live proof.

**Scoped Decision Delegate exception:** positive sub-one tooltip Credits use
`<1 Credits` to honor no-decimal wording without inventing zero; tiny USD uses
`<$0.01` only when ordinary rounding would be zero. Global formatting, visible
cards, raw Decimals and tests are unchanged by this exception. No acceptance
or verification was waived; no remaining implementation is deferred.

See [journal evidence, initial failed attempts, decision and limits](../../../journal/web/quota-tooltip-separation.md).
Current usage/Web docs and reports/code-map ownership notes are updated.
The complete specification and attachments are preserved intact. Merged default
alone advances ordinary maintenance progress to 144. No release ZIP, paid model
calls, shared-service stop or runtime reload.
