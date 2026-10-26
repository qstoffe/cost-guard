> **Unnumbered, non-executable suggestion.** Owner explicitly parked the former FR000400 concept on 2026-10-26 pending later separate approval. The old allocated identity remains reserved and must never be reused; future approval creates a new FR number. No implementation or priority is authorized by this document.

# Suggestion — Retire Legacy CLI after approved Web coexistence

## Future owner decision (not currently approved)

Only consider this suggestion after a **separately approved and implemented** future Web-promotion FR plus a genuine coexistence period. The owner must independently approve Legacy removal. A new numbered FR would then be written from the actual implementation state. Promotion approval, tests, time or this suggestion cannot authorize retirement. Until then, retain the Legacy entry points and implementation.

## Outcome

Remove the temporary terminal-report/Watch user interface once Web is the accepted product, without removing any shared analysis, source, report, account, cache, error or diagnostic functionality that the Web application still uses. Follow the migration plan in FR000290/PLAN.md when this is eventually promoted to a newly numbered FR.

## Candidate requirements for a future FR

- Inventory consumers before removal. Delete `windows/Legacy/`, `macos/Legacy/`, the explicit Legacy CLI entry and only terminal-specific presentation/bootstrap code and obsolete aliases that no longer have supported consumers. Do not equate directory names such as `watch`, `reports` or `presentation` with disposable code: Watch acquisition/tracking and shared formatters may still be essential to Web. Move genuinely shared formatting/definitions to their existing appropriate owner before deleting a wrapper.
- Keep the canonical Python application/report layer, all analysis formulas and accounting evidence, source adapters, provider integrations, cache generations, runtime-error boundary and Diagnostics functional. Remove terminal-specific tests only alongside their retired surface; retain semantic fixtures/parity tests and replace obsolete entry-point coverage with current supported flows. Do not use retirement to bypass failing accounting tests or delete inconvenient historical evidence.
- Preserve a small operational Python entry for Web startup/control, help/version, actionable startup errors and diagnostics. Retiring the CLI report UI does not mean eliminating all terminal error output or headless development/test access to the application services. An old removed report/Watch argument must fail clearly with migration guidance rather than silently starting a different operation.
- Update navigation, docs, package manifests, default launchers, native no-download startup and optional local helper generation and implementation ownership maps. Remove stale Legacy links and misleading claims of fallback availability. Retain historical completed FR bundles/COMPLETION evidence; do not rewrite history to imply Web had always been the default.
- Never delete user configuration, OpenCode data, runtime logs or historical records as a side effect. Any cleanup is restricted to demonstrably owned obsolete code/artifacts, not general application-data directories. Keep process identity/security, simple source-change shutdown, current menu actions and browser launch behavior intact.
- Do not introduce unrelated UI redesign, provider rewrites, pricing migrations, telemetry, OS services or an updater. This is the final removal of a temporary interface, not permission to rework the protected engine.

## Acceptance

Fresh clone/ZIP and an upgraded promoted installation start the same Web application on Windows/macOS, including first-run offline launch with no new packages and any built-in helper regeneration, tray/menu actions, restart and diagnostics failures. All supported report and live views remain available with unchanged numeric/unknown/partial semantics. No runtime import or packaged launcher references deleted terminal-only modules. Existing semantic test coverage remains meaningful and former CLI arguments fail with a useful explanation.

Record the explicit retirement approval and removal inventory in the normal completion evidence. Verify preserved user/runtime data and explain how users start/stop and troubleshoot the Web product after retirement. This unnumbered suggestion authorizes **no implementation or deletion**; any eventual executable FR needs a new owner decision and fresh backlog identity.
