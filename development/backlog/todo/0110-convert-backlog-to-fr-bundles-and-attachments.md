# FR 0110 — Migrate Cost Guard backlog to Toolkit's folder-per-FR contract

## Problem / dependency
Cost Guard currently stores a pending or completed request as one `development/backlog/todo|complete/NNNN-slug.md`. That cannot durably co-locate screenshots, sanitized diagnostics, benchmark inputs or other per-request evidence. The user wants one portable format owned centrally by OpenCode Toolkit, retroactively applied to both repositories.

**Required prerequisite:** Toolkit FR 0180 folder-based backlog requests, FR 0185 shared FR authoring and FR 0190 bounded completed retention must have been delivered and the corresponding Toolkit installed/available. Existing Cost Guard FR 0100 must have completed its development/ migration. If those central features are missing, leave this request pending and explain the dependency; do not fork their implementation into Cost Guard.

## Required behavior
- Convert **every existing Cost Guard pending and completed FR** from a flat numbered Markdown file to one numbered directory containing canonical `FR.md`, e.g. `development/backlog/todo/0110-convert-backlog-to-fr-bundles-and-attachments/FR.md`. Place optional relevant artifacts in its local `attachments/` subdirectory, linked relatively. Migrate this very FR as part of final delivery when appropriate.
- Preserve exact FR text, priorities, relative order and contents, plus any existing attachments and references. Future /repo-backlog moves the **whole directory** to `complete/` in its verified implementation PR. Avoid breaking an active or resumed session that captured the former path.
- Update Cost Guard's short `development/README.md`, remaining FR authoring instructions and internal test/validation references so ChatGPT/GitHub authoring and OpenCode /repo-backlog both find the canonical directory FR and safe attachments. **Do not copy** Toolkit's maintenance, scheduler or journal skills into Cost Guard.
- Adopt central 100-latest-completed-directory retention, authoritative completion order and historical priority high-watermark/scalable numbering as specified by Toolkit FR 0190. Repo-local state may track only what the central contract requires. Do not automatically delete existing completed evidence prematurely or prune beyond the global rule.
- Public-source hygiene: the Cost Guard repository is public. Never commit raw user Diagnostics ZIP, sensitive login/auth data, prompt content, session titles, tokens or OS user paths. Preserve only minimal sanitized evidence, with bounded attachment sizes. Regular Git deletion does not erase a previously committed binary from history.
- Preserve Cost Guard's vMAJOR.MINOR, `src/version.py` / root README / root VERSION_HISTORY consistency, protected product behavior, Quick/Full test membership, source-distribution privacy and existing AGENTS/FR routing. Migration is repository infrastructure, not an opportunity to relax release/test guards.

## Acceptance and verification
- Existing FR 0100 and any additional todo/complete records safely convert to bundles and are read once, in exact numeric order; no missing or duplicate work items.
- Synthetic FR with image, UTF-8 diagnostic text and binary fixture survives authorized repository publication and todo→complete relocation with relative link integrity.
- Malicious attachment path, oversized binary, stale Git base, unexpected folder and mixed-format migration errors fail safely.
- Current package tests, FR backlog-contract tests and product release checks remain valid; no runtime billing/watch changes.
- Repository is ready to author future bug FRs with safely sanitized attached evidence without additional project-specific template logic.
