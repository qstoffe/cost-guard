# FR 000553 — Reduce CostGuard verification overhead while preserving useful safeguards

## Problem and outcome

The owner requested a focused cleanup after reviewing the effort required to deliver ordinary CostGuard features. Keep the useful regression suite and the recently simplified CI. Remove avoidable work caused by ordinary documentation byte limits, tests tied to incidental source spelling, Windows fixture startup assumptions, repeated checks for reporting-only commits, and verification that expands beyond the changed behavior.

The outcome is a simpler path from an implemented feature to trustworthy delivery. This is not a target to delete a particular number of tests or reduce coverage to a prescribed percentage.

Inspected baseline: `d57760e7cd9c9070c3b9ee20f13fd2155f0ba620`. It has 126 registered test files. FR000548 already moved shared Full/validator/browser work to one Linux job, retaining focused Windows and macOS native checks. Preserve that optimization; do not rebuild it.

## Owner constraint: instruction and context limits remain hard

**Hard size limits for skills, commands, and all surrounding agent instructions, references and context must remain hard. The owner explicitly accepts unlimited additional development effort to preserve those limits.** This requirement overrides the general aim of reducing overhead.

Preserve applicable numeric thresholds, individual and aggregate/normal-path accounting, coverage and blocking enforcement, including skill roots/descriptions, references, associated AGENTS/configuration and skill-local helpers/assets. Existing authorized exceptions remain unchanged; this FR grants no worker or Decision Delegate authority to add an exception or waive these limits.

Classify documents by their purpose, not just extension or filename. A README that serves as operational agent instructions is protected. In particular, do not modify the mirrored `development/README.md`, weaken Toolkit-owned rules, split instructions into unbounded side files, introduce an exception that makes a protected hard limit advisory, or move protected content into an ordinary-document category to evade a limit.

The relaxation below concerns ordinary product documentation such as the public product README, release history and Web user guide. Other existing source/configuration/artifact limits are outside this cleanup unless a narrowly necessary classification correction preserves their protection.

## 1. Stop ordinary documentation length from blocking a valid feature

The baseline product `README.md` is 32,343 bytes against a 32,768-byte hard limit; `VERSION_HISTORY.md` is 32,473/32,768; `docs/web-beta.md` is 64,820/65,536. Recent completions record documentation-cap failures, history condensation and shortening new release text just to stay below these limits.

Make these ordinary prose limits advisory, or use an equally simple bounded archival arrangement that does not repeatedly require unrelated prose editing for each feature. Preserve useful navigation, version consistency and the ability to find older release information. Keep size warnings informative without turning an acknowledged warning into a second approval gate.

Apply the change narrowly in the existing budget policy and validator. Do not relax all Markdown, all `otherText`, or all files indiscriminately. Retain secret/runtime-artifact checks, supported-Python validation, dependency boundaries and relevant artifact caps. Note that the validator's `check_history_bounds` function is not currently called by `validate()`; do not activate dormant rules as part of this cleanup.

## 2. Test behavior instead of incidental implementation text

Inspect the concentrated source-shape assertions in `test_foundation_quick.py`, `test_windows_launcher.py`, `test_windows_web.py` and `test_ci_web_beta.py`. Replace or remove assertions whose only effect is to require exact local names, whitespace, expression spelling or equivalent workflow formatting. Retain a narrow static check when it protects a real invariant more clearly than a behavioral test.

Preserve the contracts these tests were intended to protect: correct Python selection, fallback behavior, startup/status lifetime, one initial dashboard, child exit-code propagation, safe launch behavior and the separation of common versus native CI work. Reuse existing fixtures and focused execution; no new general test framework or wholesale migration is required.

An equivalent refactor should not fail merely because its source text differs. An implementation that violates the retained behavior must still be detected. Do not delete substantive accounting, security, source-integrity, lifecycle or native-process coverage to meet an arbitrary reduction target.

## 3. Make the Windows startup fixture robust without weakening the product

Review `test_windows_web.py::test_batch_waits_for_status_process_then_exits_with_its_result` and the adjacent discovery fixtures. The batch fixture currently combines a five-second parent wait for shell startup with an independently expiring ten-second fixture lifetime. Shell startup contention must not be mistaken for a violation of the batch/status ownership contract.

Use explicit bounded readiness/release coordination and cleanup for the fixture's own processes. Distinguish a harness-startup failure from the behavior being asserted, retaining useful sanitized diagnostics. Preserve verification that the batch remains alive while its status child owns the handoff, propagates the actual exit code, and leaves no owned process behind.

Do not resolve fixture failures by increasing product readiness deadlines, hiding failures behind automatic reruns, skipping the Windows behavior, or loosening ownership assertions. Any necessary harness timeout adjustment must be justified by the actual startup stages and remain bounded. Preserve the existing distinction between synthetic shell evidence and native/consumer-desktop evidence.

## 4. Avoid repeating expensive CI just to finish the evidence report

FR000548 records a concrete loop: green implementation checks were followed by a reporting-only commit, duplicate CI, an ARM64 capacity queue, an evidence-equivalence decision and another reporting commit that superseded the previous run.

Simplify the existing workflow/evidence arrangement so a completion report or factual verification-note edit does not unnecessarily repeat expensive phases for unchanged executable content. Prefer a small change using existing mechanisms; do not build a general evidence registry, new receipt protocol or CI cache framework.

Distinguish an entirely documentation-only PR/push from a reporting-only follow-up commit on an already code-changing PR; do not assume path exclusions alone solve the latter. A concise completion record with detailed results retained in the existing CI/PR can remove the reporting loop without adding evidence machinery. If a proposed phase skip cannot be justified simply, retain that check and document the specific remaining limitation while completing the independent cleanup.

Reusing earlier evidence requires identifying what was tested and establishing that relevant implementation, tests, configuration, workflow and effective base have not changed. Changed inputs, an observed failure or an uncertain comparison require fresh applicable verification. Satisfy actual GitHub protection requirements; do not bypass them. A skipped, queued, cancelled or unexecuted check must never be reported as a pass, and a prior result must not be presented as execution on a different revision.

Keep the existing common/native division, useful native architecture coverage and ordinary cancellation behavior. The goal is to remove the reporting loop without weakening meaningful merge evidence.

## 5. Keep additional live verification proportional

For an ordinary UI, preference or documentation change, choose additional browser/live probes from its actual risks and approved acceptance criteria. Existing automated regressions should carry unchanged behavior. Do not repeatedly re-prove broad source acquisition, deep-history cancellation or unrelated provider transitions solely because those probes exist.

Preserve explicitly requested live acceptance, real-platform checks when platform behavior changes, and existing security and authorization boundaries. Record any unavailable evidence honestly. Do not add a repository-specific process manual that competes with Toolkit, a new mandatory checklist, or a blanket exemption from real browser/native verification.

This includes changes to test runners, fixtures or validation tools: their development-folder location does not make executable verification behavior risk-free. Use focused checks appropriate to those changes without reinstating blanket product-release gates for development-only work.

## Acceptance and delivery

- An ordinary product-document edit can cross its former prose threshold without a blocking budget failure. Protected agent instruction/reference/context limits retain their original hard enforcement, and relevant non-prose safeguards still operate.
- The targeted tests accept equivalent implementation structure and still detect violations of their retained behavioral contracts. Windows startup verification has bounded coordination and cleanup instead of an incidental race between independent waits.
- Reporting-only follow-up work avoids unnecessary repeated expensive CI when equivalent evidence is established; changed or uncertain tested inputs receive fresh checks. Required GitHub statuses and final reporting remain truthful.
- FR000548's shared Linux verification and focused native coverage remain intact. No numerical test-deletion target, new broad framework or permanent verification gate is introduced.
- Verify the changed validator/test/workflow behavior with focused evidence and the existing applicable delivery checks. Report what became simpler and any remaining limitation; a new benchmark campaign, exhaustive live matrix or historical-document rewrite is not required.

## Evidence and starting points

- [Budget policy](https://github.com/qstoffe/cost-guard/blob/d57760e7cd9c9070c3b9ee20f13fd2155f0ba620/development/architecture/governance/policies/file-budgets.json) and [package validator](https://github.com/qstoffe/cost-guard/blob/d57760e7cd9c9070c3b9ee20f13fd2155f0ba620/development/tools/validate_package.py).
- [Foundation assertions](https://github.com/qstoffe/cost-guard/blob/d57760e7cd9c9070c3b9ee20f13fd2155f0ba620/development/tests/test_foundation_quick.py), [Windows fixture](https://github.com/qstoffe/cost-guard/blob/d57760e7cd9c9070c3b9ee20f13fd2155f0ba620/development/tests/test_windows_web.py) and [current CI](https://github.com/qstoffe/cost-guard/blob/d57760e7cd9c9070c3b9ee20f13fd2155f0ba620/.github/workflows/web-beta.yml).
- [FR000548 completion and reporting-only CI loop](https://github.com/qstoffe/cost-guard/blob/d57760e7cd9c9070c3b9ee20f13fd2155f0ba620/development/backlog/complete/000057-000548-web-ci-shared-regression-and-native-smoke/COMPLETION.md).
- [FR000539 completion](https://github.com/qstoffe/cost-guard/blob/d57760e7cd9c9070c3b9ee20f13fd2155f0ba620/development/backlog/complete/000051-000539-persist-web-ccost-unit-in-settings/COMPLETION.md) and [FR000545 completion](https://github.com/qstoffe/cost-guard/blob/d57760e7cd9c9070c3b9ee20f13fd2155f0ba620/development/backlog/complete/000058-000545-watch-compact-cards-and-cli-colors/COMPLETION.md).

This FR authorizes the focused cleanup above. Publication of the FR itself changes no product code, version, release or runtime installation.
