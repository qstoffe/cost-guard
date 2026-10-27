# Development

`development/` holds portable project context, architecture, backlog, journal, tests and tooling. Changes confined here do not introduce product tests, release gates, version bumps, packaging or file-budget validation. Real Git, security, privacy, session ownership and authorization still apply.

## Find your way

- `architecture/`: the overview and project-specific module facts.
- `backlog/todo/` and `backlog/complete/`: pending and completed Feature Requests; completed bundles include a truthful `COMPLETION.md` report.
- `journal/`: reusable findings and their evidence.
- `tests/`: project development checks and fixtures.
- Optional `tools/` and `user-tools/`: developer and human-facing utilities.

Projects own the nested organization within these areas. Keep product-specific policies, modules and test facts in the other development documents.

## Write a Feature Request

An `FR.md` is standalone, readable Markdown. Explain the problem or observations, the desired outcome, useful constraints or non-goals, and what would make the outcome acceptable. Add dependencies or affected areas if helpful. There are no mandatory headings, minimum length, code/design proposal, product validation plan, release target, preflight or extra approval to draft. A human or external AI can use this guide without access to Toolkit or another repository.

Pending bundles use `todo/PPPPPP-IIIIII-slug/FR.md`: P is temporary queue priority (lowest first); I is the permanent FR identity. Completed bundles use `complete/CCCCCC-IIIIII-slug/`: C is chronological completion order, while I and the slug stay unchanged. All numbers have six digits. Priority is reusable after leaving todo; identity and completion order never are, even after pruning. Reprioritize only unselected work by moving its bundle without changing its specification or identity. A descriptive Markdown heading need not repeat either number; preserve historical headings and first-line directives.

A finalized, owner-approved FR authorizes its stated implementation. New permanent required product validation or release gates need explicit scope in an approved FR, not broad inference. Technical publication and implementation mechanics belong to installed Toolkit skills, not this guide.

Toolkit owns this exact mirrored guide; Contract Sync updates it from the installed master. Put consumer-specific facts elsewhere rather than customizing this file.
