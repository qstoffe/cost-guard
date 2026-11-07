# FR 000625 — Make USD the default Web CCost display unit

**Owner-approved Ready Feature Request, 2026-11-07.** Permanent ID **000625**; Ready priority **000520**, after the already-selected FR000624 (priority 000420). This publication is FR-only documentation. Do not implement or alter any running Cost Guard instance while authoring it.

## Request

In Cost Guard Web **Settings → CCost display**, change the **shipped default** from **Credits / AI Credits** to **USD**. USD amounts are easier for the owner to understand and compare at a glance than larger credit counts. The existing Credits option remains available.

The repository currently has **two independent settings**:
- Web: `config/default-config.jsonc → webSettings.ccostDisplayUnit` currently `"credits"`. Web Settings supports `Default`, explicit `Credits` and explicit `USD`, with saved user choices in `config/user-config.jsonc`.
- CLI/terminal: separate root `ccostDisplayUnit` and `--ccost-unit` option, currently defaulting to Credits.

**Change only the Web shipped default to `"usd"`. Do not change the CLI default, CLI overrides, existing stored user preferences, CCost value semantics, pricing, cost accounting, native quotas, billed amounts or conversion factors.** This is a presentation default change, not a currency conversion feature or migration.

## Required behavior

1. Fresh Web installations / users with no explicit `webSettings.ccostDisplayUnit` override open with **USD** effective display in normal Web and Mini Watch, as well as related Web CCost views.
2. A saved `"default"` choice (or omission of the Web field) **inherits the shipped USD default**. The Settings UI shows `Default (USD)` and correctly describes the inherited selection.
3. A previously saved explicit `"credits"` remains Credits after upgrade. A saved explicit `"usd"` remains USD. Do not rewrite or migrate user JSONC simply to apply the new default.
4. Switching between Credits, USD and Default continues to work and persist through the existing Web Settings API. Preserve independent CLI settings and `--ccost-unit` behavior unchanged, including the CLI's existing Credits default.
5. Existing reference CCost conversion (**100 credits = $1 reference USD**) remains display-only. No new calls, pricing recalculation, history scans, reload, background jobs or changes to data/quotas/billing.
6. Update **current** user-facing/default-description documentation where it now calls Credits the Web default (such as README and Web usage guide), without rewriting historical release records. Keep the change narrowly scoped.

## Proportional verification

Use existing focused config/Web Settings UI/API tests and, if needed, one small browser/settings check to cover default/no override, saved Default, saved Credits, saved USD, and CLI isolation. Verify that no cost numbers or source work change. Run normal applicable final product checks under the existing delivery workflow, but **do not invent a new test harness, universal gate, migration step or extended performance benchmark** for a default-value change.

## Acceptance

- **Default in Web = USD** for new and default-inheriting configurations; Settings labels the default correctly.
- **Explicit saved Credits or USD preferences remain untouched**, and selecting Credits still works.
- **CLI default stays Credits**, and billing/quotas/cost calculations are unchanged.
- The implementation is a small, ordinary Web settings change, delivered **after** the already-running FR000624 instead of modifying its selected branch or task.

**FR-only publication:** Create only this `FR.md` and advance `development/backlog/identity-state.json` highWatermark **624 → 625** atomically on `main`. No executable change, product test, release/version bump, branch or PR for the authoring transaction.
