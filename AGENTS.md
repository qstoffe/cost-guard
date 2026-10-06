# Cost Guard agent entry point

This extracted tree is designed to be maintainable by a fresh AI coding session without hidden conversation context. Treat the files in this tree as the source of truth; never reconstruct or reset them from Git unless the user explicitly asks.

## Choose the workflow from the user's request

- **Implement, fix, refactor or release:** read `development/MAINTAINER.md` first. Read `development/ARCHITECTURE.md` when boundaries are affected, then the relevant code/tests. Make the change directly in this extracted tree.
- **Brainstorm, design or create a Feature Request:** read `development/FR_GUIDE.md`. Do not modify production code or build a package unless the user explicitly transitions to implementation.
- **Understand the package:** start with `README.md`, then `development/README.md` and `development/ARCHITECTURE.md` as needed.

## Non-negotiable maintenance rules

- Preserve existing behavior outside the requested change; v77 semantics remain the historical behavioral reference where v78 has not intentionally changed them.
- Keep responsibilities inside the architecture boundaries. Do not create generic `helpers.py`/`utils.py` dumping grounds or meaningless split files.
- Respect `development/file-budgets.json`; do not raise hard caps just to make validation pass. Prefer deletion, consolidation or a responsibility-based split over append-only growth.
- Add or strengthen deterministic regression tests for bug fixes and important behavior changes.
- Never package secrets, credentials, `config/user-config.jsonc`, runtime `cache/`, runtime `diagnostics/`, `.git/`, Python bytecode, historical checkpoint artifacts or generated release debris.
- Do not commit or push automatically.

## Verification and packaging

Use the verification tier that matches the execution environment. In hosted/constrained AI sandboxes, keep the gate bounded:

```text
python development/tools/run_tests.py --suite quick
python development/tools/validate_package.py --working-tree
```

Quick runs each test file in an isolated process with a hard timeout and concurrent workers. Do not compensate for a constrained harness by running an unbounded monolithic suite. On an unrestricted local machine (human or local coding agent), run `python development/tools/run_tests.py --suite full` or preferably the normal Diagnostics launcher; Diagnostics runs the full tier plus package validation and records the result in its bundle. A final release-candidate graduation requires a successful full/local validation, even when an RC ZIP was built in a constrained environment.

When the coding agent runs on the user's workstation, it must run the relevant live integration/Diagnostics checks itself, not ask the user to run them or assume it is a hosted sandbox. Deterministic fixtures alone do not prove a workstation-specific fix. Keep live checks read-only/privacy-safe and never stop the shared OpenCode service serving the session.

If the harness kills long parent commands, run Quick first as above and then build with `--quick-already-run`; use that flag only before any further source edit. The builder will still run Quick from the clean extraction.

For a normal versioned package, run:

```text
python development/tools/build_release.py
```

The default artifact is `releases/cost-guard-vMAJOR.MINOR.zip`. The `releases/` directory is local/generated, git-ignored and excluded from the archive itself. If the user explicitly asks for a release candidate, use `--output releases/cost-guard-vMAJOR.MINOR-release-candidate-N.zip` without changing the product version merely for the RC number.

A package handoff should report the artifact path, SHA-256 and verification that actually ran. Historical/checkpoint ZIPs supplied for context are external reference material only and must never be nested into a new release.
