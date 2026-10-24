# FR 0090 — Adopt Toolkit repository contract synchronization

## Goal
Make Cost Guard adopt compatible updates to OpenCode Toolkit's shared repository-development contracts before ordinary backlog work. Toolkit FR0191 must first be implemented and available in the installed runtime; the manual Toolkit handoff at FR0195 is still required. This FR is planning only and does not install a scheduler.

## Scope
Consolidate existing Cost Guard migration requirements FR0100, FR0105, FR0110 and FR0115: development layout, shared release qualification, folder-based backlog with safe attachments, unique priorities, completed retention, and central FR-only authoring. Preserve all unique requirements and product-specific safeguards from those requests and verify them against their Git history. Do not mark an unimplemented item completed.

Use the Toolkit-owned change-driven sync procedure and its persisted revision receipt. Preserve Cost Guard Python, read-only OpenCode access, privacy protections, functional-only product versioning, existing tests and validators, source distribution, and unrelated backlog FRs. Migrate the older flat backlog safely, without interfering with active work or deleting source evidence. Keep shared process rules centralized in Toolkit, not duplicated in Cost Guard.

## Acceptance
Verified installed Toolkit capability, safe and complete migration, authoritative merged-commit and state read-back, no repeated migration after checkpoint/resume, and unchanged product version for development-only changes. Test actual priority/attachment migration and local test inventory without weakening checks.