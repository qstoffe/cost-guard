# Cost Guard development

Everything in this directory exists to design, maintain, test, validate and release Cost Guard. Runtime code under `src/` MUST NOT depend on development-only files. Root `AGENTS.md` is the first-stop router for a fresh AI coding session.

- **Implement/change/release:** read `MAINTAINER.md` first, then the active task/FR and `ARCHITECTURE.md` when boundaries are affected. In constrained AI environments use `python development/tools/run_tests.py --suite quick` plus `python development/tools/validate_package.py --working-tree`; unrestricted/local work uses Full or the Diagnostics launcher. The release builder repeats its selected tier and clean-extract verification.
- **Brainstorm/design/Feature Requests:** read `FR_GUIDE.md`. Discussion does not modify/package Cost Guard until the user explicitly transitions to implementation.
- **Architecture:** `ARCHITECTURE.md` owns runtime layering, dependency direction, source/provider contracts, cache ownership and Watch ownership.
- **HTTP account providers:** `simple-http-accounts.md` owns maintained definition/mapping limits, network/credential safety, provider evidence and extension guidance; complex providers stay first-class adapters.
- **Budgets:** `file-budgets.json` is the machine-readable authority for design warnings and hard file caps.
- **Fixtures:** `fixtures/` contains only deterministic synthetic non-secret test inputs.
- **Tools:** `tools/` contains the stdlib-only test runner, release validator and release builder.

The exact filesystem state at the start of an implementation request is authoritative. Git history is never an automatic restore baseline.

## Bounded test profiles and real-environment diagnostics

`python development/tools/run_tests.py` defaults to the bounded **Quick** suite; focused `--profile`/`--pattern` runs are available and `--suite full` is the unrestricted/local tier. `development/tools/collect_diagnostics.py` is the supported privacy-conscious environment collector for user machines and runs Full + distributable-view validation by default with progress; `--skip-validation` is for recursion/emergency diagnostics only. It must never include prompt text, session titles, auth tokens, raw auth files or raw OpenCode payloads.

Every `tests/test_*.py` module must match exactly one Quick/Full-only pattern in `tools/run_tests.py`, or have an exact relative path and reason in `EXCLUDED_TEST_MODULES`. The runner rejects missing, overlapping or stale assignments before executing any suite/profile/pattern.
