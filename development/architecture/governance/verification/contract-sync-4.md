# Contract Sync revision 4

Source base: `9040d27bcf4c807e0ca74f3f75a7644aee5c36c9` (2026-10-27).

The installed FR0190 migration preview and apply succeeded after the earlier
`ATTACHMENT_LINK_INVALID` failure on repository-documentation links in historical
completion reports. No installed code was changed by this task; no workaround or
assertion bypass was needed on continuation. The defect is resolved in the current
installed helper, so no duplicate suggestion is published.

- Four todo bundles now use priority/permanent-ID names; all remain pending.
- Twenty-eight complete bundles now use first-parent completion-order/permanent-ID
  names. Their specifications, attachments and existing completion reports remain
  unchanged. The source-bound plan updated one incoming local documentation link.
- No protected identity was moved; the plan has no deferred dependencies.
- Permanent identity watermark stays 520, ordinary completion count stays 28 and
  periodic audit milestones remain unchanged. Completion watermark is seeded at 28.
- The exact installed development guide replaces its previous mirrored revision;
  applied-contract records revision 4 with the native schema hash.

Only development documentation, backlog placement and native accounting change.
Product tests, validators, live probes, version updates and packaging are not run
for this development-only migration. Native ownership/transaction verification
and protected PR/default read-back remain required for delivery.

Architecture boundaries: unchanged. Journal: **no-update**; no new runtime learning.
Historical evidence and its stated limitations are retained, not reinterpreted as
new test or performance results.
