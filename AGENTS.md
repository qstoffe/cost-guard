# Cost Guard agent entry point

This repository tree is designed to be maintainable by a fresh AI coding session without hidden conversation context. Treat the files in this tree as the source of truth; never reconstruct or reset them from Git unless the user explicitly asks.

## Choose the workflow from the user's request

- **Implement, fix, refactor or package:** read `development/MAINTAINER.md` first. Read `development/ARCHITECTURE.md` when boundaries are affected; use `development/CODE_MAP.md` to locate the relevant owners/tests. Make the change directly in this authoritative tree. Verification and packaging depend on where you run (below).
- **Git delivery explicitly authorized by the user** (through the current task or a development workflow they started): follow [authorized Git delivery](development/MAINTAINER.md#authorized-git-delivery). Work may happen in an isolated repository clone without changing the ordinary working tree; all quality gates still apply, and no local ZIP is built unless packaging is requested.
- **Brainstorm, design or create a Feature Request:** read `development/FR_GUIDE.md`. Do not modify production code unless the user explicitly transitions to implementation; brainstorming never builds a ZIP.
- **Understand the package:** start with `README.md`, then `development/README.md` and `development/ARCHITECTURE.md` as needed.

## Non-negotiable maintenance rules

- Preserve existing behavior outside the requested change; v77 semantics remain the historical behavioral reference where v78 has not intentionally changed them.
- Keep responsibilities inside the architecture boundaries. Do not create generic `helpers.py`/`utils.py` dumping grounds or meaningless split files.
- Respect `development/file-budgets.json`; do not raise hard caps just to make validation pass. Prefer deletion, consolidation or a responsibility-based split over append-only growth.
- Feature placement and focused tests are in `development/CODE_MAP.md`. `development/structure-policy.json` gates routine growth and test coupling: do not auto-rebaseline, grow legacy exceptions or introduce test-to-test fixtures to make a feature pass. Refactor the owner; retire resolved debt entries.
- Add or strengthen deterministic regression tests for bug fixes and important behavior changes.
- Never package secrets, credentials, `config/user-config.jsonc`, runtime `cache/`, runtime `diagnostics/`, `.git/`, Python bytecode, historical checkpoint artifacts or generated release debris.
- Do not commit or push automatically unless the user has explicitly authorized Git commit, push, PR or merge through the current task or a development workflow they started; those already-authorized actions need no further confirmation.
- Current `main` is the recommended/latest supported distribution during rapid development. Packaged GitHub Releases are currently paused; changing that policy requires an explicit decision, never a version-number trigger.
- Every PR merged to `main` must increment the product version and update release date, `VERSION_HISTORY.md`, README current version and affected current docs in the same PR, including documentation-only and behavior-neutral changes; verify against the latest base before merge. See [versioning and history](development/MAINTAINER.md#versioning-and-history). Git tags, GitHub Releases and ZIP policy remain independent.

## Verification and packaging by environment

Decide first where you run. If you cannot establish that you run on the user's own workstation, treat the environment as hosted.

**Hosted/web AI** (for example ChatGPT or Claude Code on the web, or any cloud sandbox that only has the GitHub repository): run only the light, fast gate and never build a ZIP, even when the product version changes:

```text
python development/tools/run_tests.py --suite quick
python development/tools/validate_package.py --working-tree
```

Quick runs each test file in an isolated process with a hard timeout and concurrent workers. Do not start Full, Diagnostics or the release builder there, and do not compensate for a constrained harness with an unbounded monolithic suite.

**Local workstation agent or human** (for example OpenCode on the user's computer): always run every test and investigate failures, then run the relevant read-only live checks yourself (Diagnostics or headless report/Watch probes against the real installation); never ask the user to run them and never stop the shared OpenCode service serving the session. Deterministic fixtures alone do not prove a workstation-specific fix. Every completed local feature, fix or version then builds a new ZIP (authorized isolated-clone Git delivery without a packaging request excepted):

```text
python development/tools/run_tests.py --suite full
python development/tools/validate_package.py --working-tree
python development/tools/build_release.py --full-verification
```

Local work also owns the deeper upkeep hosted models cannot do: performance, robustness, Diagnostics relevance, structure ratchets and tidy, AI-maintainable code. Both environments hand off the verified authoritative working tree; brainstorm/FR sessions build nothing.

## Packaging details

The builder gates its own source tests and validation, then repeats them from a clean extraction. The default artifact is `releases/cost-guard-vMAJOR.MINOR.zip`; a rebuild of the same product version replaces it. The `releases/` directory is local/generated, git-ignored and excluded from the archive itself. If the user explicitly asks for a release candidate, use `--output releases/cost-guard-vMAJOR.MINOR-release-candidate-N.zip` without changing the product version merely for the RC number. When local commands are time-limited, run the builder as a background command rather than weakening its tier.

A package handoff reports the artifact path, SHA-256 and verification that actually ran. Release-builder regression tests create disposable archives only in isolated test directories, never a checkout deliverable. Historical/checkpoint ZIPs supplied for context are external reference material only and must never be nested into a new release.

Do not add automatic cleanup machinery for generated ZIPs. Remote GitHub Release deletion/publication is a separate explicitly authorized operation, never local cleanup. Preserve the historical v80.0 tag unless its deletion is explicitly requested.
