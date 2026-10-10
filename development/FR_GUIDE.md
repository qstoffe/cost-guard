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

Brainstorming remains non-implementing: do not modify production code unless the user explicitly transitions to implementation. Brainstorming never builds a ZIP; packaging belongs to the implementing session's environment rule in `MAINTAINER.md`. Present the finished copy-pasteable FR in one code block containing only the FR; explanatory comments belong outside it.
