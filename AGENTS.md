# Cost Guard — product-specific context

The **installed and actively loaded OpenCode Toolkit skills** own generic development, Feature Request authoring, development layout, backlog implementation, version-qualification workflow and Git delivery. This repository does not define a second development process. Do not infer that an installed runtime exists merely from GitHub source.

- Keep OpenCode source data, persistence, database migrations and credentials read-only. Never publish secrets, user config, raw diagnostics or runtime cache.
- Preserve Python 3.11+ standard-library-first, the thin `cost-guard.py` entry, disposable cache, provider-neutral analysis, bounded source/account/pricing responsibilities and Watch/report shared semantics.
- Runtime code changes require appropriate product regression testing and relevant release metadata. Do not fabricate test results, remote writes or implementation results.
- Respect permissions, branch protection, ownership of active work, explicit Stop and destructive-operation boundaries.

**Development-only changes:** A change strictly within `development/` requires no Cost Guard-local validator, product tests, development structure checks, file budget, packaging or product version/release update. The actively loaded Toolkit skills are the sole development-procedure authority. Product tests stored under `development/tests/` remain available when actual product source changes.

**Explicit approved work:** An approved FR, hotfix or current user instruction takes precedence over older conflicting *default* development rules, tests and validators in its explicit scope. Update the applicable rules and assertions during implementation instead of treating those defaults as a veto. Unrelated authorization, safety, privacy and data-integrity protections remain.

`development/ARCHITECTURE.md` and `development/CODE_MAP.md` provide product-specific technical facts and navigation, not independent development-process policy.
