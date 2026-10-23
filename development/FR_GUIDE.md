# Feature Request / brainstorming guide

Use this route when designing Cost Guard changes. The goal is an implementation-ready FR that preserves behavioral contracts without recreating a monolith.

## Start with behavior and ownership

Describe the observed problem, desired behavior, affected mode(s), evidence and protected neighboring behavior. Separate must-haves from optional ideas. Before proposing code, classify where the responsibility belongs:

- OpenCode/session acquisition or normalization → Session Source;
- account/subscription usage or quota → Account Provider;
- model price metadata/repricing → Pricing Provider;
- source-independent causal/billing/context logic → analysis;
- disposable persistence/coordination → cache;
- observation scheduling/lifecycle → Watch coordinator;
- CLI/output/color/table behavior → presentation/bootstrap as appropriate;
- deterministic development/release mechanics → `development/tools/`.

Do not fix a provider-specific problem by teaching core analysis raw provider fields. Normalize at the boundary or add a capability/domain concept whose semantics are genuinely shared.

## FR shape

A non-trivial implementation-ready FR should state:

1. problem/context and concrete evidence;
2. desired behavior/invariants;
3. protected behavior/non-goals;
4. baseline/safety assumptions;
5. ownership/layer boundaries;
6. bounded implementation guidance by responsibility (ordering only when essential to correctness);
7. focused verification expectations;
8. final acceptance criteria;
9. documentation/product-version impact, without assigning an upcoming product version (packaging follows the implementing environment's rule).

Prefer deletion/generalization and ownership correction over another special case. File-budget increases are architectural decisions, not ordinary feature work.

## AI-to-AI handoff

FRs belong to a backlog: never assume one will be implemented next, assign it an upcoming version, or make it depend on the version present when authored. Several unrelated FRs may be implemented first, in any order. Historical evidence may name its observed version, but acceptance criteria must describe behavior rather than demand that historical implementation.

Make each FR self-contained enough that a fresh implementation session needs no brainstorming conversation. State behavior, invariants, ownership, evidence, protected behavior and acceptance criteria. Point to existing authorities instead of duplicating them. Concrete modules may clarify ownership, but the implementation session must inspect the then-current package and decide exact edits. Avoid exact line numbers, brittle file-by-file rewrites and detailed step-by-step plans unless ordering is essential to correctness.

Brainstorming remains non-implementing: do not modify production code unless the user explicitly transitions to implementation. Brainstorming does not generate product archives; current `main` remains the supported source distribution. When presenting a draft in chat, use one code block containing only the FR; explanatory comments belong outside it. Authorized repository finalization follows the contract below instead of requiring manual copy/paste.

## Repository backlog authoring

This contract is shared with OpenCode Toolkit's FR workflow. It covers every backlog item (features, bug fixes, refactoring, performance, documentation and debt) under the common designation **FR**, not separate queues. It authors requests; it does not implement them.

### Brainstorm → draft → explicit finalization

1. In a fresh conversation, identify the explicitly requested repository, read its current `development/FR_GUIDE.md`, applicable development docs and relevant implementation context. Do not substitute another repository's guidance or remembered state. If access is unavailable or the target ambiguous, explain the limitation before proceeding.
2. Discuss the problem, desired behavior, architecture/ownership, protected behavior, edge cases, evidence, test strategy and acceptance criteria using the quality standards above. Prepare a complete self-contained Markdown FR; a future session must not need this chat. Do not assign an upcoming implementation version.
3. Wait for explicit finalization, e.g. “Now create the FR”, “Save this as a new feature request” or “Add this to the backlog”. Brainstorming alone creates no FR file, branch, commit or PR. Finalization authorizes saving and publishing the approved FR **through merge to `main` by default**, but not production implementation. A direct instruction to create, add, save, finalize or update an FR in this repository is the user's explicit authorization for branch, commit, push, PR **and merge**. Do not ask again or stop after opening a PR. Explicit draft-only/local-only or unmerged-PR instructions override that default.
4. Resolve the priority from freshly inspected backlog contents as below. Without a priority request, append automatically: do not ask whether last is acceptable. Ask only about a real conflict, ambiguous target/placement or missing authorization.
5. Check/create the standard directories and save the complete approved FR in `todo`, verify it, then **finish authorized Git delivery by merging to `main`** unless explicitly told otherwise or genuinely blocked by checks/protection/conflicts. Report the exact selected priority, filename/path and actual delivery status; never require the user to calculate routine priorities or place files manually.

### Layout and filenames

The only backlog root is `development/backlog`, with pending FRs in `development/backlog/todo` and implemented FRs in `development/backlog/complete`. All directory names are lowercase. Check they exist on every finalization; create missing directories without replacing existing contents. Use minimal `.gitkeep` placeholders where Git would otherwise lose empty directories, never example FRs.

New pending filenames follow `NNNN-description.md`, matching `^[0-9]{4}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$`: exactly four decimal digits, a meaningful lowercase kebab-case slug and `.md`. Lower numbers execute first. Example: `0100-improve-session-recovery.md`. Numeric identifiers must be unique across **both** directories, even when slugs differ. Ignore non-FR support files such as `.gitkeep`; no database, priority index or manifest is needed.

Inspect existing FR filenames in both directories before assigning a number. Preserve existing documents and historical names. Classify malformed names, duplicate numeric identifiers or other ambiguous numbering; stop for a user decision when they prevent safe allocation. Do not silently ignore an apparent malformed FR as a support file, discard requirements, rename historical entries, mark pending items complete or generate speculative FRs from TODO comments.

### Priority allocation

- **Default / last:** if neither directory contains numbered FRs, use `0100`. Otherwise take the highest valid priority in `todo` **and** `complete`, then choose the next multiple of 10 strictly above it: `10 * (maximum // 10 + 1)`, formatted with four digits. Thus a maximum of `0115` yields `0120`, not `0125`. Preferred increment is 10. Completed identifiers remain reserved. If the result exceeds `9999`, stop and explain that explicit renumbering is required; never wrap, reuse an identifier or rewrite historical backlog automatically.
- **Explicit number:** accept only an unused four-digit identifier; reject a collision in either directory. Never overwrite an FR or silently substitute a different priority.
- **Between / before:** use the current pending order to resolve the requested neighbors and prefer an unused numeric gap preserving that order. For “before X”, insert between X and its preceding pending item (or before the first). For `0100` and `0110`, prefer `0105`; if the midpoint is reserved in either directory, choose another unused number inside that same interval. References must resolve unambiguously; a completed entry is reserved history, not a pending execution neighbor.
- **First / next FR:** choose an unused number below the first pending priority, preferably leaving gaps. With no pending items, use default append after historical reservations. Explicit “last” also uses default append.
- **No gap / no number before first:** explain the conflict and ask permission to renumber the relevant pending items or ask for another explicit placement. Do not silently alter the requested order, rename every FR or renumber completed history. Four-digit priorities range from `0000` through `9999`; there is no valid position before `0000`.

Immediately before writing, recheck the current repository state, filename format and numeric uniqueness across both directories, correct repository/directory, approved Markdown completeness and unrelated-file diff. Never overwrite an existing file. If concurrent delivery changes the backlog, recalculate/revalidate before publishing instead of relying on the brainstorming snapshot.

### Git delivery and boundaries

Follow [authorized Git delivery](MAINTAINER.md#authorized-git-delivery), [versioning and history](MAINTAINER.md#versioning-and-history) and the environment's [testing policy](MAINTAINER.md#testing-policy), not a new FR-specific Git mechanism. A user instruction to **create/add/save/update/finalize** a repository FR authorizes the full Git publication workflow, including PR merge to `main` by default. Brainstorming or an expressly local/draft-only request does not. An open-but-unmerged PR is not a completed FR publication. Preserve unrelated work; verify the canonical remote, actual default branch and latest authoritative HEAD, using an isolated branch/clone where required. Include missing backlog-directory initialization, verify the FR/diff, commit, push and open a PR where required. Merge only when authorized, safe and required checks pass; never bypass protection or push directly to a protected default branch.

**FR-only and other documentation-only changes do not change Cost Guard's product version.** Do not edit `src/version.py`, the release date, the README current product version or `VERSION_HISTORY.md` when adding/amending FRs or other non-product documents, tests and tooling. A later implementation that changes shipped product code/functionality follows release/version requirements. Recheck latest base and backlog before merge, reconcile concurrent changes and run available verification. From GitHub-only access with no executable checkout, verify FR content, unique numbering, unchanged product version and precise diff; disclose unavailable local tests but **do not leave a safe FR-only PR unmerged solely for that reason** when required GitHub checks permit merging. Never bypass branch protection, required checks or genuine conflicts.

Verify the actual committed/pushed/merged state and approved FR content, not just a successful command invocation. Report the final FR path, priority, commit/PR/merge result and any limitations. In read-only environments provide the complete FR and intended filename/path, explicitly stating it remains uncommitted. If writes, tools, permissions, protection or conflicts block delivery, preserve the prepared FR and explain the actual blocker without claiming success.

Authoring ends at **Brainstorm → Draft → Prioritize → Save to todo → Git delivery**. Only successfully published repository state is available to future shared `/repo-backlog` processing. That separate workflow selects pending FRs, implements/tests/delivers them, then moves them to `complete`. Never start it automatically, move an authored FR to `complete` or implement production behavior while publishing its specification. Cost Guard needs no separate backlog command; `/repo-feature`, `/repo-cleanup` and Checkpoint/Resume are unchanged.

### Verification examples

Review these deterministic cases when changing the contract; no model evaluation or runtime numbering framework is required. Static documentation/layout regressions live in `development/tests/test_fr_backlog_contract.py`; examples describe model-guided decisions, not an automated allocator.

| Case | Current state / request | Required result |
| --- | --- | --- |
| FR-01 | Both directories empty (support files only) | `0100` |
| FR-02 | `0100`, `0110`, `0120`; no priority | `0130`, no question |
| FR-03 | Only completed entries, through `0170` | `0180` |
| FR-04 | Pending `0100`, `0110`; between | `0105`, existing names unchanged |
| FR-05 | Pending starts at `0100`; first | Unused lower number, e.g. `0090` |
| FR-06 | Explicit `0110` already in either directory | Refuse collision; preserve existing FR |
| FR-07 | Between `0100` and `0101` | Explain no gap; explicit renumbering/placement decision |
| FR-08 | Still brainstorming | No file, branch, commit or PR |
| FR-09 | User asks to add/update a repository FR | Approved FR in `todo`, published and merged into `main` by default |
| FR-10 | Same request in Cost Guard or Toolkit | Same lowercase layout, names and priority rules; retain each guide's quality standards |
| FR-11 | Publishing a specification | No production implementation or automatic backlog execution |
| FR-12 | Git delivery succeeds or is blocked | Verify actual published state or report blocker and preserve draft |
| FR-13 | FR-only/documentation-only delivery | No product version, release-date, README current-version or `VERSION_HISTORY.md` updates |
| FR-14 | Authorized FR PR opened successfully | Continue through merge to `main` and verify publication; never stop merely at PR creation |
| FR-15 | Conflict or required check/protection truly blocks merge | Reconcile safely or report actual blocker; never claim publication succeeded |

Also check exhaustion (`9990` cannot default-append), non-multiple maxima (`0115` → `0120`), historical midpoint reservations, duplicate identifiers with different slugs, and first before `0000`. These must never trigger silent overwrite or automatic historical renumbering.
