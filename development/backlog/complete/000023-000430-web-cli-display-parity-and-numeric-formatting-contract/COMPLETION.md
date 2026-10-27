# FR 000430 completion

Implemented in v80.92 (2026-10-27), from default revision
`20d0a90a5943b72d5ab241a97bffaaf6e2236313`.

## Delivered

- Shared CLI-owned formatting primitives and additive immutable server `display`
  tokens/roles. Canonical raw Decimal strings and numeric sorting are preserved.
- CCost rounding/partial markers; fixed USD; native quota units/directional rounding;
  Pace; compact durations/tokens/context; balanced Token Mix shares; configured-local
  cell timestamps; one-decimal `x` multipliers/compact tiers; exact native rate digits.
- Model column order, post-table promotion/new notices and final report notes;
  running/partial/estimated/threshold/new/promotion/superseded semantic classes.
- [Per-view mapping, goldens and explicit remaining page work](../../../architecture/governance/verification/web-display-parity.md).
  This is the shared foundation, not a full redesign or visual/native acceptance.
  Follow-up page FRs retain their independently specified scopes.

## Verification

- Local isolated Full suite: 107 test files, zero failures; includes deterministic
  CLI/DTO/DOM display goldens and existing report/Watch/application/security tests.
- Working-tree package validation: zero failures; four pre-existing design-budget
  warnings (README, context, report service and Watch coordinator); hard caps unchanged.
- Real-installation `probe_web_live.py --detail --reports`: V2; one acquisition
  owner, two SSE streams, three accounts; run origin preserved; detail first/latest
  access and frozen capture consistent. Normal/all-models/sessions/date completed;
  deep history cancellation preserved Live. Owned workers closed, OpenCode untouched.
- No UI/browser automation, model inference, new provider acquisition, dependency,
  archive, packaged release or automatic PR self-review.

## Knowledge, preservation and dependencies

Architecture routes updated for the shared display seam and its focused tests.
Journal assessment: **no-update**; the reusable contract and investigation limits
belong in the routed Web module/baseline, not a duplicate chronological journal entry.
The application/presentation dependency direction is unchanged. Exact selected FR
bytes are preserved; no attachments or new bundle evidence are modified/added.
Later parity/design FRs remain pending; their requirements and existing historical
evidence remain in the repository. No unfinished cross-FR implementation or stashes
are needed outside this delivery. The ordinary checkout was not edited or switched.
