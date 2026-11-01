# Development

`development/` holds portable project context, architecture, backlog, journal, tests and tooling. Changes confined here do not introduce product tests, release gates, version bumps, packaging or file-budget validation. Real Git, security, privacy, scratch isolation and authorization still apply.

## Find your way

- `architecture/`: the overview and project-specific module facts.
- `backlog/suggestions/`: numbered proposals awaiting human decisions, never executable.
- `backlog/on-hold/`: deliberately deferred FRs, never executable until an owner releases them.
- `backlog/ready-to-develop/`: approved, executable FRs, selected by priority.
- `backlog/complete/`: verified deliveries with truthful `COMPLETION.md` reports; `rejected-suggestions/` is a disposition archive, not another executable stage.
- `journal/`: reusable findings and their evidence.
- `tests/`: project development checks and fixtures.
- Optional `tools/` and `user-tools/`: developer and human-facing utilities.

Projects own the nested organization within these areas. Keep product-specific policies, modules and test facts in the other development documents.

## Write a Feature Request

An `FR.md` is standalone, readable Markdown. Explain the problem or observations, the desired outcome, useful constraints or non-goals, and what would make the outcome acceptable. Add dependencies or affected areas if helpful. There are no mandatory headings, minimum length, code/design proposal, product validation plan, release target, preflight or extra approval to draft. A human or external AI can use this guide without access to Toolkit or another repository.

Ready bundles use `ready-to-develop/PPPPPP-IIIIII-slug/FR.md`: P is temporary queue priority (lowest first); I is permanent identity. Suggestions use `suggestions/IIIIII-slug/SUGGESTION.md`; held FRs use `on-hold/IIIIII-slug/FR.md`, without a priority. Complete commonly uses `complete/CCCCCC-IIIIII-slug/`, with C presenting delivery order. Numbering is documentation, not approval or worker admission. Preserve permanent identities and task contents across reprioritization and moves. Existing legacy `todo` and understandable completion formats remain usable without mandatory migration or counter repair.

A finalized, owner-approved Ready FR authorizes its stated implementation. Only explicit human approval/release moves a proposal or held FR to Ready. Dates and dependency prose never promote work automatically. A worker keeps its selected FR-ID despite reprioritization/rename; it abandons feature delivery if removal or hold is incidentally discovered, without a special pre-merge status check. Work published on the task's branch is the recovery point, not session ownership records. New permanent product gates need explicit approved scope. Technical publication and explicit migration mechanics belong to installed Toolkit skills.

An explicit delegated or human pause may move even the selected FR and genuinely blocked dependencies from Ready or legacy `todo` to On Hold, preserving IDs, content, attachments and implementation branches. Record why and the missing prerequisite; publish only the backlog/docs change, not unfinished implementation. No migration, selected-owner consent or product release is required. Published holds continue through a fresh worker; dates never release them. Approved test/requirement exceptions remain explicit in completion and relevant journal notes: actual checks, unperformed scope, decision-maker, reason and uncertainty, never invented PASS.

Toolkit owns this exact mirrored guide; Contract Sync updates it from the installed master. Put consumer-specific facts elsewhere rather than customizing this file.
