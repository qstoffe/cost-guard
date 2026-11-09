# Unblocked — FR 000631 (2026-11-09)

**Decision:** Explicit owner approval in the follow-up conversation on 2026-11-09. Release **only FR000631** from On Hold to **Ready for Development**, restoring its original permanent ID **000631** and queue priority **000540**. No dependency holds were identified. The original work remains preserved at [fr-000631](https://github.com/qstoffe/cost-guard/tree/fr-000631), commit [155103c](https://github.com/qstoffe/cost-guard/commit/155103c). This is **not** a product delivery, successful native-save claim, or permission to alter other tasks.

## Precisely approved limited test exception

The owner approves a **narrow acceptance-evidence exception** for the *successful real Windows/Edge/Chrome Save As destination selection and completed native file write* that the previous worker could not safely test. This specific real-dialog successful-save proof is **not required to return the task to Ready or to deliver FR000631**, provided the remaining implementation requirements, available tests and normal gates pass.

- Actual headed Edge native **picker opening and Cancel** were verified without a request or file write. The native filename field was not safely identifiable, so the Save button and successful real-dialog file output were **NOT TESTED / UNVERIFIED**, not PASS. No product defect or permission denial was demonstrated.
- Deterministic browser-client tests support picker-first ordering, abort-before-export, write/close sequencing, cleanup and fallback behavior. The authenticated normal download path yielded an actual correct complete sanitized JSON file in hidden Edge; the installed OpenCode v2.2.6 native transfer matched CLI sanitized export for the worker's own session.
- Existing full suite (171 file units), focused export/detail (17 tests) and package validation passed **on the preserved WIP candidate at that time**. These do not certify a future rebased/final candidate; rerun applicable normal implementation checks.
- **No acceptance waiver** for exporting the correct complete native sanitized session JSON, source/instance identity, security/CSRF, read-only transport, native picker activation when supported, cancellation, data integrity, size/time bounds, browser fallback, cleanup, privacy, or ordinary product validation. Native Save As remains the intended product behavior; this exception changes only the **mandatory evidence of successful native-dialog completion**.
- Do not disguise this limitation by claiming real native Save As PASS from a mock, headless abort, deterministic file handle or standard download test. Record the specific test **UNVERIFIED** in eventual completion notes. If an actual saving defect emerges during development, fix it instead of invoking the exception to ignore it.
- This release does **not** authorize shared/visible desktop input, unidentified consent-dialog confirmation, overwrites, credential use, or testing on the user's personal desktop. The worker may finish via already-authorized isolated tests, preserving the safety boundaries.

## Continued development

The existing branch is a **WIP recovery point**, not yet merged. Continue from its preserved implementation, reconcile/rebase it safely onto the current main and resolve any legitimate conflicts in an ordinary delivery branch/PR; do not force-merge a divergent branch or silently discard other main changes. The exact chosen integration method must respect the repository's normal backlog/PR workflow. The original FR text is retained in this Ready bundle with the narrow supplemental decision below. Work is not automatically complete merely because the hold is removed.

**Publication scope:** documentation/backlog-only move of the original FR, archived hold rationale and this release decision. No product code, tests, release/version metadata, identity-counter increment, active session, WIP branch or unrelated backlog items changed by this transaction.
