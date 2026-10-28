# FR 000524 — Hyphenated launcher filenames

## Outcome and implementation

Implemented in v80.104 (2026-10-28). All eight report, Watch, Web Beta and Diagnostics `.cmd` / `.command` entrypoints now use hyphenated basenames in their original directories. No old-name aliases remain. README explains shortcut/bookmark migration and terminal invocation, including checkout paths containing spaces.

Updated current docs, runtime/bootstrap crash guidance, PowerShell/Python/AppleScript paths, package rules, macOS compatibility checks, native probe fixtures and regression tests. Finder helper fingerprint inputs use the renamed Web script; the filename and bytes participate in cache identity. All eight scripts are byte-identical Git renames; all four macOS scripts retain mode 100755. Console ownership, Ctrl+C reset, Web lifecycle, trust/signing policy and analysis/UI behavior are deliberately unchanged. The existing no-build Windows Web route remains; no new compiler or dependency was introduced.

Delivery PR: [#93](https://github.com/qstoffe/cost-guard/pull/93). Candidate implementation: [76e1d919](https://github.com/qstoffe/cost-guard/commit/76e1d919afded5f830b30db699d306d9a8c1f8cd).

## Verification

- `py -3 development/tools/run_tests.py --suite full`: PASS, 113 files, 4 workers, 53.3 seconds on Windows/Python 3.14.7.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, zero failures, four existing design-budget warnings. Initial README size-cap failures were repaired by shortening prose, without raising caps; Full and validation were rerun successfully.
- Added explicit eight-launcher/no-alias inventory coverage and Finder fingerprint filename/content invalidation coverage. Updated existing native-shell handoff, feedback, crash-path, macOS and package fixture expectations.
- Git proves eight 100% renames and four retained 100755 macOS modes. Existing source-copy/package regressions passed; no release ZIP was built.
- Read-only `collect_diagnostics.py --no-network --snapshots 0 --skip-validation`: actual V2 2.2.0 selection/probe healthy; 14/14 simulated macOS checks passed. Legacy V1 is unhealthy (missing legacy tables), so V2 is authoritative. Network/report building and the bundle's embedded validation tier were explicitly skipped; the independent Full/validator results above are not inferred from bundle creation. Raw diagnostic output remains private and uncommitted.
- Current source/docs/tools/tests search has no old space-named `.cmd` / `.command` references outside immutable historical backlog/version records. Historical specifications/reports and unrelated proposals are preserved, not rewritten to imply historical renames.

## Limits, dependencies and knowledge

Native Explorer/Finder double-click, physical keyboard/terminal appearance, Windows native console/Web UI probes and macOS Gatekeeper acceptance were NOT RUN in this invocation (separate bounded UI approval required; no macOS available). Deterministic tests and preserved bytes/modes do not establish fresh native desktop acceptance. Existing native-proof limits remain in current docs.

FR 000522 and FR 000520 are already complete on the selected default, despite the request's earlier ordering preference. Their console/native-handoff behavior is preserved; no cross-FR dependency or pending bundle was changed. The native transaction records this completion and leaves all seven other pending FRs intact.

Architecture: affected launcher/Web/code-map entrypoint routes updated; no boundary change. Journal: explicit **no-update** — naming introduces no new reusable runtime finding. Defect proposals: none; the README cap regression was local to this change and repaired. Completion is text-only; selected FR bytes are unchanged and no attachments were added.
