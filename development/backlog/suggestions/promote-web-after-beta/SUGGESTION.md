> **Unnumbered, non-executable suggestion.** Owner explicitly parked the former FR000390 concept on 2026-10-26 pending later separate approval. The old allocated identity remains reserved and must never be reused; future approval creates a new FR number. No implementation or priority is authorized by this document.

# Suggestion — Promote Web to standard launchers while preserving Legacy CLI

## Future owner decision (not currently approved)

Keep this suggestion unnumbered and outside the executable queue. Consider it only after FR000380 and an explicit fresh owner decision that Web Beta should become Cost Guard's default. A **newly allocated** FR, created only after that decision, would then authorize actual implementation. Neither Beta completion, elapsed time, product version nor this suggestion authorizes moving launchers.

## Outcome

Make the local Web application the ordinary entry point on Windows and macOS while preserving working CLI fallback under `Legacy/` for a further coexistence period. This is a controlled entry-point migration, not a calculation rewrite or CLI removal. Follow FR000290/PLAN.md.

## Candidate requirements for a future FR

1. Place the Web launcher at the ordinary OS-folder entry, provisionally `windows/Cost Guard.cmd`, `macos/Cost Guard.command` and the corresponding terminal-free macOS app wrapper. Move the two old report/Watch launchers to `windows/Legacy/` and `macos/Legacy/`. Update relative-root lookup and helper paths for the extra directory depth; do not merely move files and leave broken references.
2. Make normal `python cost-guard.py` start the shared Web launcher flow at this phase, not during Beta. Retain the existing CLI behavior through an explicit documented entry, provisionally `cost-guard-cli.py`, used by the Legacy launchers. Existing CLI arguments keep their meanings through that entry, including FR000200's static session snapshot and explicit CLI Watch. Do not translate unknown legacy arguments into silent new Web behavior. Help/migration errors clearly explain the supported new and Legacy commands.
3. Reuse the existing verified restart, per-checkout identity, zero-install native helper setup, loopback security, default browser, tray/menu Open/Exit and code-change shutdown. Promotion must not create a new service, second icon/instance, reset user settings/history/cache or trigger any new package installation just because a launcher moved. Treat old Beta entry points as documented delegating aliases for a transition where helpful; they must not become separate product runtimes.
4. Keep CLI genuinely usable when Web packages, GUI, browser or server fail. Do not route Legacy through HTTP or make it launch Web. Shared core fixes continue to serve both. Preserve Diagnostics and human troubleshooting launchers, update their links independently of the CLI UI path, and retain safe crash reporting even when no browser can open.
5. Update README/usage, no-install/optional first-launch compilation messaging, examples, packaging/source ZIP manifest and actual executable metadata. Clarify that closing a browser does not stop the server and that deliberate launcher invocation restarts it. Document the new Legacy path and an owner-usable fallback without requiring Git-history checkout. Avoid forced global configuration migration, shell aliases or OS preferences changes.
6. Record this promotion checkpoint and remaining Legacy support scope. Keep a reversible entry-point change: reverting promotion must not require restoring deleted analysis, personal config or user data. The future promotion FR must not remove Legacy implementation other than demonstrably obsolete duplicate wiring.

## Acceptance

Test fresh clone/ZIP and an existing Beta checkout on both platforms; launcher moves, spaces/Unicode paths, an already-running instance and locally generated/reused native helper artifacts remain correct. Default entry opens Web once and detaches correctly. Both Legacy report and Legacy Watch still start the intended CLI process and retain existing stop/console semantics. CLI help/version and Diagnostics work without Web dependencies. Numerical parity remains unchanged and no second instance appears through an old Beta alias.

Use the established targeted migration/launcher checks and native evidence, not a new permanent release gate. Retirement remains separate: see the unnumbered `retire-legacy-after-coexistence` suggestion, which requires another owner decision after real Legacy coexistence.
