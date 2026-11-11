# FR 000674 completion

Implemented in **v81.23, 2026-11-11**.

Session detail now has fair attempt admission, measured source-work phases,
bounded no-progress retirement of one owned child, typed actionable failures and
explicit Retry. Ordinary detail faults cannot terminate shared Live. Healthy
advancing work has no total-duration deadline; verified history, canonical costs,
revision-pinned chunks and source-epoch/late-result rejection remain intact.

## Verification

- Full: 183 groups passed; 2273 tests passed, two native macOS shell tests skipped
  on Windows; no failures/errors. All 14 new liveness tests passed.
- Focused detail rerun: 11 passed after adding the Retry/status-read race regression.
- Actual authenticated hidden Chrome and Edge: blocked read, healthy peer, three
  finite failures, unchanged source-capture counts under status bursts, keyboard
  Retry to 1001 rows, hidden work, route retirement, Back/Forward, focus/aria and
  24 error layouts each. Backend-ready-to-DOM: 1.065s Chrome / 1.138s Edge.
- Existing loader and native-page-zoom probes passed 48 layouts each.
- Fresh read-only real V2 installation: detail/freeze consistent, Live preserved,
  zero owned worker survivors and zero initiated model calls; shared service untouched.
- Working-tree validator: zero failures, seven existing advisory budget warnings.

The initial Full/UI expectation and browser-fixture transport failures were
investigated and corrected, not counted as successful runs. No verification waiver
was used. Foreground Decision Delegate selected the owned-process design, not a
relaxation of acceptance.

## Evidence and limits

[Investigation, causality and measurements](../../../journal/web/session-loading.md#finite-source-acquisition-fr000674)
and [compact evidence](../../../architecture/governance/verification/session-detail-liveness-674.json).

The unidentified private owner session was not reconstructed. Reproduced blocked,
factory-failure and escaped-future paths establish finite recovery rather than
claiming its exact cause. No physical-input, spoken-screen-reader, OS-scaling or
macOS proof; no natural-arrival/global-sort completion claim. No paid inference,
account-login/source mutation, release ZIP, tag or GitHub Release.
