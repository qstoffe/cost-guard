# FR 000523 — Exclude local Visual Studio cache artifacts from working-tree package validation

## Reproduced evidence

The colleague's 2026-10-28 sanitized Cost Guard Diagnostics bundle (v80.100, Windows 11, Python 3.14.7) reports a failed package validator and two failures in development.tests.test_foundation. The common cause is local, untracked Visual Studio .vs state:
- A mixed-case directory under .vs/.../FileContentIndex violates the lowercase-directory rule.
- An indexed .vsidx and .vs/slnx.sqlite exceed the otherText file cap.
- Both foundation failures rerun the same --working-tree package validator; they are not independent product or OpenCode source failures.

Source inspection confirms .gitignore lacks an entry for the root .vs directory. The validate_package.py --working-tree copy excludes Git, Python bytecode and selected runtime folders but does not exclude .vs. It consequently treats local IDE-generated data as distributable files. Existing unrelated budget warnings are not the failing condition.

## Required behavior

- Treat the **root-owned, untracked Visual Studio .vs/** directory as local generated state: ignore it in Git and exclude it from the temporary distributable working-tree view. Local IDE files must not cause package validation, Diagnostics Full Tests or source ZIP hygiene to fail.
- Maintain the distinction between a working-tree packaging view and an explicitly supplied distributable package: genuinely packaged unexpected files should still be rejected or flagged. Do not blindly disable lowercase/path/budget checks, suppress all unknown directories or ignore arbitrary user project files.
- Preserve existing released-source file-budget, Python 3.11, security, architecture and UTF-8 checks. No user .vs cleanup, deletion or process shutdown.
- Update the specific tests/fixtures and package validation documentation as needed, without making a broad automatic .gitignore rule parser a new requirement.

## Acceptance

- A working tree with representative .vs/slnx.sqlite, large .vsidx data and mixed-case .vs subdirectories passes the original unrelated checks and does not copy those artifacts into the distributable view.
- A deliberately malformed real package file outside excluded local state still fails its corresponding rule; an explicit package containing unexpected IDE data is not silently treated as a valid clean release.
- The previously failing foundation cases and package validator pass against synthetic fixtures with these artifacts, with no unrelated validation weakening. State that the report's other source/quotas diagnostics were independent.
- Publication is FR-only; actual source, tests and runtime version remain unchanged for now.

**Priority:** High / immediately after FR000522. Relevant files: .gitignore, development/tools/validate_package.py, development/tests/test_foundation.py and package-copy fixtures.
