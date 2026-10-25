# Cost Guard development data

This directory contains product test suites and fixtures, technical architecture/navigation, diagnostic tooling and backlog specifications. It defines **no local development-process authority or verification gate**.

The actively loaded compatible OpenCode Toolkit shared repository skills govern its layout, FR authoring, backlog work, maintenance and development-only Git workflow. Historic files and completed FRs are historical evidence, not competing instructions.

Authority: [installed shared-repo-contract](https://github.com/qstoffe/opencode-toolkit/tree/main/skills/shared-repo-contract). Repository release facts are in [repository.json](repository.json); the applied revision is [applied-contract.json](applied-contract.json), not proof without the actual layout.

- [Architecture overview](architecture/OVERVIEW.md) and [code/test map](architecture/modules/CODE_MAP.md).
- [Engineering knowledge](journal/INDEX.md), including historical performance evidence.
- [Pending requests](backlog/todo/), [completed requests](backlog/complete/), reserved human-review [suggestions](backlog/suggestions/) and [rejected suggestions](backlog/rejected-suggestions/).
- Deterministic tests in `tests/`, synthetic fixtures in `tests/fixtures/`, and reserved provider/live integration tests in `tests/integration/live/`.
- Development scripts in `tools/`; human Diagnostics launchers in `user-tools/diagnostics/windows/` and `user-tools/diagnostics/macos/`.

**Development-only changes** have no Cost Guard-local package validation, regression-suite requirement, file/structure budget or product version bump. For modifications to shipped product code, continue using the product regression tests and applicable runtime/package safeguards. Never misclassify source changes as development-only.
