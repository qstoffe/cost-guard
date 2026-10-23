# Cost Guard agent entry point

This repository tree is designed to be maintainable by a fresh AI coding session without hidden conversation context. Treat the files in this tree as the source of truth; never reconstruct or reset them from Git unless the user explicitly asks.

## Choose the workflow from the user's request

- **Implement, fix, refactor or package:** read `development/MAINTAINER.md` first. Read `development/ARCHITECTURE.md` when boundaries are affected; use `development/CODE_MAP.md` to locate the relevant owners/tests. Make the change directly in this authoritative tree. Verification and packaging depend on where you run (below).
- **Git delivery explicitly authorized by the user** (through the current task or a development workflow they started): follow [authorized Git delivery](development/MAINTAINER.md#authorized-git-delivery). Work may happen in an isolated repository clone without changing the ordinary working tree; all quality gates still apply.
- **Brainstorm, design or create a Feature Request:** read `development/FR_GUIDE.md`. Direct instructions to create/add/update an FR in the repository authorize publishing and merging it into `main` by default; brainstorming alone does not. Do not modify production code unless the user explicitly transitions to implementation; brainstorming never builds a ZIP.
- **Understand the package:** start with `README.md`, then `development/README.md` and `development/ARCHITECTURE.md` as needed.

## Non-negotiable maintenance rules

- Preserve existing behavior outside the requested change; v77 semantics remain the historical behavioral reference where v78 has not intentionally changed them.
- Keep responsibilities inside the architecture boundaries. Do not create generic `helpers.py`/`utils.py` dumping grounds or meaningless split files.
- Respect `development/file-budgets.json`; do not raise hard caps just to make validation pass. Prefer deletion, consolidation or a responsibility-based split over append-only growth.
- Feature placement and focused tests are in `development/CODE_MAP.md`. `development/structure-policy.json` gates routine growth and test coupling: do not auto-rebaseline, grow legacy exceptions or introduce test-to-test fixtures to make a feature pass. Refactor the owner; retire resolved debt entries.
- Add or strengthen deterministic regression tests for bug fixes and important behavior changes.
- Never package secrets, credentials, `config/user-config.jsonc`, runtime `cache/`, runtime `diagnostics/`, `.git/`, Python bytecode, historical checkpoint artifacts or generated release debris.
- Do not commit or push automatically unless the user authorizes Git through the current task or a development workflow they started. A direct repository FR creation/update request explicitly authorizes commit, push, PR and merge; those already-authorized actions need no further confirmation.
- Current `main` is the recommended/latest supported distribution during rapid development. Packaged GitHub Releases are currently paused; changing that policy requires an explicit decision, never a version-number trigger.
- Every PR merged to `main` that changes shipped Cost Guard product code or functionality must increment the product version and update release date, `VERSION_HISTORY.md`, README current version and affected current docs in the same PR. **FR-only, documentation-only, test-only and development-tool-only changes must not bump product version/history**. Verify the latest base and change scope before merge. See [versioning and history](development/MAINTAINER.md#versioning-and-history). Git tags, GitHub Releases and ZIP policy remain independent.

## Verification by environment

Decide first where you run. If you cannot establish that you run on the user's own workstation, treat the environment as hosted.

**Hosted/web AI** (for example ChatGPT or Claude Code on the web, or any cloud sandbox that only has the GitHub repository): run only the light, fast gate and never build a ZIP, even when the product version changes:

```text
python development/tools/run_tests.py --suite quick
python development/tools/validate_package.py --working-tree
```

Quick runs each test file in an isolated process with a hard timeout and concurrent workers. Do not start Full or Diagnostics there, and do not compensate for a constrained harness with an unbounded monolithic suite.

**Local workstation agent or human** (for example OpenCode on the user's computer): always run every test and investigate failures, then run the relevant read-only live checks yourself (Diagnostics or headless report/Watch probes against the real installation); never ask the user to run them and never stop the shared OpenCode service serving the session. Deterministic fixtures alone do not prove a workstation-specific fix. No local release ZIP is routinely generated; use current `main` as the supported distribution:

```text
python development/tools/run_tests.py --suite full
python development/tools/validate_package.py --working-tree
```

Local work also owns the deeper upkeep hosted models cannot do: performance, robustness, Diagnostics relevance, structure ratchets and tidy, AI-maintainable code. Both environments hand off the verified authoritative working tree; brainstorm/FR sessions build nothing.

## Distribution and archives

The repository has no local product-release ZIP builder or routine archive-generation workflow. Current `main` is distributed as source; GitHub's **Code → Download ZIP** is a source snapshot, not a separately packaged release. Diagnostics bundles remain a distinct troubleshooting artifact. Historical/checkpoint ZIPs supplied for context are external references only and must never be nested into a source snapshot.

Remote GitHub Release deletion/publication is a separate explicitly authorized operation. Preserve the historical v80.0 tag unless its deletion is explicitly requested.
