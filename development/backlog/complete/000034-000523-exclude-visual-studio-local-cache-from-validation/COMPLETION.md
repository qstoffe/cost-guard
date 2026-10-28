# FR 000523 — Completed

## Outcome

Root Visual Studio `.vs/` state is ignored by Git and omitted from both the validator's working-tree view and the package-copy fixture. Explicit packages reject root `.vs/` even when empty. Nested IDE directories and arbitrary project files retain ordinary path/size validation. No local IDE state is deleted or processes stopped. Delivered as v80.103 (2026-10-28).

## Changes and decisions

- Add only the root `/.vs/` Git exclusion and corresponding root copy exclusions; no automatic Git-ignore parser or blanket unknown-directory suppression.
- Preserve explicit-package checks; extend forbidden packaged top-level artifacts with `.vs`.
- Exercise large binary SQLite/index files, mixed-case IDE paths, view omission, original-file preservation, explicit-package rejection, nested-path rejection and unrelated malformed-file failures.
- Repair the legacy public-layout test to inspect the distributable fixture, not the raw checkout. The first real Diagnostics run exposed that separate raw-checkout assumption after the foundation cases and validator already passed.
- Preserve the selected FR bytes. Its publication-only wording described initial FR authoring; this authorized Backlog delivery implements the approved behavior.

## Verification

Windows 11, Python 3.14.7; base `ba1eeae6e68e215bb64fac867624b51b3effcb0a`.

- Focused foundation: nine tests passed.
- Full deterministic suite before the IDE-cache probe: 113 files, zero failures (50.9 s).
- Working-tree validator: 11 passes, zero failures, four existing design-budget warnings; hard caps unchanged.
- Real `collect_diagnostics.py --no-network --snapshots 1` with synthetic root `.vs/CostGuard/FileContentIndex/cache.vsidx` and `.vs/slnx.sqlite` (65,537 bytes each) initially exposed one raw-layout test failure. After its fixture correction, rerun: Full 113 files, zero failures (51.9 s), package validator exit 0, both recorded `ok: true` in the actual generated ZIP.
- `git check-ignore .vs/slnx.sqlite` confirms exclusion; `git ls-files .vs` is empty.
- Diagnostics reached the installed V2 service without stopping it. Legacy V1 schema incompatibility is independent of this repair. `--no-network` deliberately omits quota/pricing requests; report/Watch acquisition success is not claimed. The colleague's other source/quotas diagnostics remain independent.

Generated diagnostic ZIPs and synthetic IDE files are disposable, ignored local probe artifacts, not release/source content or selected attachments. No product ZIP, browser/native UI automation, model calls or self-review was performed. The colleague's original workstation is not re-tested here.

## Knowledge assessment

Journal: no-update; existing test-health knowledge already distinguishes package negatives, responsibility-owned fixtures and consumer-local proof. The specific raw-checkout fixture correction is retained here. Architecture: no-update; no runtime boundaries, dependencies or permanent gates changed. No Toolkit defect proposal: the observed failure was a repository test assumption repaired in scope.

## Delivery

PR: pending creation; the verified PR link will replace this line before merge.
