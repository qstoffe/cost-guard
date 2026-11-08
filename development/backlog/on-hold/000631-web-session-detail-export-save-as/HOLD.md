# On Hold — FR 000631

**Decision:** Foreground Decision Delegate, 2026-11-08. Hold only this FR;
no blocked dependencies were identified. No acceptance waiver or automatic release.

## Reason and prerequisite

Native destination selection and successful Save As of the correct complete
sanitized session JSON remain **UNVERIFIED**. A safe filename-control route was
unavailable on the isolated Windows desktop. This is a verification-capability
hold, not a demonstrated product failure or permission denial.

Release requires a safe authorized route to control the native filename/destination
and verify successful Save As on a real loopback Edge/Chrome host. A subsequent
explicit owner change to that acceptance requirement could also resolve the hold;
none is assumed here. Dates alone do not release it.

## Preserved work and actual checks

Implementation is retained on [fr-000631](https://github.com/qstoffe/cost-guard/tree/fr-000631),
commit [155103c](https://github.com/qstoffe/cost-guard/commit/155103c).
Its [candidate evidence](https://github.com/qstoffe/cost-guard/blob/155103c/development/journal/web/session-export.md)
separates implementation, measurements and limitations. It is not merged or delivered.

- Full suite: 171 test-file units, zero failures; focused export/detail: 17 tests.
- Package validation: zero failures, seven existing advisory budget warnings.
- Installed OpenCode v2.2.6: native sanitized export matched CLI sanitized JSON for
  the worker's own session. No model call, source mutation or shared-service restart.
- Hidden Edge: authenticated standard download produced the complete synthetic
  native JSON; malformed responses produced no second file; focus, navigation,
  object-URL cleanup and narrow/wide layout checks passed.
- Headed Edge on an owned, never-switched Windows desktop: genuine native picker
  and real Cancel verified; operation settled, no export request and no output file.
- Native Save was not invoked after the filename control could not be uniquely
  identified. No shared input, visible-desktop interaction, overwrite or separate
  unidentified permission dialog was authorized. Headless aborts and deterministic
  write/close tests are not successful native-save proof.

This publication moves the original FR intact and adds only this hold record.
No product/test/version changes, completion move, completed-progress increment or
architecture/current-product-documentation update belongs to this hold-only PR.
