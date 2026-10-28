# FR 000522 — Windows CLI console ownership

## Outcome

Implemented v80.102. Report, Watch and Diagnostics now open their own persistent
PowerShell console rather than sharing the caller's console asynchronously.
The caller can return immediately without competing for Cost Guard input/output.
Child completion/errors/Ctrl+C retain a usable prompt and meaningful native result.
The batch reports launch status, not the later Python result; direct Python remains
the synchronous exit-code route.

Implementation candidate: [11fa96c](https://github.com/qstoffe/cost-guard/commit/11fa96c2bea806c7a66341e407bc04eb1611d079).
The native delivery receipt records the confirmed PR/merge after publication.

## Changes and alternatives

- Removed START /B consistently from all three batch entrypoints; kept -NoExit,
  shell fallback, relative paths, Python discovery and explicit Ctrl+C reset.
- Requirement feedback belongs to the child, never to the caller's decorated prompt.
- Updated focused launcher contracts, version/history/README, the architecture route
  and Windows-startup knowledge. Added manual, explicitly approval-gated native
  reproduction harnesses under development/tests/evidence/windows-console/.
- A waiting shared batch risks the termination question; hiding output does not
  repair competing readers. A separate terminal is the FR-permitted safe alternative.
- No launcher rename (separate pending FR), numerical/analysis changes, new installed
  dependencies, global policy/profile changes, Web Beta changes or service interruption.

## Evidence and verification

[Native evidence, exact comparator/candidate and manual re-run commands](../../../architecture/governance/verification/windows-console-ownership.md).
The original bounded decorated-prompt reproduction confirmed parent prompt return
while Python and the caller shared a console. The fixed path confirmed distinct
console membership and input queues, advancing progress, usable child prompts,
Ctrl+C without a batch question, and native results 0/1/9009.

Native coverage includes vanilla/synthetic Git prompt plus PSReadLine, PowerShell
7/5.1 fallback, explicit Windows Terminal/Console Host callers, cmd, Explorer-style
open, measured 80/120/160-column buffers, missing Python and crash guidance. Actual
read-only report/Watch/Diagnostics smoke passed; real Watch displayed its stopped
message and released Python before the subsequent command. Diagnostics' private
bundle explicitly reports full-local validation ok, not merely ZIP collection.

Final verification after implementation/version/docs/accounting:

- `py -3 development/tools/run_tests.py --suite full`: PASS, 113 files, 46.9 seconds.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, zero failures,
  four existing design warnings (README and three unrelated runtime modules).
- First-run stale /B assertions and a later README hard-cap overflow were repaired;
  no cap/assertion weakening or failed run was counted as PASS.
- Journal and architecture contract/routes updated with guarded source/hash checks;
  core architecture and validation-flow gates are unchanged.

## Limits and follow-up

The colleague's exact PowerShell 7.6.9/prompt plugin, physical keyboard/focus and
pixel/cursor appearance remain unverified. Used the FR's explicitly permitted
bounded instrumented competing-prompt reproduction, not a plugin installation or
claim of colleague-machine acceptance. Buffer-width and console-input observations
are not physical screenshot/resize-appearance evidence. Existing deterministic
progress/Watch-rendering regressions passed without semantic changes.

No screenshots/raw buffers/private Diagnostics bundle are published. Private
scratch observations are summarized in the durable evidence above. No cross-FR
dependency was introduced; pending launcher renaming remains independent. No
Toolkit defect proposal was needed; probe/input failures were repaired locally.
