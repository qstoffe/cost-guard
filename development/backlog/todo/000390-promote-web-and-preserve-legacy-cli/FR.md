# FR 000390 — Promote Web to standard launchers and retain explicit Legacy CLI

## Blocking owner checkpoint

Depends on completed FR000380 AND a new explicit owner decision that the tested Web Beta is ready to be Cost Guard's default. The instruction to publish this migration chain is NOT that promotion decision. Until approval is recorded, leave this FR pending/blocked and do not move launchers or change the root Python default. Do not infer approval from time elapsed, a version number, completed tests or the existence of this specification.

## Outcome

Make the local Web application the ordinary entry point on Windows and macOS while preserving working CLI fallback under `Legacy/` for a further coexistence period. This is a controlled entry-point migration, not a calculation rewrite or CLI removal. Follow FR000290/PLAN.md.

## Required behavior after approval

1. Place the Web launcher at the ordinary OS-folder entry, provisionally `windows/Cost Guard.cmd`, `macos/Cost Guard.command` and the corresponding terminal-free macOS app wrapper. Move the two old report/Watch launchers to `windows/Legacy/` and `macos/Legacy/`. Update relative-root lookup and helper paths for the extra directory depth; do not merely move files and leave broken references.
2. Make normal `python cost-guard.py` start the shared Web launcher flow at this phase, not during Beta. Retain the existing CLI behavior through an explicit documented entry, provisionally `cost-guard-cli.py`, used by the Legacy launchers. Existing CLI arguments keep their meanings through that entry, including FR000200's static session snapshot and explicit CLI Watch. Do not translate unknown legacy arguments into silent new Web behavior. Help/migration errors clearly explain the supported new and Legacy commands.
3. Reuse the existing verified restart, per-checkout identity, environment, loopback security, default browser, tray/menu Open/Exit and code-change shutdown. Promotion must not create a new service, second icon/instance, reset user settings/history/cache or cause a second dependency installation just because a launcher moved. Treat old Beta entry points as documented delegating aliases for a transition where helpful; they must not become separate product runtimes.
4. Keep CLI genuinely usable when Web packages, GUI, browser or server fail. Do not route Legacy through HTTP or make it launch Web. Shared core fixes continue to serve both. Preserve Diagnostics and human troubleshooting launchers, update their links independently of the CLI UI path, and retain safe crash reporting even when no browser can open.
5. Update README/usage, installation/setup messaging, examples, packaging/source ZIP manifest and actual executable metadata. Clarify that closing a browser does not stop the server and that deliberate launcher invocation restarts it. Document the new Legacy path and an owner-usable fallback without requiring Git-history checkout. Avoid forced global configuration migration, shell aliases or OS preferences changes.
6. Record this promotion checkpoint and remaining Legacy support scope. Keep a reversible entry-point change: reverting promotion must not require restoring deleted analysis, personal config or user data. No Legacy code is removed in this FR except obsolete duplicate launcher wiring that has a proven replacement.

## Acceptance

Test fresh clone/ZIP and an existing Beta checkout on both platforms; launcher moves, spaces/Unicode paths, an already-running instance and the same managed environment remain correct. Default entry opens Web once and detaches correctly. Both Legacy report and Legacy Watch still start the intended CLI process and retain existing stop/console semantics. CLI help/version and Diagnostics work without Web dependencies. Numerical parity remains unchanged and no second instance appears through an old Beta alias.

Use the established targeted migration/launcher checks and native evidence, not a new permanent release gate. Retirement is explicitly not authorized here: FR000400 requires another owner decision after the Legacy coexistence period.
